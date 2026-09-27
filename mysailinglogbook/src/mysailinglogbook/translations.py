"""
UI text in the same 4 languages the Android app's own strings.xml supports (nl/en/fr/de,
English fallback) -- asked for explicitly: "same as the multilingual plan for Android". Follows
the device's system language automatically, same as Android's own resource-qualifier mechanism
(values-nl/values-fr/values-de falling back to values/ -- see the Android app's own README).

Keys mirror Android's own string resource names one-for-one where the same text is used in both
apps (e.g. label_w2k2_user), with the exact same English/Dutch/French/German wording copied from
strings.xml/values-nl/values-fr/values-de, so the two apps say literally the same thing. A
handful of keys are iOS-only (no Android equivalent: the Cancel button, since there's no back
button/Activity stack to fall back on here; a few of this app's own not-yet-fully-ported status
messages) -- composed fresh, following the same direct, concise tone as Android's own strings.

Deliberately NOT covered here: the pipeline's own log lines (from nmea2log's log() calls, via
android_entry.py) -- those are shared with the desktop CLI and the Android app alike, and neither
of those translates them either; only this app's own UI labels and its own locally-authored log/
status lines are in scope.
"""

from __future__ import annotations

from rubicon.objc import ObjCClass

_NSLocale = ObjCClass("NSLocale")

_SUPPORTED = ("en", "nl", "fr", "de")

