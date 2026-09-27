# My Sailing Logbook (iOS)

iOS counterpart to [mysailinglogbook-android](https://github.com/Ayuus/mysailinglogbook-android): syncs
voyage data from a boat's [Actisense W2K-2](https://actisense.com) NMEA 2000-to-WiFi gateway,
builds the same HTML sailing logbook the desktop [nmea2log](https://github.com/Ayuus/nmea2log)
CLI produces, shows it in-app, and (optionally) publishes it to a WordPress site or over SFTP --
same feature set as the Android app, same underlying `nmea2log` Python package, different
platform.

## Design principle: match the Android app exactly

Asked for explicitly: same icons (toolbar icons *and* the app/launcher icon itself, e.g. the
book-with-course-line design already used for `ic_launcher_foreground.xml` on Android), same
logic, same everything as the Android app, wherever iOS lets it be the same. The Android app's
own README (its "Design choices worth knowing before changing this code" section) and its
UI/settings/boat-mode behavior are the reference to build from -- not a fresh design. Only
diverge from it where the platform genuinely forces a difference (e.g. no Chaquopy equivalent,
different notification/background-execution rules, a
UI toolkit that can't reproduce something pixel-for-pixel); anything that *can* match, should.

## Status

**Real app, most of the toolbar wired up.** The `mysailinglogbook/` directory in this repo is
the actual [Briefcase](https://github.com/beeware/briefcase)/[Toga](https://github.com/beeware/toga)
app (`com.ayuus.mysailinglogbook`, same applicationId as Android):

- The toolbar has all 6 of Android's own buttons, in the same order (download, rebuild, publish,
  view logbook, boat mode, settings), using the same icon shapes as Android's own vector
  drawables (`ic_download_24`, `ic_refresh_24`, `ic_upload_24`, `ic_article_24`, `ic_sailboat_24`,
  `ic_settings_24`) -- rasterized from hand-written SVGs that reproduce Android's `pathData`
  verbatim, and the same tight, icon-only spacing (Settings pinned to the far right behind a
  flexible spacer, no visible text label -- tooltip text only, same as `iconButton()`).
- **Download/Rebuild**: call the same `nmea2log.android_entry.build_from_local_files()`/
  `sync_from_w2k2()` functions Android calls via Chaquopy -- plain Python calling Python here, no
  language boundary to cross. Runs on a background thread; UI updates marshal onto the main
  thread via `loop.call_soon_threadsafe()`.
- **View**: toggles the toolbar's content area between the log and a `toga.WebView` showing
  `logbook.html`, same `set_content(root_url, html)` technique as `loadLogbookIntoWebView()`, and
  the toolbar itself stays visible/usable throughout (including while a sync is running), matching
  `viewLocalLogbook()`'s own documented behavior.
- **Settings**: mirrors `SettingsActivity.kt` field-for-field (W2K-2 login, boat identity,
  publish method, boat-mode section, cache-clear buttons). iOS forces two adaptations, documented
  in `settings_screen.py`: no second `toga.Window` (iOS disallows one), so this swaps the single
  MainWindow's content in place instead; and `toga.Selection` (an iOS picker) instead of Android's
  RadioGroup/Spinner. Persisted as plain JSON in the sandbox (`settings_store.py`) rather than
  Android's EncryptedSharedPreferences -- no Keychain wiring yet, a real gap worth closing before
  this app handles anyone's data but the developer's own test credentials.
- Still placeholders: Publish (upload), Boat mode, and the app/launcher icon itself.
- `nmea2log` itself (zero third-party dependencies, `requires-python = ">=3.10"`) builds as a
  pure-Python wheel and **imports and runs correctly inside the app on the iOS Simulator**, and
  its full real pipeline (decode -> build trips -> write HTML) has been run against real archive
  folders from the developer's own boat.
- Needed Python 3.14 specifically to match `nmea2log`'s own `requires-python` and Chaquopy's
  Python version on the Android side (installed via [uv](https://docs.astral.sh/uv/), no sudo
  needed on a fresh Mac instance -- Homebrew needs admin rights this account didn't have).
- Real gotchas found in practice, worth remembering:
  - A fresh macOS instance with no one ever logged in at the GUI (only ever SSH'd into) could
    download the Simulator runtime but never got it past "Verifying" / registered as a usable
    `simctl` runtime -- logging in once via VNC/Screen Sharing fixed it. CoreSimulator (and likely
    other Xcode-adjacent frameworks) appear to need a real, logged-in Aqua session at least once,
    not just SSH access.
  - `briefcase build` does **not** re-copy changed Python source/resources into the app bundle by
    itself -- only `briefcase update` does that (`briefcase build` only refreshes app metadata and
    compiles the Xcode project). Editing `src/` and going straight to `briefcase build` silently
    runs the stale bundled code with no error; always `briefcase update` first when app content
    changed.
  - `briefcase run` **wipes the app's sandboxed Documents directory** (settings.json, any local
    `.ebl` archive, `logbook.html`, ...) on every single run -- its own log says why: "Uninstalling
    any existing app version" runs before every install, and an iOS uninstall deletes the whole
    data container, not just the binary. Confirmed in practice: a saved Settings screen and an 11GB
    test `.ebl` archive were both gone after one `briefcase run`. To iterate without losing test
    data, build with `briefcase build` as usual, then install/launch directly instead of through
    `briefcase run`: `xcrun simctl install booted <path/to/My Sailing Logbook.app>` followed by
    `xcrun simctl launch booted com.ayuus.mysailinglogbook` -- confirmed to preserve the existing
    Documents content across repeated installs, unlike `briefcase run`'s own uninstall-first
    behavior.

## How `nmea2log` runs on iOS (resolved)

[Python-Apple-support](https://github.com/beeware/Python-Apple-support) (BeeWare), used via
Briefcase -- see "Status" above. The alternatives considered but not needed:

- **[PythonKit](https://github.com/pvieito/PythonKit)** -- a nicer Swift-facing API over the
  embedded interpreter than the raw Python C API; worth adding later if writing directly against
  `Py_Initialize()`/the C API from Swift gets unwieldy, but not required to embed Python itself.
- Reimplementing the needed subset natively in Swift -- not needed; `nmea2log` imports as-is.

## Related repos

- [nmea2log](https://github.com/Ayuus/nmea2log) -- the shared Python core (decoding, trip
  building, HTML generation, desktop CLI).
- [mysailinglogbook-android](https://github.com/Ayuus/mysailinglogbook-android) -- the Android app this
  one mirrors; the reference for the overall app design (UI flow, settings, boat mode,
  publishing) even where the platform-specific implementation has to differ.
