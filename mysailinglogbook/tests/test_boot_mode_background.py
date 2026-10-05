"""The boat mode's background rounds (boot_mode_controller.py): the state is persisted after every step, a started app
restores it, a background task from iOS makes the machine do what is due and is finished when nothing runs any more,
and the next task is requested for the time the machine asks for. iOS itself is replaced by FakeNative; the work of
a probe / round / publish runs on the spot instead of on a thread."""

from pathlib import Path

import pytest
from nmea2log.bootmode import Phase

from mysailinglogbook import boot_mode_controller as module
from mysailinglogbook.boot_mode_controller import BACKGROUND_TASK_ID, BootModeController


class FakeHandle:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class FakeLoop:
    def __init__(self):
        self.timers = []

    def call_later(self, delay, callback, *args):
        handle = FakeHandle()
        self.timers.append((delay, callback, handle))
        return handle

    def call_soon_threadsafe(self, callback, *args):
        callback(*args)


class FakeStore:
    boot_round_interval_minutes = 60
    boot_publish_every_round = False
    boot_final_on_harbour = True
    boot_harbour_stationary_minutes = 30
    boot_harbour_engine_off_minutes = 10
    boot_final_on_left_boat = True
    boot_left_boat_minutes = 20
    boot_stop_after_final = False
    is_rest_upload_config_complete = True
    is_sftp_config_complete = False
    is_w2k2_config_complete = True
    w2k2_user = "admin"
    w2k2_password = "pw"
    boat_name = "Boat"
    mmsi = "1"
    call_sign = "X"
    min_stop_minutes = 10.0


class FakeApp:
    def __init__(self, data_dir: Path):
        self.paths = type("Paths", (), {"data": data_dir})()
        self.loop = FakeLoop()
        self.settings_store = FakeStore()
        self.sync_in_progress = False
        self.logs = []
        self.active_changes = []

    def log(self, line):
        self.logs.append(line)

    def on_boot_mode_active_changed(self, active):
        self.active_changes.append(active)

    def ebl_dir(self):
        return self.paths.data

    def output_html_path(self):
        return self.paths.data / "logbook.html"

    def sample_cache_path(self):
        return self.paths.data / "sample_cache.pkl"

    def _publish_logbook(self):
        return True


class FakeNative:
    def __init__(self):
        self.scheduled = []
        self.cancelled = []
        self.completed = []
        self.expiration = None
        self.notifications = []
        self.permission_requests = 0

    def schedule_background_task(self, identifier, at_ms):
        self.scheduled.append((identifier, at_ms))
        return True

    def cancel_background_tasks(self, identifier):
        self.cancelled.append(identifier)

    def complete_background_task(self, task, success):
        self.completed.append((task, success))

    def set_background_task_expiration(self, task, handler):
        self.expiration = handler

    def request_notification_permission(self):
        self.permission_requests += 1

    def post_local_notification(self, identifier, title, body):
        self.notifications.append((identifier, title, body))


def make_controller(data_dir: Path) -> BootModeController:
    controller = BootModeController(FakeApp(data_dir), native=FakeNative())
    controller._spawn = lambda target: target()  # no threads: the work runs at once
    controller._probe_subnet = lambda subnet: (True, True)
    return controller


@pytest.fixture(autouse=True)
def w2k2_on_the_network(monkeypatch):
    monkeypatch.setattr(module, "detect_subnet_prefix", lambda: "192.168.1.")
    monkeypatch.setattr(
        module.android_entry,
        "sync_from_w2k2",
        lambda *args, **kwargs: {"ok": True, "downloaded_count": 2, "trip_count": 3, "boat_state": None},
    )


def test_starting_requests_notifications_persists_the_state_and_asks_ios_for_a_task(tmp_path):
    controller = make_controller(tmp_path)
    controller._probe_subnet = lambda subnet: (False, False)  # nothing found: the machine waits and schedules a tick

    controller.start()

    assert controller._native.permission_requests == 1
    assert controller.machine.state.phase is Phase.SEARCHING
    assert (tmp_path / "boot_mode_state.json").exists()
    assert controller._native.scheduled and controller._native.scheduled[-1][0] == BACKGROUND_TASK_ID


