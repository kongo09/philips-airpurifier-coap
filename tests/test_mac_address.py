"""Tests for MAC address handling."""

from custom_components.philips_airpurifier_coap.helpers import normalize_connection_mac


def test_all_zero_mac_is_ignored() -> None:
    """All-zero MAC addresses must not be used for device registry connections."""

    assert normalize_connection_mac("00:00:00:00:00:00") is None


def test_broadcast_mac_is_ignored() -> None:
    """Broadcast MAC addresses must not be used for device registry connections."""

    assert normalize_connection_mac("ff:ff:ff:ff:ff:ff") is None


def test_normal_mac_is_accepted() -> None:
    """A normal unicast MAC must remain valid."""

    assert normalize_connection_mac("6A:96:FB:2B:9B:CF") == "6a:96:fb:2b:9b:cf"


def test_missing_mac_is_ignored() -> None:
    """Missing MAC values must not create a device registry connection."""

    assert normalize_connection_mac(None) is None
