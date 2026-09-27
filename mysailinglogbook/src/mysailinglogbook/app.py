"""
My Sailing Logbook (iOS) -- mirrors the Android app's own MainActivity as closely as the
platform allows (asked for explicitly, see this repo's own README: "Design principle: match
the Android app exactly"). Toolbar order, button purpose, and overall layout (toolbar, log/
status area, logbook view) are the same; see the Android app's MainActivity.kt for the
reference behavior each of these will eventually need to match.
"""

import socket
import threading
from pathlib import Path

import toga
from rubicon.objc import Block, ObjCClass
from toga.style.pack import COLUMN, ROW, Pack

from nmea2log import android_entry

from .settings_screen import SettingsScreen
from .settings_store import SettingsStore

_UIView = ObjCClass("UIView")
# Standard UIKit UIViewAnimationOptions bit values (not exposed as named constants anywhere in
# toga_iOS -- these are stable, documented Apple values, safe to hardcode).
_UI_VIEW_ANIMATION_OPTION_REPEAT = 1 << 3
_UI_VIEW_ANIMATION_OPTION_AUTOREVERSE = 1 << 4


def _set_busy_pulse(button, busy: bool) -> None:
    """Same "something is happening" pulse as Android's own setBusyAppearance() (alpha 1.0 <->
    0.35, 1500ms each way, repeating indefinitely while busy -- see MainActivity.kt's own doc
    comment on the exact timing choice). Ported directly against UIKit via rubicon-objc instead
    of through any Toga cross-platform API -- Toga has no generic opacity-animation concept, and
    Android's own version is itself platform-native code (a plain ObjectAnimator), not something
    to abstract over; this is the iOS-native equivalent of the same thing, not a workaround.
    """
    native = button._impl.native
    if busy:
        def _dim():
            native.alpha = 0.35

        _UIView.animateWithDuration(
            1.5,
            delay=0.0,
            options=_UI_VIEW_ANIMATION_OPTION_REPEAT | _UI_VIEW_ANIMATION_OPTION_AUTOREVERSE,
            animations=Block(_dim, None),
            completion=None,
        )
    else:
        native.layer.removeAllAnimations()
        native.alpha = 1.0


