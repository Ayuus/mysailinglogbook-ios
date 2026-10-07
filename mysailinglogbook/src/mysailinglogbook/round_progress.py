"""The progress of a boat-mode round, as a quiet notification while iOS runs the round in the background.

iOS has no foreground service and no progress bar in a notification: the one thing an app can do is replace a notification
with new text. During a background round (the task iOS starts when it decides to) this shows "Downloading 12/80" and the like,
replaced every ``MIN_INTERVAL_S`` seconds and whenever the phase changes -- quietly (no sound, no lit screen), so it does not
nag. Only while iOS runs the round: with the app on screen the progress bar is visible, and an app that is not given
background time is suspended by iOS shortly after it is left.

No UIKit in here: the controller hands in what posts the notification and what says whether the round runs in the background,
so the logic can be tested without an iPhone.
"""

from __future__ import annotations

import time
from typing import Callable, Dict


class BackgroundRoundProgress:
    """The ``progress_callback`` of ``android_entry.sync_from_w2k2()`` (the contract is in android_entry.py) for a boat-mode
    round. ``post(text)`` shows a notification; ``active()`` says whether the round runs in the background right now;
    ``on_log_line(line)`` gets every log line of the round (the same lines the Android app shows in its log);
    ``labels`` maps the phase ("downloading", "decoding", "building_trips") to its text."""

    MIN_INTERVAL_S = 15.0

    def __init__(
        self,
        post: Callable[[str], None],
        active: Callable[[], bool],
        on_log_line: Callable[[str], None],
        labels: Dict[str, str],
        clock: Callable[[], float] = time.monotonic,
    ):
        self._post = post
        self._active = active
        self._on_log_line = on_log_line
        self._labels = labels
        self._clock = clock
        self._last_phase = None
        self._last_at = 0.0

    def _update(self, phase: str, current: int, total: int) -> None:
        if total <= 0 or phase not in self._labels or not self._active():
            return
        now = self._clock()
        if phase == self._last_phase and now - self._last_at < self.MIN_INTERVAL_S and current < total:
            return
        self._last_phase, self._last_at = phase, now
        self._post(f"{self._labels[phase]} {current}/{total}")

    # -- the progress_callback contract ----------------------------------------------------------------------

    def report(self, current, total, file_name):
        self._update("downloading", current, total)

    def onProgress(self, phase, current, total):
        self._update(phase, current, total)

    def onLogLine(self, line):
        self._on_log_line(line)

    def isCancelled(self):
        return False

    def onDownloadComplete(self):
        pass

    def onBoatState(self, boat_state_json):
        pass

    def onResult(self, ok, error, cancelled, trip_count, html_path, downloaded_count):
        pass
