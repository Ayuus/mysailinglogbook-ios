"""
Settings screen -- mirrors SettingsActivity.kt field-for-field (see that file's own doc
comments for the reasoning behind individual fields/defaults). iOS has no separate-Activity
equivalent to swap to (toga_iOS explicitly raises "Secondary windows cannot be created on
iOS" for a second toga.Window -- see toga_iOS's own window.py), so this instead swaps the
single MainWindow's content in place, the same technique the "View logbook" button already
uses on Android (and will use here too once it's ported) -- see MySailingLogbook.
show_settings_screen()/show_main_screen().

Also unlike Android: no RadioGroup/Spinner widgets exist on Toga, so the publish-method choice
(don't publish / WordPress) and the boat-mode round interval use toga.Selection (an iOS
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
from toga.dialogs import ConfirmDialog, InfoDialog
from toga.style.pack import COLUMN, NONE, ROW, Pack

from nmea2log import app_settings, ebl_storage

from . import native_ui
from .settings_store import DEFAULT_MIN_STOP_MINUTES
from .translations import t

# What the form leaves free on each side of the screen (Pack margin=16 on the form box).
_FORM_MARGIN = 16
# The "Clear" button of a cache row plus the gap before it, and the same room to spare.
_CACHE_BUTTON_WIDTH = 72 + 8 + 16
_DELETE_BUTTON_WIDTH = 112 + 8 + 16


_BOOT_INTERVAL_MINUTES = list(app_settings.BOOT_INTERVAL_CHOICES)
_BOOT_INTERVAL_KEYS = ["boat_interval_30", "boat_interval_60", "boat_interval_120", "boat_interval_180"]


def _float_or(text: str, default: float) -> float:
    return app_settings.parse_float(text, default)


class SettingsScreen:
    def __init__(self, app):
        self.app = app
        self.store = app.settings_store

        # Built per instance (not module-level) since they depend on t() -- see this module's
        # own doc comment on why the display text doubles as the comparison identifier.
        self._publish_none = t("radio_publish_none")
        self._publish_wordpress = t("radio_publish_wordpress")
        publish_options = [self._publish_none, self._publish_wordpress]
        boot_interval_labels = [t(key) for key in _BOOT_INTERVAL_KEYS]

        # A plain vertical Box (not yet in a ScrollContainer -- that wraps it below), same
        # top-to-bottom field order as SettingsActivity.kt's own layout.
        form = toga.Box(style=Pack(direction=COLUMN, margin=16))

        self._section_header(form, t("section_w2k2_boat"))
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

        # Plain static header -- was "Publish to {host}"/"Publish (not configured)", derived
        # from what's actually saved to disk, but that read as contradictory/stale the moment
        # you picked a publish method in the Selection below without having saved yet: the
        # dropdown said "WordPress" while this header still said "not configured" right above
        # it (found in practice, asked for explicitly to simplify instead of making the header
        # itself reactive).
        self._section_header(form, t("section_publish"))
        self.auto_publish_switch = self._switch(
            form, t("checkbox_auto_publish_after_build"), self.store.auto_publish_after_build
        )

        form.add(self._wrapped_label(t("label_publish_method"), style=Pack(margin_top=8)))
        self.publish_method_selection = toga.Selection(items=publish_options)
        if self.store.is_publish_configured:
            self.publish_method_selection.value = self._publish_wordpress
        else:
            self.publish_method_selection.value = self._publish_none
        self.publish_method_selection.on_change = self._update_publish_method_visibility
        native_ui.closing_picker(self.publish_method_selection, self.app.loop)
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
            placeholder=t("hint_rest_upload_url"),
            disable_autofill=True,
        )
        self.rest_user_field = self._field(
            self.wordpress_box, t("label_rest_upload_user"), self.store.rest_upload_user
        )
        self.rest_password_field = self._field(
            self.wordpress_box, t("label_rest_upload_password"), self.store.rest_upload_password, is_password=True
        )
        form.add(self.wordpress_box)


        self._section_header(form, t("section_boat_mode"))
        form.add(self._wrapped_label(t("label_boat_interval"), style=Pack(margin_top=8)))
        self.boot_interval_selection = native_ui.closing_picker(toga.Selection(items=boot_interval_labels), self.app.loop)
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
        self.theme_selection = native_ui.closing_picker(toga.Selection(items=theme_options, style=Pack(margin_top=8)), self.app.loop)
        self.theme_selection.value = {
            "light": self._theme_light,
            "dark": self._theme_dark,
            "system": self._theme_system,
        }.get(self.store.theme_mode, self._theme_system)
        form.add(self.theme_selection)

        # How the logbook page lays out its trips; handed to the page after it has loaded (app.py's apply_logbook_prefs()),
        # as the page's own buttons store their choice where the web view does not keep it.
        form.add(toga.Label(t("label_logbook_layout"), style=Pack(margin_top=12)))
        self._layout_auto = t("radio_layout_auto")
        self._layout_cards = t("radio_layout_cards")
        self._layout_table = t("radio_layout_table")
        self.layout_selection = native_ui.closing_picker(
            toga.Selection(items=[self._layout_auto, self._layout_cards, self._layout_table], style=Pack(margin_top=8)),
            self.app.loop,
        )
        self.layout_selection.value = {
            "cards": self._layout_cards,
            "table": self._layout_table,
        }.get(self.store.logbook_view, self._layout_auto)
        form.add(self.layout_selection)

        # Same reasoning as SettingsActivity.kt's own clearCacheButton(): two separate buttons,
        # not one "clear everything" -- clearing the wrong cache is real, avoidable extra
        # network/CPU cost.
        self._section_header(form, t("section_cache"))
        # Same row shape as _switch()'s own label+control pairing -- asked for explicitly, found
        # in practice: a standalone toga.Button per cache with its own long label ("Cache: Data")
        # read as an odd, oversized action compared to every switch/field row around it. Now the
        # descriptive text lives in a plain Label on the left (like a switch's own label), and
        # the button itself is a small, compact "Clear" on the right -- same visual weight as a
        # Switch's own control, not a full sentence trying to also be a tappable button.
        self._cache_row(form, t("button_cache_data"), self._on_clear_data_cache)
        self._cache_row(form, t("button_cache_places"), self._on_clear_places_cache)

        # The raw .ebl files themselves (the caches above never touch them), for freeing the phone's
        # storage -- counted and deleted by nmea2log.ebl_storage, the same code the Android app uses.
        self._section_header(form, t("section_ebl_files"))
        self._cache_row(
            form, t("button_ebl_files"), self._on_delete_ebl_files, button_text=t("button_delete"), button_width=112
        )

        # horizontal=False -- found in practice, asked for explicitly to fix: toga_iOS's own
        # ScrollContainer.content_refreshed() lets the document container grow wider than the
        # viewport whenever horizontal scrolling is allowed (its own default), and does so purely
        # to accommodate whatever the content's widest child measures unconstrained -- which for a
        # long, non-wrapping field Label (several of this screen's own field labels are full
        # sentences) is wider than the screen. With horizontal scrolling off, that same code path
        # instead pins the document container's own width to the viewport, which is what actually
        # constrains those Labels' own Auto Layout enough to wrap. A Switch's own built-in label
        # is a separate case entirely, not fixable this way -- see _switch_with_wrapped_label()'s
        # own comment.
        scroll = toga.ScrollContainer(content=form, style=Pack(flex=1), horizontal=False)

        # Cancel/Save live outside the scroll area, always visible regardless of scroll
        # position -- same reasoning as SettingsActivity.kt's own Opslaan button placement
        # (found in practice there: with this many fields, a button living at the bottom of the
        # scrolling list was easy to believe you'd saved without ever actually reaching it).
        cancel_button = toga.Button(t("button_cancel"), on_press=self._on_cancel, style=Pack(flex=1, margin=8))
        save_button = toga.Button(t("button_save"), on_press=self._on_save, style=Pack(flex=1, margin=8))
        button_row = toga.Box(children=[cancel_button, save_button], style=Pack(direction=ROW))
        # A plain 1pt line (iOS's own standard systemGray4 separator color) -- asked for
        # explicitly to fix: with nothing marking the boundary, the scroll area's content just
        # cut off abruptly right where the fixed Cancel/Save row began, which read as sloppy/
        # unfinished rather than a deliberate edge.
        button_row_divider = toga.Box(style=Pack(height=1, background_color="#C6C6C8"))

        self.content = toga.Box(children=[scroll, button_row_divider, button_row], style=Pack(direction=COLUMN))
        self._keyboard_avoidance = native_ui.KeyboardAvoidance(scroll)

    # -- small widget-building helpers, same role as SettingsActivity.kt's own field()/
    # sectionHeader()/checkbox() local functions --

    def _available_width(self, reserved=0) -> float:
        """The width the screen leaves for a label: the window minus the margins of the form and ``reserved`` for a
        control next to it."""
        return native_ui.window_width(self.app) - 2 * _FORM_MARGIN - reserved

    def _wrapped_label(self, text, reserved=0, style=None):
        """A Label whose text is broken into lines that fit the screen (see native_ui.wrapped_label())."""
        return native_ui.wrapped_label(text, self._available_width(reserved), style=style)

    def _field(self, container, label, initial_value, is_password=False, placeholder=None, disable_autofill=False):
        container.add(self._wrapped_label(label, style=Pack(margin_top=8)))
        widget_cls = toga.PasswordInput if is_password else toga.TextInput
        field = widget_cls(value=initial_value, placeholder=placeholder)
        native_ui.configure_technical_text_entry(field, disable_autofill)
        container.add(field)
        if is_password:
            self._add_password_toggle(container, field)
        return field

    def _add_password_toggle(self, container, field) -> None:
        switch = toga.Switch(t("checkbox_show_password"), value=False, style=Pack(margin_top=4))
        native_ui.attach_secure_entry_toggle(field, switch)
        container.add(switch)

    def _switch(self, container, label, initial_value):
        row, switch = native_ui.switch_row(label, initial_value, self._available_width())
        container.add(row)
        return switch

    def _section_header(self, container, text):
        container.add(toga.Label(text, style=Pack(margin_top=20, font_weight="bold", font_size=19)))

    def _cache_row(self, container, label_text, on_press, button_text=None, button_width=72):
        """A single cache-clear row: descriptive Label on the left (flex=1, same as any other
        Label here), a small "Clear" toga.Button on the right sized to its own text -- same
        left-label/right-control shape as _switch(), just with a tap-to-confirm Button standing
        in for the boolean Switch there.
        """
        row = toga.Box(style=Pack(direction=ROW, margin_top=8))
        row.add(self._wrapped_label(label_text, reserved=button_width + 8 + 16, style=Pack(flex=1)))
        # width/height close to a native UISwitch's own ~51x31pt footprint -- asked for
        # explicitly ("zelfde als schuifjes"): matches the control every other row in this
        # section ends its own row with, rather than either the button's default tiny
        # sized-to-text self, or an arbitrarily bigger one.
        button = toga.Button(
            button_text or t("button_clear"),
            on_press=on_press,
            style=Pack(width=button_width, height=32, background_color="#E5E5EA"),
        )
        native_ui.round_corners(button)
        row.add(button)
        container.add(row)

    def _remove_keyboard_avoidance(self) -> None:
        self._keyboard_avoidance.remove()

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
        self.wordpress_box.style.display = "pack" if show_wordpress else "none"
        self.wordpress_box.style.visibility = "visible" if show_wordpress else "hidden"
        self.wordpress_box.style.height = NONE if show_wordpress else 0
        # Same reasoning for both: neither means anything with no publish method chosen -- found
        # in practice, left enabled with "Niet publiceren" picked, they read as real, live
        # settings despite doing nothing at all in that state.
        native_ui.set_switch_enabled(self.boot_publish_every_round_switch, show_wordpress)
        native_ui.set_switch_enabled(self.auto_publish_switch, show_wordpress)

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

    async def _on_delete_ebl_files(self, widget):
        title = t("section_ebl_files")
        if self.app.sync_in_progress or self.app.boot_mode_controller.busy:
            await self.app.main_window.dialog(InfoDialog(title, t("toast_ebl_delete_busy")))
            return
        folder = self.app.ebl_dir()
        count, size = ebl_storage.describe(folder)
        if count == 0:
            await self.app.main_window.dialog(InfoDialog(title, t("toast_ebl_files_none")))
            return
        confirmed = await self.app.main_window.dialog(
            ConfirmDialog(title, t("dialog_delete_ebl_message", count=count, size=size))
        )
        if not confirmed:
            return
        deleted, freed = ebl_storage.delete_all(folder)
        await self.app.main_window.dialog(InfoDialog(title, t("toast_ebl_files_deleted", count=deleted, size=freed)))

    async def _on_cancel(self, widget):
        self._remove_keyboard_avoidance()
        self.app.show_main_screen()

    async def _on_save(self, widget):
        # No longer required to be filled in before saving (asked for explicitly, found in
        # practice: this predates on_import()'s SD/USB-based import, which reaches the exact same
        # decode/build/publish pipeline without the W2K-2 involved at all -- someone who only ever
        # imports from a card has no reason to have W2K-2 credentials at all, and blocking Save
        # entirely until they typed something in one made every other setting on this screen
        # unreachable too, not just the download feature). Matches SettingsActivity.kt's own
        # behavior, which has never validated these fields -- it just saves whatever's there,
        # trimmed, same as every other field on this screen.
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
            "boot_harbour_stationary_minutes": app_settings.parse_int(self.boot_harbour_stationary_field.value, app_settings.DEFAULTS["boot_harbour_stationary_minutes"], app_settings.MINIMUM_MINUTES),
            "boot_harbour_engine_off_minutes": app_settings.parse_int(self.boot_harbour_engine_off_field.value, app_settings.DEFAULTS["boot_harbour_engine_off_minutes"], app_settings.MINIMUM_MINUTES),
            "boot_final_on_left_boat": self.boot_final_left_switch.value,
            "boot_left_boat_minutes": app_settings.parse_int(self.boot_left_minutes_field.value, app_settings.DEFAULTS["boot_left_boat_minutes"], app_settings.MINIMUM_MINUTES),
            "boot_stop_after_final": self.boot_stop_after_final_switch.value,
            "boot_auto_start": self.boot_auto_start_switch.value,
            "theme_mode": {
                self._theme_light: "light",
                self._theme_dark: "dark",
                self._theme_system: "system",
            }[self.theme_selection.value],
            "logbook_view": {
                self._layout_auto: "auto",
                self._layout_cards: "cards",
                self._layout_table: "table",
            }[self.layout_selection.value],
        }

        # The details are always saved as typed, and the choice only says whether publishing is on -- picking
        # "don't publish" must not wipe them (same as SettingsActivity.kt's own save handler).
        fields.update(
            rest_upload_url=self.rest_url_field.value.strip(),
            rest_upload_user=self.rest_user_field.value.strip(),
            rest_upload_password=self.rest_password_field.value,
            publish_enabled=self.publish_method_selection.value == self._publish_wordpress,
        )

        self.store.update(**fields)
        self.app.apply_theme_mode()
        self.app.apply_logbook_prefs()
        self._remove_keyboard_avoidance()
        self.app.show_main_screen()
        # Android shows a toast; the log is the nearest thing here.
        self.app.log("[info] " + t("toast_settings_saved"))
