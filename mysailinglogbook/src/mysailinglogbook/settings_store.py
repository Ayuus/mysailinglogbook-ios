"""
Persists the same settings as Android's own SettingsStore.kt: W2K-2 login, boat identity, and
the WordPress publish settings -- see that file's own doc comments for the full field-by-
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

from nmea2log import app_settings

# The defaults of both apps are defined once, in nmea2log/app_settings.py (SettingsStore.kt gets them as a
# generated Kotlin file); the comments on why a field is never defaulted are there too.
DEFAULT_MIN_STOP_MINUTES = app_settings.DEFAULT_MIN_STOP_MINUTES

_DEFAULTS: Dict[str, Any] = dict(app_settings.DEFAULTS)


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
        return app_settings.is_w2k2_complete(self.w2k2_user, self.w2k2_password)

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
        return app_settings.is_rest_complete(self.rest_upload_url, self.rest_upload_user, self.rest_upload_password)

    @property
    def publish_enabled(self) -> bool:
        """Whether publishing is switched on ("WordPress" picked in Settings), kept apart from the WordPress details:
        picking "don't publish" must not wipe them."""
        return self._values["publish_enabled"]

    @property
    def is_publish_configured(self) -> bool:
        """Publishing is on and the details are all there -- what every "can this be published" check asks."""
        return app_settings.is_publish_configured(
            self.publish_enabled, self.rest_upload_url, self.rest_upload_user, self.rest_upload_password
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

    @property
    def logbook_view(self) -> str:
        return self._values["logbook_view"]
