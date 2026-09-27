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
from toga.dialogs import ConfirmDialog, ErrorDialog, InfoDialog
from toga.style.pack import COLUMN, ROW, Pack

from .settings_store import DEFAULT_MIN_STOP_MINUTES, DEFAULT_SFTP_PORT
from .translations import t

_BOOT_INTERVAL_MINUTES = [30, 60, 120, 180]
_BOOT_INTERVAL_KEYS = ["boat_interval_30", "boat_interval_60", "boat_interval_120", "boat_interval_180"]


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
        # real server hostname/path. The exact format (not just the site's own homepage or the
        # logbook page -- that redirects to a login page instead of uploading, see this repo's
        # README) matches the Android app's own README wording verbatim.
        self.rest_url_field = self._field(
            self.wordpress_box,
            t("label_rest_upload_url"),
            self.store.rest_upload_url,
            placeholder="https://your-site.example/wp-json/nmea2log/v1/logbook",
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

        self._update_publish_method_visibility(self.publish_method_selection)

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

        scroll = toga.ScrollContainer(content=form, style=Pack(flex=1))

        # Cancel/Save live outside the scroll area, always visible regardless of scroll
        # position -- same reasoning as SettingsActivity.kt's own Opslaan button placement
        # (found in practice there: with this many fields, a button living at the bottom of the
        # scrolling list was easy to believe you'd saved without ever actually reaching it).
        cancel_button = toga.Button(t("button_cancel"), on_press=self._on_cancel, style=Pack(flex=1, margin=8))
        save_button = toga.Button(t("button_save"), on_press=self._on_save, style=Pack(flex=1, margin=8))
        button_row = toga.Box(children=[cancel_button, save_button], style=Pack(direction=ROW))

        self.content = toga.Box(children=[scroll, button_row], style=Pack(direction=COLUMN))

    # -- small widget-building helpers, same role as SettingsActivity.kt's own field()/
    # sectionHeader()/checkbox() local functions --

    def _field(self, container, label, initial_value, is_password=False, placeholder=None):
        container.add(toga.Label(label, style=Pack(margin_top=8)))
        widget_cls = toga.PasswordInput if is_password else toga.TextInput
        field = widget_cls(value=initial_value, placeholder=placeholder)
        container.add(field)
        return field

    def _switch(self, container, label, initial_value):
        switch = toga.Switch(label, value=initial_value, style=Pack(margin_top=8))
        container.add(switch)
        return switch

    def _section_header(self, container, text):
        container.add(toga.Label(text, style=Pack(margin_top=16, font_weight="bold")))

    def _current_publish_host(self):
        if self.store.rest_upload_url.strip():
            try:
                from urllib.parse import urlparse

                host = urlparse(self.store.rest_upload_url).hostname
                if host:
                    return host
            except ValueError:
                pass
        if self.store.sftp_host.strip():
            return self.store.sftp_host
        return None

    def _update_publish_method_visibility(self, widget):
        self.wordpress_box.style.display = "pack" if self.publish_method_selection.value == self._publish_wordpress else "none"
        self.sftp_box.style.display = "pack" if self.publish_method_selection.value == self._publish_sftp else "none"

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
        self.app.show_main_screen()
