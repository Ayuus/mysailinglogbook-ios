"""
My Sailing Logbook (iOS) -- mirrors the Android app's own MainActivity as closely as the
platform allows (asked for explicitly, see this repo's own README: "Design principle: match
the Android app exactly"). Toolbar order, button purpose, and overall layout (toolbar, log/
status area, logbook view) are the same; see the Android app's MainActivity.kt for the
reference behavior each of these will eventually need to match.
"""

import threading
import time
from pathlib import Path

import toga
from rubicon.objc import Block, CGPoint, NSObject, NSRange, ObjCClass, ObjCInstance, ObjCProtocol, objc_method
from toga.style.pack import COLUMN, NONE, ROW, Pack

from nmea2log import android_entry, app_constants, import_ebl, run_outcome
from nmea2log import log as nmea_log
from nmea2log.upload import UploadError, normalize_rest_upload_url, upload_via_rest

from .boot_mode_controller import BootModeController
from .network import detect_subnet_prefix
from .settings_screen import SettingsScreen
from .settings_store import SettingsStore
from .translations import t

_UIApplication = ObjCClass("UIApplication")

# Only a guard against a service running for days: the log view appends lines to its text (see
# MySailingLogbook.log()) instead of rebuilding it, so a long log costs memory, not time. When more than
# _MAX_LOG_LINES are kept, the oldest are dropped down to _LOG_TRIM_TO; nmea2log.log has everything.
_MAX_LOG_LINES = app_constants.LOG_MAX_LINES
_LOG_TRIM_TO = app_constants.LOG_TRIM_TO

# How many characters at the end of the log are laid out when scrolling to the end (see _lay_out_log()).
_LOG_TAIL_LAYOUT_CHARS = 4000

# How long log lines are collected before the log view is updated once -- see MySailingLogbook.log().
_LOG_FLUSH_INTERVAL_S = app_constants.LOG_REFRESH_INTERVAL_MS / 1000

# MainActivity.kt's own collapsed log height after a run (150dp), see _show_logbook_with_log_strip().
_LOG_STRIP_HEIGHT = app_constants.LOG_STRIP_HEIGHT

_UIView = ObjCClass("UIView")
_UIFont = ObjCClass("UIFont")
_NSAttributedString = ObjCClass("NSAttributedString")
_NSMutableAttributedString = ObjCClass("NSMutableAttributedString")
_UIColor = ObjCClass("UIColor")
# Standard UIKit UIViewAnimationOptions bit values (not exposed as named constants anywhere in
# toga_iOS -- these are stable, documented Apple values, safe to hardcode).
_UI_VIEW_ANIMATION_OPTION_REPEAT = 1 << 3
_UI_VIEW_ANIMATION_OPTION_AUTOREVERSE = 1 << 4
# UIImageRenderingMode.alwaysTemplate -- same reasoning as the animation options above.
_UI_IMAGE_RENDERING_MODE_ALWAYS_TEMPLATE = 2

_UIDocumentPickerViewController = ObjCClass("UIDocumentPickerViewController")
_UTType = ObjCClass("UTType")
_UIDocumentPickerDelegate = ObjCProtocol("UIDocumentPickerDelegate")

class _ImportDocumentPickerDelegate(NSObject, protocols=[_UIDocumentPickerDelegate]):
    """UIDocumentPickerViewController's own delegate, defined here via rubicon-objc's custom-
    Objective-C-class support -- Toga has no folder picker on iOS of its own (toga_iOS.dialogs'
    SelectFolderDialog/OpenFileDialog are both not_implemented() stubs, checked directly), so this
    talks to UIKit the same way idle-timer/UIFileSharingEnabled already do elsewhere in this file:
    directly, not a workaround.

    app_ref is set by on_import() right after alloc().init(), the only place to stash a reference
    back to the running MySailingLogbook instance -- an instance of this class is otherwise
    indistinguishable from any other bare NSObject to Python. Held as self._import_picker_delegate
    on the app too, for the same reason UIKit delegates are conventionally kept alive by their
    owner: UIDocumentPickerViewController's own delegate property does not retain it."""

    @objc_method
    def documentPicker_didPickDocumentsAtURLs_(self, controller, urls) -> None:
        url = ObjCInstance(urls).objectAtIndex(0)
        self.app_ref.on_folder_picked(url)

    @objc_method
    def documentPickerWasCancelled_(self, controller) -> None:
        pass


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


