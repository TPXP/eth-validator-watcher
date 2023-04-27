import json
from pathlib import Path
from typing import List, Optional

import requests
import typer
from prometheus_client import Counter, Gauge, start_http_server
from sseclient import SSEClient
from typer import Option

from .beacon import Beacon, NoBlockError
from .missed_attestations import handle_missed_attestations
from .missed_blocks import handle_missed_block_detection
from .models import Block, EventBlock
from .next_blocks_proposal import handle_next_blocks_proposal
from .suboptimal_attestations import handle_suboptimal_attestation
from .utils import NB_SLOT_PER_EPOCH, get_our_pubkeys, write_liveness_file
from .web3signer import Web3Signer

app = typer.Typer()


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
    prometheus_probe_missed_block_proposals: str = Option(
        "eth_validator_watcher_missed_block_proposals",
        help="Prometheus probe name for missed block proposals",
    ),
    prometheus_probe_rate_of_not_optimal_attestation_inclusion: str = Option(
        "eth_validator_watcher_rate_of_not_optimal_attestation_inclusion",
        help="Prometheus probe name for rate of non optimal attestation inclusion",
    ),
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

    missed_block_proposals_counter = Counter(
        prometheus_probe_missed_block_proposals,
        "Ethereum validator watcher missed block proposals",
    )

    rate_of_not_optimal_attestation_inclusion_gauge = Gauge(
        prometheus_probe_rate_of_not_optimal_attestation_inclusion,
        "Ethereum validator watcher rate of not optimal attestation inclusion",
    )

    beacon = Beacon(beacon_url)
    web3signers = {Web3Signer(web3signer_url) for web3signer_url in web3signer_urls}

    previous_slot: Optional[int] = None
    previous_epoch: Optional[int] = None

    our_pubkeys = get_our_pubkeys(pubkeys_file_path, web3signers)

    # Dict containing, for our active validators:
    # - key  : Validator index
    # - value: Validator pubkey
    our_active_val_index_to_pubkey = beacon.get_active_validator_index_to_pubkey(
        our_pubkeys
    )

    for event in SSEClient(
        requests.get(
            f"{beacon_url}/eth/v1/events",
            stream=True,
            params=dict(topics="block"),
            headers={"Accept": "text/event-stream"},
        )
    ).events():
        data_dict = json.loads(event.data)
        slot = EventBlock(**data_dict).slot
        epoch = slot // NB_SLOT_PER_EPOCH

        def get_potential_block(slot) -> Optional[Block]:
            try:
                return beacon.get_block(slot)
            except NoBlockError:
                # The block is probably orphaned:
                # The beacon saw the block (that's why we received the event) but it was
                # orphaned before we could fetch it.
                return None

        potential_block = get_potential_block(slot)

        handle_missed_block_detection(
            beacon,
            potential_block,
            slot,
            previous_slot,
            missed_block_proposals_counter,
            our_pubkeys,
        )

        if previous_epoch is None or previous_epoch != epoch:
            our_pubkeys = get_our_pubkeys(pubkeys_file_path, web3signers)

            our_active_val_index_to_pubkey = (
                beacon.get_active_validator_index_to_pubkey(our_pubkeys)
            )

            handle_next_blocks_proposal(beacon, our_pubkeys, slot)

            handle_missed_attestations(
                beacon, our_active_val_index_to_pubkey, epoch - 1
            )

        if potential_block is not None:
            handle_suboptimal_attestation(
                beacon,
                potential_block,
                slot,
                our_active_val_index_to_pubkey,
                rate_of_not_optimal_attestation_inclusion_gauge,
            )

        previous_slot = slot
        previous_epoch = epoch

        if liveness_file is not None:
            write_liveness_file(liveness_file)
