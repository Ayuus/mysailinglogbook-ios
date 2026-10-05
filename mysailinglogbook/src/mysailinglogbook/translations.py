"""
UI text in the same 4 languages the Android app's own strings.xml supports (nl/en/fr/de,
English fallback) -- asked for explicitly: "same as the multilingual plan for Android". Follows
the device's system language automatically, same as Android's own resource-qualifier mechanism
(values-nl/values-fr/values-de falling back to values/ -- see the Android app's own README).

The texts both apps show come from nmea2log (``nmea2log.app_texts.TEXTS``), the single source for them: a
wording is changed there once, and the Android app's strings.xml is generated from the same file, so the two
apps say literally the same thing and cannot drift apart. What is defined in this file is only what exists on
iOS alone (the Show password checkbox, a few of this app's own status messages) -- composed fresh,
following the same direct, concise tone as the shared strings.

Deliberately NOT covered here: the pipeline's own log lines (from nmea2log's log() calls, via
android_entry.py) -- those are shared with the desktop CLI and the Android app alike, and neither
of those translates them either; only this app's own UI labels and its own locally-authored log/
status lines are in scope.
"""

from __future__ import annotations

from rubicon.objc import ObjCClass

from nmea2log.app_texts import TEXTS

_NSLocale = ObjCClass("NSLocale")

_SUPPORTED = ("en", "nl", "fr", "de")

_STRINGS = {
    "checkbox_show_password": {
        "en": "Show password",
        "nl": "Wachtwoord tonen",
        "fr": "Afficher le mot de passe",
        "de": "Passwort anzeigen",
    },
    "log_sync_already_running": {
        "en": "A sync is already running.",
        "nl": "Er loopt al een synchronisatie.",
        "fr": "Une synchronisation est déjà en cours.",
        "de": "Es läuft bereits eine Synchronisierung.",
    },
    "log_build_already_running": {
        "en": "An assembly is already running.",
        "nl": "Er loopt al een samenstelactie.",
        "fr": "Un assemblage est déjà en cours.",
        "de": "Es läuft bereits eine Zusammenstellung.",
    },
    "log_import_already_running": {
        "en": "An import is already running.",
        "nl": "Er loopt al een import.",
        "fr": "Une importation est déjà en cours.",
        "de": "Es läuft bereits ein Import.",
    },
    "log_import_found": {
        # {count} substituted at call time.
        "en": "Found {count} .ebl file(s), importing...",
        "nl": "{count} .ebl-bestand(en) gevonden, importeren...",
        "fr": "{count} fichier(s) .ebl trouvé(s), importation en cours...",
        "de": "{count} .ebl-Datei(en) gefunden, werden importiert...",
    },
    "boat_bg_missed": {
        # {planned} substituted at call time (HH:MM).
        "en": "Boat mode: the {planned} round did not run.",
        "nl": "Boot-modus: de ronde van {planned} is niet uitgevoerd.",
        "fr": "Mode bateau : le tour de {planned} n'a pas été exécuté.",
        "de": "Bootsmodus: die Runde um {planned} lief nicht.",
    },
    "boat_catch_up_nothing_new": {
        "en": "Boat mode: W2K-2 reachable, no new files.",
        "nl": "Boot-modus: W2K-2 bereikbaar, geen nieuwe bestanden.",
        "fr": "Mode bateau : W2K-2 joignable, pas de nouveaux fichiers.",
        "de": "Bootsmodus: W2K-2 erreichbar, keine neuen Dateien.",
    },
    "label_publish_method": {
        "en": "Publish method",
        "nl": "Publicatiewijze",
        "fr": "Mode de publication",
        "de": "Veröffentlichungsart",
    },
    "boat_bg_low_power": {
        "en": "Low Power Mode is on: no background tasks then.",
        "nl": "Spaarstand staat aan: dan draaien er geen achtergrondtaken.",
        "fr": "Le mode économie d'énergie est activé : pas de tâches d'arrière-plan.",
        "de": "Der Stromsparmodus ist an: dann laufen keine Hintergrundaufgaben.",
    },
    "boat_bg_refresh_off": {
        "en": "Background App Refresh is off for this app.",
        "nl": "Achtergrondverversing staat uit voor deze app.",
        "fr": "L'actualisation en arrière-plan est désactivée pour cette app.",
        "de": "Die Hintergrundaktualisierung ist für diese App aus.",
    },
    "log_publish_already_running": {
        "en": "A publish is already running.",
        "nl": "Er loopt al een publicatie.",
        "fr": "Une publication est déjà en cours.",
        "de": "Es läuft bereits eine Veröffentlichung.",
    },
}

# The texts both apps show come from nmea2log (app_texts.py), the single source for them: a wording is
# changed there once, and the Android app's strings.xml is generated from the same file. What stays
# above is only what exists on iOS alone.
_STRINGS.update(TEXTS)


def pick_language(preferred_codes) -> str:
    """The first of preferred_codes (e.g. ["nl-NL", "en-US"], iOS's own NSLocale.preferredLanguages
    format -- a language tag, region optional) that's one of this app's 4 supported languages;
    English otherwise. Pure and side-effect-free (plain strings in, no NSLocale/rubicon-objc
    involved) specifically so it can be unit-tested directly -- see detect_system_language(),
    the only caller, for the actual OS integration."""
    for code in preferred_codes:
        short = str(code)[:2].lower()
        if short in _SUPPORTED:
            return short
    return "en"


def detect_system_language() -> str:
    """The device's own current language, mapped to one of this app's 4 supported ones (falls
    back to English for anything else) -- Toga/Python has no built-in way to read iOS's own
    language setting (stdlib locale functions reflect the *simulator/build host's* locale, not
    the device's), so this reads it directly via NSLocale, same source iOS's own Settings app
    uses."""
    try:
        return pick_language(list(_NSLocale.preferredLanguages))
    except (AttributeError, IndexError, ValueError, TypeError):
        return "en"


_LANGUAGE = detect_system_language()


def t(key: str, **kwargs) -> str:
    """Looks up key in the device's own language (detected once at import time), falling back
    to English if the key or language is missing. kwargs are substituted into the string via
    str.format() -- e.g. t("log_checking_for_w2k2", subnet=subnet_prefix)."""
    entry = _STRINGS[key]
    text = entry.get(_LANGUAGE, entry["en"])
    return text.format(**kwargs) if kwargs else text
