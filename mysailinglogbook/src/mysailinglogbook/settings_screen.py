"""
Settings screen -- mirrors SettingsActivity.kt field-for-field (see that file's own doc
comments for the reasoning behind individual fields/defaults). iOS has no separate-Activity
equivalent to swap to (toga_iOS explicitly raises "Secondary windows cannot be created on
iOS" for a second toga.Window -- see toga_iOS's own window.py), so this instead swaps the
single MainWindow's content in place, the same technique the "View logbook" button already
uses on Android (and will use here too once it's ported) -- see MySailingLogbook.
show_settings_screen()/show_main_screen().

Also unlike Android: no RadioGroup/Spinner widgets exist on Toga, so the publish-method choice
(don't publish / WordPress / SFTP) and the boat-mode round interval use toga.Selection (an iOS
picker) instead -- same three/four choices, same behavior (only the picked publish method's own
fields are shown, and saved; the others are cleared), just a native iOS-idiomatic control instead
of Android's radio buttons/dropdown.

All labels come from translations.py (t()), same nl/en/fr/de text Android's own strings.xml
uses -- built fresh per instance (not module-level constants) since they depend on t(), and the
publish-method/boot-interval Selection values double as both display text and the internal
comparison identifier (t() is deterministic per process, so this is safe).
"""

from __future__ import annotations

import toga
from rubicon.objc import Block, CGSize, NSMakeRect, ObjCClass, UIEdgeInsetsMake, objc_id
from toga.dialogs import ConfirmDialog, ErrorDialog, InfoDialog
from toga.style.pack import COLUMN, NONE, ROW, Pack
from travertino.size import at_least

from .settings_store import DEFAULT_MIN_STOP_MINUTES, DEFAULT_SFTP_PORT
from .translations import t

_NSNotificationCenter = ObjCClass("NSNotificationCenter")

_BOOT_INTERVAL_MINUTES = [30, 60, 120, 180]
_BOOT_INTERVAL_KEYS = ["boat_interval_30", "boat_interval_60", "boat_interval_120", "boat_interval_180"]


def _patch_switch_rehint_for_multiline_labels() -> None:
    """toga_iOS's own Switch.rehint() (toga_iOS/widgets/switch.py) measures its label via
    native_label.systemLayoutSizeFittingSize(CGSize(0, 0)) -- called this way, in isolation,
    that always reports a single line's height, even once the label's text actually contains
    literal "\n" breaks (see _wrap_switch_label() below on why "\n" is the only way to get
    multi-line text into a toga_iOS label at all) and numberOfLines is set to allow it: Pack
    then only ever allocates one line's worth of height for the whole switch row, so every line
    after the first is really there but silently clipped off in the row's own too-short frame
    -- found in practice, with the multi-line "\n" breaks from that same fix still visibly
    cut down to their first line only.

    toga_iOS's own Label widget (toga_iOS/widgets/label.py) measures itself correctly for
    exactly this case via native.textRectForBounds(rect, limitedToNumberOfLines:) -- a huge
    (100000x100000) bounding rect with the real line count, which (unlike
    systemLayoutSizeFittingSize used in isolation) is a plain text-layout query, unaffected by
    Auto Layout/constraint state. This monkeypatches toga_iOS's own Switch.rehint() to measure
    its label the exact same way, keeping label and switch widgets consistent. Idempotent
    (guarded by an attribute on the class itself) since this module can be imported more than
    once across the app's lifetime (this screen is rebuilt fresh every visit -- see this
    module's own doc comment).
    """
    from toga_iOS.widgets.switch import Switch as toga_switch_impl

    if getattr(toga_switch_impl, "_multiline_rehint_patch_applied", False):
        return

    def _rehint(self) -> None:
        text = str(self.native_label.text)
        num_lines = len(text.split("\n"))
        label_size = self.native_label.textRectForBounds(
            NSMakeRect(0, 0, 100_000, 100_000),
            limitedToNumberOfLines=num_lines,
        ).size
        switch_size = self.native_switch.systemLayoutSizeFittingSize(CGSize(0, 0))
        self.interface.intrinsic.width = at_least(
            label_size.width + self.SPACING + switch_size.width
        )
        self.interface.intrinsic.height = max(label_size.height, switch_size.height)

    toga_switch_impl.rehint = _rehint
    toga_switch_impl._multiline_rehint_patch_applied = True


