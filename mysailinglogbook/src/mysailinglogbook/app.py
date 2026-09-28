"""
My Sailing Logbook (iOS) -- mirrors the Android app's own MainActivity as closely as the
platform allows (asked for explicitly, see this repo's own README: "Design principle: match
the Android app exactly"). Toolbar order, button purpose, and overall layout (toolbar, log/
status area, logbook view) are the same; see the Android app's MainActivity.kt for the
reference behavior each of these will eventually need to match.
"""

import threading
from pathlib import Path

import toga
from rubicon.objc import Block, ObjCClass
from toga.style.pack import COLUMN, NONE, ROW, Pack

from nmea2log import android_entry
from nmea2log.upload import UploadError, normalize_rest_upload_url, upload_via_rest

from .boot_mode_controller import BootModeController
from .network import detect_subnet_prefix
from .settings_screen import SettingsScreen
from .settings_store import SettingsStore
from .translations import t

_UIApplication = ObjCClass("UIApplication")

# See MySailingLogbook._trim_log_if_needed()'s own doc comment for why this exists at all.
_MAX_LOG_LINES = 1000

_UIView = ObjCClass("UIView")
_UIColor = ObjCClass("UIColor")
# Standard UIKit UIViewAnimationOptions bit values (not exposed as named constants anywhere in
# toga_iOS -- these are stable, documented Apple values, safe to hardcode).
_UI_VIEW_ANIMATION_OPTION_REPEAT = 1 << 3
_UI_VIEW_ANIMATION_OPTION_AUTOREVERSE = 1 << 4
# UIImageRenderingMode.alwaysTemplate -- same reasoning as the animation options above.
_UI_IMAGE_RENDERING_MODE_ALWAYS_TEMPLATE = 2


def _template_tint_icon(button) -> None:
    """toga_iOS's own Button.set_icon() (toga_iOS/widgets/button.py) sets the icon image with
    UIKit's default rendering mode, which keeps every pixel exactly as rasterized -- solid black,
    same as Android's vector drawables before tinting. That's invisible against a dark toolbar
    background, found in practice testing "Apparaat volgen"/"Donker" (see apply_theme_mode()):
    the title text next to these buttons already adapts automatically (UIKit's own dynamic label
    color), but the icons didn't move at all.

    Re-applying the same image in "always template" mode instead makes UIKit ignore its own
    pixels and paint the shape using the button's tintColor -- set to UIColor.labelColor here, the
    same dynamic black-in-light/white-in-dark color the title text already uses, so both switch
    together.
    """
    native = button._impl.native
    templated = native.imageForState(0).imageWithRenderingMode(_UI_IMAGE_RENDERING_MODE_ALWAYS_TEMPLATE)
    native.setImage(templated, forState=0)
    native.tintColor = _UIColor.labelColor()


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


def _set_idle_timer_disabled(disabled: bool) -> None:
    """Keeps the screen from auto-locking while boat mode is on -- asked for explicitly: boat
    mode is foreground-only (see this repo's own README on why iOS has no equivalent to Android's
    foreground service), so the app being suspended when the screen locks would stop it just as
    surely as closing the app would. As long as the phone is left with the screen on (e.g. propped
    up at the helm) and the app isn't manually switched away from, this keeps it alive indefinitely
    despite that limitation.

    UIApplication.sharedApplication is a class-side singleton accessor, the same category as
    NSNotificationCenter.defaultCenter in settings_screen.py -- rubicon-objc resolved that one as
    an already-invoked property rather than a bound method (found in practice, the hard way: a
    trailing () there raised "not callable"). Tried as a property first here for the same reason,
    falling back to calling it if that guess is wrong for this particular selector, and giving up
    silently rather than crashing boat mode over what is, worst case, just a missed screen-lock
    prevention rather than a functional failure.
    """
    try:
        _UIApplication.sharedApplication.idleTimerDisabled = disabled
    except TypeError:
        try:
            _UIApplication.sharedApplication().idleTimerDisabled = disabled
        except Exception:
            pass


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
            self.app.log, "[info] " + t("log_downloading", current=current, total=total, file_name=file_name)
        )

    def isCancelled(self):
        return self.cancel_event.is_set()

    def onLogLine(self, line):
        self.app.loop.call_soon_threadsafe(self.app.log, line)

    def onDownloadComplete(self):
        pass

    def onBoatState(self, boat_state_json):
        pass  # only boat mode needs this; boat_mode_controller.py's own round path builds its
        # own BoatSnapshot straight from sync_from_w2k2()'s return dict instead of this callback

    def onResult(self, ok, error, cancelled, trip_count, html_path, downloaded_count):
        pass  # the pipeline functions' own return value already has everything we need


