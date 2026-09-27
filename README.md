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

**Real app started: toolbar skeleton with Android's own icons, working and running.** The
`mysailinglogbook/` directory in this repo is the actual [Briefcase](https://github.com/beeware/briefcase)/[Toga](https://github.com/beeware/toga)
app (`com.ayuus.mysailinglogbook`, same applicationId as Android), not just a proof of concept
anymore:

- The toolbar has all 6 of Android's own buttons, in the same order (download, rebuild, publish,
  view logbook, boat mode, settings), using the same icon shapes as Android's own vector
  drawables (`ic_download_24`, `ic_refresh_24`, `ic_upload_24`, `ic_article_24`, `ic_sailboat_24`,
  `ic_settings_24`) -- rasterized from hand-written SVGs that reproduce Android's `pathData`
  verbatim. Icon-only, no visible text label, same as Android's own `iconButton()` toolbar
  (tooltip text only) -- confirmed on-screen on the iOS Simulator (iPhone 17, iOS 26.5).
- Button handlers are still placeholders (`"not implemented yet"` log lines) -- real logic
  mirroring `MainActivity.kt`'s `runSync()`/`buildFromLocalFilesAndMaybePublish()`/`runPublish()`/
  `viewLocalLogbook()`/boat-mode toggle/Settings screen comes next.
- `nmea2log` itself (zero third-party dependencies, `requires-python = ">=3.10"`) builds as a
  pure-Python wheel and **imports and runs correctly inside the app on the iOS Simulator** --
  confirmed on-screen, not just in the build log.
- Needed Python 3.14 specifically to match `nmea2log`'s own `requires-python` and Chaquopy's
  Python version on the Android side (installed via [uv](https://docs.astral.sh/uv/), no sudo
  needed on a fresh Mac instance -- Homebrew needs admin rights this account didn't have).
- Two real gotchas, worth remembering:
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

Not started yet: W2K-2 download, settings storage, publishing, boat mode, the app/launcher icon
itself -- only the toolbar skeleton and its icons are done so far.

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