_patch_switch_rehint_for_multiline_labels()


def _int_or(text: str, default: int) -> int:
    try:
        return max(1, int(text))
    except (TypeError, ValueError):
        return default


def _float_or(text: str, default: float) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


class SettingsScreen:
    def __init__(self, app):
        self.app = app
        self.store = app.settings_store

        # Built per instance (not module-level) since they depend on t() -- see this module's
        # own doc comment on why the display text doubles as the comparison identifier.
        self._publish_none = t("radio_publish_none")
        self._publish_wordpress = t("radio_publish_wordpress")
        self._publish_sftp = t("radio_publish_sftp")
        publish_options = [self._publish_none, self._publish_wordpress, self._publish_sftp]
        boot_interval_labels = [t(key) for key in _BOOT_INTERVAL_KEYS]

        # A plain vertical Box (not yet in a ScrollContainer -- that wraps it below), same
        # top-to-bottom field order as SettingsActivity.kt's own layout.
        form = toga.Box(style=Pack(direction=COLUMN, margin=16))

        self.user_field = self._field(form, t("label_w2k2_user"), self.store.w2k2_user)
        self.password_field = self._field(
            form, t("label_w2k2_password"), self.store.w2k2_password, is_password=True
        )
        self.boat_name_field = self._field(form, t("label_boat_name"), self.store.boat_name)
        self.mmsi_field = self._field(form, t("label_mmsi"), self.store.mmsi)
        self.call_sign_field = self._field(form, t("label_call_sign"), self.store.call_sign)
        self.auto_sync_switch = self._switch(
            form, t("checkbox_auto_sync_on_launch"), self.store.auto_sync_on_launch
        )

        self._section_header(form, t("section_trips"))
        self.min_stop_minutes_field = self._field(
            form, t("label_min_stop_minutes"), str(self.store.min_stop_minutes)
        )

        # Same "derived from what's actually configured, not hardcoded" header as
        # SettingsActivity.kt's own publishHost logic -- a fresh install with nothing filled in
        # shouldn't claim a destination that isn't really set up yet.
        publish_host = self._current_publish_host()
        self._section_header(
            form,
            t("section_publish_configured", host=publish_host) if publish_host else t("section_publish_not_configured"),
        )
        self.auto_publish_switch = self._switch(
            form, t("checkbox_auto_publish_after_build"), self.store.auto_publish_after_build
        )

        self.publish_method_selection = toga.Selection(items=publish_options, style=Pack(margin_top=8))
        if self.store.is_rest_upload_config_complete:
            self.publish_method_selection.value = self._publish_wordpress
        elif self.store.is_sftp_config_complete:
            self.publish_method_selection.value = self._publish_sftp
        else:
            self.publish_method_selection.value = self._publish_none
        self.publish_method_selection.on_change = self._update_publish_method_visibility
        form.add(self.publish_method_selection)

        self.wordpress_box = toga.Box(style=Pack(direction=COLUMN))
        # Placeholder, not a default value (never saved unless typed) -- same reasoning as
        # SettingsStore.kt's own restUploadUrl doc comment: a brand new install shouldn't show a
        # real server hostname/path. Just the bare site address, not the full REST URL -- stored
        # exactly as typed (see _on_save() below), never expanded in the field itself; the rest
        # is filled in via nmea2log.upload.normalize_rest_upload_url() only where the URL is
        # actually used (app.py's own _publish_logbook()), asked for explicitly: expanding it into
        # the field at save time meant the field showed something different from what was typed
        # the next time Settings opened, which read as "I typed X, Y appeared" -- confusing on its
        # own, and it also made iOS's own AutoFill treat the field as a real saved website once it
        # held a full URL, offering unrelated saved-site suggestions from Safari (found in
        # practice: a leftover "stud.com"-ish suggestion that kept coming back). disable_autofill
        # below stops that regardless of what the field ends up holding.
        self.rest_url_field = self._field(
            self.wordpress_box,
            t("label_rest_upload_url"),
            self.store.rest_upload_url,
            placeholder="your-site.example",
            disable_autofill=True,
        )
        self.rest_user_field = self._field(
            self.wordpress_box, t("label_rest_upload_user"), self.store.rest_upload_user
        )
        self.rest_password_field = self._field(
            self.wordpress_box, t("label_rest_upload_password"), self.store.rest_upload_password, is_password=True
        )
        form.add(self.wordpress_box)

        self.sftp_box = toga.Box(style=Pack(direction=COLUMN))
        self.sftp_host_field = self._field(self.sftp_box, t("label_sftp_host"), self.store.sftp_host)
        self.sftp_port_field = self._field(self.sftp_box, t("label_sftp_port"), str(self.store.sftp_port))
        self.sftp_user_field = self._field(self.sftp_box, t("label_sftp_user"), self.store.sftp_user)
        self.sftp_password_field = self._field(
            self.sftp_box, t("label_sftp_password"), self.store.sftp_password, is_password=True
        )
        self.sftp_remote_path_field = self._field(
            self.sftp_box, t("label_sftp_remote_path"), self.store.sftp_remote_path
        )
        self.sftp_host_key_field = self._field(
            self.sftp_box, t("label_sftp_host_key_fingerprint"), self.store.sftp_host_key_fingerprint
        )
        form.add(self.sftp_box)

        self._section_header(form, t("section_boat_mode"))
        form.add(toga.Label(t("label_boat_interval"), style=Pack(margin_top=8)))
        self.boot_interval_selection = toga.Selection(items=boot_interval_labels)
        try:
            index = _BOOT_INTERVAL_MINUTES.index(self.store.boot_round_interval_minutes)
        except ValueError:
            index = 1  # 60 minutes, same fallback as SettingsActivity.kt's own setSelection()
        self.boot_interval_selection.value = boot_interval_labels[index]
        form.add(self.boot_interval_selection)
        self.boot_publish_every_round_switch = self._switch(
            form, t("checkbox_boat_publish_every_round"), self.store.boot_publish_every_round
        )
        # Only meaningful with a publish method actually chosen -- see
        # _update_publish_method_visibility()'s own comment on why this one specifically (asked
        # for explicitly; the harbour/left-the-boat final-round checkboxes below it stay enabled
        # either way, since that round still builds a fresh local logbook regardless of whether
        # anywhere is configured to publish it). Called here, after this switch exists, rather
        # than right after publish_method_selection above -- this is the first call that needs it.
        self._update_publish_method_visibility(self.publish_method_selection)
        self.boot_final_harbour_switch = self._switch(
            form, t("checkbox_boat_final_harbour"), self.store.boot_final_on_harbour
        )
        self.boot_harbour_stationary_field = self._field(
            form, t("label_boat_harbour_stationary_minutes"), str(self.store.boot_harbour_stationary_minutes)
        )
        self.boot_harbour_engine_off_field = self._field(
            form, t("label_boat_harbour_engine_off_minutes"), str(self.store.boot_harbour_engine_off_minutes)
        )
        self.boot_final_left_switch = self._switch(
            form, t("checkbox_boat_final_left"), self.store.boot_final_on_left_boat
        )
        self.boot_left_minutes_field = self._field(
            form, t("label_boat_left_minutes"), str(self.store.boot_left_boat_minutes)
        )
        self.boot_stop_after_final_switch = self._switch(
            form, t("checkbox_boat_stop_after_final"), self.store.boot_stop_after_final
        )
        self.boot_auto_start_switch = self._switch(
            form, t("checkbox_boat_auto_start"), self.store.boot_auto_start
        )

        # Licht/Donker/Apparaat -- asked for explicitly (this app's own launch screen can't
        # follow it, since that renders before Python even starts and reads this setting at all;
        # see app.py's own apply_theme_mode() for what this *does* reach: the app's UI, including
        # the log screen, applied immediately via UIWindow.overrideUserInterfaceStyle, same choice
        # Android's own SettingsActivity now offers via AppCompatDelegate).
        self._section_header(form, t("section_appearance"))
        self._theme_light = t("radio_theme_light")
        self._theme_dark = t("radio_theme_dark")
        self._theme_system = t("radio_theme_system")
        theme_options = [self._theme_light, self._theme_dark, self._theme_system]
        self.theme_selection = toga.Selection(items=theme_options, style=Pack(margin_top=8))
        self.theme_selection.value = {
            "light": self._theme_light,
            "dark": self._theme_dark,
            "system": self._theme_system,
        }.get(self.store.theme_mode, self._theme_system)
        form.add(self.theme_selection)

        # Same reasoning as SettingsActivity.kt's own clearCacheButton(): two separate buttons,
        # not one "clear everything" -- clearing the wrong cache is real, avoidable extra
        # network/CPU cost.
        self._section_header(form, t("section_cache"))
        form.add(
            toga.Button(
                t("button_cache_data"), on_press=self._on_clear_data_cache, style=Pack(margin_top=8)
            )
        )
        form.add(
            toga.Button(
                t("button_cache_places"), on_press=self._on_clear_places_cache, style=Pack(margin_top=8)
            )
        )

        # horizontal=False -- found in practice, asked for explicitly to fix: toga_iOS's own
        # ScrollContainer.content_refreshed() lets the document container grow wider than the
        # viewport whenever horizontal scrolling is allowed (its own default), and does so purely
        # to accommodate whatever the content's widest child measures unconstrained -- which for a
        # long, non-wrapping Label or Switch label (several of this screen's own field
        # labels/checkboxes are full sentences) is wider than the screen. With horizontal
        # scrolling off, that same code path instead pins the document container's own width to
        # the viewport, which is what actually constrains those children's own Auto Layout enough
        # to wrap/shrink to fit -- not something fixable per-widget (see _wrap_switch_label()'s
        # own comment: that alone wasn't enough while the container itself still had no width
        # limit for it to wrap *within*).
        scroll = toga.ScrollContainer(content=form, style=Pack(flex=1), horizontal=False)

        # Cancel/Save live outside the scroll area, always visible regardless of scroll
        # position -- same reasoning as SettingsActivity.kt's own Opslaan button placement
        # (found in practice there: with this many fields, a button living at the bottom of the
        # scrolling list was easy to believe you'd saved without ever actually reaching it).
        cancel_button = toga.Button(t("button_cancel"), on_press=self._on_cancel, style=Pack(flex=1, margin=8))
        save_button = toga.Button(t("button_save"), on_press=self._on_save, style=Pack(flex=1, margin=8))
        button_row = toga.Box(children=[cancel_button, save_button], style=Pack(direction=ROW))

        self.content = toga.Box(children=[scroll, button_row], style=Pack(direction=COLUMN))
        self._install_keyboard_avoidance(scroll)

    # -- small widget-building helpers, same role as SettingsActivity.kt's own field()/
    # sectionHeader()/checkbox() local functions --

    def _field(self, container, label, initial_value, is_password=False, placeholder=None, disable_autofill=False):
        container.add(toga.Label(label, style=Pack(margin_top=8)))
        widget_cls = toga.PasswordInput if is_password else toga.TextInput
        field = widget_cls(value=initial_value, placeholder=placeholder)
        # Every field here is a technical value (URL, host, username, credential) or a short
        # proper noun (boat name, call sign) -- not a sentence -- so iOS's default "capitalize
        # the first letter of what looks like a new sentence" is actively wrong on all of them,
        # not just occasionally (found in practice, asked for explicitly to fix: it kept
        # recapitalizing the first character of the WordPress URL while typing). UITextField has
        # no cross-platform Toga API for this -- set directly on the native field, same pattern as
        # _template_tint_icon() in app.py. Autocorrection off for the same reason (a "corrected"
        # URL/hostname/username is just wrong, not helpful); spell-checking off too, since it's
        # the same red-squiggle mechanism working off the same wrong assumption these are words.
        native = field._impl.native
        native.autocapitalizationType = 0  # UITextAutocapitalizationTypeNone
        native.autocorrectionType = 1  # UITextAutocorrectionTypeNo
        native.spellCheckingType = 1  # UITextSpellCheckingTypeNo
        if disable_autofill:
            # Tells iOS not to guess what kind of field this is at all, so it never offers a
            # Safari-saved-website/AutoFill suggestion here -- see the WordPress URL field's own
            # comment on why this matters specifically for that one. "" (a real, empty NSString),
            # not None/nil -- Apple's own documented way to clear an inferred content type; also
            # sidesteps whatever rubicon-objc does converting a bare Python None into this
            # property's Optional<NSString> type, untested and not worth the risk here.
            native.textContentType = ""
        container.add(field)
        if is_password:
            self._add_password_toggle(container, field)
        return field

    def _add_password_toggle(self, container, field) -> None:
        """No cross-platform Toga API to reveal a PasswordInput's text -- toggles the native
        UITextField's own secureTextEntry directly (same _impl.native pattern as the autocap/
        autocorrect fix above), asked for explicitly (also done for Android's own password
        fields, via Material's standard end-icon toggle there -- see SettingsActivity.kt's own
        field()). Reassigning .text to itself right after the toggle works around a well-known
        UITextField quirk: a secureTextEntry change alone doesn't reliably redraw an
        already-populated field's current text, only what's typed after the change.
        """
        native = field._impl.native

        def _on_change(widget) -> None:
            native.secureTextEntry = not widget.value
            native.text = native.text

        switch = toga.Switch(t("checkbox_show_password"), value=False, style=Pack(margin_top=4))
        self._wrap_switch_label(switch)
        switch.on_change = _on_change
        container.add(switch)

    def _switch(self, container, label, initial_value):
        switch = toga.Switch(label, value=initial_value, style=Pack(margin_top=8))
        self._wrap_switch_label(switch)
        container.add(switch)
        return switch

    def _wrap_switch_label(self, switch) -> None:
        """toga_iOS's own Switch backend (toga_iOS/widgets/switch.py) uses a plain single-line
        UILabel with no reflow -- its own rehint() measures the label with an unconstrained
        systemLayoutSizeFittingSize(CGSize(0, 0)), always reporting the label's full single-line
        width as the widget's own intrinsic width, regardless of numberOfLines/
        preferredMaxLayoutWidth (those only affect a label already inside a real constrained
        Auto Layout pass, which this isolated measurement never runs) -- confirmed by toga_iOS's
        own Label widget (toga_iOS/widgets/label.py), which documents the same constraint by
        deliberately clipping rather than reflowing and only ever wraps at literal "\\n"
        characters in the text.

        So: this only sets numberOfLines=0 (needed so an embedded "\\n" actually renders as
        separate lines instead of being clipped after the first one) -- getting a label to
        actually take up more than one line at all requires the *text itself* to contain the
        line break, chosen by hand in translations.py for whichever strings are long enough to
        overflow at this screen width (found in practice: a long label otherwise pushes the
        whole row, and this screen's own scroll view along with it, wider than the actual
        device, which was also corrupting the scroll view's vertical layout). No public Toga
        API for numberOfLines either, so it's set directly on the native label
        (switch._impl.native_label, toga_iOS's own attribute name for it) -- same _impl.native
        pattern as _template_tint_icon() in app.py.

        numberOfLines alone still isn't enough on its own, though: the *row*'s own height also
        needs to grow to fit those extra lines, which is Switch.rehint()'s job, not this
        label's -- see _patch_switch_rehint_for_multiline_labels() above for that other half of
        this same fix (found in practice: without it, an embedded "\n" is fully wired up here
        but the row still only reserves one line of height, so every line past the first is
        just as invisible as it was before, silently clipped off the bottom of its own frame).
        """
        switch._impl.native_label.numberOfLines = 0

    def _section_header(self, container, text):
        container.add(toga.Label(text, style=Pack(margin_top=16, font_weight="bold")))

    def _install_keyboard_avoidance(self, scroll) -> None:
        """Found in practice: toga_iOS's ScrollContainer/TextInput have no keyboard-avoidance of
        their own -- with a form this long (W2K-2 login through boat-mode settings), the on-screen
        keyboard covering a field near the bottom (or the Opslaan/Cancel row below the scroll area
        entirely) reads as "everything disappeared" the moment you start typing, since there is
        nothing to scroll the focused field back into view.

        A generous fixed bottom inset while the keyboard is up, rather than reading its exact
        height out of the notification's userInfo (an NSValue-wrapped CGRect -- an extra struct
        extraction step over rubicon-objc that isn't needed here), covers every keyboard height in
        practice; a too-generous inset only ever means a bit of harmless extra empty scroll room,
        never a hidden field. Observers are removed in _on_cancel()/_on_save() -- this screen is
        rebuilt fresh every visit (see this module's own doc comment), so leaving them registered
        would otherwise stack up one more (increasingly redundant, but never wrong on its own)
        observer per visit.

        Tried also shifting self.content's own bottom margin (so the Opslaan/Cancel row, which
        lives *outside* the scroll area, would stay clear of a picker covering it too) -- reverted
        (asked for explicitly, found in practice): that margin change on self.content -- the box
        holding *both* the scroll area and the button row -- ended up corrupting the scroll area's
        own layout after opening the publish-method/boat-interval picker, leaving most of the form
        unreachable (looked like fields had vanished; they were still there, just outside a
        miscalculated scrollable region). The scroll view's own contentInset alone, below, is
        narrower in scope and doesn't have this problem -- it just doesn't reach the button row,
        which is a smaller, already-known gap, not a new one.
        """
        native = scroll._impl.native

        def _on_show(_notification: objc_id) -> None:
            native.contentInset = UIEdgeInsetsMake(0, 0, 300, 0)
            native.scrollIndicatorInsets = UIEdgeInsetsMake(0, 0, 300, 0)

        def _on_hide(_notification: objc_id) -> None:
            native.contentInset = UIEdgeInsetsMake(0, 0, 0, 0)
            native.scrollIndicatorInsets = UIEdgeInsetsMake(0, 0, 0, 0)

        center = _NSNotificationCenter.defaultCenter
        self._keyboard_show_observer = center.addObserverForName(
            "UIKeyboardWillShowNotification", object=None, queue=None, usingBlock=Block(_on_show, None, objc_id)
        )
        self._keyboard_hide_observer = center.addObserverForName(
            "UIKeyboardWillHideNotification", object=None, queue=None, usingBlock=Block(_on_hide, None, objc_id)
        )

    def _remove_keyboard_avoidance(self) -> None:
        center = _NSNotificationCenter.defaultCenter
        center.removeObserver(self._keyboard_show_observer)
        center.removeObserver(self._keyboard_hide_observer)

    def _current_publish_host(self):
        # Normalized first (same call app.py's own _publish_logbook() makes at upload time) --
        # rest_upload_url is stored as exactly what was typed (see the rest_url_field comment
        # above), and urlparse("ayuus.com").hostname is None without a scheme: this header would
        # otherwise misread a validly-configured bare address as "not configured" too.
        if self.store.rest_upload_url.strip():
            try:
                from urllib.parse import urlparse

                from nmea2log.upload import normalize_rest_upload_url

                host = urlparse(normalize_rest_upload_url(self.store.rest_upload_url)).hostname
                if host:
                    return host
            except ValueError:
                pass
        if self.store.sftp_host.strip():
            return self.store.sftp_host
        return None

    def _update_publish_method_visibility(self, widget):
        # Found in practice: Pack's own "display" property (PACK/NONE) alone isn't enough on
        # iOS -- toga_iOS's constraint-based layout still rendered the collapsed box's fields,
        # unlike display:none's usual "removed from layout entirely" behavior. "visibility"
        # (VISIBLE/HIDDEN) is the property actually wired to the native setHidden() call (see
        # toga's own style/applicator.py), so both are set together here: display for layout
        # sizing, visibility for what actually determines whether the native views draw at all.
        # height=0 on top of both (same fix content_area's own log/web view toggle needed, see
        # app.py) -- found in practice, asked for explicitly: even with display+visibility both
        # set, the collapsed box still reserved its full content height as blank space, since
        # toga_iOS's own setHidden() behaves like CSS visibility:hidden (invisible, but still
        # occupying its laid-out frame) rather than actually collapsing to nothing.
        show_wordpress = self.publish_method_selection.value == self._publish_wordpress
        show_sftp = self.publish_method_selection.value == self._publish_sftp
        self.wordpress_box.style.display = "pack" if show_wordpress else "none"
        self.wordpress_box.style.visibility = "visible" if show_wordpress else "hidden"
        self.wordpress_box.style.height = NONE if show_wordpress else 0
        self.sftp_box.style.display = "pack" if show_sftp else "none"
        self.sftp_box.style.visibility = "visible" if show_sftp else "hidden"
        self.sftp_box.style.height = NONE if show_sftp else 0
        # Same reasoning for both: neither means anything with no publish method chosen -- found
        # in practice, left enabled with "Niet publiceren" picked, they read as real, live
        # settings despite doing nothing at all in that state.
        self.boot_publish_every_round_switch.enabled = show_wordpress or show_sftp
        self.auto_publish_switch.enabled = show_wordpress or show_sftp

    async def _on_clear_data_cache(self, widget):
        confirmed = await self.app.main_window.dialog(
            ConfirmDialog(t("section_cache"), t("dialog_clear_data_cache_message"))
        )
        if not confirmed:
            return
        for name in ("sample_cache.pkl", ".trip_cache.pkl"):
            path = self.app.paths.data / name
            if path.is_dir():
                import shutil

                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        await self.app.main_window.dialog(InfoDialog(t("section_cache"), t("toast_cache_cleared")))

    async def _on_clear_places_cache(self, widget):
        confirmed = await self.app.main_window.dialog(
            ConfirmDialog(t("section_cache"), t("dialog_clear_places_cache_message"))
        )
        if not confirmed:
            return
        for name in (".geocode_cache.json", ".weather_cache.json", ".marine_cache.json"):
            path = self.app.paths.data / name
            if path.exists():
                path.unlink()
        await self.app.main_window.dialog(InfoDialog(t("section_cache"), t("toast_cache_cleared")))

    async def _on_cancel(self, widget):
        self._remove_keyboard_avoidance()
        self.app.show_main_screen()

    async def _on_save(self, widget):
        if not self.user_field.value.strip() or not self.password_field.value.strip():
            await self.app.main_window.dialog(
                ErrorDialog(t("label_w2k2_user"), t("toast_username_password_required"))
            )
            return

        fields = {
            "w2k2_user": self.user_field.value.strip(),
            "w2k2_password": self.password_field.value,
            "boat_name": self.boat_name_field.value.strip(),
            "mmsi": self.mmsi_field.value.strip(),
            "call_sign": self.call_sign_field.value.strip(),
            "auto_sync_on_launch": self.auto_sync_switch.value,
            "min_stop_minutes": _float_or(self.min_stop_minutes_field.value, DEFAULT_MIN_STOP_MINUTES),
            "auto_publish_after_build": self.auto_publish_switch.value,
            "boot_round_interval_minutes": _BOOT_INTERVAL_MINUTES[
                [t(key) for key in _BOOT_INTERVAL_KEYS].index(self.boot_interval_selection.value)
            ],
            "boot_publish_every_round": self.boot_publish_every_round_switch.value,
            "boot_final_on_harbour": self.boot_final_harbour_switch.value,
            "boot_harbour_stationary_minutes": _int_or(self.boot_harbour_stationary_field.value, 30),
            "boot_harbour_engine_off_minutes": _int_or(self.boot_harbour_engine_off_field.value, 10),
            "boot_final_on_left_boat": self.boot_final_left_switch.value,
            "boot_left_boat_minutes": _int_or(self.boot_left_minutes_field.value, 20),
            "boot_stop_after_final": self.boot_stop_after_final_switch.value,
            "boot_auto_start": self.boot_auto_start_switch.value,
            "theme_mode": {
                self._theme_light: "light",
                self._theme_dark: "dark",
                self._theme_system: "system",
            }[self.theme_selection.value],
        }

        # Only the picked method's fields are actually saved -- the other route(s) are cleared
        # instead of just left untouched, same reasoning as SettingsActivity.kt's own save
        # handler: the radio/selection choice is a real, unambiguous either-or-or-neither rather
        # than just a display filter.
        if self.publish_method_selection.value == self._publish_wordpress:
            fields.update(
                rest_upload_url=self.rest_url_field.value.strip(),
                rest_upload_user=self.rest_user_field.value.strip(),
                rest_upload_password=self.rest_password_field.value,
                sftp_host="",
                sftp_port=DEFAULT_SFTP_PORT,
                sftp_user="",
                sftp_password="",
                sftp_remote_path="",
                sftp_host_key_fingerprint="",
            )
        elif self.publish_method_selection.value == self._publish_sftp:
            fields.update(
                rest_upload_url="",
                rest_upload_user="",
                rest_upload_password="",
                sftp_host=self.sftp_host_field.value.strip(),
                sftp_port=_int_or(self.sftp_port_field.value, DEFAULT_SFTP_PORT),
                sftp_user=self.sftp_user_field.value.strip(),
                sftp_password=self.sftp_password_field.value,
                sftp_remote_path=self.sftp_remote_path_field.value.strip(),
                sftp_host_key_fingerprint=self.sftp_host_key_field.value.strip(),
            )
        else:
            fields.update(
                rest_upload_url="",
                rest_upload_user="",
                rest_upload_password="",
                sftp_host="",
                sftp_port=DEFAULT_SFTP_PORT,
                sftp_user="",
                sftp_password="",
                sftp_remote_path="",
                sftp_host_key_fingerprint="",
            )

        self.store.update(**fields)
        self.app.apply_theme_mode()
        self._remove_keyboard_avoidance()
        self.app.show_main_screen()