def _hex_color(value: str):
    """A UIColor from a "#RRGGBB" string."""
    red, green, blue = (int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))
    return _UIColor.colorWithRed(red, green=green, blue=blue, alpha=1.0)


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
        # Only the progress bar, no log line per file: a first full download is thousands of files
        # (MainActivity.kt's own report() leaves them out for the same reason).
        self.app.loop.call_soon_threadsafe(self.app.update_progress_bar, t("phase_downloading"), current, total)

    def isCancelled(self):
        return self.cancel_event.is_set()

    def onLogLine(self, line):
        self.app.loop.call_soon_threadsafe(self.app.log, line)

    def onProgress(self, phase, current, total):
        """Decoding and building the trips have no per-file callback of their own: nmea2log recognises their
        log lines (progress.py, shared with the Android app) and reports (phase, current, total) here."""
        label = {"decoding": "phase_decoding", "building_trips": "phase_building_trips"}.get(phase)
        if label is not None:
            self.app.loop.call_soon_threadsafe(self.app.update_progress_bar, t(label), current, total)

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
        # A second way to get .ebl files onto the device besides download_button's own W2K-2
        # download (matching Android's own importButton, see MainActivity.kt): picks a folder via
        # UIDocumentPickerViewController (see _ImportDocumentPickerDelegate above), copies whatever
        # .ebl files it finds anywhere in there into this app's own ebl_dir(), then builds/
        # publishes exactly like a normal download would. Placed right next to download_button
        # (asked for explicitly, same reasoning as Android's own placement): this is a download
        # too in the end, just from a folder instead of the W2K-2.
        self.import_button = toga.Button(icon=toga.Icon("resources/folder_download"), on_press=self.on_import)
        self.build_button = toga.Button(icon=toga.Icon("resources/refresh"), on_press=self.on_build)
        self.publish_button = toga.Button(icon=toga.Icon("resources/upload"), on_press=self.on_publish)
        self.view_button = toga.Button(icon=toga.Icon("resources/article"), on_press=self.on_view)
        self.boat_mode_button = toga.Button(icon=toga.Icon("resources/sailboat"), on_press=self.on_boat_mode)
        self.settings_button = toga.Button(icon=toga.Icon("resources/settings"), on_press=self.on_settings)
        for button in (
            self.download_button,
            self.import_button,
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
                self.import_button,
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
        # toga's WebView reports a minimum height of 100 even while hidden (display none, height 0 and
        # flex 0 included), which kept 100pt of the screen reserved under the log -- found in practice:
        # a blank band below the last log line, with the log only 600pt tall on a 700pt area. Shown, it
        # takes all remaining space (flex 1), so its minimum never mattered.
        self.web_view._MIN_HEIGHT = 0
        self.showing_local_logbook = False
        # True while the logbook shows as a run's result with the log still visible as a strip
        # next to it (see _show_logbook_with_log_strip()) -- MainActivity.kt's own
        # logbookShownAsRunResult. on_build() reads it.
        self.logbook_shown_as_run_result = False
        # The log's lines live here, not only in the UITextView: log() appends to this list and a
        # short timer pushes it to the view once (see log()/_flush_log()).
        self._log_lines = []
        # How many of _log_lines are in the view's text already, and whether the text has to be rebuilt
        # from scratch (lines were dropped from the front) instead of only appended to.
        self._log_shown = 0
        self._log_rebuild = False
        self._log_flush_scheduled = False
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

        # Bottom progress bar + "phase: x/y" label -- mirrors MainActivity.kt's own progressBar/
        # progressLabel exactly (same 5 phases, same wording, see update_progress_bar()'s own doc
        # comment below), asked for explicitly ("zoveel mogelijk identiek aan android"). Hidden
        # (style.visibility) rather than shown at 0/0 until the first real update_progress_bar()
        # call, same as Android's own View.GONE default. progress_bar's own margin is set
        # dynamically in update_progress_bar() -- toga_iOS's MainWindow (see window.py's own
        # content_native_layout()) only ever insets its content from the *top* (status bar/
        # navigation bar height); nothing insets it from the bottom, so a fixed guess here either
        # clips under the home indicator (portrait) or leaves an oversized gap (landscape, where
        # the same point value reads much bigger against a shorter screen) -- found in practice,
        # both ways, testing this on the simulator.
        self.progress_label = toga.Label(
            "", style=Pack(display="none", visibility="hidden", height=0)
        )
        self.progress_bar = toga.ProgressBar(
            max=1, value=0, style=Pack(display="none", visibility="hidden", height=0)
        )

        # toolbar + content_area + progress bar -- the "main" screen this swaps back to from
        # Settings (there's no second toga.Window to switch to on iOS, see settings_screen.py's
        # own doc comment on why Settings swaps the single MainWindow's content in place instead;
        # unlike Settings, the View toggle only swaps content_area's own child, leaving the
        # toolbar in place, to match Android's own layout -- see the comment above).
        self.main_content = toga.Box(
            children=[toolbar, self.content_area, self.progress_label, self.progress_bar],
            style=Pack(direction=COLUMN),
        )

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.main_content
        self.apply_theme_mode()
        self.main_window.show()

        # Mirrors SyncState.inProgress/cancelled on Android (MainActivity.runSync()'s own
        # guard) -- only one sync/build runs at a time; tapping the button that started the run
        # again cancels it (_cancel_if_running()).
        self.sync_in_progress = False
        self.cancel_event = threading.Event()
        self._busy_button = None
        self._run_initiator = "build"
        self.update_publish_button_enabled()

        # "Boot-modus starten bij openen" (Settings) -- mirrors MainActivity.kt's own
        # shouldAutoStartBootMode(), called from onCreate(). Found in practice: this setting
        # existed, got saved, and had no effect at all -- nothing here ever read it. No
        # "userStopped" tracking needed the way Android's own version has: this app's boat mode
        # is foreground-only with no persisted state at all (see boot_mode_controller.py's own
        # doc comment), so a fresh launch always starts with it off regardless of whether it was
        # manually stopped last time -- there's no "still running in the background, but the
        # owner turned it off" case here to distinguish, only "on this launch, should it start".
        # Only one of these two auto-behaviors ever fires on a given launch, same as
        # MainActivity.kt's own onCreate() branching -- boat mode's own round starts by
        # downloading itself, so a plain download on top of that would just be redundant.
        if self._should_auto_start_boot_mode():
            self.boot_mode_controller.start()
        elif self.settings_store.auto_sync_on_launch:
            self._auto_sync_on_launch()
        else:
            # Same fallback as MainActivity.kt's own onCreate() (the "else" branch of its own
            # settingsStore.autoSyncOnLaunch check) -- shows whatever's already on the phone
            # right away instead of leaving the log's own placeholder text sitting there doing
            # nothing until the owner taps something themselves.
            self.on_view(None)

    def _should_auto_start_boot_mode(self) -> bool:
        store = self.settings_store
        return (
            store.boot_auto_start
            and store.is_w2k2_config_complete
            and detect_subnet_prefix() is not None
        )

    def _auto_sync_on_launch(self) -> None:
        """"Automatisch downloaden bij starten" (Settings) -- mirrors MainActivity.kt's own
        autoStartSyncWithSettingsRetry(), minus its own retry-for-settings-not-loaded-yet loop:
        that loop exists because Android's SharedPreferences-backed SettingsStore can still be
        loading asynchronously a few hundred ms after onCreate() starts, but this app's own
        SettingsStore reads its JSON file synchronously in startup() (see its own call, above,
        near the very top of this method), fully loaded well before this ever runs -- nothing to
        retry waiting for here.

        Found in practice: this setting existed, got saved, and had no effect at all -- nothing
        here ever read it either, the same dead-setting gap _should_auto_start_boot_mode() had.
        """
        store = self.settings_store
        if not store.is_w2k2_config_complete:
            # Just calls on_download() rather than duplicating its own is_w2k2_config_complete
            # check and log_fill_w2k2_credentials line here too (asked for explicitly, matching
            # MainActivity.kt's own equivalent simplification: "1x is toch genoeg?") --
            # on_download() already starts with the exact same check and produces the exact same
            # message for a manual tap on the download button, so this is the single source of
            # truth for what to show when settings are incomplete, reached either way. No
            # existing-logbook fallback either way (asked for explicitly, "logboek alleen tonen
            # als auto download uit staat") -- that fallback belongs solely to startup()'s own
            # else branch (self.on_view(None), unconditional) for when auto-download is off.
            self.on_download(None)
            return
        subnet_prefix = detect_subnet_prefix()
        if subnet_prefix is None:
            # Same calm, no-popup treatment as MainActivity.kt's own equivalent branch (a real
            # Android notification there too, which this app has no equivalent mechanism for at
            # all -- boat mode's own status lines are all just in-app log() calls, nothing this
            # reuses for a background system notification). No existing-logbook fallback here
            # either, same reasoning as the branch above.
            self.log("[info] " + t("log_hotspot_precheck_skipped"))
            return
        self.log("[info] " + t("status_listing_files", subnet=subnet_prefix))
        self._start_background(self._run_download, subnet_prefix, busy_button=self.download_button)

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
        """Adds a line to the log. The view itself is only updated by _flush_log(), at most every
        _LOG_FLUSH_INTERVAL_S, and then only the lines gained since the last flush are appended to the
        text: found in practice (an import of 2326 files, one line each, then the decode progress after
        it), setting the whole UITextView text on every line kept the main thread so busy the log could
        not be scrolled at all. The full history stays available (up to _MAX_LOG_LINES) and is also in
        nmea2log.log on disk (see android_entry.py's set_log_file())."""
        # A line the app made itself has no timestamp yet (Python's have): give it one like the rest and
        # put it in nmea2log.log too, as the Android app does (AppLog) -- the log and the file then tell
        # the same story.
        stamped = nmea_log.stamp_line(line)
        if stamped != line:
            self._append_to_log_file(stamped)
        self._log_lines.append(stamped)
        if len(self._log_lines) > _MAX_LOG_LINES:
            del self._log_lines[:-_LOG_TRIM_TO]
            self._log_shown = 0
            self._log_rebuild = True
        if not self._log_flush_scheduled:
            self._log_flush_scheduled = True
            self.loop.call_later(_LOG_FLUSH_INTERVAL_S, self._flush_log)

    def _append_to_log_file(self, stamped_line: str) -> None:
        """A line made by the app itself, added to nmea2log.log; failing is never worth breaking the app."""
        try:
            with open(self.paths.data / app_constants.LOG_FILE_NAME, "a", encoding="utf-8") as log_file:
                log_file.write(stamped_line + "\n")
        except OSError:
            pass

    def _attributed_log_text(self, lines):
        """The lines as attributed text: errors in red and warnings in yellow, both bold, like the Android
        log (app_constants decides which lines are which, and the colours)."""
        native = self.log_view._impl.native
        # textColor is nil until something sets it: then the text is drawn in the system label colour.
        font, color = native.font, native.textColor or _UIColor.labelColor()
        bold = _UIFont.fontWithDescriptor(font.fontDescriptor.fontDescriptorWithSymbolicTraits(2), size=font.pointSize)
        error_color = _hex_color(app_constants.LOG_ERROR_COLOR)
        warning_color = _hex_color(app_constants.LOG_WARNING_COLOR)
        text = _NSMutableAttributedString.alloc().init()
        for line in lines:
            kind = app_constants.classify_line(line)
            if kind == "error":
                attributes = {"NSFont": bold, "NSColor": error_color}
            elif kind == "warning":
                attributes = {"NSFont": bold, "NSColor": warning_color}
            else:
                attributes = {"NSFont": font, "NSColor": color}
            text.appendAttributedString(_NSAttributedString.alloc().initWithString(line + "\n", attributes=attributes))
        return text

    def _flush_log(self) -> None:
        # Same "only follow along if already at the bottom" behavior as MainActivity's own
        # refreshLogView()/isLogScrolledToBottom(): checked *before* the text changes, so a user
        # who scrolled up to read an earlier line doesn't get yanked back down the moment the next
        # line arrives (and keeps their position instead of the view jumping to the top).
        self._log_flush_scheduled = False
        native = self.log_view._impl.native
        was_at_bottom = self._log_is_scrolled_to_bottom()
        offset = native.contentOffset
        storage = native.textStorage
        if self._log_rebuild or self._log_shown == 0 or storage.length() == 0:
            # The first lines, or after lines were dropped from the front.
            native.attributedText = self._attributed_log_text(self._log_lines)
            self._log_rebuild = False
        elif self._log_shown < len(self._log_lines):
            # Appended to the existing text.
            storage.appendAttributedString(self._attributed_log_text(self._log_lines[self._log_shown:]))
        self._log_shown = len(self._log_lines)
        if was_at_bottom:
            self._scroll_log_to_bottom()
        else:
            native.contentOffset = offset
        # The scroll indicator fades after a moment, and it is the handle that can be touched and dragged to
        # get to the first line of a long log at once (Android's fast-scroll handle): keep it showing
        # while the log is growing.
        native.flashScrollIndicators()

    def _lay_out_log(self) -> None:
        """UIKit lays a UITextView's text out lazily, so right after the text changes its contentSize
        is still the old one -- which is what made both the was-at-bottom check and the scroll to the
        end come out wrong. Forces the layout of the end of the text now: only that, not the whole log,
        so it costs the same however long the log is."""
        native = self.log_view._impl.native
        length = native.textStorage.length()
        start = max(length - _LOG_TAIL_LAYOUT_CHARS, 0)
        native.layoutManager.ensureLayoutForCharacterRange(NSRange(start, length - start))
        native.layoutIfNeeded()

    def _scroll_log_to_bottom(self) -> None:
        native = self.log_view._impl.native
        self._lay_out_log()
        end = native.contentSize.height - native.bounds.size.height + native.adjustedContentInset.bottom
        native.contentOffset = CGPoint(0, max(end, 0))

    def _scroll_log_to_bottom_soon(self) -> None:
        """For when the log view is about to change size (shown again, or shrunk to a strip): once now
        and once more after UIKit has applied the new frame."""
        self._scroll_log_to_bottom()
        self.loop.call_later(0.2, self._scroll_log_to_bottom)
        self.log_view._impl.native.flashScrollIndicators()

    def _log_is_scrolled_to_bottom(self) -> bool:
        native = self.log_view._impl.native
        # A few points of slack, same reasoning as Android's own 4dp: scroll position/content
        # height can be off by a rounding point or two even while visually "at the bottom".
        slack = 4
        end = native.contentSize.height + native.adjustedContentInset.bottom
        return native.contentOffset.y + native.bounds.size.height >= end - slack

    def ebl_dir(self) -> Path:
        """Where downloaded/local .ebl files live -- same folder name as Android's own
        EblStorage.downloadDir() ("Actisense"), under the iOS app's Documents directory
        (self.paths.data, see toga_iOS's own Paths.get_data_path()) so the files are reachable
        from the Files app / Finder over USB, the iOS equivalent of Android's own
        getExternalFilesDir() being USB-browsable."""
        directory = self.paths.data / app_constants.EBL_DIR_NAME
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def output_html_path(self) -> Path:
        return self.paths.data / app_constants.LOGBOOK_FILE_NAME

    def sample_cache_path(self) -> Path:
        return self.paths.data / app_constants.SAMPLE_CACHE_FILE_NAME

    def on_download(self, widget):
        if self._cancel_if_running(self.download_button):
            return
        # Every early return below switches away from a currently-shown logbook first, same as
        # _start_background()'s own matching reset for the success path just below (asked for
        # explicitly, matching MainActivity.kt's own runSync()/runPublish() fix, "check ook bij
        # andere knoppen of dit goed gaat in alle gevallen"): self.log() always appends to the log
        # view's own text regardless of whether it's actually the visible layout right now, so
        # without this each message was added but invisible behind a still-showing logbook,
        # reading as if the button had done nothing at all.
        if self.boot_mode_controller.busy:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_boat_busy"))
            return
        if self.sync_in_progress:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_sync_already_running"))
            return
        if not self.settings_store.is_w2k2_config_complete:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_fill_w2k2_credentials"))
            return
        subnet_prefix = detect_subnet_prefix()
        if subnet_prefix is None:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("status_hotspot_off"))
            return
        self.log("[info] " + t("status_listing_files", subnet=subnet_prefix))
        self._start_background(self._run_download, subnet_prefix, busy_button=self.download_button)

    def on_import(self, widget):
        if self.boot_mode_controller.busy:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_boat_busy"))
            return
        if self.sync_in_progress:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_import_already_running"))
            return
        # Switches away from a currently-shown logbook right away, on the tap itself (asked for
        # explicitly, matching MainActivity.kt's own importButton onClick -- see its own comment):
        # the picker sheet can sit there a while before the owner actually picks anything, and the
        # log is where every outcome below shows up, including "picked nothing" (cancelled).
        self.showing_local_logbook = False
        self._show_log_content()
        folder_type = _UTType.typeWithIdentifier("public.folder")
        picker = _UIDocumentPickerViewController.alloc().initForOpeningContentTypes([folder_type])
        # Held on self, not just a local -- UIDocumentPickerViewController's own delegate property
        # does not retain it (see _ImportDocumentPickerDelegate's own doc comment); without this,
        # nothing else keeps the delegate alive until the picker actually calls back.
        self._import_picker_delegate = _ImportDocumentPickerDelegate.alloc().init()
        self._import_picker_delegate.app_ref = self
        picker.delegate = self._import_picker_delegate
        toga.App.app.current_window._impl.native.rootViewController.presentViewController(
            picker, animated=True, completion=None
        )

    def on_folder_picked(self, url) -> None:
        """_ImportDocumentPickerDelegate's own callback once a folder is picked -- always runs on
        the main thread (UIKit delegate callbacks do), so _start_background() itself is safe to
        call directly from here, same as any toolbar button's on_press."""
        self._start_background(self._run_import, url, busy_button=self.import_button)

    def on_build(self, widget):
        if self._cancel_if_running(self.build_button):
            return
        if self.logbook_shown_as_run_result:
            # Asked for explicitly (Android's buildButton does the same): with a run's own result
            # showing next to a strip of the log, this tap only brings the log back -- a run takes
            # minutes, and tapping here to read the log must not also start one. The next tap,
            # with the log already showing, assembles.
            self.showing_local_logbook = False
            self._show_log_content()
            return
        if self.boot_mode_controller.busy:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_boat_busy"))
            return
        if self.sync_in_progress:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_build_already_running"))
            return
        self.log("[info] " + t("status_building_with_existing_data"))
        self._start_background(self._run_build_from_local_files, busy_button=self.build_button)

    def on_publish(self, widget):
        if self._cancel_if_running(self.publish_button):
            return
        # Same sequence as MainActivity.kt's own runPublish()/buildFromLocalFilesAndMaybePublish():
        # always rebuilds fresh from local .ebl data first (not just "upload whatever HTML happens
        # to already be on disk"), then always publishes regardless of auto_publish_after_build --
        # an explicit tap of this button is itself the "yes, publish" instruction.
        if self.boot_mode_controller.busy:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_boat_busy"))
            return
        if self.sync_in_progress:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_publish_already_running"))
            return
        store = self.settings_store
        if not store.is_rest_upload_config_complete and not store.is_sftp_config_complete:
            self.showing_local_logbook = False
            self._show_log_content()
            self.log("[info] " + t("log_fill_publish_settings"))
            return
        self.log("[info] " + t("status_building_with_existing_data"))
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
        publish_failed = False
        if result.get("ok"):
            publish_failed = self._publish_attempt_failed()
        self._log_result(result, "publish", publish_failed)

    def _publish_attempt_failed(self) -> bool:
        """Runs the publish step after a build and says whether it failed (run_outcome.publish_failed():
        nothing set up to publish to is not a failure, only an upload that was attempted and failed)."""
        published = self._publish_logbook()
        store = self.settings_store
        return run_outcome.publish_failed(
            published, store.is_rest_upload_config_complete, store.is_sftp_config_complete
        )

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

        if not self.output_html_path().exists():
            self.log("[info] " + t("log_no_logbook_to_view"))
            return
        if not self._load_logbook_into_web_view():
            return
        self.showing_local_logbook = True
        self._show_logbook_content()

    def _load_logbook_into_web_view(self) -> bool:
        """MainActivity's own loadLogbookIntoWebView(): puts the current logbook.html into the WebView.
        False (after logging why) when it could not be read."""
        html_path = self.output_html_path()
        try:
            html = html_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.log("[error] " + t("error_logbook_display_failed", error=exc))
            return False
        # Same technique as MainActivity's own loadLogbookIntoWebView(): pass the HTML in as a
        # string with the file's own parent directory as the root/base URL (for any relative
        # resource references), rather than pointing the WebView straight at a file:// URL.
        self.web_view.set_content(f"file://{html_path.parent}/", html)
        return True

    def _show_log_content(self) -> None:
        self.logbook_shown_as_run_result = False
        self.loop.call_soon(self._scroll_log_to_bottom_soon)
        self.web_view.style.display = "none"
        self.web_view.style.visibility = "hidden"
        self.web_view.style.flex = 0
        self.web_view.style.height = 0
        self.log_view.style.display = "pack"
        self.log_view.style.visibility = "visible"
        self.log_view.style.flex = 1
        self.log_view.style.height = NONE

    def _show_logbook_content(self) -> None:
        self.logbook_shown_as_run_result = False
        self.log_view.style.display = "none"
        self.log_view.style.visibility = "hidden"
        self.log_view.style.flex = 0
        self.log_view.style.height = 0
        self.web_view.style.display = "pack"
        self.web_view.style.height = NONE
        self.web_view.style.visibility = "visible"
        self.web_view.style.flex = 1

    def _show_logbook_with_log_strip(self) -> None:
        """The logbook with a small strip of the log kept above it -- MainActivity.kt's own
        setLogExpanded(false) after a run (log first, 150dp tall, the WebView taking the rest).
        Shown instead of covering the log completely, so a finished run's last lines stay
        readable without a tap; _show_log_content() brings the whole log back."""
        self.web_view.style.display = "pack"
        self.web_view.style.height = NONE
        self.web_view.style.visibility = "visible"
        self.web_view.style.flex = 1
        self.log_view.style.display = "pack"
        self.log_view.style.visibility = "visible"
        self.log_view.style.flex = 0
        self.log_view.style.height = _LOG_STRIP_HEIGHT
        self._scroll_log_to_bottom_soon()
        self.logbook_shown_as_run_result = True

    def update_progress_bar(self, phase: str, current: int, total: int) -> None:
        """Bottom progress bar + "phase: x/y" label -- mirrors MainActivity.kt's own
        updateProgressBar() exactly (asked for explicitly, "zoveel mogelijk identiek aan
        android"): fed from ProgressCallback.report() (download), ProgressCallback.onLogLine()'s
        regex matches (decode, build-trips), and the report_progress closure inside _run_import()
        (importing). Hidden
        rather than shown at 0/0 for a total <= 0 (nothing meaningful to show yet), same as
        Android's own View.GONE default.

        Always called via self.loop.call_soon_threadsafe() by every one of those callers except
        report_progress-during-copying which itself is only ever invoked on the main thread
        (same reasoning as report() elsewhere in this file) -- never call this directly from a
        background thread.
        """
        if total <= 0 or self.cancel_event.is_set():
            # Nothing to show yet, or the run was cancelled and its last updates must not bring the
            # bar back.
            self.hide_progress_bar()
            return
        self.progress_label.style.display = "pack"
        self.progress_label.style.visibility = "visible"
        self.progress_label.style.height = NONE
        self.progress_bar.style.display = "pack"
        self.progress_bar.style.visibility = "visible"
        self.progress_bar.style.height = NONE
        # Re-read every call, not just once -- cheap, and the same rotation that changes the
        # home indicator's on-screen footprint can happen at any point while a run is in progress.
        self.progress_label.style.margin = (4, 8, 0, 8)
        self.progress_bar.style.margin = (2, 8, self._bottom_safe_area_margin(), 8)
        self.progress_bar.max = total
        self.progress_bar.value = current
        self.progress_label.text = t("progress_label_format", phase=phase, current=current, total=total)

    def _bottom_safe_area_margin(self) -> int:
        """The real height of the home indicator's own gesture area (0 on an iPad or an older
        Home-button iPhone) -- read live from the view hierarchy, plus a small fixed gutter, so
        the bar clears it exactly regardless of device or orientation. toga_iOS's own MainWindow
        (see window.py's content_native_layout()) only ever insets its content from the *top*
        (status bar/navigation bar height); nothing insets the bottom, unlike MainActivity.kt's
        own onApplyWindowInsetsListener, which pads all four sides from the real system-bar
        insets -- this is that same idea, ported by hand since toga_iOS has no equivalent of its
        own. Falls back to a plain fixed gutter if the native view isn't reachable for any reason
        (matches _set_idle_timer_disabled()'s own defensive style above)."""
        try:
            inset = float(self.main_window._impl.container.native.safeAreaInsets.bottom)
        except Exception:
            inset = 0.0
        return int(round(inset)) + 4

    def hide_progress_bar(self) -> None:
        # No margins while hidden either: display none keeps a widget's margins in the layout.
        self.progress_label.style.margin = 0
        self.progress_bar.style.margin = 0
        self.progress_label.style.display = "none"
        self.progress_label.style.visibility = "hidden"
        self.progress_label.style.height = 0
        self.progress_bar.style.display = "none"
        self.progress_bar.style.visibility = "hidden"
        self.progress_bar.style.height = 0

    def on_boat_mode(self, widget):
        # The mode reports through the log, so bring it back over the logbook -- like a download or
        # an assemble does when it starts (MainActivity.toggleBootMode() does the same); otherwise
        # its lines land in a log nobody can see.
        self.showing_local_logbook = False
        self._show_log_content()
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
        self.update_publish_button_enabled()

    def _start_background(self, target, *args, busy_button=None) -> None:
        self.sync_in_progress = True
        self.cancel_event.clear()
        self._busy_button = busy_button
        self._run_initiator = "download" if busy_button is self.download_button else "build"
        self._set_toolbar_enabled(False)
        # Same reset as MainActivity.kt's own buildFromLocalFilesAndMaybePublish()/runSync()
        # (showingLocalLogbook = false at the start of every run) -- found in practice, missing
        # here before this: starting a new download/assemble/publish while the previous run's
        # logbook was still on screen left it there with no visible sign anything was
        # happening, so a second run looked like it silently did nothing until you manually
        # switched back to the log yourself.
        if self.showing_local_logbook:
            self.showing_local_logbook = False
            self._show_log_content()
        if busy_button is not None:
            # Left enabled (excluded from the disable loop below) -- pulsing a *disabled* button
            # would fight Toga's own disabled-state dimming, and Android's own equivalent button
            # deliberately stays enabled too (tapping it again cancels, see _cancel_if_running()).
            _set_busy_pulse(busy_button, True)
        threading.Thread(target=self._run_and_finish, args=(target, args), daemon=True).start()

    def _cancel_if_running(self, button) -> bool:
        """Tapping the button that started the running download / assemble / publish cancels it, as on
        Android (MainActivity.cancelSyncStayInApp()): the button is the one pulsing, and stays enabled
        for this. True when the tap was a cancel and nothing else is to be done."""
        if not (self.sync_in_progress and self._busy_button is button):
            return False
        self.cancel_event.set()
        text = t("status_sync_cancelled" if self._run_initiator == "download" else "status_build_cancelled")
        self.log("[info] " + text)
        self.hide_progress_bar()
        # The run only notices the flag between steps (before each file, or when a long trip-cache load
        # ends), so say so if it takes a while: nothing else would appear in the log until it stops.
        self.loop.call_later(3, self._log_still_stopping)
        return True

    def _log_still_stopping(self) -> None:
        if self.sync_in_progress and self.cancel_event.is_set():
            self.log("[info] " + t("status_cancel_still_stopping"))

    def _run_and_finish(self, target, args) -> None:
        try:
            target(*args)
        except Exception as e:
            # Whatever the run did not catch itself: said in the log instead of the run ending silently
            # (MainActivity.runDownload() catches the same way).
            self.loop.call_soon_threadsafe(self.log, "[error] " + t("error_unexpected", detail=str(e)))
        finally:
            self.loop.call_soon_threadsafe(self._on_run_finished)

    def _on_run_finished(self) -> None:
        self.sync_in_progress = False
        self._set_toolbar_enabled(True)
        self.hide_progress_bar()
        if self._busy_button is not None:
            _set_busy_pulse(self._busy_button, False)
            self._busy_button = None

    def _publish_configured(self) -> bool:
        store = self.settings_store
        return store.is_rest_upload_config_complete or store.is_sftp_config_complete

    def update_publish_button_enabled(self) -> None:
        """Publish is only usable once WordPress or SFTP is filled in (MainActivity.updatePublishButtonEnabled()):
        called at start and when Settings was saved. The log says so once, when the button has just become
        unusable, instead of the button silently looking broken."""
        configured = self._publish_configured()
        was_enabled = self.publish_button.enabled
        if not self.sync_in_progress:
            self.publish_button.enabled = configured
            if not configured and was_enabled:
                self.log("[info] " + t("log_publish_not_configured"))

    def _set_toolbar_enabled(self, enabled: bool) -> None:
        # settings_button and view_button are left out deliberately, matching MainActivity.kt:
        # Settings is its own screen, unaffected by a sync/build in progress; viewLocalLogbook()
        # "works even while a sync is running" (its own doc comment) since it only reads a file
        # already on disk, never touches SyncState. The button currently pulsing (self._busy_button,
        # see _start_background()) is left out too, same reasoning as Android's own busy button
        # staying enabled.
        for button in (
            self.download_button,
            self.import_button,
            self.build_button,
            self.publish_button,
            self.boat_mode_button,
        ):
            if button is self._busy_button:
                continue
            # Publish only makes sense once a destination is filled in (MainActivity's
            # updatePublishButtonEnabled()); Assemble covers building without one.
            button.enabled = enabled and (button is not self.publish_button or self._publish_configured())

    # Runs on the background thread started by _start_background() -- see the comment above
    # _run_build_from_local_files(). Reached from on_folder_picked() via _start_background().
    def _run_import(self, url) -> None:
        granted = False
        try:
            granted = bool(url.startAccessingSecurityScopedResource())
            source_root = Path(str(url.path))
            source_files = sorted(source_root.rglob("*.ebl"))
            if not source_files:
                self.loop.call_soon_threadsafe(self.log, "[info] " + t("log_import_no_files"))
                return
            self.loop.call_soon_threadsafe(
                self.log, "[info] " + t("log_import_found", count=len(source_files))
            )

            # One line per newly-imported file, reported live as each one actually lands -- the
            # same "Python calls back during its own real work, one file at a time" shape
            # ProgressCallback.report() already uses for a download (see import_ebl.py's own
            # ImportProgressCallback doc comment: root-caused, not logged from a loop over
            # result["files"] after import_staged_ebl_files() has already finished all the real
            # work, which found in practice -- Android hit the exact same thing first -- has
            # nothing left to pace it and reads as the log doing nothing until the entire batch
            # lands at once).
            #
            # "skipped_duplicate" deliberately does NOT get its own live line here (asked for
            # explicitly, "zoveel mogelijk identiek aan android" -- this used to log both, matching
            # MainActivity.kt's own progressCallback.report() before its "gelijk maken" fix).
            # Matches w2k2_download.py's own "[skip] ... already complete locally" being logged at
            # level="debug" rather than the default "info": a reformatted or previously-imported SD
            # card/folder can just as easily be mostly duplicates, and a line per one would flood
            # the log for zero new information the same way it would for a download. Still counted
            # in the "skipped" summary line below (result["skipped_duplicate"]) -- only the one
            # line per duplicate file is gone, not the information that it happened.
            def report_progress(current: int, total: int, name: str, outcome: str) -> None:
                if outcome == "imported":
                    self.loop.call_soon_threadsafe(self.log, "[info] " + t("log_import_copied", name=name))
                # The progress-bar update itself fires unconditionally, regardless of outcome --
                # matches MainActivity.kt's own ImportProgressCallback.report() exactly, which
                # calls updateProgressBar() outside its own "if (outcome == imported)" check.
                self.loop.call_soon_threadsafe(self.update_progress_bar, t("phase_importing"), current, total)

            # Straight from the picked folder, no copy to a scratch directory first (Android's
            # stageForImport() only exists because a SAF content:// Uri is not a real path; here
            # url.path already is one, and import_staged_ebl_files() only ever *copies* from its
            # sources, never moves or deletes them) -- a second full copy of a whole SD card was just
            # extra time and disk for nothing.
            result = import_ebl.import_staged_ebl_files(
                [str(p) for p in source_files], str(self.ebl_dir()), report_progress
            )
            # What the end of the import says (renamed and failed files as warnings, then one summary line) is
            # decided in nmea2log/run_outcome.py, shared with the Android app.
            for line in run_outcome.describe_import(result):
                self.loop.call_soon_threadsafe(self.log, self._outcome_line_text(line))
            imported = result["imported"]
            if imported > 0:
                self._run_build_from_local_files()
        except OSError:
            # The picked folder's own connection was lost mid-import (asked for explicitly,
            # matching MainActivity.kt's own FileNotFoundException/SecurityException handling) --
            # a removable drive disconnected, or an iCloud Drive item that never finished
            # downloading. Reads as the mundane, expected thing it is, not an app bug.
            self.loop.call_soon_threadsafe(self.log, "[error] " + t("log_import_media_disconnected"))
        except Exception as e:
            self.loop.call_soon_threadsafe(self.log, "[error] " + t("error_unexpected", detail=str(e)))
        finally:
            if granted:
                url.stopAccessingSecurityScopedResource()

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
        # logbook's already shown would read as a glitch) -- see _log_result()'s own
        # show_logbook_on_success param, which is what actually shows it.
        publish_failed = False
        if result.get("ok") and self.settings_store.auto_publish_after_build:
            publish_failed = self._publish_attempt_failed()
        self._log_result(result, "build", publish_failed)

    # Runs on the background thread started by _start_background() -- see the comment above
    # _run_build_from_local_files().
    def _run_download(self, subnet_prefix: str) -> None:
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
        publish_failed = False
        if result.get("ok") and self.settings_store.auto_publish_after_build:
            publish_failed = self._publish_attempt_failed()
        self._log_result(result, "download", publish_failed)

    def _log_result(self, result: dict, initiator: str, publish_failed: bool = False) -> None:
        """The end of a run: run_outcome.describe_result() (shared with the Android app) decides which
        lines to log and what to show, this only turns that into the log view and the WebView. On a
        successful run the fresh logbook is shown with the log as a strip next to it; the log stays in
        front when a publish that was attempted failed, so its error stays visible."""
        outcome = run_outcome.describe_result(result, initiator, publish_failed)

        def show():
            for line in outcome.lines:
                self.log(self._outcome_line_text(line))
            if outcome.show == run_outcome.SHOW_LOGBOOK:
                # The run has just written a new logbook.html: load it, or the WebView would show the
                # one loaded earlier (or nothing at all on a first run) -- MainActivity.showSyncResult()
                # does the same via loadLogbookIntoWebView().
                if self._load_logbook_into_web_view():
                    self.showing_local_logbook = True
                    self._show_logbook_with_log_strip()
            elif outcome.show == run_outcome.SHOW_EXISTING_LOGBOOK:
                # Not at the boat: the logbook that is already there is made ready behind the log.
                if self.output_html_path().exists():
                    self._load_logbook_into_web_view()
            if result.get("ok"):
                # One closing line for the whole run, publish included -- the same marker the Android
                # app logs ("Voltooid: 14:05").
                self.log(t("log_sync_done_at", time=time.strftime("%H:%M")))

        self.loop.call_soon_threadsafe(show)

    @staticmethod
    def _outcome_line_text(line) -> str:
        """The text of a run_outcome.Line with its [level] tag, as every other log line."""
        if line.text is not None:
            text = line.text
        else:
            params = dict(line.params)
            if "error" in params and params["error"] is None:
                params["error"] = t("error_unknown")
            text = t(line.key, **params)
        return f"[{line.level}] {text}" if line.level else text


def main():
    return MySailingLogbook()
