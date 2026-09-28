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
    "section_w2k2_boat": {
        "en": "W2K-2 & boat",
        "nl": "W2K-2 & boot",
        "fr": "W2K-2 et bateau",
        "de": "W2K-2 & Boot",
    },
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
        "en": "Download automatically on launch",
        "nl": "Automatisch downloaden bij starten",
        "fr": "Télécharger automatiquement au démarrage",
        "de": "Beim Start automatisch herunterladen",
    },
    "checkbox_show_password": {
        "en": "Show password",
        "nl": "Wachtwoord tonen",
        "fr": "Afficher le mot de passe",
        "de": "Passwort anzeigen",
    },
    "section_trips": {
        "en": "Trips",
        "nl": "Reizen",
        "fr": "Trajets",
        "de": "Fahrten",
    },
    "label_min_stop_minutes": {
        "en": "Minimum stop duration to count\nas a port visit (minutes)",
        "nl": "Minimale stop-tijd om als\nhavenbezoek te tellen (minuten)",
        "fr": "Durée d'arrêt minimale pour\ncompter comme escale (minutes)",
        "de": "Mindeststandzeit, um als\nHafenbesuch zu zählen (Minuten)",
    },
    "checkbox_auto_publish_after_build": {
        "en": "Publish automatically after assembling",
        "nl": "Automatisch publiceren na samenstellen",
        "fr": "Publier automatiquement après l'assemblage",
        "de": "Nach dem Zusammenstellen automatisch veröffentlichen",
    },
    "section_publish": {
        "en": "Publish",
        "nl": "Publiceren",
        "fr": "Publier",
        "de": "Veröffentlichen",
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
        "en": "WordPress site address",
        "nl": "WordPress-siteadres",
        "fr": "Adresse du site WordPress",
        "de": "WordPress-Website-Adresse",
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
        "en": "SFTP host key fingerprint (optional;\nempty = trust automatically on first\nconnection)",
        "nl": "SFTP host-key fingerprint (optioneel;\nleeg = automatisch vertrouwen bij\neerste verbinding)",
        "fr": "Empreinte de clé hôte SFTP\n(facultatif ; vide = faire confiance\nautomatiquement à la première\nconnexion)",
        "de": "SFTP-Hostschlüssel-Fingerabdruck\n(optional; leer = bei erster\nVerbindung automatisch vertrauen)",
    },
    "section_boat_mode": {
        "en": "Boat mode",
        "nl": "Boot-modus",
        "fr": "Mode bateau",
        "de": "Boot-Modus",
    },
    "label_boat_interval": {
        "en": "A round (download + assemble) every",
        "nl": "Een ronde (downloaden + samenstellen) elke",
        "fr": "Une ronde (télécharger + assembler) toutes les",
        "de": "Eine Runde (Herunterladen + Zusammenstellen) alle",
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
        "en": "Final round once the boat is in harbour",
        "nl": "Laatste ronde zodra de boot in de haven ligt",
        "fr": "Dernière ronde dès que le bateau est au port",
        "de": "Letzte Runde, sobald das Boot im Hafen liegt",
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
        "en": "Turn off after final round",
        "nl": "Uitzetten na laatste ronde",
        "fr": "Désactiver après la dernière ronde",
        "de": "Nach letzter Runde ausschalten",
    },
    "checkbox_boat_auto_start": {
        "en": "Start automatically on launch",
        "nl": "Automatisch starten bij openen",
        "fr": "Démarrer automatiquement au lancement",
        "de": "Automatisch starten beim Öffnen",
    },
    "boat_status_searching": {
        "en": "Boat mode: looking for the W2K-2...",
        "nl": "Boot-modus: op zoek naar de W2K-2...",
        "fr": "Mode bateau : recherche du W2K-2...",
        "de": "Boot-Modus: Suche nach dem W2K-2...",
    },
    "boat_status_round_started": {
        "en": "Boat mode: round started (download and assemble)...",
        "nl": "Boot-modus: ronde gestart (downloaden en samenstellen)...",
        "fr": "Mode bateau : tour démarré (téléchargement et assemblage)...",
        "de": "Boot-Modus: Runde gestartet (Download und Zusammenstellen)...",
    },
    "boat_status_round_done": {
        # {time} substituted at call time.
        "en": "Boat mode: round done, next round at {time}.",
        "nl": "Boot-modus: ronde klaar, volgende ronde om {time}.",
        "fr": "Mode bateau : tour terminé, prochain tour à {time}.",
        "de": "Boot-Modus: Runde abgeschlossen, nächste Runde um {time}.",
    },
    "boat_status_round_failed": {
        "en": "Boat mode: round failed, trying again.",
        "nl": "Boot-modus: ronde mislukt, wordt opnieuw geprobeerd.",
        "fr": "Mode bateau : tour échoué, nouvelle tentative en cours.",
        "de": "Boot-Modus: Runde fehlgeschlagen, wird erneut versucht.",
    },
    "boat_status_w2k2_not_found_retry": {
        # {time} substituted at call time.
        "en": "Boat mode: W2K-2 not reachable, trying again at {time}.",
        "nl": "Boot-modus: W2K-2 niet bereikbaar, nieuwe poging om {time}.",
        "fr": "Mode bateau : W2K-2 injoignable, nouvelle tentative à {time}.",
        "de": "Boot-Modus: W2K-2 nicht erreichbar, nächster Versuch um {time}.",
    },
    "boat_status_harbour_final": {
        "en": "Boat mode: the boat is in harbour, final round.",
        "nl": "Boot-modus: de boot ligt in de haven, laatste ronde.",
        "fr": "Mode bateau : le bateau est au port, dernier tour.",
        "de": "Boot-Modus: das Boot liegt im Hafen, letzte Runde.",
    },
    "boat_status_left_boat": {
        "en": "Boat mode: left the boat (W2K-2 gone), final round.",
        "nl": "Boot-modus: de boot verlaten (W2K-2 weg), laatste ronde.",
        "fr": "Mode bateau : bateau quitté (W2K-2 disparu), dernier tour.",
        "de": "Boot-Modus: Boot verlassen (W2K-2 weg), letzte Runde.",
    },
    "boat_status_left_boat_nothing": {
        "en": "Boat mode: left the boat, nothing new to publish.",
        "nl": "Boot-modus: de boot verlaten, niets nieuws te publiceren.",
        "fr": "Mode bateau : bateau quitté, rien de nouveau à publier.",
        "de": "Boot-Modus: Boot verlassen, nichts Neues zu veröffentlichen.",
    },
    "boat_status_waiting_in_port": {
        # {time} substituted at call time.
        "en": "Boat mode: waiting in port, next check at {time}.",
        "nl": "Boot-modus: wachten in de haven, volgende controle om {time}.",
        "fr": "Mode bateau : attente au port, prochaine vérification à {time}.",
        "de": "Boot-Modus: warte im Hafen, nächste Prüfung um {time}.",
    },
    "boat_status_publish_started": {
        "en": "Boat mode: publishing...",
        "nl": "Boot-modus: publiceren...",
        "fr": "Mode bateau : publication...",
        "de": "Boot-Modus: wird veröffentlicht...",
    },
    "boat_status_publish_ok": {
        "en": "Boat mode: published.",
        "nl": "Boot-modus: gepubliceerd.",
        "fr": "Mode bateau : publié.",
        "de": "Boot-Modus: veröffentlicht.",
    },
    "boat_status_publish_failed": {
        # {time} substituted at call time.
        "en": "Boat mode: publishing failed, trying again at {time}.",
        "nl": "Boot-modus: publiceren mislukt, nieuwe poging om {time}.",
        "fr": "Mode bateau : échec de la publication, nouvelle tentative à {time}.",
        "de": "Boot-Modus: Veröffentlichung fehlgeschlagen, nächster Versuch um {time}.",
    },
    "boat_status_stopped": {
        "en": "Boat mode stopped.",
        "nl": "Boot-modus gestopt.",
        "fr": "Mode bateau arrêté.",
        "de": "Boot-Modus gestoppt.",
    },
    "tooltip_boat_mode_on": {
        "en": "Stop boat mode",
        "nl": "Boot-modus stoppen",
        "fr": "Arrêter le mode bateau",
        "de": "Boot-Modus stoppen",
    },
    "section_appearance": {
        "en": "Appearance",
        "nl": "Weergave",
        "fr": "Apparence",
        "de": "Darstellung",
    },
    "radio_theme_light": {
        "en": "Light",
        "nl": "Licht",
        "fr": "Clair",
        "de": "Hell",
    },
    "radio_theme_dark": {
        "en": "Dark",
        "nl": "Donker",
        "fr": "Sombre",
        "de": "Dunkel",
    },
    "radio_theme_system": {
        "en": "Follow device",
        "nl": "Apparaat volgen",
        "fr": "Suivre l'appareil",
        "de": "Gerät folgen",
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
        "en": "Deletes the decode/trip cache. The next download or assembly will re-decode every "
        ".ebl file from scratch (slower, no data lost).",
        "nl": "Verwijdert de decode-/reizencache. De volgende download of samenstelling decodeert elk "
        ".ebl-bestand opnieuw vanaf nul (langzamer, geen dataverlies).",
        "fr": "Supprime le cache de décodage/trajets. Le prochain téléchargement ou le prochain "
        "assemblage redécodera chaque fichier .ebl depuis le début (plus lent, aucune "
        "perte de données).",
        "de": "Löscht den Decodier-/Fahrten-Cache. Der nächste Download oder die nächste Zusammenstellung decodiert "
        "jede .ebl-Datei von Grund auf neu (langsamer, kein Datenverlust).",
    },
    "dialog_clear_places_cache_message": {
        "en": "Deletes the place-name/weather/marine lookup cache. The next download or assembly "
        "will re-fetch every lookup (slower, no data lost).",
        "nl": "Verwijdert de cache voor plaatsnamen/weer/getijden. De volgende download of "
        "samenstelling haalt elke opzoeking opnieuw op (langzamer, geen dataverlies).",
        "fr": "Supprime le cache des noms de lieux/météo/marine. Le prochain téléchargement ou "
        "le prochain assemblage récupérera chaque recherche à nouveau (plus lent, "
        "aucune perte de données).",
        "de": "Löscht den Cache für Ortsnamen/Wetter/Gezeiten. Der nächste Download oder die nächste Zusammenstellung "
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
        "en": "An assembly is already running.",
        "nl": "Er loopt al een samenstelactie.",
        "fr": "Un assemblage est déjà en cours.",
        "de": "Es läuft bereits eine Zusammenstellung.",
    },
    "log_fill_w2k2_credentials": {
        "en": "Fill in the W2K-2 username and password via Settings first.",
        "nl": "Vul eerst de W2K-2 gebruikersnaam en het wachtwoord in via Instellingen.",
        "fr": "Renseignez d'abord le nom d'utilisateur et le mot de passe W2K-2 via les Paramètres.",
        "de": "Geben Sie zuerst den W2K-2-Benutzernamen und das Passwort über die Einstellungen ein.",
    },
    "log_boat_busy": {
        "en": "Boat mode is busy with a round or a publish; try again in a moment.",
        "nl": "Boot-modus is bezig met een ronde of publicatie; probeer het zo weer.",
        "fr": "Le mode bateau est occupé avec un tour ou une publication ; réessayez dans un instant.",
        "de": "Der Boot-Modus ist mit einer Runde oder einer Veröffentlichung beschäftigt; versuche es gleich noch einmal.",
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
    "log_publish_already_running": {
        "en": "A publish is already running.",
        "nl": "Er loopt al een publicatie.",
        "fr": "Une publication est déjà en cours.",
        "de": "Es läuft bereits eine Veröffentlichung.",
    },
    "log_fill_publish_settings": {
        "en": "Fill in the publish settings (WordPress) via Settings first.",
        "nl": "Vul eerst de publiceer-instellingen (WordPress) in via Instellingen.",
        "fr": "Renseignez d'abord les paramètres de publication (WordPress) dans les Paramètres.",
        "de": "Trage zuerst die Veröffentlichungseinstellungen (WordPress) in den Einstellungen ein.",
    },
    "status_uploading_wordpress": {
        "en": "Uploading (to WordPress)...",
        "nl": "Uploaden (naar WordPress)...",
        "fr": "Envoi (vers WordPress)...",
        "de": "Wird hochgeladen (zu WordPress)...",
    },
    "log_upload_ok_wordpress": {
        # {url} substituted at call time.
        "en": "Uploaded to WordPress: {url}",
        "nl": "Geüpload naar WordPress: {url}",
        "fr": "Envoyé vers WordPress : {url}",
        "de": "Zu WordPress hochgeladen: {url}",
    },
    "log_upload_failed_wordpress": {
        # {error} substituted at call time.
        "en": "upload to WordPress failed: {error}",
        "nl": "upload naar WordPress mislukt: {error}",
        "fr": "l'envoi vers WordPress a échoué : {error}",
        "de": "Hochladen zu WordPress fehlgeschlagen: {error}",
    },
    "log_upload_not_configured": {
        "en": "Upload not configured",
        "nl": "Upload niet ingesteld",
        "fr": "Envoi non configuré",
        "de": "Upload nicht konfiguriert",
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
