"""
Subnet detection for the Download button -- best-effort port of Android's own
HotspotDetector.detectSubnetPrefix() (see that file's own doc comment): the phone's own IPv4
address on whichever private network the W2K-2 is also joined to (typically this phone's own
Personal Hotspot, turned on by the user beforehand -- same assumption Android makes).

Diverges from Android here only because the platform forces it (see this repo's own README,
"Design principle: match the Android app exactly"): Android enumerates NetworkInterface objects
by name to specifically find the hotspot's own bridge interface, ruling out the cellular one even
though both are up at once. Plain Python on iOS has no equivalent interface-by-name enumeration
available without extra native bindings, so this instead asks the OS which local address it would
route outbound traffic from (a UDP "connect" sends no actual packets, it only makes the kernel
pick a route) -- correct whenever the OS prefers WiFi over cellular for routing, which is the
normal case.

Split out from app.py so the classification logic (is_private_ipv4/subnet_prefix_of) can be unit-
tested directly, without needing a real network or any Toga/rubicon-objc dependency -- only
detect_subnet_prefix() itself does real I/O (a UDP socket "connect"), see tests/test_network.py's
own doc comment on why that one isn't unit-tested the same way.
"""

from __future__ import annotations

import socket
from typing import Optional


def is_private_ipv4(ip: str) -> bool:
    """Same three ranges as Android's own HotspotDetector.isPrivateIpv4(): 10.0.0.0/8,
    172.16.0.0/12, 192.168.0.0/16. False for anything malformed, not just non-private."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        first, second = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return first == 10 or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168)


def subnet_prefix_of(ip: str) -> Optional[str]:
    """The first three octets plus a trailing dot (e.g. "10.190.25."), or None if ip isn't a
    private IPv4 address at all."""
    if not is_private_ipv4(ip):
        return None
    parts = ip.split(".")
    return ".".join(parts[:3]) + "."


def _local_outbound_ip() -> Optional[str]:
    """The address the OS would route outbound traffic from, or None if that can't be
    determined at all (e.g. no network up)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def detect_subnet_prefix() -> Optional[str]:
    """None (same as Android) if nothing suitable is found."""
    local_ip = _local_outbound_ip()
    if local_ip is None:
        return None
    return subnet_prefix_of(local_ip)
