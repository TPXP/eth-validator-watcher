import json
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import List, Optional

import requests
import typer
from prometheus_client import Gauge, start_http_server
from sseclient import SSEClient
from typer import Option

from .beacon import Beacon, NoBlockError
from .missed_attestations import (
    process_double_missed_attestations,
    process_missed_attestations,
)
from .missed_blocks import process_missed_blocks
from .models import Block, EventBlock
from .next_blocks_proposal import process_future_blocks_proposal
from .suboptimal_attestations import process_suboptimal_attestations
from .utils import (
    BLOCK_NOT_ORPHANED_TIME,
    NB_SLOT_PER_EPOCH,
    SLOT_FOR_MISSED_ATTESTATIONS_PROCESS,
    get_our_pubkeys,
    write_liveness_file,
)
from .web3signer import Web3Signer

app = typer.Typer()

slot_count = Gauge("slot", "Slot")
epoch_count = Gauge("epoch", "Epoch")


@app.command()
def handler(
    beacon_url: str = Option(..., help="URL of beacon node"),
    pubkeys_file_path: Optional[Path] = Option(
        None,
        help="File containing the list of public keys to watch",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    web3signer_url: Optional[List[str]] = Option(
        None, help="URL to web3signer managing keys to watch"
    ),
    liveness_file: Optional[Path] = Option(None, help="Liveness file"),
) -> None:
    """
    🚨 Be alerted when you miss a block proposal / when your attestations are late! 🚨

    \b
    This tool watches the 🥓 Ethereum Beacon chain 🥓 and tells you:
    - when you miss a block proposal
    - when some of your attestations are not optimally included in the next slot
    - when some of your attestations are not optimally included in the next slot two
      times in a raw (may indicates there is an issue with this specific key)
    - if one of your keys are about to propose a block in the next two epochs (useful
      when you want to reboot one of your validator client without pressure)

    \b
    You can specify:
    - the path to a file containing the list of public your keys to watch, or / and
    - an URL to a Web3Signer instance managing your keys to watch.

    \b
    Pubkeys are load dynamically, on the first slot of each epoch.
    - If you use pubkeys file, you can change it without having to restart the watcher.
    - If you use Web3Signer, a call to Web3Signer will be done at every slot to get the
    latest keys to watch.

    \b
    Three prometheus probes are exposed:
    - A missed block proposals counter of your keys
    - The rate of non optimal attestation inclusion of your keys for a given slot
    - The number of two non optimal attestation inclusion in a raw of your keys

    Prometheus server is automatically exposed on port 8000.
    """

    default_set: set[str] = set()

    web3signer_urls = set(web3signer_url) if web3signer_url is not None else default_set
    start_http_server(8000)

    beacon = Beacon(beacon_url)

    def get_potential_block(slot) -> Optional[Block]:
        try:
            return beacon.get_block(slot)
        except NoBlockError:
            # The block is probably orphaned:
            # The beacon saw the block (that's why we received the event) but it was
            # orphaned before we could fetch it.
            return None

    web3signers = {Web3Signer(web3signer_url) for web3signer_url in web3signer_urls}

    our_pubkeys: set[str] = set()
    our_active_index_to_pubkey: dict[int, str] = {}
    our_dead_indexes: set[int] = set()
    previous_dead_indexes: set[int] = set()

    previous_slot: Optional[int] = None
    previous_epoch: Optional[int] = None

    last_missed_attestations_process_epoch: Optional[int] = None

    for event in SSEClient(
        requests.get(
            f"{beacon_url}/eth/v1/events",
            stream=True,
            params=dict(topics="block"),
            headers={"Accept": "text/event-stream"},
        )
    ).events():
        time_slot_start = datetime.now()

        data_dict = json.loads(event.data)
        slot = EventBlock(**data_dict).slot
        epoch = slot // NB_SLOT_PER_EPOCH
        slot_in_epoch = slot % NB_SLOT_PER_EPOCH

        slot_count.set(slot)
        epoch_count.set(epoch)

        is_new_epoch = previous_epoch is None or previous_epoch != epoch

        if is_new_epoch:
            our_pubkeys = get_our_pubkeys(pubkeys_file_path, web3signers)
            our_active_index_to_pubkey = beacon.get_active_index_to_pubkey(our_pubkeys)

        time_now = datetime.now()
        delta = BLOCK_NOT_ORPHANED_TIME - (time_now - time_slot_start)
        delta_secs = delta.total_seconds()

        should_process_missed_attestations = (
            last_missed_attestations_process_epoch is None
            or (
                last_missed_attestations_process_epoch != epoch
                and slot_in_epoch >= SLOT_FOR_MISSED_ATTESTATIONS_PROCESS
            )
        )

        if should_process_missed_attestations:
            our_dead_indexes = process_missed_attestations(
                beacon, our_active_index_to_pubkey, epoch
            )

            process_double_missed_attestations(
                our_dead_indexes,
                previous_dead_indexes,
                our_active_index_to_pubkey,
                epoch,
            )

            last_missed_attestations_process_epoch = epoch

        process_future_blocks_proposal(beacon, our_pubkeys, slot, is_new_epoch)

        sleep(max(0, delta_secs))

        potential_block = get_potential_block(slot)

        if potential_block is not None:
            process_suboptimal_attestations(
                beacon,
                potential_block,
                slot,
                our_active_index_to_pubkey,
            )

        process_missed_blocks(
            beacon,
            potential_block,
            slot,
            previous_slot,
            our_pubkeys,
        )

        previous_dead_indexes = our_dead_indexes
        previous_slot = slot
        previous_epoch = epoch

        if slot_in_epoch >= SLOT_FOR_MISSED_ATTESTATIONS_PROCESS:
            should_process_missed_attestations = True

        if liveness_file is not None:
            write_liveness_file(liveness_file)