class MySailingLogbook(toga.App):
    def startup(self):
        # Created before any widget below -- apply_theme_mode() (called right before
        # main_window.show()) needs it already loaded, so the app's chosen Licht/Donker/Apparaat
        # appearance is applied on the very first frame instead of flashing the wrong one first.
        self.settings_store = SettingsStore(self.paths.data)
        self.boot_mode_controller = BootModeController(self)

        # Same order as Android's own toolbar (MainActivity.kt): download, build, publish,
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
        self.build_button = toga.Button(icon=toga.Icon("resources/refresh"), on_press=self.on_build)
        self.publish_button = toga.Button(icon=toga.Icon("resources/upload"), on_press=self.on_publish)
        self.view_button = toga.Button(icon=toga.Icon("resources/article"), on_press=self.on_view)
        self.boat_mode_button = toga.Button(icon=toga.Icon("resources/sailboat"), on_press=self.on_boat_mode)
        self.settings_button = toga.Button(icon=toga.Icon("resources/settings"), on_press=self.on_settings)
        for button in (
            self.download_button,
            self.build_button,
            self.publish_button,
            self.view_button,
            self.boat_mode_button,
            self.settings_button,
        ):
            _template_tint_icon(button)

        toolbar_spacer = toga.Box(style=Pack(flex=1))
        toolbar = toga.Box(
            children=[
                self.download_button,
                self.build_button,
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
        self.web_view = toga.WebView(style=Pack(flex=0, display="none"))
        self.showing_local_logbook = False
        # Both children stay in content_area permanently -- _show_log_content()/
        # _show_logbook_content() toggle which one is visible (display+visibility, same
        # mechanism settings_screen.py's own wordpress_box/sftp_box already use) rather than
        # content_area.clear()+add() swapping which widget is actually attached. Found in
        # practice, asked for explicitly to fix: removing log_view from its container and
        # re-adding it (every View tap) left its native UIScrollView's contentOffset reset to
        # the top and unresponsive to further scroll gestures the next time it came back --
        # toga_iOS's own container-attach path isn't built to be run more than once per widget.
        # flex is toggled too (1 when shown, 0 when hidden) -- display:none alone didn't free up
        # the space it would have taken in this COLUMN box's own flex distribution (found in
        # practice: the visible one only got half the screen, with a large blank gap where the
        # hidden-but-still-flex-1 other one was still being measured).
        self.content_area = toga.Box(children=[self.log_view, self.web_view], style=Pack(flex=1, direction=COLUMN))

        # toolbar + content_area -- the "main" screen this swaps back to from Settings (there's
        # no second toga.Window to switch to on iOS, see settings_screen.py's own doc comment on
        # why Settings swaps the single MainWindow's content in place instead; unlike Settings,
        # the View toggle only swaps content_area's own child, leaving the toolbar in place, to
        # match Android's own layout -- see the comment above).
        self.main_content = toga.Box(children=[toolbar, self.content_area], style=Pack(direction=COLUMN))

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_content
        self.apply_theme_mode()
        self.main_window.show()

        # Mirrors SyncState.inProgress/cancelled on Android (MainActivity.runSync()'s own
        # guard) -- only one sync/build runs at a time; tapping Download/Rebuild again while one
        # is running is ignored for now (Android instead turns the button that started the run
        # into its own cancel button -- not ported yet, see cancel_event below, which the
        # plumbing already supports).
        self.sync_in_progress = False
        self.cancel_event = threading.Event()
        self._busy_button = None

        # "Boot-modus starten bij openen" (Settings) -- mirrors MainActivity.kt's own
        # shouldAutoStartBootMode(), called from onCreate(). Found in practice: this setting
        # existed, got saved, and had no effect at all -- nothing here ever read it. No
        # "userStopped" tracking needed the way Android's own version has: this app's boat mode
        # is foreground-only with no persisted state at all (see boot_mode_controller.py's own
        # doc comment), so a fresh launch always starts with it off regardless of whether it was
        # manually stopped last time -- there's no "still running in the background, but the
        # owner turned it off" case here to distinguish, only "on this launch, should it start".
        if self._should_auto_start_boot_mode():
            self.boot_mode_controller.start()

    def _should_auto_start_boot_mode(self) -> bool:
        store = self.settings_store
        return (
            store.boot_auto_start
            and store.is_w2k2_config_complete
            and detect_subnet_prefix() is not None
        )

    def apply_theme_mode(self) -> None:
        """Applies settings_store.theme_mode to the app's own UI (main_window and everything in
        it, including the log view) -- called once at startup (before main_window.show(), see
        the comment there) and again the moment Settings is saved, so a change takes effect
        immediately rather than needing a relaunch.

        Can't reach the native Launch Screen.storyboard shown before this even runs -- that's a
        real platform limit, not an oversight (see settings_screen.py's own comment on this
        section): the storyboard is resolved by iOS itself before any Python code, let alone this
        method, has run. It still automatically follows the phone's own Appearance setting on its
        own via UIKit's usual dynamic-color resolution, same as it always has; "Licht"/"Donker"
        chosen here just doesn't retroactively change that one brief pre-launch frame.

        UIUserInterfaceStyle's raw values (Unspecified=0, Light=1, Dark=2) aren't exposed as named
        constants anywhere in toga_iOS or rubicon-objc -- stable, documented Apple values, same
        reasoning as _UI_VIEW_ANIMATION_OPTION_REPEAT/_AUTOREVERSE above for hardcoding them.
        """
        style = {"light": 1, "dark": 2}.get(self.settings_store.theme_mode, 0)
        self.main_window._impl.native.overrideUserInterfaceStyle = style

    def log(self, line: str) -> None:
        # Same "only follow along if already at the bottom" behavior as MainActivity's own
        # refreshLogView()/isLogScrolledToBottom(): checked *before* appending, so a user who
        # scrolled up to read an earlier line doesn't get yanked back down to the bottom the
        # moment the next line arrives. Toga's own MultilineTextInput has no cross-platform way
        # to query scroll position, so this reads the native UITextView directly (it's a
        # UIScrollView subclass) -- same contentOffset/contentSize/bounds properties toga_iOS's
        # own ScrollContainer backend already reads the same way.
        was_at_bottom = self._log_is_scrolled_to_bottom()
        self.log_view.value += line + "\n"
        self._trim_log_if_needed()
        if was_at_bottom:
            self.log_view.scroll_to_bottom()

    def _trim_log_if_needed(self) -> None:
        """Caps the in-app log view at _MAX_LOG_LINES, trimmed back down to it once past double
        that -- found in practice: an unbounded UITextView.text (Toga's own MultilineTextInput.
        value setter replaces the *whole* string on every append) turns sluggish, barely
        scrollable after a long session piles up thousands of decode-progress/retry lines. The
        full history is never lost -- it's already persisted to nmea2log.log on disk regardless
        of what this view shows (see android_entry.py's own set_log_file()); this only trims
        what's kept in memory/on screen. Checked with a hysteresis band (trim only once past
        double the cap, back down to the cap) rather than every single line, which would mean
        reconstructing this potentially-large string on every append instead of only rarely.
        """
        lines = self.log_view.value.split("\n")
        if len(lines) <= _MAX_LOG_LINES * 2:
            return
        self.log_view.value = "\n".join(lines[-_MAX_LOG_LINES:])

    def _log_is_scrolled_to_bottom(self) -> bool:
        native = self.log_view._impl.native
        # A few points of slack, same reasoning as Android's own 4dp: scroll position/content
        # height can be off by a rounding point or two even while visually "at the bottom".
        slack = 4
        return native.contentOffset.y + native.bounds.size.height >= native.contentSize.height - slack

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
        if self.boot_mode_controller.busy:
            self.log("[info] " + t("log_boat_busy"))
            return
        if self.sync_in_progress:
            self.log("[info] " + t("log_sync_already_running"))
            return
        if not self.settings_store.is_w2k2_config_complete:
            self.log("[info] " + t("log_fill_w2k2_credentials"))
            return
        subnet_prefix = detect_subnet_prefix()
        if subnet_prefix is None:
            self.log("[info] " + t("log_no_hotspot"))
            return
        self.log("[info] " + t("log_checking_for_w2k2", subnet=subnet_prefix))
        self._start_background(self._run_sync, subnet_prefix, busy_button=self.download_button)

    def on_build(self, widget):
        if self.boot_mode_controller.busy:
            self.log("[info] " + t("log_boat_busy"))
            return
        if self.sync_in_progress:
            self.log("[info] " + t("log_build_already_running"))
            return
        self.log("[info] " + t("log_building_from_local_files"))
        self._start_background(self._run_build_from_local_files, busy_button=self.build_button)

    def on_publish(self, widget):
        # Same sequence as MainActivity.kt's own runPublish()/buildFromLocalFilesAndMaybePublish():
        # always rebuilds fresh from local .ebl data first (not just "upload whatever HTML happens
        # to already be on disk"), then always publishes regardless of auto_publish_after_build --
        # an explicit tap of this button is itself the "yes, publish" instruction.
        if self.boot_mode_controller.busy:
            self.log("[info] " + t("log_boat_busy"))
            return
        if self.sync_in_progress:
            self.log("[info] " + t("log_publish_already_running"))
            return
        store = self.settings_store
        if not store.is_rest_upload_config_complete and not store.is_sftp_config_complete:
            self.log("[info] " + t("log_fill_publish_settings"))
            return
        self.log("[info] " + t("log_building_from_local_files"))
        self._start_background(self._run_build_and_publish, busy_button=self.publish_button)

    def _run_build_and_publish(self) -> None:
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
        if result.get("ok"):
            self._publish_logbook()
        self._log_result(result)

    def _publish_logbook(self) -> bool:
        """The actual upload step, run on the same background thread as the build above -- see
        LogbookPublisher.kt's own publish() for the Android original this mirrors (REST preferred
        over SFTP whenever both are configured, never falls back silently from one to the other).
        SFTP itself can't be ported here at all (see translations.py's own
        log_upload_sftp_not_supported_ios comment on why): every maintained Python SSH library
        needs the `cryptography` package's compiled C extension, which has no iOS build on PyPI,
        and cross-compiling OpenSSL/a Rust toolchain for iOS -- or bridging a native Swift SSH
        library in instead -- is real, separate work, not a quick port.

        Returns whether the upload actually happened and succeeded -- boot_mode_controller.py's
        own Publish action needs this (same bool LogbookPublisher.kt's own publish() returns) to
        report PublishFinished back to the state machine; "not configured" is reported as False
        the same as a real failure would be, matching Android's own publishFailed calculation in
        MainActivity.buildFromLocalFilesAndMaybePublish() (not configured at all is treated
        differently there, before ever calling this -- but from *this* function's own point of
        view, nothing was published either way).
        """
        store = self.settings_store
        use_rest = store.is_rest_upload_config_complete
        if use_rest:
            # Expanded here, not stored expanded -- see settings_screen.py's own comment on the
            # rest_url_field for why: the Settings field always shows exactly what was typed, and
            # only the actual upload (here) and this log line's own %s ever see the full URL.
            url = normalize_rest_upload_url(store.rest_upload_url)
            self.loop.call_soon_threadsafe(self.log, "[info] " + t("status_uploading_wordpress"))
            try:
                html_bytes = self.output_html_path().read_bytes()
                upload_via_rest(html_bytes, url, store.rest_upload_user, store.rest_upload_password)
            except (UploadError, OSError) as exc:
                self.loop.call_soon_threadsafe(
                    self.log, "[error] " + t("log_upload_failed_wordpress", error=str(exc))
                )
                return False
            self.loop.call_soon_threadsafe(
                self.log, "[ok] " + t("log_upload_ok_wordpress", url=url)
            )
            return True
        elif store.is_sftp_config_complete:
            self.loop.call_soon_threadsafe(self.log, "[error] " + t("log_upload_sftp_not_supported_ios"))
            return False
        else:
            self.loop.call_soon_threadsafe(self.log, "[skip] " + t("log_upload_not_configured"))
            return False

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
            self.log("[info] " + t("log_no_logbook_to_view"))
            return
        try:
            html = html_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.log("[error] " + t("log_logbook_display_failed", error=exc))
            return
        # Same technique as MainActivity's own loadLogbookIntoWebView(): pass the HTML in as a
        # string with the file's own parent directory as the root/base URL (for any relative
        # resource references), rather than pointing the WebView straight at a file:// URL.
        self.web_view.set_content(f"file://{html_path.parent}/", html)
        self.showing_local_logbook = True
        self._show_logbook_content()

    def _show_log_content(self) -> None:
        self.web_view.style.display = "none"
        self.web_view.style.visibility = "hidden"
        self.web_view.style.flex = 0
        self.web_view.style.height = 0
        self.log_view.style.display = "pack"
        self.log_view.style.visibility = "visible"
        self.log_view.style.flex = 1
        self.log_view.style.height = NONE

    def _show_logbook_content(self) -> None:
        self.log_view.style.display = "none"
        self.log_view.style.visibility = "hidden"
        self.log_view.style.flex = 0
        self.log_view.style.height = 0
        self.web_view.style.display = "pack"
        self.web_view.style.height = NONE
        self.web_view.style.visibility = "visible"
        self.web_view.style.flex = 1

    def on_boat_mode(self, widget):
        if self.boot_mode_controller.active:
            self.boot_mode_controller.stop()
        else:
            self.boot_mode_controller.start()

    def on_boot_mode_active_changed(self, active: bool) -> None:
        """Called by BootModeController whenever BootModeMachine's own phase crosses to/from OFF
        -- not just on a direct tap of the boat button, since e.g. stop_after_final can turn the
        mode off on its own after a final round, with nobody tapping anything (see
        boat_mode_controller.py's own BootModeController._handle()).

        Runs on the main thread already (every call into this either starts on the main thread --
        on_boat_mode() -- or comes back via loop.call_soon_threadsafe() further down the chain),
        so no thread-marshalling needed here.
        """
        self.boat_mode_button.icon = toga.Icon(
            "resources/sailboat_filled" if active else "resources/sailboat"
        )
        _template_tint_icon(self.boat_mode_button)
        _set_idle_timer_disabled(active)

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
            # mid-run, see on_download()/on_build()'s own guards).
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
            self.build_button,
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
        # Same "Automatisch publiceren na samenstellen" gate as MainActivity.kt's own
        # buildFromLocalFilesAndMaybePublish(forcePublish=false) -- found in practice: this was
        # missing entirely on iOS, so the setting existed in Settings and got saved, but tapping
        # Assemble never actually published regardless of it. Before _log_result(), not after --
        # same reasoning as _run_build_and_publish() above (a publish problem surfacing after the
        # logbook's already shown would read as a glitch).
        if result.get("ok") and self.settings_store.auto_publish_after_build:
            self._publish_logbook()
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
        # Same gate/ordering as _run_build_from_local_files() above -- also missing entirely
        # before this, matching MainActivity.kt's own runSync() gate on the same setting.
        if result.get("ok") and self.settings_store.auto_publish_after_build:
            self._publish_logbook()
        self._log_result(result)

    def _log_result(self, result: dict) -> None:
        def show():
            if result.get("ok"):
                self.log("[ok] " + t("log_logbook_ready", count=result.get("trip_count")))
            elif result.get("cancelled"):
                self.log("[info] " + t("log_cancelled"))
            else:
                self.log(f"[error] {result.get('error')}")

        self.loop.call_soon_threadsafe(show)


def main():
    return MySailingLogbook()
