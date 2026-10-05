"""Drives nmea2log.bootmode.BootModeMachine for iOS -- the same state machine Android's own
BootModeController.kt/W2kBootExecutor.kt drive, see bootmode.py's own module doc comment for the
full state machine description.

iOS has no foreground service: an app that goes to the background is suspended within seconds, and no timer
runs. So the mode works in two ways:

- In the foreground the machine runs on timers, as it always did (the app keeps the screen on, see
  app.on_boot_mode_active_changed()).
- In the background iOS runs a BGProcessingTask when IT decides (some time after the time the machine asked
  for -- possibly hours later, and not at all in Low Power Mode): the app is started or woken, the machine
  gets a Resume event and does what is due (look for the W2K-2, download and build, publish), and the next
  task is requested for the time the machine then asks for. A local notification says what happened.

The machine's state is persisted after every step (boot_mode_state.json) so a task that starts a fresh
process, or the user opening the app again, carries on where it was. Rounds in the background are
therefore best effort: how often they run is iOS's choice, unlike Android's alarm.

Simpler than the Android original in two ways: no JSON round-trip through step() (plain Python calling
Python, BootModeMachine.handle() is called directly), and no BootClock/simulation support (Android's
developer-only fast-forward testing tool; this module is tested by driving BootModeMachine directly, see
nmea2log's own tests/test_bootmode.py and tests/test_boot_mode_background.py here).
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import replace
from typing import Optional

from nmea2log import android_entry
from nmea2log.bootmode import (
    BootState,
    Resume,
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
    RoundOutcome,
    ScheduleTick,
    Start,
    STATUS_TEXT_KEYS,
    StartRound,
    Stop,
    StopService,
    Tick,
    round_outcome_from_result,
)

from .network import detect_subnet_prefix
from .translations import t

def format_status(kind: str, next_at_ms: Optional[int]) -> Optional[str]:
    """The (translated) text for a bootmode.Status name -- same role as BootStatusText.kt's own
    format(). None for a kind this version does not know (mirrors the Kotlin original's own
    fallback), so a future bootmode.py addition doesn't crash an app that hasn't been updated for
    it yet, just silently shows nothing for that one status."""
    key = STATUS_TEXT_KEYS.get(kind)
    if key is None:
        return None
    if next_at_ms is None:
        return t(key)
    time_text = time.strftime("%H:%M", time.localtime(next_at_ms / 1000))
    return t(key, time=time_text)


# The identifier of the background task (also in Info.plist, BGTaskSchedulerPermittedIdentifiers).
BACKGROUND_TASK_ID = "com.ayuus.mysailinglogbook.boatmode"
# When a background task was refused or has no next time, ask for one this long from now.
_FALLBACK_WAKE_MS = 15 * 60 * 1000
_STATE_FILE_NAME = "boot_mode_state.json"
# A planned wake-up this much overdue, seen when the app is opened, means iOS did not run the background task.
_MISSED_GRACE_MS = 10 * 60 * 1000


class BootModeController:
    """Owned by MySailingLogbook (app.py); one instance for the app's lifetime. All decisions are
    Python's (bootmode.py) -- this class only feeds events in and carries out the actions that
    come back, the same division of labour as BootModeController.kt, just without that file's own
    JSON/worker-thread-per-event machinery (not needed: no Chaquopy boundary to cross here, and
    every actual network call below already runs on its own daemon thread)."""

    def __init__(self, app, native=None):
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
        # The background task iOS started (None while the app is not running one), how many probes/rounds/
        # publishes are still running, and when the machine wants to be woken next.
        self._bg_task = None
        self._pending_work = 0
        self._next_wake_ms: Optional[int] = None
        # Set while the app has just been opened and the probe it started has not reported yet (see on_app_became_active()).
        self._catching_up = False
        # Seams for the tests: how work gets onto a thread, and the iOS calls.
        self._spawn = lambda target: threading.Thread(target=target, daemon=True).start()
        if native is None:
            # Imported here, not at the top: native_ui looks up UIKit classes, which only exist on an iPhone/simulator
            # (the tests of this module pass a stand-in).
            from . import native_ui as native
        self._native = native

    @property
    def _state_path(self):
        return self.app.paths.data / _STATE_FILE_NAME

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
            publish_configured=store.is_publish_configured,
        )

    def start(self) -> None:
        # Refreshed from Settings right before starting, not just once at __init__ time -- the
        # owner normally fills in Settings, then taps the boat button, and BootModeMachine only
        # ever reads its config field, never re-derives it mid-run (see bootmode.py's own
        # __init__), so this is the one place a stale config could otherwise stick for the whole
        # session.
        self.machine.config = self._config()
        # So a background round can tell what it did.
        self._native.request_notification_permission()
        self._handle(self.machine.handle(Start(at=self._now_ms())))

    def stop(self) -> None:
        self._handle(self.machine.handle(Stop(at=self._now_ms())))

    # -- persisted state, and starting again where it was -----------------------------------------------------

    def _save_state(self) -> None:
        """The machine's state (and when it wants to be woken) after a step, so a new process -- started by iOS for a
        background task, or by the user -- carries on where it was. Failing is never worth breaking the mode."""
        try:
            self._state_path.write_text(
                json.dumps({"state": self.machine.state.to_dict(), "next_wake_ms": self._next_wake_ms})
            )
        except OSError:
            pass

    def restore(self) -> bool:
        """Takes the persisted state back after the app was started again, whether by iOS for a background task or by
        the user. Whatever was running died with the old process, so ``working`` is cleared (an interrupted publish
        stays pending). True when the mode was on. Nothing is started here: a background task (on_background_task())
        or the app becoming active (on_app_became_active()) does that."""
        try:
            data = json.loads(self._state_path.read_text())
            state = BootState.from_dict(data["state"])
        except (OSError, ValueError, KeyError):
            return False
        if state.phase is Phase.OFF:
            return False
        self.machine.config = self._config()
        self.machine.state = replace(state, working=None)
        self._next_wake_ms = data.get("next_wake_ms")
        self._was_active = True
        self.app.on_boot_mode_active_changed(True)
        return True

    def on_app_became_active(self) -> None:
        """The app came to the foreground (opened, or opened again): with the boat mode on, try right away -- look for
        the W2K-2, download and build -- instead of waiting for the time the machine had planned. Not when something
        is running already."""
        if not self.active or self._pending_work > 0 or self.busy or self.machine.state.working is not None:
            return
        self._log_missed_background_round()
        # What came of it is said afterwards (see _on_probe_result()): trying at once leaves no trace in the log when
        # the W2K-2 is simply not on this network, which reads as "nothing happened".
        self._catching_up = True
        self._on_tick_fired()
        if self._pending_work == 0:
            self._catching_up = False  # nothing was started (the machine was busy): no result to report

    def _log_missed_background_round(self) -> None:
        """The log would otherwise say nothing about rounds that never ran: when the app is opened and the planned
        wake-up is long overdue, iOS did not start the background task -- say so, and why when that is known."""
        planned = self._next_wake_ms
        if planned is None or self._now_ms() - planned < _MISSED_GRACE_MS:
            return
        planned_text = time.strftime("%H:%M", time.localtime(planned / 1000))
        self.app.log("[warning] " + t("boat_bg_missed", planned=planned_text))
        if self._native.low_power_mode_enabled():
            self.app.log("[info] " + t("boat_bg_low_power"))
        elif not self._native.background_refresh_available():
            self.app.log("[info] " + t("boat_bg_refresh_off"))

    def _handle(self, actions) -> None:
        for action in actions:
            self._perform(action)
        now_active = self.active
        if now_active != self._was_active:
            self._was_active = now_active
            self.app.on_boot_mode_active_changed(now_active)
        self._save_state()
        self._finish_background_task_if_idle()

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
        self._next_wake_ms = at_ms
        if at_ms is None:
            self._native.cancel_background_tasks(BACKGROUND_TASK_ID)
            return
        # In the background no timer runs: iOS is asked to start the app for this time instead.
        self._native.schedule_background_task(BACKGROUND_TASK_ID, at_ms)
        delay = max(0.0, (at_ms - self._now_ms()) / 1000.0)
        self._tick_handle = self.app.loop.call_later(delay, self._on_tick_fired)

    def _on_tick_fired(self) -> None:
        self._tick_handle = None
        self._handle(self.machine.handle(Tick(at=self._now_ms(), busy=self.app.sync_in_progress)))

    # -- probe --------------------------------------------------------------------------------

    def _start_probe(self) -> None:
        self._pending_work += 1
        self._spawn(self._run_probe)

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
        self._pending_work -= 1
        catching_up, self._catching_up = self._catching_up, False
        self._handle(
            self.machine.handle(ProbeResult(at=self._now_ms(), found=found, has_new_files=has_new_files))
        )
        if not catching_up:
            return
        if not found:
            text = format_status("W2K_NOT_FOUND_RETRY", self._next_wake_ms) if self._next_wake_ms is not None else None
            if text:  # the same line a round that finds no W2K-2 gives
                self.app.log("[info] " + text)
        elif self._pending_work == 0:
            self.app.log("[info] " + t("boat_catch_up_nothing_new"))  # reachable, and no round was started

    # -- round ----------------------------------------------------------------------------------

    def _start_round(self) -> None:
        self._pending_work += 1
        self._spawn(self._run_round)

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
        self._pending_work -= 1
        self._handle(self.machine.handle(RoundFinished(at=self._now_ms(), outcome=outcome)))

    # -- publish ----------------------------------------------------------------------------------

    def _start_publish(self) -> None:
        self._pending_work += 1
        self._spawn(self._run_publish)

    def _run_publish(self) -> None:
        # Reuses the exact same publish path the Publish toolbar button itself uses (REST
        # see app.py's own _publish_logbook() doc comment) rather than a separate implementation.
        self.busy = True
        try:
            ok = self.app._publish_logbook()
        finally:
            self.busy = False
        self.app.loop.call_soon_threadsafe(self._on_publish_finished, ok)

    def _on_publish_finished(self, ok: bool) -> None:
        self._pending_work -= 1
        self._handle(self.machine.handle(PublishFinished(at=self._now_ms(), ok=ok)))

    # -- background task ------------------------------------------------------------------------------------------

    def on_background_task(self, task) -> None:
        """iOS started the background task (on the main thread, via the app's loop): do what is due, then finish the task
        when nothing is running any more -- the next task is requested by the machine's own ScheduleTick."""
        if self._bg_task is not None:
            self._native.complete_background_task(task, True)  # one is being handled already
            return
        if self.machine.state.phase is Phase.OFF:
            self._native.complete_background_task(task, True)
            return
        self._bg_task = task
        self._native.set_background_task_expiration(task, self._on_background_expired)
        self.machine.config = self._config()
        if self.machine.state.working is not None or self.busy or self.app.sync_in_progress:
            # Something is running already (the app is in use); that run's own step will finish the task.
            self._finish_background_task_if_idle()
            return
        self._handle(self.machine.handle(Resume(at=self._now_ms())))

    def _finish_background_task_if_idle(self) -> None:
        if self._bg_task is None or self._pending_work > 0:
            return
        task, self._bg_task = self._bg_task, None
        self._native.complete_background_task(task, True)

    def _on_background_expired(self) -> None:
        """iOS is about to end the task's time: finish it, and ask for the next one -- what is running goes on as long
        as the process lives, and the machine's next tick then finds it done."""
        task, self._bg_task = self._bg_task, None
        if task is not None:
            self._native.complete_background_task(task, False)
        when = self._next_wake_ms if self._next_wake_ms is not None else self._now_ms() + _FALLBACK_WAKE_MS
        self._native.schedule_background_task(BACKGROUND_TASK_ID, when)

    # -- notify / stop ----------------------------------------------------------------------------

    def _notify(self, kind, next_at_ms) -> None:
        text = format_status(kind.value if hasattr(kind, "value") else kind, next_at_ms)
        if text is None:
            return
        self.app.log("[info] " + text)
        if self._bg_task is not None:
            # The app is not on screen: this is how the user finds out what a background round did.
            self._native.post_local_notification("boatmode-status", t("tooltip_boat_mode_on"), text)

    def _stop_service(self) -> None:
        # No foreground-service equivalent to stop on iOS (see this module's own doc comment) --
        # the phase is already OFF by the time this action comes back, so _handle()'s own
        # active-check above already notifies the app. Nothing further to do here; this method
        # exists only so StopService has a handler, matching every other Action.
        pass
