"""Tests for boot_mode_controller.py's own pure functions -- the two places it does real
mapping/formatting work of its own, rather than just carrying out an Action by calling into
android_entry/detect_subnet_prefix (real network I/O, not unit-tested here, same reasoning as
network.py's own _local_outbound_ip()). Everything the state machine itself decides (phases,
thresholds, harbour/left-the-boat detection) is covered by nmea2log's own tests/test_bootmode.py,
not duplicated here."""

from nmea2log.bootmode import BoatSnapshot, RoundFailed, RoundNotFound, RoundOk

from mysailinglogbook.boot_mode_controller import format_status, round_outcome_from_result


def test_round_outcome_from_result_maps_a_successful_round_with_no_boat_state():
    outcome = round_outcome_from_result({"ok": True, "downloaded_count": 3, "boat_state": None})

    assert outcome == RoundOk(downloaded_count=3, boat=None)


def test_round_outcome_from_result_builds_a_boat_snapshot_when_present():
    outcome = round_outcome_from_result(
        {
            "ok": True,
            "downloaded_count": 1,
            "boat_state": {
                "underway": False,
                "stationary_since": "2026-09-27T12:00:00",
                "stationary_seconds": 1800,
                "engine_running": False,
                "engine_off_seconds": 900,
            },
        }
    )

    assert isinstance(outcome, RoundOk)
    assert outcome.boat == BoatSnapshot(
        underway=False,
        stationary_since="2026-09-27T12:00:00",
        stationary_seconds=1800,
        engine_running=False,
        engine_off_seconds=900,
    )


def test_round_outcome_from_result_floors_a_negative_downloaded_count_at_zero():
    outcome = round_outcome_from_result({"ok": True, "downloaded_count": -1, "boat_state": None})

    assert outcome.downloaded_count == 0


def test_round_outcome_from_result_treats_a_cancelled_run_as_failed():
    outcome = round_outcome_from_result({"ok": False, "cancelled": True, "error": "Sync cancelled."})

    assert outcome == RoundFailed(message="Sync cancelled.")


def test_round_outcome_from_result_falls_back_to_a_generic_message_when_failed_without_one():
    outcome = round_outcome_from_result({"ok": False})

    assert outcome == RoundFailed(message="unknown error")


def test_round_outcome_from_result_reports_a_real_failure_message_when_given_one():
    outcome = round_outcome_from_result({"ok": False, "error": "401: token expired."})

    assert outcome == RoundFailed(message="401: token expired.")


def test_format_status_returns_none_for_an_unknown_kind():
    assert format_status("SOME_FUTURE_STATUS", None) is None


def test_format_status_with_no_time_returns_the_plain_line():
    assert format_status("SEARCHING", None) == "Boat mode: looking for the W2K-2..."


def test_format_status_substitutes_a_formatted_time_when_given_one():
    import time

    # A fixed, known local time (2026-09-27 14:05 local) expressed as epoch milliseconds, so the
    # test doesn't depend on the machine's own timezone doing anything unexpected -- built the
    # same way the value itself will be, via time.localtime(), so this only checks the %H:%M
    # formatting/substitution, not a specific timezone's own wall-clock reading.
    at_ms = int(time.mktime(time.strptime("2026-09-27 14:05", "%Y-%m-%d %H:%M"))) * 1000

    result = format_status("ROUND_DONE", at_ms)

    assert result == "Boat mode: round done, next round at 14:05."