def test_a_started_app_restores_the_state_and_clears_what_was_running(tmp_path):
    first = make_controller(tmp_path)
    first.start()
    first_phase = first.machine.state.phase

    second = make_controller(tmp_path)
    restored = second.restore()

    assert restored is True
    assert second.machine.state.phase is first_phase
    assert second.machine.state.working is None
    assert second.app.active_changes == [True]
    assert second._native.scheduled == []  # nothing is started by restoring


def test_restore_does_nothing_when_the_mode_was_off(tmp_path):
    controller = make_controller(tmp_path)

    assert controller.restore() is False
    controller.start()
    controller.stop()
    assert make_controller(tmp_path).restore() is False


def test_stopping_cancels_the_background_task(tmp_path):
    controller = make_controller(tmp_path)
    controller.start()

    controller.stop()

    assert BACKGROUND_TASK_ID in controller._native.cancelled
    assert controller.machine.state.phase is Phase.OFF


def test_a_background_task_with_the_mode_off_is_finished_at_once(tmp_path):
    controller = make_controller(tmp_path)

    controller.on_background_task("task")

    assert controller._native.completed == [("task", True)]


def test_a_background_task_runs_what_is_due_then_finishes_and_asks_for_the_next(tmp_path):
    controller = make_controller(tmp_path)
    controller._probe_subnet = lambda subnet: (False, False)
    controller.start()  # SEARCHING, nothing found yet
    # The app is started again by iOS for a background task: a new process restores the state.
    revived = make_controller(tmp_path)
    revived.restore()
    scheduled_before = len(revived._native.scheduled)

    revived.on_background_task("task")  # the W2K-2 is found now: a round runs, in the background

    assert revived._native.completed == [("task", True)]
    assert revived.machine.state.phase is Phase.ABOARD
    assert len(revived._native.scheduled) > scheduled_before  # the next round is requested
    assert revived._bg_task is None
    # What happened is told with a notification, since the app is not on screen.
    assert revived._native.notifications


def test_a_background_task_waits_for_the_running_work_before_it_finishes(tmp_path):
    controller = make_controller(tmp_path)
    controller.start()
    controller._spawn = lambda target: None  # the next probe / round does not finish

    controller.on_background_task("task")

    assert controller._pending_work == 1
    assert controller._native.completed == []
    controller._pending_work = 0
    controller._finish_background_task_if_idle()
    assert controller._native.completed == [("task", True)]


def test_a_second_background_task_while_one_is_handled_is_finished_at_once(tmp_path):
    controller = make_controller(tmp_path)
    controller.start()
    controller._spawn = lambda target: None

    controller.on_background_task("first")
    controller.on_background_task("second")

    assert controller._native.completed == [("second", True)]


def test_when_ios_ends_the_time_the_task_is_finished_and_the_next_one_requested(tmp_path):
    controller = make_controller(tmp_path)
    controller.start()
    controller._spawn = lambda target: None
    controller.on_background_task("task")
    scheduled_before = len(controller._native.scheduled)

    controller._native.expiration()

    assert controller._native.completed == [("task", False)]
    assert len(controller._native.scheduled) == scheduled_before + 1


def test_opening_the_app_with_the_mode_on_tries_right_away(tmp_path):
    controller = make_controller(tmp_path)
    controller._probe_subnet = lambda subnet: (False, False)
    controller.start()
    started = []
    controller._spawn = lambda target: started.append(target)

    controller.on_app_became_active()

    assert len(started) == 1  # a probe, at once, not at the planned time


def test_opening_the_app_does_not_start_a_second_run_while_one_is_going(tmp_path):
    controller = make_controller(tmp_path)
    controller._probe_subnet = lambda subnet: (False, False)
    controller.start()
    started = []
    controller._spawn = lambda target: started.append(target)
    controller.on_app_became_active()

    controller.on_app_became_active()

    assert len(started) == 1


def test_opening_the_app_with_the_mode_off_does_nothing(tmp_path):
    controller = make_controller(tmp_path)
    started = []
    controller._spawn = lambda target: started.append(target)

    controller.on_app_became_active()

    assert started == []
