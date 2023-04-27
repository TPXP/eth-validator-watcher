import functools

from .beacon import Beacon


print = functools.partial(print, flush=True)


def handle_missed_attestations(
    beacon: Beacon, our_active_index_to_pubkey: dict[int, str], epoch: int
) -> set[int]:
    validators_index = set(our_active_index_to_pubkey)
    validators_liveness = beacon.get_validators_liveness(epoch - 1, validators_index)

    dead_indexes = {
        index for index, liveness in validators_liveness.items() if not liveness
    }

    if len(dead_indexes) == 0:
        return set()

    first_indexes = list(dead_indexes)[:5]

    first_pubkeys = (
        our_active_index_to_pubkey[first_index] for first_index in first_indexes
    )

    short_first_pubkeys = [pubkey[:10] for pubkey in first_pubkeys]
    short_first_pubkeys_str = ", ".join(short_first_pubkeys)

    print(
        f"☹️  Our validator {short_first_pubkeys_str} and "
        f"{len(dead_indexes) - len(short_first_pubkeys)} more "
        f"missed attestation at epoch {epoch - 1}"
    )

    return dead_indexes


def handle_double_missed_attestations(
    dead_indexes: set[int],
    previous_dead_indexes: set[int],
    our_active_index_to_pubkey: dict[int, str],
    epoch: int,
) -> None:
    double_dead_indexes = dead_indexes & previous_dead_indexes

    if len(double_dead_indexes) == 0:
        return

    first_indexes = list(dead_indexes)[:5]

    first_pubkeys = (
        our_active_index_to_pubkey[first_index] for first_index in first_indexes
    )

    short_first_pubkeys = [pubkey[:10] for pubkey in first_pubkeys]
    short_first_pubkeys_str = ", ".join(short_first_pubkeys)

    print(
        f"😱  Our validator {short_first_pubkeys_str} and "
        f"{len(double_dead_indexes) - len(short_first_pubkeys)} more "
        f"missed 2 attestations in a raw from epoch {epoch - 2}"
    )
