from pathlib import Path
from eth_validator_watcher.beacon import Beacon
from requests_mock import Mocker
from tests.beacon import assets
import json
from eth_validator_watcher.models import Block


def test_get_block_exists() -> None:
    block_path = Path(assets.__file__).parent / "block.json"

    with block_path.open() as file_descriptor:
        block_dict = json.load(file_descriptor)

    beacon = Beacon("http://beacon-node:5052")

    with Mocker() as mock:
        mock.get(
            f"http://beacon-node:5052/eth/v2/beacon/blocks/4839775", json=block_dict
        )
        block = beacon.get_block(4839775)
        assert block.data.message.proposer_index == 365100
