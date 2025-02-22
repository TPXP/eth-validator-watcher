Ethereum Validator Watcher
==========================

![kiln-logo](docs/img/Kiln_Logo-Transparent-Dark.svg)

[![License](https://img.shields.io/badge/license-MIT-blue)](https://opensource.org/licenses/MIT)

The code is provided as-is with no warranties.

![kiln-logo](docs/img/grafana_dashboard.png)

Description
-----------
**Ethereum Validator Watcher** monitors the Ethereum beacon chain in real-time and notifies you when any of your validators:
- are going to propose a block in the next two epochs
- missed a block proposal
- did not optimally attest
- missed an attestation
- missed two attestations in a row
- proposed a block with the wrong fee recipient
- has exited
- got slashed
- proposed a block with an unknown relay (alpha feature)

It also exports some general metrics such as:
- your USD assets under management
- the total staking market cap
- the epoch and slot
- the number or total slashed validators
- the ETH/USD conversion rate
- the number of your queued validators
- the number of your active validators
- the number of your exited validators
- the number of the network queued validators
- the number of the network active validators
- the entry queue duration estimation

Optionally, you can specify the following parameters:
- the path to a file containing the list of public keys to watch, or / and
- a URL to a Web3Signer instance managing your keys to watch.

Pubkeys are dynamically loaded, at each epoch start.
- If you use a pubkeys file, you can change it without having to restart the watcher.
- If you use Web3Signer, a request to Web3Signer is done at every epoch to get the latest set of keys to watch.

Finally, this program exports the following sets of data from:
- Prometheus (you can use this Grafana dashboard to monitor your validators)
- Slack
- logs
  
Prometheus server is automatically exposed on port 8000.

Command line options
--------------------
 
```
╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --beacon-url               TEXT                            URL of beacon node [required]                                                                   │
│    --execution-url            TEXT                            URL of execution node                                                                           │
│    --pubkeys-file-path        FILE                            File containing the list of public keys to watch                                                │
│    --web3signer-url           TEXT                            URL to web3signer managing keys to watch                                                        │
│    --fee-recipient            TEXT                            Fee recipient address - --execution-url must be set                                             │
│    --slack-channel            TEXT                            Slack channel to send alerts - SLACK_TOKEN env var must be set                                  │
│    --beacon-type              [lighthouse|nimbus|teku|other]  Use this option if connected to a teku, lighthouse or nimbus beacon node. See                   │
│                                                               https://github.com/ConsenSys/teku/issues/7204 for Teku <                                        │
│                                                               23.6.0,https://github.com/sigp/lighthouse/issues/4243 for Lighthouse and                        │
│                                                               https://github.com/status-im/nimbus-eth2/issues/5019 for Nimbus.                                |
|    --relay-url                TEXT                            URL of allow listed relay (alpha feature)                                                       │
│    --liveness-file            PATH                            Liveness file                                                                                   │
│    --help                                                     Show this message and exit.                                                                     │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

Beacon nodes compatibility
--------------------------
Beacon type      | Compatibility
-----------------|----------------------------------------------------------------------------------------------------------
Prysm            | Full
Teku `>= 23.6.0` | Full
Teku `< 23.6.0 ` | Full with `--beacon-type=teku`. See https://github.com/ConsenSys/teku/pull/7212 for more details.
Lighthouse       | Full with `--beacon-type=lighthouse`. See https://github.com/sigp/lighthouse/issues/4243 for more details.
Nimbus           | Partial with `--beacon-type=nimbus` - Missed attestations detection disabled. See https://github.com/status-im/nimbus-eth2/issues/5019 for more details.
Lodestar         | Not (yet) tested.

Command lines examples
----------------------

Minimal example, connected to Prysm:
```
eth-validator-watcher --beacon-url http://localhost:3500
```

Example with Lighthouse and with keys to watch retrieved from Web3Signer:
```
eth-validator-watcher --beacon-url http://localhost:5052 --beacon-type lighthouse --web3signer-url http://localhost:9000
```

Example with Lighthouse, with keys to watch retrieved from a file, and with a specified fee recipient:
```
eth-validator-watcher --beacon-url http://localhost:5052 --beacon-type lighthouse --execution-url http://localhost:8545 --pubkeys-file-path keys.txt --fee-recipient 0x4675c7e5baafbffbca748158becba61ef3b0a263
```

With the following `keys.txt` file:
```
0x815210c169e598f1800dbda3b2ee146a0178f772c5105722e0673d824535bcab03aa6bc422955264bb201b5ddbb6981d
0x950f77f6cba50c9ad97240a7171cf4506bf86cbed11bb8e2f45a38036e4375c4f5344647e7150c640f308fd9d6de4d59
0x8adf063f810e2321a1aea258fd3a6ee5560911cee631980e1ef32bd88bf8c3dd5d28724e22a8987bfe411dd731f6dd38
```

 `--pubkeys-file-path` and `--fee-recipient` flag allow both `0x` prefixed and non `0x` prefixed ETH1 address / pubkeys.

Example with Prysm, with keys to watch retrieved from Web3Signer and with Slack alerting:
```
export SLACK_TOKEN=xoxb-xxxxxxxxxxxxx-xxxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxx
eth-validator-watcher --beacon-url http://localhost:3500 --web3signer-url http://localhost:9000 --slack-channel eth-alerting
```

Example with Prysm, with keys to watch retrieved from Web3Signer and with Flasbots and UltraSound as allowed relays:
```
eth-validator-watcher --beacon-url http://localhost:3500 --web3signer-url http://localhost:9000 --relay-url https://0xac6e77dfe25ecd6110b8e780608cce0dab71fdd5ebea22a16c0205200f2f8e2e3ad3b71d3499c54ad14d6c21b41a37ae@boost-relay.flashbots.net --relay-url https://0xa1559ace749633b997cb3fdacffb890aeebdb0f5a3b6aaa7eeeaf1a38af0a8fe88b9e4b1f61f236d2e64d95733327a62@relay.ultrasound.money
```
Exported Prometheus metrics
---------------------------

name                                       | description
-------------------------------------------|------------
`eth_usd`                                  | ETH/USD conversion rate
`entry_queue_duration_sec`                 | Entry queue duration in seconds
`our_pending_queued_validators_count`      | Our pending queued validators count
`total_pending_queued_validators_count`    | Total pending queued validators count
`our_active_validators_count`              | Our active validators count
`total_active_validators_count`            | Total active validators count
`our_exited_validators_count`              | Our exited validators count
`wrong_fee_recipient_proposed_block_count` | Wrong fee recipient proposed block count
`missed_attestations_count`                | Missed attestations count
`double_missed_attestations_count`         | Double missed attestations count
`missed_block_proposals_count`             | Missed block proposals count
`missed_block_proposals_count_details`     | Missed block proposals count with slot and epoch labels
`future_block_proposals_count`             | Future block proposals count
`our_slashed_validators_count`             | Our slashed validators count
`total_slashed_validators_count`           | Total slashed validators count
`suboptimal_attestations_rate`             | Suboptimal attestations rate
`keys_count`                               | Keys count
`bad_relay_count`                          | Bad relay count


Installation
------------

From source:
```
git clone git@github.com:kilnfi/eth-validator-watcher.git
cd eth-validator-watcher
pip install .
```

Docker images
-------------
Docker images (built for AMD64 and ARM64) are available [here](https://github.com/kilnfi/eth-validator-watcher/pkgs/container/eth-validator-watcher).


Logs
----

Description | Log
------------|----
A new epoch starts. | ```🎂     Epoch     209904     starts```
You are going to propose a block in the next two epochs. | ```💍 Our validator 0xa6cdd026 is going to propose a block at   slot 6716781 (in 13 slots)```
Someone [proposed](https://beaconcha.in/slot/6716776) a block. | ```✅     validator 0xb9d2439f proposed block at epoch 209899 - slot 6716776 ✅```
You [proposed](https://beaconcha.in/slot/6716781) a block. | ```✨ Our validator 0xa6cdd026 proposed block at epoch 209899 - slot 6716781 ✨```
You proposed a block with the wrong fee recipient. | ```🚩 Our validator 0x00000000 proposed block at epoch 209952 - slot 6718495 with the wrong fee recipient```
You [did not had](https://github.com/kilnfi/eth-validator-watcher/assets/4943830/666dad82-2f67-432d-97eb-9f99ef6c106a) optimal attestation inclusion. | ```☣️ Our validator 0x98a5bad4, 0x8116a5f8, 0xa2fff7bd, 0x87cd0fd3, 0x978ebbdb and 1 more (1.2 %) had not optimal attestation inclusion at slot 6716778```
Someone [missed](https://beaconcha.in/validator/399279#blocks) a block proposal.  | ```💩     validator 0xa3dbc635 missed   block at epoch 209894 - slot 6716637 💩```
You [missed](https://beaconcha.in/validator/631094#blocks) a block proposal. | ```❌ Our validator 0xa66d5712 missed   block at epoch 209695 - slot 6710240 ❌```
You [missed](https://github.com/kilnfi/eth-validator-watcher/assets/4943830/9bed8b53-5c53-4cf0-818d-066434660004) an attestation. | ```☹️ Our validator 0xa672f362, 0xb5f46214, 0xac81b7f4 and 0 more missed attestation at epoch 209894```
You [missed](https://github.com/kilnfi/eth-validator-watcher/assets/4943830/74326f4f-d3f5-405d-87ce-9576f9ed79a0) 2 attestations in a raw. | ```😱  Our validator 0x8c9bfca1, 0xa68f7c5d and 0 more missed 2 attestations in a raw from epoch 209367```
You [exited](https://beaconcha.in/validator/491565). | ```🚶 Our validator 0xaeb82c90 is exited```
Someone [got](https://beaconcha.in/validator/647102) slashed. | ```✂️     validator 0xb3a608a7 is slashed```
You got slashed (you don't want to see this one). | ```🔕 Our validator 0x00000000 is slashed```
You proposed a block with a non-allowed relay. | ```🟧 Block proposed with unknown builder (may be a locally built block)```

Slack messages
--------------
If a Slack channel is specified, the slack messages are sent according to the following events:
- When you exited
- When you got slashed
- If fee recipient is specified, when you proposed a block with the wrong fee recipient
- When you missed 2 attestations in a raw
- When you missed a block

Developer guide
---------------
We use [Poetry](https://python-poetry.org/) to manage dependencies and packaging.

**Installation:**
```
git clone git@github.com:kilnfi/validator-watcher.git
cd validator-watcher
poetry install --with dev
poetry shell # To activate Python virtual environment
```

**Running tests:**
```
pytest

# With coverage
pytest --cov eth_validator_watcher --cov-report=term-missing
```

# Liveness
You can use `--liveness-file <path-to-a-file>` option to ensure the watcher is live.
If using this option, at the end of every slot, the watcher will simply write `OK` in the specified file.

**Example of liveness probe usage on Kubernetes**
```yaml
livenessProbe:
  periodSeconds: 60
  initialDelaySeconds: 60
  failureThreshold: 1
  exec:
    command:
    - /usr/bin/python3.9
    - /usr/local/bin/liveness_check.py
    - <path-to-a-file>
```

## FAQ
Why `--execution-url` is needed when `--fee-recipient` is used?

When using external block building (with MEV-boost for example), then the block builder may set its address as a fee recipient.
In such a case, it adds an extra transaction in the block from its address to the proposer's fee recipient.
To check this last transaction, the watcher needs to retrieve the execution block.

## License

[MIT License](LICENSE).
