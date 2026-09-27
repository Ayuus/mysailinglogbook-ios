"""
Tests for network.py's pure classification logic (is_private_ipv4/subnet_prefix_of). Mirrors
the Android app's own HotspotDetectorTest.kt (same three private ranges, same boundary cases) --
see network.py's own doc comment for why the two apps use different detection *mechanisms* while
sharing this same classification.

detect_subnet_prefix() itself isn't unit-tested here: its only real logic is calling
_local_outbound_ip() (real socket I/O) and feeding the result through subnet_prefix_of(), which
is already covered directly below -- mocking the socket to test that thin wiring wouldn't cover
anything is_private_ipv4/subnet_prefix_of's own tests don't already.
"""

from mysailinglogbook.network import is_private_ipv4, subnet_prefix_of


def test_10_dot_x_dot_x_dot_x_is_private_regardless_of_the_second_octet():
    assert is_private_ipv4("10.0.0.1")
    assert is_private_ipv4("10.255.255.255")
    assert is_private_ipv4("10.190.25.4")


def test_172_dot_16_through_172_dot_31_is_private():
    assert is_private_ipv4("172.16.0.1")
    assert is_private_ipv4("172.31.255.255")
    assert is_private_ipv4("172.20.5.5")


def test_172_dot_15_and_172_dot_32_are_just_outside_the_private_range():
    assert not is_private_ipv4("172.15.255.255")
    assert not is_private_ipv4("172.32.0.0")


def test_192_dot_168_dot_x_dot_x_is_private():
    assert is_private_ipv4("192.168.0.1")
    assert is_private_ipv4("192.168.255.255")


def test_192_dot_167_and_192_dot_169_are_not_private():
    assert not is_private_ipv4("192.167.0.1")
    assert not is_private_ipv4("192.169.0.1")


def test_public_addresses_are_not_private():
    assert not is_private_ipv4("8.8.8.8")
    assert not is_private_ipv4("1.1.1.1")


def test_loopback_is_not_private_by_this_check():
    assert not is_private_ipv4("127.0.0.1")


def test_malformed_addresses_are_not_private():
    assert not is_private_ipv4("not-an-ip")
    assert not is_private_ipv4("10.0.0")
    assert not is_private_ipv4("")


def test_subnet_prefix_of_a_private_address_is_its_first_three_octets_with_a_trailing_dot():
    assert subnet_prefix_of("10.190.25.4") == "10.190.25."
    assert subnet_prefix_of("192.168.1.42") == "192.168.1."


def test_subnet_prefix_of_a_public_address_is_none():
    assert subnet_prefix_of("8.8.8.8") is None
