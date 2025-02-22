from eth_validator_watcher.utils import eth2_address_0x_prefixed
from pytest import raises


def test_eth2_address_0x_prefixed_invalid() -> None:
    # Too short
    with raises(ValueError):
        eth2_address_0x_prefixed("0x123")

    # Too long
    with raises(ValueError):
        eth2_address_0x_prefixed(
            "0x123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789"
        )

    # Invalid character
    with raises(ValueError):
        eth2_address_0x_prefixed("0x8d8b1b85d02d05ad3a14e2e9cc7b458d5invalid")


def test_eth2_address_0x_prefixed_valid_already_prefixed() -> None:
    address = "0xb2ddae7e32fd8257c2dd468ca16dc86d310cab218f9a41ed6fabea525a9620d46955350776e8496553138c8a291a365b"
    assert eth2_address_0x_prefixed(address) == address


def test_eth2_address_0x_prefixed_valid_not_already_prefixed() -> None:
    address_without_prefix = "b2ddae7e32fd8257c2dd468ca16dc86d310cab218f9a41ed6fabea525a9620d46955350776e8496553138c8a291a365b"
    address_with_prefix = "0xb2ddae7e32fd8257c2dd468ca16dc86d310cab218f9a41ed6fabea525a9620d46955350776e8496553138c8a291a365b"
    assert eth2_address_0x_prefixed(address_without_prefix) == address_with_prefix
