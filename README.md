# My Sailing Logbook (iOS)

iOS counterpart to [mysailinglogbook-android](https://github.com/Ayuus/mysailinglogbook-android): downloads
voyage data from a boat's [Actisense W2K-2](https://actisense.com) NMEA 2000-to-WiFi gateway,
assembles the same HTML sailing logbook the desktop [nmea2log](https://github.com/Ayuus/nmea2log)
CLI produces, shows it in-app, and (optionally) publishes it to a WordPress site --
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

**Texts:** the strings both apps share (boat-mode status lines, import log lines, settings labels, ...)
live in the nmea2log repo's `src/nmea2log/app_texts.py` -- `translations.py` here only holds what exists
on iOS alone and merges the shared ones in. Change a shared wording there once; the Android app's
`strings.xml` is generated from the same file, so the two cannot drift apart again.

## Status

**Real app; download/assemble/view/settings/appearance/language/publish/boat mode are all done and
working.** The `mysailinglogbook/` directory in this repo is
the actual [Briefcase](https://github.com/beeware/briefcase)/[Toga](https://github.com/beeware/toga)
app (`com.ayuus.mysailinglogbook`, same applicationId as Android):

- The toolbar has all 7 of Android's own buttons, in the same order (download, import, assemble, publish,
  view logbook, boat mode, settings), using the same icon shapes as Android's own vector
  drawables (download, folder-download, refresh, upload, article, sailboat, settings; the SVGs are in
  `resources/icons-svg/`) -- rasterized from hand-written SVGs that reproduce Android's `pathData`
  verbatim, and the same tight, icon-only spacing (Settings pinned to the far right behind a
  flexible spacer, no visible text label -- tooltip text only, same as `iconButton()`). Icons are
  tinted via UIKit's "always template" rendering mode (`_template_tint_icon()` in `app.py`) so
  they switch between black and white with Light/Dark mode the same way the title text next to
  them already does -- found in practice: left untinted, they render as solid black regardless of
  appearance, invisible against a dark toolbar.
- **Download/Assemble**: call the same `nmea2log.android_entry.build_from_local_files()`/
  `sync_from_w2k2()` functions Android calls via Chaquopy -- plain Python calling Python here, no
  language boundary to cross. Runs on a background thread; UI updates marshal onto the main
  thread via `loop.call_soon_threadsafe()`.
- **View**: toggles the toolbar's content area between the log and a `toga.WebView` showing
  `logbook.html`, same `set_content(root_url, html)` technique as `loadLogbookIntoWebView()`, and
  the toolbar itself stays visible/usable throughout (including while a download or assemble is running), matching
  `viewLocalLogbook()`'s own documented behavior.
- **Settings**: mirrors `SettingsActivity.kt` field-for-field (W2K-2 login, boat identity,
  publish method, boat-mode section, cache-clear buttons, a **Delete** button for the local `.ebl`
  files (counts them, asks for confirmation with the number and size, then deletes them and the empty
  folders; `nmea2log.ebl_storage`, shared with the Android app) and an Appearance section -- see below).
  iOS forces two adaptations, documented in `settings_screen.py`: no second `toga.Window` (iOS
  disallows one), so this swaps the single MainWindow's content in place instead; and
  `toga.Selection` (an iOS picker) instead of Android's RadioGroup/Spinner. Persisted as plain
  JSON in the sandbox (`settings_store.py`) rather than Android's EncryptedSharedPreferences -- no
  Keychain wiring yet, a real gap worth closing before this app handles anyone's data but the
  developer's own test credentials.
- **Multilingual** (nl/en/fr/de), same four languages the generated HTML logbook and the Android
  app both support: `translations.py` mirrors Android's `strings.xml` wording where the two
  overlap, `detect_system_language()` picks the phone's own language (via `NSLocale`, rubicon-objc)
  falling back to English, same as Android's own resource-qualifier fallback.
- **Appearance**: Light/Dark/Follow device, set in Settings and applied immediately via
  `UIWindow.overrideUserInterfaceStyle` (`apply_theme_mode()` in `app.py`) -- same three-way choice
  Android's own `AppCompatDelegate`-based setting offers. One real platform gap, not fixable from
  here: the native Launch Screen (shown before Python even starts, so before this setting is ever
  read) can only follow the *phone's* own Light/Dark setting, via `systemColor="systemBackgroundColor"`
  in `Launch Screen.storyboard` -- it cannot honor the in-app override for that one brief frame.
  Android has the same limitation for its own splash screen, for the same underlying reason (the OS
  draws it before any app code runs).
- A real test suite (`tests/`) covers the pure logic: `network.py`'s private-IPv4 classification (mirrors
  Android's own `HotspotDetectorTest.kt`), `settings_store.py`, `translations.py`, the boat-mode controller (with
  stand-ins for the iOS calls) and `handlers.py`. Run it with pytest (the iOS classes it needs come from
  `rubicon-objc`, which imports on a Mac); the two tests in `test_app.py` need UIKit itself and only pass on an
  iPhone or in the Simulator.
- The app's own launcher/app icon matches Android's design exactly (navy `#0D3358` background,
  cream `#F5F1E6` book-with-course-line glyph) -- rendered from one shared SVG
  (`resources/icons-svg/app-icon.svg`) at every size Xcode's `AppIcon.appiconset` and
  `Splash.imageset` need (see "Real gotchas" below for how those sizes actually map).
- **Publish**: uploads the just-built logbook to a WordPress site over REST
  (`upload_via_rest()`, `_publish_logbook()` in `app.py`), the same as Android's own
  `LogbookPublisher.kt`. WordPress is the only publish destination in both apps.
- **Boat mode**: drives the same `nmea2log.bootmode.BootModeMachine` state machine Android's own
  `BootModeController.kt`/`W2kBootExecutor.kt` drive (`boot_mode_controller.py`). iOS has no
  foreground service, so there are two ways it runs:
  - In the foreground it runs on timers, as before; the screen stays awake while it's active
    (`UIApplication.idleTimerDisabled`).
  - In the background iOS runs a `BGProcessingTask` **when iOS decides to** (some time after the time the
    machine asked for -- possibly hours later, not at all in Low Power Mode): the machine gets a `Resume`
    event, does what is due (look for the W2K-2, download and assemble, publish) and asks for the next task. A
    local notification tells what happened. The machine's state is persisted after every step
    (`boot_mode_state.json`), so a task that starts a fresh process, or opening the app again, carries on
    where it was -- and every time the app becomes active it tries right away. The log then says what came of it,
    in one short line: the W2K-2 is not reachable from this network (and when the next try is), reachable with
    nothing new, or a round that starts as usual. When the planned round was missed, a line says so first.
  Rounds in the background are best effort (how often is iOS's choice); there is no location access on
  purpose. The Info.plist keys (`UIBackgroundModes: processing`, `BGTaskSchedulerPermittedIdentifiers`,
  `NSLocalNetworkUsageDescription`) are in `pyproject.toml`; `briefcase update` does not copy them into an
  existing generated Xcode project (only `briefcase create` does), so add them to
  `build/.../xcode/MySailingLogbook/MySailingLogbook-Info.plist` by hand when that project already exists.
  Background tasks do not run in the Simulator; to try one on a device, pause in Xcode and run
  `e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.ayuus.mysailinglogbook.boatmode"]`.
- `nmea2log` itself (zero third-party dependencies, `requires-python = ">=3.10"`) builds as a
  pure-Python wheel and **imports and runs correctly inside the app on the iOS Simulator**, and
  its full real pipeline (decode -> build trips -> write HTML) has been run against real archive
  folders from the developer's own boat.
- Runs on Python 3.14, the version Chaquopy bundles on the Android side (`nmea2log` itself only requires
  `>=3.10`); Briefcase and the tests are run through [uv](https://docs.astral.sh/uv/) with `--python 3.14`, no sudo
  needed on a fresh Mac instance -- Homebrew needs admin rights this account didn't have.
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
    changed. The same goes for Xcode's own Run: it compiles the Xcode project as it is, so Python changes
    reach the iPhone only through `briefcase update`. And a change in `nmea2log` (a new module, say) needs
    `briefcase update iOS -r`, which reinstalls the requirements; without `-r` the bundled copy of `nmea2log`
    stays old and the app can fail on import.
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
  - That same plain `xcrun simctl install` (no prior uninstall) is exactly what silently serves
    **stale compiled resources** when only images/icons/the asset catalog changed, not Python
    source -- found in practice chasing why a freshly rebuilt app icon and Launch Screen kept
    showing Briefcase's default bee mascot. CoreSimulator appears to treat "same bundle ID already
    installed" as a reason to skip actually replacing the on-disk app bundle, even though
    `simctl install` prints no warning that it did so. `assetutil -I` on the freshly built
    `Assets.car` will show the *correct*, new renditions even while the *installed* copy on the
    simulator still renders the old ones -- that mismatch is the tell. Fix: `xcrun simctl
    uninstall com.ayuus.mysailinglogbook` before `simctl install` whenever anything in
    `Images.xcassets` (icons, the launch screen's image) changed -- which, per the point above,
    also wipes Documents, so re-seed test data afterward.
  - A named/custom **Dark Mode color asset** (an `Images.xcassets` colorset with an "Any" +
    "Dark" appearance pair, referenced from a storyboard as `<color key="..." name="MyColor"/>`)
    compiled correctly (confirmed via `assetutil -I`, both renditions present) and was correctly
    referenced in the compiled `.nib` (confirmed via `strings`), but never actually resolved to
    its Dark variant on the Simulator's Launch Screen, regardless of uninstall/reinstall, snapshot
    cache clearing (`~/Library/.../Library/SplashBoard/Snapshots`), or a full `simctl shutdown`
    + `boot`. A plain **system color** (`<color key="backgroundColor"
    systemColor="systemBackgroundColor"/>`) resolved correctly on the very first try. Root cause
    unconfirmed -- possibly a Simulator-specific limitation of custom named colors specifically in
    a *Launch Screen* storyboard, as opposed to a normal app screen (where a custom named color,
    untested here, may well work fine). Prefer a system color for anything Launch-Screen-related;
    don't assume a custom color asset that compiles cleanly also *resolves* correctly there.

## How `nmea2log` runs on iOS (resolved)

[Python-Apple-support](https://github.com/beeware/Python-Apple-support) (BeeWare), used via
Briefcase -- see "Status" above. The alternatives considered but not needed:

- **[PythonKit](https://github.com/pvieito/PythonKit)** -- a nicer Swift-facing API over the
  embedded interpreter than the raw Python C API; worth adding later if writing directly against
  `Py_Initialize()`/the C API from Swift gets unwieldy, but not required to embed Python itself.
- Reimplementing the needed subset natively in Swift -- not needed; `nmea2log` imports as-is.

## Backing up your data

What is worth keeping is the **`.ebl` archive**: the logbook and the caches are rebuilt from it with one tap on
assemble.

- **The archive** is the folder `Documents/Actisense/` of the app. The app enables file sharing, so it shows in the
  **Files** app (On My iPhone > My Sailing Logbook > Actisense) and in Finder over USB (select the iPhone > Files). The
  simplest cloud backup: in Files, copy the folder to **iCloud Drive**, or to OneDrive, Dropbox or Google Drive once
  their apps are installed. Do it after every trip or season, and **before** you use Settings > Local .ebl files >
  Delete.
- **Restoring**: copy the folder back into the app's folder in Files (or Finder) and tap assemble. The first assemble
  takes longer, as the caches are rebuilt too.
- **The settings** are `Documents/settings.json` in the same place, **with the W2K-2 and WordPress passwords in plain
  text**: keep that file out of cloud folders you do not fully trust. Typing the logins in again after a restore (from a
  password manager) is the safe way.
- **The iPhone's own backup** (iCloud, or Finder on a Mac) includes the app's Documents folder unless you have switched
  it off, so a restored phone gets the archive and the settings back. The archive can be several GB, more than what is
  left of the 5 GB of free iCloud space next to everything else: buy more space, or switch this app off in iPhone
  Settings > your name > iCloud > Manage Account Storage > Backups.
- **The built logbook** is also on your WordPress site when you publish.

## The log file

The app's log (every level, also the debug lines the log view does not show) is `Documents/nmea2log.log`: visible in
the Files app (On My iPhone > My Sailing Logbook) and Finder over USB. 30 days of lines are kept (pruned when a run
starts) and there is no size limit; with the boat mode on, each round's download adds a debug line per file the W2K-2
holds. Details: [nmea2log/docs/log-file.md](https://github.com/Ayuus/nmea2log/blob/main/docs/log-file.md).

## Screenshots

Taken in the simulator in English, with the fictional trips of the demo logbook (a made-up boat, "Sea Swallow", not a
real one) -- generated with `examples/generate_demo_logbook.py` in the
[nmea2log](https://github.com/Ayuus/nmea2log) repo.

<p>
<img src="docs/screenshots/logbook.png" width="230" alt="The logbook">
<img src="docs/screenshots/run.png" width="230" alt="After an assemble: the logbook with the log as a strip above it">
<img src="docs/screenshots/log.png" width="230" alt="The log">
</p>

*The logbook (what the phone shows when it is opened) -- after an assemble, the logbook with the log as a strip above it
-- the log (tap the log button).*

<p>
<img src="docs/screenshots/map-trip.png" width="230" alt="The map of one trip, opened from the Map button in the trip list">
<img src="docs/screenshots/trip-log.png" width="230" alt="The log of one trip, opened from the Log button">
<img src="docs/screenshots/map-overview.png" width="230" alt="The overview map of the year, opened from the Overview link">
</p>

*The maps in the logbook (OpenStreetMap): the **Map** button of a trip shows its route -- its **Log** button the positions, course and speed along the way, with the water temperature and the boat's motion -- the **Overview** link of a year puts all trips of that year on one map.*

<p>
<img src="docs/screenshots/settings.png" width="230" alt="Settings: W2K-2, boat, trips, publish">
<img src="docs/screenshots/settings-more.png" width="230" alt="Settings: boat mode, appearance, clearing the caches">
<img src="docs/screenshots/boat-mode.png" width="230" alt="Boat mode on: the filled sailboat button and its status in the log">
</p>

*Settings (top and bottom) -- boat mode on: the sailboat button is filled and the log reports what it is doing.*

## Related repos

- [nmea2log](https://github.com/Ayuus/nmea2log) -- the shared Python core (decoding, trip
  building, HTML generation, desktop CLI).
- [mysailinglogbook-android](https://github.com/Ayuus/mysailinglogbook-android) -- the Android app this
  one mirrors; the reference for the overall app design (UI flow, settings, boat mode,
  publishing) even where the platform-specific implementation has to differ.
