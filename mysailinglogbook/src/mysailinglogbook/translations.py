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
    "log_no_hotspot": {
        "en": "No WiFi network detected -- turn on your phone's hotspot (or join the "
        "W2K-2's own network) first.",
        "nl": "Geen wifinetwerk gevonden -- zet eerst de hotspot van je telefoon aan (of "
        "verbind met het eigen netwerk van de W2K-2).",
        "fr": "Aucun réseau WiFi détecté -- activez d'abord le partage de connexion de "
        "votre téléphone (ou rejoignez le réseau propre du W2K-2).",
        "de": "Kein WLAN-Netzwerk gefunden -- schalten Sie zuerst den Hotspot Ihres "
        "Telefons ein (oder verbinden Sie sich mit dem eigenen Netzwerk des W2K-2).",
    },
    "log_checking_for_w2k2": {
        # {subnet} substituted at call time.
        "en": "Checking {subnet}0/24 for a W2K-2...",
        "nl": "{subnet}0/24 controleren op een W2K-2...",
        "fr": "Recherche d'un W2K-2 sur {subnet}0/24...",
        "de": "Suche nach einem W2K-2 auf {subnet}0/24...",
    },
    "log_building_from_local_files": {
        "en": "Assembling logbook with existing data...",
        "nl": "Logboek samenstellen met bestaande data...",
        "fr": "Assemblage du carnet avec les données existantes...",
        "de": "Logbuch mit vorhandenen Daten zusammenstellen...",
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
    "log_publish_already_running": {
        "en": "A publish is already running.",
        "nl": "Er loopt al een publicatie.",
        "fr": "Une publication est déjà en cours.",
        "de": "Es läuft bereits eine Veröffentlichung.",
    },
    "log_upload_sftp_not_supported_ios": {
        "en": "SFTP publishing isn't supported on iOS yet (no SSH library that runs on this "
        "platform) -- switch to WordPress REST publishing in Settings instead.",
        "nl": "Publiceren via SFTP wordt nog niet ondersteund op iOS (geen SSH-library die op "
        "dit platform werkt) -- gebruik in plaats daarvan WordPress-publiceren via Instellingen.",
        "fr": "La publication par SFTP n'est pas encore prise en charge sur iOS (aucune "
        "bibliothèque SSH ne fonctionne sur cette plateforme) -- utilisez plutôt la "
        "publication WordPress dans les Paramètres.",
        "de": "Veröffentlichen über SFTP wird auf iOS noch nicht unterstützt (keine "
        "SSH-Bibliothek läuft auf dieser Plattform) -- verwenden Sie stattdessen die "
        "WordPress-Veröffentlichung in den Einstellungen.",
    },
    "log_logbook_display_failed": {
        # {error} substituted at call time.
        "en": "Logbook could not be displayed: {error}",
        "nl": "Logboek kon niet worden getoond: {error}",
        "fr": "Le carnet n'a pas pu être affiché : {error}",
        "de": "Logbuch konnte nicht angezeigt werden: {error}",
    },
    "log_logbook_ready": {
        # {count} substituted at call time.
        "en": "Logbook ready ({count} trip(s)).",
        "nl": "Logboek klaar ({count} reis(en)).",
        "fr": "Carnet prêt ({count} trajet(s)).",
        "de": "Logbuch fertig ({count} Fahrt(en)).",
    },
    "log_cancelled": {
        "en": "Cancelled.",
        "nl": "Geannuleerd.",
        "fr": "Annulé.",
        "de": "Abgebrochen.",
    },
    "log_downloading": {
        # {current}/{total}/{file_name} substituted at call time.
        "en": "Downloading: {current}/{total} ({file_name})",
        "nl": "Downloaden: {current}/{total} ({file_name})",
        "fr": "Téléchargement : {current}/{total} ({file_name})",
        "de": "Herunterladen: {current}/{total} ({file_name})",
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
