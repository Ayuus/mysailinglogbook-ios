"""
Persists the same settings as Android's own SettingsStore.kt: W2K-2 login, boat identity, and
the SFTP/WordPress publish settings -- see that file's own doc comments for the full field-by-
field reasoning (why some fields are deliberately never defaulted, min_stop_minutes matching the
desktop CLI's own --min-stop-minutes default, etc.), replicated here field-for-field (snake_case
instead of camelCase, otherwise the same names/defaults).

Stored as plain JSON in the app's own sandboxed Documents directory (paths.data/settings.json)
rather than Android's EncryptedSharedPreferences -- a real platform gap, not a deliberate choice:
iOS's own equivalent (Keychain, via the Security framework) needs its own Objective-C bridging
work this hasn't had yet. Still private to this app (the iOS sandbox, not readable by other apps),
just not encrypted at rest the way Android's copy is. Worth revisiting before this app handles
anyone's data but the developer's own test W2K-2 credentials.

Unlike Android's SettingsStore (a separate property setter per field, each persisting
immediately), writes here go through one batched update() call instead -- the Settings screen's
own Save button sets every field at once, so 25 separate immediate disk writes would just be
wasted work for the same end state. Reads are still one property per field, same call-site
ergonomics as Android (store.w2k2_user, not store.values["w2k2_user"]).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_SFTP_PORT = 22
# Same default as build_arg_parser()'s own --min-stop-minutes (see cli.py in the nmea2log repo).
DEFAULT_MIN_STOP_MINUTES = 10.0

_DEFAULTS: Dict[str, Any] = {
    "w2k2_user": "",
    "w2k2_password": "",
    "boat_name": "",
    "mmsi": "",
    "call_sign": "",
    # On by default -- see SettingsStore.kt's own comment: preserves the original, always-on
    # behavior for anyone upgrading.
    "auto_sync_on_launch": True,
    "auto_publish_after_build": True,
    "min_stop_minutes": DEFAULT_MIN_STOP_MINUTES,
    # Never defaulted (see SettingsStore.kt) -- a brand new install shouldn't show a real
    # server hostname/path despite nothing ever being entered on that install.
    "rest_upload_url": "",
    "rest_upload_user": "",
    "rest_upload_password": "",
    "sftp_host": "",
    "sftp_port": DEFAULT_SFTP_PORT,
    "sftp_user": "",
    "sftp_password": "",
    "sftp_remote_path": "",
    "sftp_host_key_fingerprint": "",
    "boot_round_interval_minutes": 60,
    "boot_publish_every_round": False,
    "boot_final_on_harbour": True,
    "boot_harbour_stationary_minutes": 30,
    "boot_harbour_engine_off_minutes": 10,
    "boot_final_on_left_boat": True,
    "boot_left_boat_minutes": 20,
    "boot_stop_after_final": False,
    "boot_auto_start": False,
    # "light" / "dark" / "system" -- see SettingsStore.kt's own themeMode for the Android
    # equivalent. Defaults to "system" here (not "dark" like Android): this app's UI has always
    # simply followed whatever UIKit resolves from the phone's own Appearance setting, so "system"
    # preserves that existing behavior for anyone upgrading, the same reasoning Android's own
    # "dark" default uses for *its* previous (forced) behavior -- each platform keeps looking the
    # way it already did until someone opens Settings and picks something else.
    "theme_mode": "system",
}


class SettingsStore:
    def __init__(self, data_dir: Path):
        self._path = data_dir / "settings.json"
        self._values: Dict[str, Any] = dict(_DEFAULTS)
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text())
                self._values.update({k: v for k, v in loaded.items() if k in _DEFAULTS})
            except (OSError, ValueError):
                pass  # corrupt/unreadable -- fall back to defaults, same as a fresh install

    def update(self, **fields: Any) -> None:
        """Sets every given field and persists once -- see this module's own doc comment on why
        this replaces Android's per-field property setters. Unknown keys are a programming error
        (a typo'd field name), not a silently-ignored no-op -- fail loudly instead."""
        for key in fields:
            if key not in _DEFAULTS:
                raise KeyError(f"Unknown setting: {key}")
        self._values.update(fields)
        self._path.write_text(json.dumps(self._values, indent=2))

    @property
    def w2k2_user(self) -> str:
        return self._values["w2k2_user"]

    @property
    def w2k2_password(self) -> str:
        return self._values["w2k2_password"]

    @property
    def boat_name(self) -> str:
        return self._values["boat_name"]

    @property
    def mmsi(self) -> str:
        return self._values["mmsi"]

    @property
    def call_sign(self) -> str:
        return self._values["call_sign"]

    @property
    def is_w2k2_config_complete(self) -> bool:
        return bool(self.w2k2_user.strip()) and bool(self.w2k2_password.strip())

    @property
    def auto_sync_on_launch(self) -> bool:
        return self._values["auto_sync_on_launch"]

    @property
    def auto_publish_after_build(self) -> bool:
        return self._values["auto_publish_after_build"]

    @property
    def min_stop_minutes(self) -> float:
        return self._values["min_stop_minutes"]

    @property
    def rest_upload_url(self) -> str:
        return self._values["rest_upload_url"]

    @property
    def rest_upload_user(self) -> str:
        return self._values["rest_upload_user"]

    @property
    def rest_upload_password(self) -> str:
        return self._values["rest_upload_password"]

    @property
    def is_rest_upload_config_complete(self) -> bool:
        return bool(self.rest_upload_url.strip()) and bool(self.rest_upload_user.strip()) and bool(
            self.rest_upload_password.strip()
        )

    @property
    def sftp_host(self) -> str:
        return self._values["sftp_host"]

    @property
    def sftp_port(self) -> int:
        return self._values["sftp_port"]

    @property
    def sftp_user(self) -> str:
        return self._values["sftp_user"]

    @property
    def sftp_password(self) -> str:
        return self._values["sftp_password"]

    @property
    def sftp_remote_path(self) -> str:
        return self._values["sftp_remote_path"]

    @property
    def sftp_host_key_fingerprint(self) -> str:
        return self._values["sftp_host_key_fingerprint"]

    @property
    def is_sftp_config_complete(self) -> bool:
        return (
            bool(self.sftp_host.strip())
            and bool(self.sftp_user.strip())
            and bool(self.sftp_password.strip())
            and bool(self.sftp_remote_path.strip())
        )

    @property
    def boot_round_interval_minutes(self) -> int:
        return self._values["boot_round_interval_minutes"]

    @property
    def boot_publish_every_round(self) -> bool:
        return self._values["boot_publish_every_round"]

    @property
    def boot_final_on_harbour(self) -> bool:
        return self._values["boot_final_on_harbour"]

    @property
    def boot_harbour_stationary_minutes(self) -> int:
        return self._values["boot_harbour_stationary_minutes"]

    @property
    def boot_harbour_engine_off_minutes(self) -> int:
        return self._values["boot_harbour_engine_off_minutes"]

    @property
    def boot_final_on_left_boat(self) -> bool:
        return self._values["boot_final_on_left_boat"]

    @property
    def boot_left_boat_minutes(self) -> int:
        return self._values["boot_left_boat_minutes"]

    @property
    def boot_stop_after_final(self) -> bool:
        return self._values["boot_stop_after_final"]

    @property
    def boot_auto_start(self) -> bool:
        return self._values["boot_auto_start"]

    @property
    def theme_mode(self) -> str:
        return self._values["theme_mode"]

    def boot_mode_config_json(self) -> str:
        """The boat-mode settings as the JSON nmea2log.bootmode.BootModeConfig.from_dict() takes
        -- same shape as SettingsStore.kt's own bootModeConfigJson(), for when boat mode itself is
        ported (not yet -- see MySailingLogbook.on_boat_mode)."""
        return json.dumps(
            {
                "round_interval_minutes": self.boot_round_interval_minutes,
                "publish_every_round": self.boot_publish_every_round,
                "final_on_harbour": self.boot_final_on_harbour,
                "harbour_stationary_minutes": self.boot_harbour_stationary_minutes,
                "harbour_engine_off_minutes": self.boot_harbour_engine_off_minutes,
                "final_on_left_boat": self.boot_final_on_left_boat,
                "left_boat_minutes": self.boot_left_boat_minutes,
                "stop_after_final": self.boot_stop_after_final,
                "publish_configured": self.is_rest_upload_config_complete or self.is_sftp_config_complete,
            }
        )
