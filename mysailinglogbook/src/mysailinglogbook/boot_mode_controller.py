"""Drives nmea2log.bootmode.BootModeMachine for iOS -- the same state machine Android's own
BootModeController.kt/W2kBootExecutor.kt drive, see bootmode.py's own module doc comment for the
full state machine description. Deliberately simpler than the Android original in three ways, all
because this app's boat mode is foreground-only (see the main README's own "Appearance" section
and this repo's top-level README for why iOS has no equivalent to a foreground service):

- No JSON round-trip through step() -- Kotlin needs that to cross the Chaquopy boundary, but this
  is plain Python calling Python, so BootModeMachine.handle() is called directly with real
  dataclass instances.
- No persisted state (BootModeStateStore.kt's own SharedPreferences-backed equivalent) -- if the
  app is killed, boat mode is gone regardless of what's persisted, since there is no background
  service to resume it. State lives in memory for exactly as long as the app process does.
- No BootClock/simulation support (Android's own developer-only fast-forward testing tool) -- not
  needed here; this module is tested by driving BootModeMachine directly instead (see
  nmea2log's own tests/test_bootmode.py, already covering everything this module delegates to it).
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from nmea2log import android_entry
from nmea2log.bootmode import (
    BoatSnapshot,
    BootModeConfig,
    BootModeMachine,
    Notify,
    Phase,
    Publish,
    PublishFinished,
    ProbeResult,
    ProbeW2k,
    RoundFailed,
    RoundFinished,
    RoundNotFound,
    RoundOk,
    RoundOutcome,
    ScheduleTick,
    Start,
    StartRound,
    Stop,
    StopService,
    Tick,
)

from .network import detect_subnet_prefix
from .translations import t

_BOAT_STATUS_KEYS = {
    "SEARCHING": "boat_status_searching",
    "ROUND_STARTED": "boat_status_round_started",
    "ROUND_DONE": "boat_status_round_done",
    "ROUND_FAILED": "boat_status_round_failed",
    "W2K_NOT_FOUND_RETRY": "boat_status_w2k2_not_found_retry",
    "HARBOUR_FINAL": "boat_status_harbour_final",
    "LEFT_BOAT": "boat_status_left_boat",
    "LEFT_BOAT_NOTHING_TO_PUBLISH": "boat_status_left_boat_nothing",
    "WAITING_IN_PORT": "boat_status_waiting_in_port",
    "PUBLISH_STARTED": "boat_status_publish_started",
    "PUBLISH_OK": "boat_status_publish_ok",
    "PUBLISH_FAILED": "boat_status_publish_failed",
    "STOPPED": "boat_status_stopped",
}


def format_status(kind: str, next_at_ms: Optional[int]) -> Optional[str]:
    """The (translated) text for a bootmode.Status name -- same role as BootStatusText.kt's own
    format(). None for a kind this version does not know (mirrors the Kotlin original's own
    fallback), so a future bootmode.py addition doesn't crash an app that hasn't been updated for
    it yet, just silently shows nothing for that one status."""
    key = _BOAT_STATUS_KEYS.get(kind)
    if key is None:
        return None
    if next_at_ms is None:
        return t(key)
    time_text = time.strftime("%H:%M", time.localtime(next_at_ms / 1000))
    return t(key, time=time_text)


def round_outcome_from_result(result: dict) -> RoundOutcome:
    """[result] is android_entry.sync_from_w2k2()'s own return dict -- see that function's doc
    comment for its exact shape. Pulled out of _run_round() as its own pure function so the
    mapping itself (cancelled/failed/ok, and BoatSnapshot construction) is unit-testable without
    any real network I/O, mirroring W2kBootExecutor.kt's own runRound() -- same three outcomes,
    same "cancelled counts as failed" and "downloaded_count floored at 0" choices."""
    if result.get("cancelled"):
        return RoundFailed(message=result.get("error") or "cancelled")
    if not result.get("ok"):
        return RoundFailed(message=result.get("error") or "unknown error")
    boat = result.get("boat_state")
    return RoundOk(
        downloaded_count=max(result.get("downloaded_count", 0), 0),
        boat=BoatSnapshot.from_dict(boat) if boat else None,
    )


class BootModeController:
    """Owned by MySailingLogbook (app.py); one instance for the app's lifetime. All decisions are
    Python's (bootmode.py) -- this class only feeds events in and carries out the actions that
    come back, the same division of labour as BootModeController.kt, just without that file's own
    JSON/worker-thread-per-event machinery (not needed: no Chaquopy boundary to cross here, and
    every actual network call below already runs on its own daemon thread)."""

    def __init__(self, app):
        self.app = app
        self.machine = BootModeMachine()
        self._tick_handle = None
        self._was_active = False
        # True only while a round or publish (not a probe -- cheap, same as W2kBootExecutor.kt's
        # own probeW2k() never setting SyncState.bootBusy) is actually running, so the toolbar's
        # own Download/Build/Publish guards (see app.py's own on_download()/on_build()/
        # on_publish()) can refuse a manual tap that would otherwise run concurrently with boat
        # mode's own network/pipeline work on the same local files.
        self.busy = False

    @property
    def active(self) -> bool:
        return self.machine.state.phase is not Phase.OFF

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _config(self) -> BootModeConfig:
        store = self.app.settings_store
        return BootModeConfig(
            round_interval_minutes=store.boot_round_interval_minutes,
            publish_every_round=store.boot_publish_every_round,
            final_on_harbour=store.boot_final_on_harbour,
            harbour_stationary_minutes=store.boot_harbour_stationary_minutes,
            harbour_engine_off_minutes=store.boot_harbour_engine_off_minutes,
            final_on_left_boat=store.boot_final_on_left_boat,
            left_boat_minutes=store.boot_left_boat_minutes,
            stop_after_final=store.boot_stop_after_final,
            publish_configured=store.is_rest_upload_config_complete or store.is_sftp_config_complete,
        )

    def start(self) -> None:
        # Refreshed from Settings right before starting, not just once at __init__ time -- the
        # owner normally fills in Settings, then taps the boat button, and BootModeMachine only
        # ever reads its config field, never re-derives it mid-run (see bootmode.py's own
        # __init__), so this is the one place a stale config could otherwise stick for the whole
        # session.
        self.machine.config = self._config()
        self._handle(self.machine.handle(Start(at=self._now_ms())))

    def stop(self) -> None:
        self._handle(self.machine.handle(Stop(at=self._now_ms())))

    def _handle(self, actions) -> None:
        for action in actions:
            self._perform(action)
        now_active = self.active
        if now_active != self._was_active:
            self._was_active = now_active
            self.app.on_boot_mode_active_changed(now_active)

    def _perform(self, action) -> None:
        if isinstance(action, ScheduleTick):
            self._schedule_tick(action.at)
        elif isinstance(action, ProbeW2k):
            self._start_probe()
        elif isinstance(action, StartRound):
            self._start_round()
        elif isinstance(action, Publish):
            self._start_publish()
        elif isinstance(action, Notify):
            self._notify(action.kind, action.next_at)
        elif isinstance(action, StopService):
            self._stop_service()

    # -- timer --------------------------------------------------------------------------------

    def _schedule_tick(self, at_ms: Optional[int]) -> None:
        if self._tick_handle is not None:
            self._tick_handle.cancel()
            self._tick_handle = None
        if at_ms is None:
            return
        delay = max(0.0, (at_ms - self._now_ms()) / 1000.0)
        self._tick_handle = self.app.loop.call_later(delay, self._on_tick_fired)

    def _on_tick_fired(self) -> None:
        self._tick_handle = None
        self._handle(self.machine.handle(Tick(at=self._now_ms(), busy=self.app.sync_in_progress)))

    # -- probe --------------------------------------------------------------------------------

    def _start_probe(self) -> None:
        threading.Thread(target=self._run_probe, daemon=True).start()

    def _run_probe(self) -> None:
        found, has_new_files = False, False
        try:
            store = self.app.settings_store
            subnet = detect_subnet_prefix()
            if subnet is not None and store.is_w2k2_config_complete:
                found, has_new_files = self._probe_subnet(subnet)
        except Exception as exc:
            self.app.loop.call_soon_threadsafe(self.app.log, f"[warning] {exc}")
        self.app.loop.call_soon_threadsafe(self._on_probe_result, found, has_new_files)

    def _probe_subnet(self, subnet: str) -> tuple[bool, bool]:
        store = self.app.settings_store
        outcome = {"found": False, "has_new_files": False}

        class _ProbeCallback:
            def onProbeResult(self, found, has_new_files):
                outcome["found"] = found
                outcome["has_new_files"] = has_new_files

        android_entry.probe_w2k2(
            store.w2k2_user, store.w2k2_password, subnet, str(self.app.ebl_dir()), _ProbeCallback()
        )
        return outcome["found"], outcome["has_new_files"]

    def _on_probe_result(self, found: bool, has_new_files: bool) -> None:
        self._handle(
            self.machine.handle(ProbeResult(at=self._now_ms(), found=found, has_new_files=has_new_files))
        )

    # -- round ----------------------------------------------------------------------------------

    def _start_round(self) -> None:
        threading.Thread(target=self._run_round, daemon=True).start()

    def _run_round(self) -> None:
        self.busy = True
        try:
            outcome = self._round_outcome()
        finally:
            self.busy = False
        self.app.loop.call_soon_threadsafe(self._on_round_finished, outcome)

    def _round_outcome(self) -> RoundOutcome:
        store = self.app.settings_store
        if not store.is_w2k2_config_complete:
            return RoundFailed(message=t("log_fill_w2k2_credentials"))
        subnet = detect_subnet_prefix()
        if subnet is None:
            return RoundNotFound()
        # Only a quick look first -- same reasoning as W2kBootExecutor.kt's own runRound(): the
        # machine needs "not reachable" apart from "failed", and sync_from_w2k2() itself reports
        # a missing W2K-2 as just another error string, not a distinct outcome.
        found, _ = self._probe_subnet(subnet)
        if not found:
            return RoundNotFound()
        try:
            result = android_entry.sync_from_w2k2(
                store.w2k2_user,
                store.w2k2_password,
                subnet,
                str(self.app.ebl_dir()),
                str(self.app.output_html_path()),
                str(self.app.sample_cache_path()),
                store.boat_name,
                store.mmsi,
                store.call_sign,
                progress_callback=None,
                min_stop_minutes=store.min_stop_minutes,
            )
        except Exception as exc:
            return RoundFailed(message=str(exc))
        return round_outcome_from_result(result)

    def _on_round_finished(self, outcome: RoundOutcome) -> None:
        self._handle(self.machine.handle(RoundFinished(at=self._now_ms(), outcome=outcome)))

    # -- publish ----------------------------------------------------------------------------------

    def _start_publish(self) -> None:
        threading.Thread(target=self._run_publish, daemon=True).start()

    def _run_publish(self) -> None:
        # Reuses the exact same publish path the Publish toolbar button itself uses (REST
        # preferred over SFTP, SFTP shows the "not supported on iOS" error -- see app.py's own
        # _publish_logbook() doc comment) rather than a separate implementation of the same
        # REST-vs-SFTP choice.
        self.busy = True
        try:
            ok = self.app._publish_logbook()
        finally:
            self.busy = False
        self.app.loop.call_soon_threadsafe(self._on_publish_finished, ok)

    def _on_publish_finished(self, ok: bool) -> None:
        self._handle(self.machine.handle(PublishFinished(at=self._now_ms(), ok=ok)))

    # -- notify / stop ----------------------------------------------------------------------------

    def _notify(self, kind, next_at_ms) -> None:
        text = format_status(kind.value if hasattr(kind, "value") else kind, next_at_ms)
        if text is None:
            return
        self.app.log("[info] " + text)

    def _stop_service(self) -> None:
        # No foreground-service equivalent to stop on iOS (see this module's own doc comment) --
        # the phase is already OFF by the time this action comes back, so _handle()'s own
        # active-check above already notifies the app. Nothing further to do here; this method
        # exists only so StopService has a handler, matching every other Action.
        pass
