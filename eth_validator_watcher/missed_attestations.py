import functools
from typing import Optional, Tuple

from prometheus_client import Gauge

from .models import Block

from .beacon import Beacon
from .utils import NB_SLOT_PER_EPOCH, apply_mask

print = functools.partial(print, flush=True)


def handle_suboptimal_attestation_detection(
    beacon: Beacon,
    potential_block: Optional[Block],
    slot: int,
    our_pubkeys: set[str],
    our_active_val_index_to_pubkey: Optional[dict[int, str]],
    cumulated_our_ko_vals_index: set[int],
    rate_of_not_optimal_attestation_inclusion_gauge: Gauge,
) -> Tuple[dict[int, str], set[int]]:
    """Handle missed attestaion detection

    Print log for our public keys which:
    - Did not attested correctly during the last epoch
    - Did not attested correctly during the last two epochs

    Update prometheus probes for our public keys which:
    - Did not attested correctly during the last epoch
    - Did not attested correctly during the last two epochs

    Returns:
    - A dictionnary with:
      - key  : our active validator index
      - value: our active validator public key
    - A set containing our validator pubkeys with suboptimal attestation inclusion
      during the last epoch
    - A set containing our validator pubkeys with suboptimal attestation inclusion
      for at least two epochs in a raw

    beacon     : Beacon
    slot       : Slot
    our_pubkeys: Set of our validators public keys

    our_active_val_index_to_pubkey (Optional): dictionnary with:
      - key  : index of our active validator
      - value: public key of our active validator

    cumulated_our_ko_vals_index: A set containing our validator pubkeys with suboptimal
                                 attestation inclusion during the last epoch

    rate_of_not_optimal_attestation_inclusion_gauge: Prometheus gauge
    """
    if our_pubkeys == set():
        return {}, set()

    our_active_val_index_to_pubkey = (
        beacon.get_active_validator_index_to_pubkey(our_pubkeys)
        if (our_active_val_index_to_pubkey is None or slot % NB_SLOT_PER_EPOCH == 0)
        else our_active_val_index_to_pubkey
    )

    if potential_block is None:
        return (
            our_active_val_index_to_pubkey,
            cumulated_our_ko_vals_index,
        )

    block = potential_block

    # From here, `our_active_val_index_to_pubkey` cannot be `None`, but the linter
    # does not get it.
    assert our_active_val_index_to_pubkey is not None

    previous_slot = slot - 1
    epoch_of_previous_slot = previous_slot // NB_SLOT_PER_EPOCH

    # All our active validators index
    our_active_vals_index = set(our_active_val_index_to_pubkey.keys())

    # Nested dict.
    # - Key of the outer dict is the slot
    # - Key of the inner dict is the committee index
    # - Value of the inner dict is the list of validators index which have to attest
    #   for the given slot and the given committee index
    duty_slot_to_committee_index_to_vals_index: dict[
        int, dict[int, list[int]]
    ] = beacon.get_duty_slot_to_committee_index_to_validators_index(
        epoch_of_previous_slot
    )

    # Dict where key is committee index and value is the list of validators
    # index which had to attest for the previous slot
    duty_committee_index_to_validators_index = (
        duty_slot_to_committee_index_to_vals_index[previous_slot]
    )

    # Index of validators which had to attest for the previous slot
    duty_vals_index: set[int] = set().union(
        *duty_committee_index_to_validators_index.values()
    )

    # Index ouf our validators which had to attest for the previous slot
    our_duty_vals_index = duty_vals_index & our_active_vals_index

    # ---------------------
    # To refactor from here

    previous_slot_duty_committies_index = duty_slot_to_committee_index_to_vals_index[
        previous_slot
    ]

    actual_committee_index_to_validator_attestation_success = (
        beacon.aggregate_attestations(block, previous_slot)
    )

    list_of_ok_vals_index = (
        apply_mask(
            previous_slot_duty_committies_index[actual_committee_index],
            validator_attestation_success,
        )
        for (
            actual_committee_index,
            validator_attestation_success,
        ) in actual_committee_index_to_validator_attestation_success.items()
    )

    # To refactor until here
    # ----------------------

    # Index of validators which actually attested for the previous slot
    ok_vals_index: set[int] = set(
        item for sublist in list_of_ok_vals_index for item in sublist
    )

    # Index of our validators which actually attested for the previous slot
    our_ok_vals_index = ok_vals_index & our_duty_vals_index

    # Index of our validators which failed to attest for the previous slot
    our_ko_vals_index = our_duty_vals_index - our_ok_vals_index

    our_nok_rate = (
        len(our_ko_vals_index) / len(our_duty_vals_index)
        if len(our_duty_vals_index) != 0
        else None
    )

    if our_nok_rate is not None:
        rate_of_not_optimal_attestation_inclusion_gauge.set(100 * our_nok_rate)

    if len(our_ko_vals_index) > 0:
        assert our_nok_rate is not None

        firsts_index = list(our_ko_vals_index)[:5]

        firsts_pubkey = (
            our_active_val_index_to_pubkey[first_index] for first_index in firsts_index
        )

        short_firsts_pubkey = [pubkey[:10] for pubkey in firsts_pubkey]
        short_firsts_pubkey_str = ", ".join(short_firsts_pubkey)

        print(
            f"☣️  Our validator {short_firsts_pubkey_str} and "
            f"{len(our_ko_vals_index) - len(short_firsts_pubkey)} more "
            f"({round(100 * our_nok_rate, 1)} %) had not optimal attestation "
            f"inclusion at slot {previous_slot}"
        )

        our_reccurent_ko_vals_index = our_ko_vals_index & cumulated_our_ko_vals_index

        if len(our_reccurent_ko_vals_index) > 0:
            firsts_index = list(our_reccurent_ko_vals_index)[:5]

            firsts_pubkey = (
                our_active_val_index_to_pubkey[first_index]
                for first_index in firsts_index
            )

            short_firsts_pubkey = [pubkey[:10] for pubkey in firsts_pubkey]
            short_firsts_pubkey_str = ", ".join(short_firsts_pubkey)

            print(
                f"☠️  Our validator {short_firsts_pubkey_str} and "
                f"{len(our_reccurent_ko_vals_index) - len(short_firsts_pubkey)} more "
                f"had not optimal attestation at least 2 times in a raw"
            )

    new_cumulated_our_ko_vals_index = (
        cumulated_our_ko_vals_index | our_ko_vals_index
    ) - our_ok_vals_index

    return (
        our_active_val_index_to_pubkey,
        new_cumulated_our_ko_vals_index,
    )
