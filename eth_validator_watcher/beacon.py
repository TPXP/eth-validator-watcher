from collections import defaultdict
from functools import lru_cache

from requests import Session, codes
from requests.adapters import HTTPAdapter, Retry

from .models import Block, Committees, ProposerDuties, Validators
from .utils import (
    aggregate_bools,
    convert_hex_to_bools,
    remove_all_items_from_last_true,
    switch_endianness,
)


class Beacon:
    def __init__(self, url: str) -> None:
        """Beacon

        url: URL where the beacon can be reached
        """
        self.__url = url
        self.__http = Session()

        self.__http.mount(
            "http://",
            HTTPAdapter(
                max_retries=Retry(
                    backoff_factor=0.5,
                    total=3,
                    status_forcelist=[codes.not_found],
                )
            ),
        )

    @lru_cache(maxsize=2)
    def get_proposer_duties(self, epoch: int) -> ProposerDuties:
        """Get proposer duties

        epoch: Epoch
        """
        response = self.__http.get(
            f"{self.__url}/eth/v1/validator/duties/proposer/{epoch}"
        )

        response.raise_for_status()

        proposer_duties_dict = response.json()
        return ProposerDuties(**proposer_duties_dict)

    def get_active_validator_index_to_pubkey(self, pubkeys: set[str]) -> dict[int, str]:
        """Return a dictionnary with:
        key  : Index of validator
        value: Public key for validator

        pubkeys: The list of validators pubkey to use.
        """
        response = self.__http.get(
            f"{self.__url}/eth/v1/beacon/states/head/validators",
        )

        response.raise_for_status()
        validators_dict = response.json()
        validators = Validators(**validators_dict)

        active_statuses = {
            Validators.DataItem.StatusEnum.activeOngoing,
            Validators.DataItem.StatusEnum.activeExiting,
        }

        return {
            item.index: item.validator.pubkey
            for item in validators.data
            if item.validator.pubkey in pubkeys and item.status in active_statuses
        }

    @lru_cache(maxsize=1)
    def get_duty_slot_to_committee_index_to_validators_index(
        self, epoch: int
    ) -> dict[int, dict[int, list[int]]]:
        """Return a nested dictionnary.
        outer key               : Slot number
        outer value (=inner key): Committee index
        inner value             : Index of validators which have to attest in the
                                  given committee index at the given slot

        epoch: Epoch
        """
        response = self.__http.get(
            f"{self.__url}/eth/v1/beacon/states/head/committees",
            params=dict(epoch=epoch),
        )

        response.raise_for_status()
        committees_dict = response.json()

        committees = Committees(**committees_dict)
        data = committees.data

        # TODO: Do it with dict comprehension
        result: dict[int, dict[int, list[int]]] = defaultdict(dict)

        for item in data:
            result[item.slot][item.index] = item.validators

        return result

    def aggregate_attestations_from_previous_slot(
        self, slot: int
    ) -> dict[int, list[bool]]:
        """Return a nested dictionnary.
        key  : Committee index
        value: A list of boolean

        Each boolean of the list corresponds to a validator in the given committee.
        If the validator attestation from the previous slot is included in the current
        slot, the boolean is True. Else, it is False.

        slot: Slot
        """
        response = self.__http.get(f"{self.__url}/eth/v2/beacon/blocks/{slot}")
        response.raise_for_status()
        block_dict = response.json()
        block = Block(**block_dict)
        attestations = block.data.message.body.attestations

        attestations_from_previous_block = (
            attestation
            for attestation in attestations
            if attestation.data.slot == slot - 1
        )

        # TODO: Write this code with dict comprehension
        committee_index_to_list_of_aggregation_bools: dict[
            int, list[list[bool]]
        ] = defaultdict(list)

        for attestation in attestations_from_previous_block:
            aggregated_bits_little_endian_with_last_bit = attestation.aggregation_bits

            # Aggregations bits are given under binary (hexadecimal) shape.
            # We convert bytes to booleans.
            aggregated_bools_little_endian_with_last_bit = convert_hex_to_bools(
                aggregated_bits_little_endian_with_last_bit
            )

            # Aggregations bits are represented in little endian shape.
            # However, validators in committees are listed in big endian shape.
            # We switch endianness
            aggregated_bools_with_last_bit = switch_endianness(
                aggregated_bools_little_endian_with_last_bit
            )

            # Aggregations bits in a given committee are represented with one bit for
            # one validator. The number of validators bit is always a multiple of 8,
            # even if the number of validators is not a multiple of 8.
            # The last `1` (or last `True` in our boolean list) represents the boundary.
            # All following `0`s can be ignored, as they do not represent validators
            # As a consequence, we remove the last `1` and all following `0`s
            aggregated_bools = remove_all_items_from_last_true(
                aggregated_bools_with_last_bit
            )

            committee_index_to_list_of_aggregation_bools[attestation.data.index].append(
                aggregated_bools
            )

        # Finally, we aggregate all attestations
        return {
            committee_index: aggregate_bools(list_of_aggregation_bools)
            for committee_index, list_of_aggregation_bools in committee_index_to_list_of_aggregation_bools.items()
        }
