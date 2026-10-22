"""
detect_subnet_prefix() only chooses between nmea2log.subnet's two answers (the outbound address and the prefix of
it); the address ranges and the socket itself are tested there (nmea2log's tests/test_subnet.py), which is also
where the boundary cases the Android app's HotspotDetectorTest.kt has live now.
"""

from mysailinglogbook import network


def test_detect_subnet_prefix_is_the_prefix_of_the_outbound_address(monkeypatch):
    monkeypatch.setattr(network, "outbound_ipv4", lambda: "192.168.1.42")

    assert network.detect_subnet_prefix() == "192.168.1."


def test_detect_subnet_prefix_is_none_without_a_route(monkeypatch):
    monkeypatch.setattr(network, "outbound_ipv4", lambda: None)

    assert network.detect_subnet_prefix() is None


def test_detect_subnet_prefix_is_none_for_a_public_address(monkeypatch):
    """Cellular only: the phone is not on a private network, so there is no W2K-2 to look for."""
    monkeypatch.setattr(network, "outbound_ipv4", lambda: "100.64.3.9")

    assert network.detect_subnet_prefix() is None