_STRINGS = {
    "label_w2k2_user": {
        "en": "W2K-2 username",
        "nl": "W2K-2 gebruikersnaam",
        "fr": "Nom d'utilisateur W2K-2",
        "de": "W2K-2-Benutzername",
    },
    "label_w2k2_password": {
        "en": "W2K-2 password",
        "nl": "W2K-2 wachtwoord",
        "fr": "Mot de passe W2K-2",
        "de": "W2K-2-Passwort",
    },
    "label_boat_name": {
        "en": "Boat name",
        "nl": "Bootnaam",
        "fr": "Nom du bateau",
        "de": "Bootsname",
    },
    "label_mmsi": {
        "en": "MMSI",
        "nl": "MMSI",
        "fr": "MMSI",
        "de": "MMSI",
    },
    "label_call_sign": {
        "en": "Call sign",
        "nl": "Roepnaam",
        "fr": "Indicatif d'appel",
        "de": "Rufzeichen",
    },
    "checkbox_auto_sync_on_launch": {
        "en": "Automatically download on launch",
        "nl": "Automatisch downloaden bij starten",
        "fr": "Télécharger automatiquement au démarrage",
        "de": "Beim Start automatisch herunterladen",
    },
    "section_trips": {
        "en": "Trips",
        "nl": "Reizen",
        "fr": "Trajets",
        "de": "Fahrten",
    },
    "label_min_stop_minutes": {
        "en": "Minimum stop duration to count as a port visit (minutes)",
        "nl": "Minimale stop-tijd om als havenbezoek te tellen (minuten)",
        "fr": "Durée d'arrêt minimale pour compter comme escale (minutes)",
        "de": "Mindeststandzeit, um als Hafenbesuch zu zählen (Minuten)",
    },
    "checkbox_auto_publish_after_build": {
        "en": "Automatically publish after building",
        "nl": "Automatisch publiceren na bouwen",
        "fr": "Publier automatiquement après la construction",
        "de": "Nach dem Erstellen automatisch veröffentlichen",
    },
    "section_publish_configured": {
        # {host} substituted at call time -- see t().
        "en": "Publish to {host}",
        "nl": "Publiceren naar {host}",
        "fr": "Publier vers {host}",
        "de": "Veröffentlichen auf {host}",
    },
    "section_publish_not_configured": {
        "en": "Publish (not configured)",
        "nl": "Publiceren (niet ingesteld)",
        "fr": "Publier (non configuré)",
        "de": "Veröffentlichen (nicht konfiguriert)",
    },
    "radio_publish_none": {
        "en": "Don't publish (local only)",
        "nl": "Niet publiceren (alleen lokaal)",
        "fr": "Ne pas publier (local uniquement)",
        "de": "Nicht veröffentlichen (nur lokal)",
    },
    "radio_publish_wordpress": {
        "en": "Publish via WordPress",
        "nl": "Publiceren via WordPress",
        "fr": "Publier via WordPress",
        "de": "Über WordPress veröffentlichen",
    },
    "radio_publish_sftp": {
        "en": "Publish via SFTP",
        "nl": "Publiceren via SFTP",
        "fr": "Publier via SFTP",
        "de": "Über SFTP veröffentlichen",
    },
    "label_rest_upload_url": {
        "en": "REST upload URL (WordPress)",
        "nl": "REST upload-URL (WordPress)",
        "fr": "URL d'envoi REST (WordPress)",
        "de": "REST-Upload-URL (WordPress)",
    },
    "label_rest_upload_user": {
        "en": "WordPress username",
        "nl": "WordPress gebruikersnaam",
        "fr": "Nom d'utilisateur WordPress",
        "de": "WordPress-Benutzername",
    },
    "label_rest_upload_password": {
        "en": "WordPress application password",
        "nl": "WordPress application password",
        "fr": "Mot de passe d'application WordPress",
        "de": "WordPress-Anwendungspasswort",
    },
    "label_sftp_host": {
        "en": "SFTP host",
        "nl": "SFTP host",
        "fr": "Hôte SFTP",
        "de": "SFTP-Host",
    },
    "label_sftp_port": {
        "en": "SFTP port",
        "nl": "SFTP poort",
        "fr": "Port SFTP",
        "de": "SFTP-Port",
    },
    "label_sftp_user": {
        "en": "SFTP username",
        "nl": "SFTP gebruikersnaam",
        "fr": "Nom d'utilisateur SFTP",
        "de": "SFTP-Benutzername",
    },
    "label_sftp_password": {
        "en": "SFTP password",
        "nl": "SFTP wachtwoord",
        "fr": "Mot de passe SFTP",
        "de": "SFTP-Passwort",
    },
    "label_sftp_remote_path": {
        "en": "SFTP path on the server",
        "nl": "SFTP pad op de server",
        "fr": "Chemin SFTP sur le serveur",
        "de": "SFTP-Pfad auf dem Server",
    },
    "label_sftp_host_key_fingerprint": {
        "en": "SFTP host key fingerprint (optional; empty = trust automatically on first connection)",
        "nl": "SFTP host-key fingerprint (optioneel; leeg = automatisch vertrouwen bij eerste verbinding)",
        "fr": "Empreinte de clé hôte SFTP (facultatif ; vide = faire confiance automatiquement à la première connexion)",
        "de": "SFTP-Hostschlüssel-Fingerabdruck (optional; leer = bei erster Verbindung automatisch vertrauen)",
    },
    "section_boat_mode": {
        "en": "Boat mode",
        "nl": "Boot-modus",
        "fr": "Mode bateau",
        "de": "Boot-Modus",
    },
    "label_boat_interval": {
        "en": "A round (download + build) every",
        "nl": "Een ronde (downloaden + bouwen) elke",
        "fr": "Une ronde (télécharger + construire) toutes les",
        "de": "Eine Runde (Herunterladen + Erstellen) alle",
    },
    "boat_interval_30": {
        "en": "30 minutes",
        "nl": "30 minuten",
        "fr": "30 minutes",
        "de": "30 Minuten",
    },
    "boat_interval_60": {
        "en": "1 hour",
        "nl": "1 uur",
        "fr": "1 heure",
        "de": "1 Stunde",
    },
    "boat_interval_120": {
        "en": "2 hours",
        "nl": "2 uur",
        "fr": "2 heures",
        "de": "2 Stunden",
    },
    "boat_interval_180": {
        "en": "3 hours",
        "nl": "3 uur",
        "fr": "3 heures",
        "de": "3 Stunden",
    },
    "checkbox_boat_publish_every_round": {
        "en": "Publish after every round",
        "nl": "Elke ronde publiceren",
        "fr": "Publier après chaque ronde",
        "de": "Nach jeder Runde veröffentlichen",
    },
    "checkbox_boat_final_harbour": {
        "en": "Final round (publish) once the boat is in harbour",
        "nl": "Laatste ronde (publiceren) zodra de boot in de haven ligt",
        "fr": "Dernière ronde (publication) dès que le bateau est au port",
        "de": "Letzte Runde (veröffentlichen), sobald das Boot im Hafen liegt",
    },
    "label_boat_harbour_stationary_minutes": {
        "en": "Harbour: stationary for (minutes)",
        "nl": "Haven: stil gedurende (minuten)",
        "fr": "Port : à l'arrêt depuis (minutes)",
        "de": "Hafen: stillstehend seit (Minuten)",
    },
    "label_boat_harbour_engine_off_minutes": {
        "en": "Harbour: engine off for (minutes)",
        "nl": "Haven: motor uit gedurende (minuten)",
        "fr": "Port : moteur coupé depuis (minutes)",
        "de": "Hafen: Motor aus seit (Minuten)",
    },
    "checkbox_boat_final_left": {
        "en": "Final round when I have left the boat",
        "nl": "Laatste ronde als ik van boord ben",
        "fr": "Dernière ronde quand j'ai quitté le bateau",
        "de": "Letzte Runde, wenn ich das Boot verlassen habe",
    },
    "label_boat_left_minutes": {
        "en": "Left the boat: W2K-2 unreachable for (minutes)",
        "nl": "Van boord: W2K-2 niet bereikbaar gedurende (minuten)",
        "fr": "Quitté le bateau : W2K-2 injoignable depuis (minutes)",
        "de": "Boot verlassen: W2K-2 nicht erreichbar seit (Minuten)",
    },
    "checkbox_boat_stop_after_final": {
        "en": "Switch boat mode off after the final round",
        "nl": "Boot-modus zelf uitzetten na de laatste ronde",
        "fr": "Désactiver le mode bateau après la dernière ronde",
        "de": "Boot-Modus nach der letzten Runde selbst ausschalten",
    },
    "checkbox_boat_auto_start": {
        "en": "Start automatically when the app is opened at the W2K-2 (hotspot on)",
        "nl": "Automatisch beginnen als de app wordt geopend bij de W2K-2 (hotspot aan)",
        "fr": "Démarrer automatiquement quand l'application est ouverte près du W2K-2 (point d'accès activé)",
        "de": "Automatisch starten, wenn die App am W2K-2 geöffnet wird (Hotspot an)",
    },
    "section_cache": {
        "en": "Clear cache",
        "nl": "Cache legen",
        "fr": "Vider le cache",
        "de": "Cache leeren",
    },
    "button_cache_data": {
        "en": "Cache: Data",
        "nl": "Cache: Data",
        "fr": "Cache : Données",
        "de": "Cache: Daten",
    },
    "button_cache_places": {
        "en": "Cache: Place names",
        "nl": "Cache: Plaatsnamen",
        "fr": "Cache : Noms de lieux",
        "de": "Cache: Ortsnamen",
    },
    "button_save": {
        "en": "Save",
        "nl": "Opslaan",
        "fr": "Enregistrer",
        "de": "Speichern",
    },
    # iOS-only from here -- no Android equivalent (see this module's own doc comment).
    "button_cancel": {
        "en": "Cancel",
        "nl": "Annuleren",
        "fr": "Annuler",
        "de": "Abbrechen",
    },
    "toast_username_password_required": {
        "en": "Fill in the W2K-2 username and password.",
        "nl": "Vul de W2K-2 gebruikersnaam en het wachtwoord in.",
        "fr": "Renseignez le nom d'utilisateur et le mot de passe W2K-2.",
        "de": "Geben Sie den W2K-2-Benutzernamen und das Passwort ein.",
    },
    "dialog_clear_data_cache_message": {
        "en": "Deletes the decode/trip cache. The next download or rebuild will re-decode every "
        ".ebl file from scratch (slower, no data lost).",
        "nl": "Verwijdert de decode-/reizencache. De volgende download of rebuild decodeert elk "
        ".ebl-bestand opnieuw vanaf nul (langzamer, geen dataverlies).",
        "fr": "Supprime le cache de décodage/trajets. Le prochain téléchargement ou la prochaine "
        "reconstruction redécodera chaque fichier .ebl depuis le début (plus lent, aucune "
        "perte de données).",
        "de": "Löscht den Decodier-/Fahrten-Cache. Der nächste Download oder Rebuild decodiert "
        "jede .ebl-Datei von Grund auf neu (langsamer, kein Datenverlust).",
    },
    "dialog_clear_places_cache_message": {
        "en": "Deletes the place-name/weather/marine lookup cache. The next download or rebuild "
        "will re-fetch every lookup (slower, no data lost).",
        "nl": "Verwijdert de cache voor plaatsnamen/weer/getijden. De volgende download of "
        "rebuild haalt elke opzoeking opnieuw op (langzamer, geen dataverlies).",
        "fr": "Supprime le cache des noms de lieux/météo/marine. Le prochain téléchargement ou "
        "la prochaine reconstruction récupérera chaque recherche à nouveau (plus lent, "
        "aucune perte de données).",
        "de": "Löscht den Cache für Ortsnamen/Wetter/Gezeiten. Der nächste Download oder Rebuild "
        "ruft jede Abfrage erneut ab (langsamer, kein Datenverlust).",
    },
    "toast_cache_cleared": {
        "en": "Cache cleared.",
        "nl": "Cache leeggemaakt.",
        "fr": "Cache vidé.",
        "de": "Cache geleert.",
    },
    "toast_settings_saved": {
        "en": "Settings saved.",
        "nl": "Instellingen opgeslagen.",
        "fr": "Paramètres enregistrés.",
        "de": "Einstellungen gespeichert.",
    },
    "log_sync_already_running": {
        "en": "A sync is already running.",
        "nl": "Er loopt al een synchronisatie.",
        "fr": "Une synchronisation est déjà en cours.",
        "de": "Es läuft bereits eine Synchronisierung.",
    },
    "log_build_already_running": {
        "en": "A build is already running.",
        "nl": "Er loopt al een bouwactie.",
        "fr": "Une construction est déjà en cours.",
        "de": "Es läuft bereits ein Build.",
    },
    "log_fill_w2k2_credentials": {
        "en": "Fill in the W2K-2 username and password via Settings first.",
        "nl": "Vul eerst de W2K-2 gebruikersnaam en het wachtwoord in via Instellingen.",
        "fr": "Renseignez d'abord le nom d'utilisateur et le mot de passe W2K-2 via les Paramètres.",
        "de": "Geben Sie zuerst den W2K-2-Benutzernamen und das Passwort über die Einstellungen ein.",
    },
    "log_no_hotspot": {
        "en": "No WiFi/hotspot network detected -- turn on Personal Hotspot (or join the "
        "W2K-2's own network) first.",
        "nl": "Geen wifi-/hotspotnetwerk gevonden -- zet eerst Persoonlijke Hotspot aan (of "
        "verbind met het eigen netwerk van de W2K-2).",
        "fr": "Aucun réseau WiFi/point d'accès détecté -- activez d'abord le partage de "
        "connexion (ou rejoignez le réseau propre du W2K-2).",
        "de": "Kein WLAN-/Hotspot-Netzwerk gefunden -- schalten Sie zuerst den persönlichen "
        "Hotspot ein (oder verbinden Sie sich mit dem eigenen Netzwerk des W2K-2).",
    },
    "log_checking_for_w2k2": {
        # {subnet} substituted at call time.
        "en": "Checking {subnet}0/24 for a W2K-2...",
        "nl": "{subnet}0/24 controleren op een W2K-2...",
        "fr": "Recherche d'un W2K-2 sur {subnet}0/24...",
        "de": "Suche nach einem W2K-2 auf {subnet}0/24...",
    },
    "log_building_from_local_files": {
        "en": "Building logbook with existing data...",
        "nl": "Logboek bouwen met bestaande data...",
        "fr": "Construction du carnet avec les données existantes...",
        "de": "Logbuch mit vorhandenen Daten erstellen...",
    },
    "log_not_implemented_yet": {
        # {feature} substituted at call time.
        "en": "{feature} tapped (not implemented yet)",
        "nl": "{feature} aangetikt (nog niet gebouwd)",
        "fr": "{feature} pressé (pas encore implémenté)",
        "de": "{feature} angetippt (noch nicht implementiert)",
    },
    "feature_publish": {
        "en": "Publish",
        "nl": "Publiceren",
        "fr": "Publier",
        "de": "Veröffentlichen",
    },
    "feature_boat_mode": {
        "en": "Boat mode",
        "nl": "Boot-modus",
        "fr": "Mode bateau",
        "de": "Boot-Modus",
    },
    "log_no_logbook_to_view": {
        "en": "No logbook to view yet -- download first.",
        "nl": "Nog geen logboek om te bekijken -- download eerst.",
        "fr": "Aucun carnet à afficher pour l'instant -- téléchargez d'abord.",
        "de": "Noch kein Logbuch zum Anzeigen -- zuerst herunterladen.",
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