def detect_subnet_prefix():
    """Best-effort port of Android's HotspotDetector.detectSubnetPrefix() (see that file's own
    doc comment): the phone's own IPv4 address on whichever private network the W2K-2 is also
    joined to (typically this phone's own Personal Hotspot, turned on by the user beforehand --
    same assumption Android makes).

    Diverges from Android here only because the platform forces it (see this repo's own README,
    "Design principle: match the Android app exactly"): Android enumerates NetworkInterface
    objects by name to specifically find the hotspot's own bridge interface, ruling out the
    cellular one even though both are up at once. Plain Python on iOS has no equivalent
    interface-by-name enumeration available without extra native bindings, so this instead asks
    the OS which local address it would route outbound traffic from (a UDP "connect" sends no
    actual packets, it only makes the kernel pick a route) -- correct whenever the OS prefers
    WiFi over cellular for routing, which is the normal case. Returns None (same as Android) if
    nothing suitable is found.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
    except OSError:
        return None

    parts = local_ip.split(".")
    if len(parts) != 4:
        return None
    try:
        first, second = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    is_private = first == 10 or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168)
    if not is_private:
        return None
    return ".".join(parts[:3]) + "."


class ProgressCallback:
    """Plays the same role as MainActivity.kt's own SyncController object: the duck-typed
    progress_callback android_entry.build_from_local_files()/sync_from_w2k2() call into during
    the run (see android_entry.py's own doc comments for the exact method contract: report(),
    isCancelled(), onLogLine(), onDownloadComplete(), onBoatState(), onResult()). Simpler here
    than on Android -- this is plain Python calling Python directly, no Chaquopy/Kotlin boundary
    to cross, so there's no need for MainActivity's own "capture via onResult() instead of
    trusting callAttr()'s return value" workaround; the pipeline functions' own return value is
    used directly instead (see MySailingLogbook._log_result()).

    Every call here happens on the background thread actually running the sync/build (see
    MySailingLogbook._start_background()) -- report() and onLogLine() are the only two that
    touch the UI (via app.log()), so only those marshal onto the main thread via
    loop.call_soon_threadsafe(), the same pattern Toga's own App class uses internally for
    cross-thread handler dispatch.
    """

    def __init__(self, app, cancel_event):
        self.app = app
        self.cancel_event = cancel_event

    def report(self, current, total, file_name):
        self.app.loop.call_soon_threadsafe(
            self.app.log, f"[info] Downloading: {current}/{total} ({file_name})"
        )

    def isCancelled(self):
        return self.cancel_event.is_set()

    def onLogLine(self, line):
        self.app.loop.call_soon_threadsafe(self.app.log, line)

    def onDownloadComplete(self):
        pass

    def onBoatState(self, boat_state_json):
        pass  # only boat mode needs this (MainActivity's W2kBootExecutor) -- not ported yet

    def onResult(self, ok, error, cancelled, trip_count, html_path, downloaded_count):
        pass  # the pipeline functions' own return value already has everything we need


class MySailingLogbook(toga.App):
    def startup(self):
        # Same order as Android's own toolbar (MainActivity.kt): download, rebuild, publish,
        # view logbook, boat mode, [flexible spacer], settings. Android's own toolbar buttons
        # are icon-only, no visible text label (see MainActivity.kt's iconButton() helper --
        # tooltip text only, shown on long-press/hover) -- matched here the same way. Icons are
        # the same shapes as Android's own vector drawables (ic_download_24, ic_refresh_24,
        # ic_upload_24, ic_article_24, ic_sailboat_24, ic_settings_24), rasterized from matching
        # SVGs -- see resources/icons-svg/.
        #
        # No flex on the buttons themselves (asked for explicitly, matching Android's own
        # buttonRow: the first 5 icons sit at their natural size, tightly packed, with no gap
        # LayoutParams between them at all) -- a single flexible spacer between boat_mode_button
        # and settings_button does the same job as Android's own zero-size weight=1 spacer View,
        # pushing only Settings to the far right instead of stretching every icon's own slot to
        # fill the toolbar width.
        self.download_button = toga.Button(icon=toga.Icon("resources/download"), on_press=self.on_download)
        self.rebuild_button = toga.Button(icon=toga.Icon("resources/refresh"), on_press=self.on_rebuild)
        self.publish_button = toga.Button(icon=toga.Icon("resources/upload"), on_press=self.on_publish)
        self.view_button = toga.Button(icon=toga.Icon("resources/article"), on_press=self.on_view)
        self.boat_mode_button = toga.Button(icon=toga.Icon("resources/sailboat"), on_press=self.on_boat_mode)
        self.settings_button = toga.Button(icon=toga.Icon("resources/settings"), on_press=self.on_settings)

        toolbar_spacer = toga.Box(style=Pack(flex=1))
        toolbar = toga.Box(
            children=[
                self.download_button,
                self.rebuild_button,
                self.publish_button,
                self.view_button,
                self.boat_mode_button,
                toolbar_spacer,
                self.settings_button,
            ],
            style=Pack(direction=ROW),
        )

        # The log view (a plain scrolling text area) and the WebView that shows the built
        # logbook -- MainActivity.kt's own log/webView pair, toggled by the View button
        # (viewLocalLogbook()) while the toolbar itself stays visible and usable the whole time
        # (asked for explicitly there: "works even while a sync is running", since it only reads
        # a file already on disk -- doesn't touch SyncState at all). content_area holds whichever
        # one is currently showing; see _show_log_content()/_show_logbook_content().
        self.log_view = toga.MultilineTextInput(readonly=True, style=Pack(flex=1))
        self.web_view = toga.WebView(style=Pack(flex=1))
        self.showing_local_logbook = False
        self.content_area = toga.Box(children=[self.log_view], style=Pack(flex=1, direction=COLUMN))

        # toolbar + content_area -- the "main" screen this swaps back to from Settings (there's
        # no second toga.Window to switch to on iOS, see settings_screen.py's own doc comment on
        # why Settings swaps the single MainWindow's content in place instead; unlike Settings,
        # the View toggle only swaps content_area's own child, leaving the toolbar in place, to
        # match Android's own layout -- see the comment above).
        self.main_content = toga.Box(children=[toolbar, self.content_area], style=Pack(direction=COLUMN))

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_content
        self.main_window.show()

        # Mirrors SyncState.inProgress/cancelled on Android (MainActivity.runSync()'s own
        # guard) -- only one sync/build runs at a time; tapping Download/Rebuild again while one
        # is running is ignored for now (Android instead turns the button that started the run
        # into its own cancel button -- not ported yet, see cancel_event below, which the
        # plumbing already supports).
        self.sync_in_progress = False
        self.cancel_event = threading.Event()
        self._busy_button = None

        # Same fields/defaults as Android's own SettingsStore, see settings_store.py.
        self.settings_store = SettingsStore(self.paths.data)

    def log(self, line: str) -> None:
        self.log_view.value += line + "\n"

    def ebl_dir(self) -> Path:
        """Where downloaded/local .ebl files live -- same folder name as Android's own
        EblStorage.downloadDir() ("Actisense"), under the iOS app's Documents directory
        (self.paths.data, see toga_iOS's own Paths.get_data_path()) so the files are reachable
        from the Files app / Finder over USB, the iOS equivalent of Android's own
        getExternalFilesDir() being USB-browsable."""
        directory = self.paths.data / "Actisense"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def output_html_path(self) -> Path:
        return self.paths.data / "logbook.html"

    def sample_cache_path(self) -> Path:
        return self.paths.data / "sample_cache.pkl"

    def on_download(self, widget):
        if self.sync_in_progress:
            self.log("[info] A sync is already running.")
            return
        if not self.settings_store.is_w2k2_config_complete:
            self.log("[info] Fill in the W2K-2 username and password in Settings first.")
            return
        subnet_prefix = detect_subnet_prefix()
        if subnet_prefix is None:
            self.log(
                "[hotspot] No WiFi/hotspot network detected -- turn on Personal Hotspot (or join "
                "the W2K-2's own network) first."
            )
            return
        self.log(f"[info] Checking {subnet_prefix}0/24 for a W2K-2...")
        self._start_background(self._run_sync, subnet_prefix, busy_button=self.download_button)

    def on_rebuild(self, widget):
        if self.sync_in_progress:
            self.log("[info] A build is already running.")
            return
        self.log("[info] Building the logbook from files already on this device...")
        self._start_background(self._run_build_from_local_files, busy_button=self.rebuild_button)

    def on_publish(self, widget):
        self.log("[info] Publish tapped (not implemented yet)")

    def on_view(self, widget):
        # Toggles back to the log -- the logbook itself is already loaded in the WebView from
        # the tap that showed it, nothing to reload. Same behavior as MainActivity's own
        # viewLocalLogbook() early-return.
        if self.showing_local_logbook:
            self.showing_local_logbook = False
            self._show_log_content()
            return

        html_path = self.output_html_path()
        if not html_path.exists():
            self.log("[info] No logbook to show yet.")
            return
        try:
            html = html_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.log(f"[error] Could not read the logbook: {exc}")
            return
        # Same technique as MainActivity's own loadLogbookIntoWebView(): pass the HTML in as a
        # string with the file's own parent directory as the root/base URL (for any relative
        # resource references), rather than pointing the WebView straight at a file:// URL.
        self.web_view.set_content(f"file://{html_path.parent}/", html)
        self.showing_local_logbook = True
        self._show_logbook_content()

    def _show_log_content(self) -> None:
        self.content_area.clear()
        self.content_area.add(self.log_view)

    def _show_logbook_content(self) -> None:
        self.content_area.clear()
        self.content_area.add(self.web_view)

    def on_boat_mode(self, widget):
        self.log("[info] Boat mode tapped (not implemented yet)")

    def on_settings(self, widget):
        self.show_settings_screen()

    def show_settings_screen(self) -> None:
        # Rebuilt fresh every time Settings is opened -- always reflects whatever was last
        # saved, and avoids keeping a second, potentially-stale set of field widgets around
        # between visits (see settings_screen.py).
        self.main_window.content = SettingsScreen(self).content

    def show_main_screen(self) -> None:
        self.main_window.content = self.main_content

    def _start_background(self, target, *args, busy_button=None) -> None:
        self.sync_in_progress = True
        self.cancel_event.clear()
        self._busy_button = busy_button
        self._set_toolbar_enabled(False)
        if busy_button is not None:
            # Left enabled (excluded from the disable loop below) -- pulsing a *disabled* button
            # would fight Toga's own disabled-state dimming, and Android's own equivalent button
            # deliberately stays enabled too (tapping it again cancels instead -- not ported yet,
            # so this just re-logs "already running" for now, same as any other button tapped
            # mid-run, see on_download()/on_rebuild()'s own guards).
            _set_busy_pulse(busy_button, True)
        threading.Thread(target=self._run_and_finish, args=(target, args), daemon=True).start()

    def _run_and_finish(self, target, args) -> None:
        try:
            target(*args)
        finally:
            self.loop.call_soon_threadsafe(self._on_run_finished)

    def _on_run_finished(self) -> None:
        self.sync_in_progress = False
        self._set_toolbar_enabled(True)
        if self._busy_button is not None:
            _set_busy_pulse(self._busy_button, False)
            self._busy_button = None

    def _set_toolbar_enabled(self, enabled: bool) -> None:
        # settings_button and view_button are left out deliberately, matching MainActivity.kt:
        # Settings is its own screen, unaffected by a sync/build in progress; viewLocalLogbook()
        # "works even while a sync is running" (its own doc comment) since it only reads a file
        # already on disk, never touches SyncState. The button currently pulsing (self._busy_button,
        # see _start_background()) is left out too, same reasoning as Android's own busy button
        # staying enabled.
        for button in (
            self.download_button,
            self.rebuild_button,
            self.publish_button,
            self.boat_mode_button,
        ):
            if button is self._busy_button:
                continue
            button.enabled = enabled

    # Runs on the background thread started by _start_background() -- must not touch the UI
    # directly (see ProgressCallback's own doc comment and _log_result() below).
    def _run_build_from_local_files(self) -> None:
        callback = ProgressCallback(self, self.cancel_event)
        ebl_paths = [str(p) for p in sorted(self.ebl_dir().rglob("*.ebl"))]
        result = android_entry.build_from_local_files(
            ebl_paths,
            str(self.output_html_path()),
            str(self.sample_cache_path()),
            self.settings_store.boat_name,
            self.settings_store.mmsi,
            self.settings_store.call_sign,
            progress_callback=callback,
            min_stop_minutes=self.settings_store.min_stop_minutes,
        )
        self._log_result(result)

    # Runs on the background thread started by _start_background() -- see the comment above
    # _run_build_from_local_files().
    def _run_sync(self, subnet_prefix: str) -> None:
        callback = ProgressCallback(self, self.cancel_event)
        result = android_entry.sync_from_w2k2(
            self.settings_store.w2k2_user,
            self.settings_store.w2k2_password,
            subnet_prefix,
            str(self.ebl_dir()),
            str(self.output_html_path()),
            str(self.sample_cache_path()),
            self.settings_store.boat_name,
            self.settings_store.mmsi,
            self.settings_store.call_sign,
            progress_callback=callback,
            min_stop_minutes=self.settings_store.min_stop_minutes,
        )
        self._log_result(result)

    def _log_result(self, result: dict) -> None:
        def show():
            if result.get("ok"):
                self.log(f"[ok] Logbook ready ({result.get('trip_count')} trip(s)).")
            elif result.get("cancelled"):
                self.log("[info] Cancelled.")
            else:
                self.log(f"[error] {result.get('error')}")

        self.loop.call_soon_threadsafe(show)


def main():
    return MySailingLogbook()
