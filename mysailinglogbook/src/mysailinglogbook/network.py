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
route outbound traffic from -- correct whenever the OS prefers WiFi over cellular for routing,
which is the normal case. The private-address check, the prefix and that outbound-address question
are nmea2log's (nmea2log.subnet), shared with the desktop; only the choice is made here.
"""

from __future__ import annotations

from typing import Optional

from nmea2log.subnet import outbound_ipv4, subnet_prefix_of


def detect_subnet_prefix() -> Optional[str]:
    """None (same as Android) if nothing suitable is found."""
    local_ip = outbound_ipv4()
    if local_ip is None:
        return None
    return subnet_prefix_of(local_ip)
