import functools

from .beacon import Beacon


print = functools.partial(print, flush=True)


def handle_missed_attestations(
    beacon: Beacon, our_active_val_index_to_pubkey: dict[int, str], epoch: int
) -> None:
    validators_index = set(our_active_val_index_to_pubkey)
    validators_liveness = beacon.get_validators_liveness(epoch, validators_index)

    dead_indexes = {
        index for index, liveness in validators_liveness.items() if not liveness
    }

    if len(dead_indexes) > 0:
        firsts_index = list(dead_indexes)[:5]

        firsts_pubkey = (
            our_active_val_index_to_pubkey[first_index] for first_index in firsts_index
        )

        short_firsts_pubkey = [pubkey[:10] for pubkey in firsts_pubkey]
        short_firsts_pubkey_str = ", ".join(short_firsts_pubkey)

        print(
            f"☹️  Our validator {short_firsts_pubkey_str} and "
            f"{len(dead_indexes) - len(short_firsts_pubkey)} more "
            f"missed attestation at epoch {epoch}"
        )
