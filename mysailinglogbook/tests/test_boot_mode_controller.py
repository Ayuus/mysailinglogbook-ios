"""Tests for boot_mode_controller.py's own pure function -- the one place it does real
formatting work of its own (the round outcome and the status table moved to nmea2log's bootmode.py, and
their tests to its tests/test_bootmode.py), rather than just carrying out an Action by calling into
android_entry/detect_subnet_prefix (real network I/O, not unit-tested here, same reasoning as
network.py's own _local_outbound_ip()). Everything the state machine itself decides (phases,
thresholds, harbour/left-the-boat detection) is covered by nmea2log's own tests/test_bootmode.py,
not duplicated here."""

from mysailinglogbook import translations
from mysailinglogbook.boot_mode_controller import format_status


def test_format_status_returns_none_for_an_unknown_kind():
    assert format_status("SOME_FUTURE_STATUS", None) is None


# The expected texts are English; translations picks the language of the device the tests run on.
def test_format_status_with_no_time_returns_the_plain_line(monkeypatch):
    monkeypatch.setattr(translations, "_LANGUAGE", "en")

    assert format_status("SEARCHING", None) == "Boat mode: looking for the W2K-2..."


def test_format_status_substitutes_a_formatted_time_when_given_one(monkeypatch):
    import time

    monkeypatch.setattr(translations, "_LANGUAGE", "en")

    # A fixed, known local time (2026-09-27 14:05 local) expressed as epoch milliseconds, so the
    # test doesn't depend on the machine's own timezone doing anything unexpected -- built the
    # same way the value itself will be, via time.localtime(), so this only checks the %H:%M
    # formatting/substitution, not a specific timezone's own wall-clock reading.
    at_ms = int(time.mktime(time.strptime("2026-09-27 14:05", "%Y-%m-%d %H:%M"))) * 1000

    result = format_status("ROUND_DONE", at_ms)

    assert result == "Boat mode: round done, next round at 14:05."
