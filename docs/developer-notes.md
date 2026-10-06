# Notes for developers

What to know before changing this code. The README is the user manual; this is the part for whoever changes the app.

## How it fits together

The app is a Briefcase/Toga app (`com.ayuus.mysailinglogbook`, the same applicationId as Android) that calls the same
`nmea2log` functions the Android app calls via Chaquopy -- here as plain Python calling Python:

```
MySailingLogbook (manual download + auto-start on launch)
  -> network.detect_subnet_prefix()   network detection: finds the phone's own private-network subnet
  -> android_entry.sync_from_w2k2()   [plain call into the real nmea2log package]
       -> w2k2_download.discover_w2k2()   scans that subnet for the W2K-2's HTTP API
       -> w2k2_download.download_file()    downloads new/changed .ebl files
       -> run_pipeline()                  decode -> build_trips -> write_html_logbook()
  -> WebView shows the resulting logbook.html
  -> upload_via_rest() (optional)     publishes logbook.html to WordPress
```

The app calls these actions **download**, **assemble**, **publish** and **import**. Some names in the code still say sync
or build (`sync_from_w2k2()`, `build_from_local_files()`): they are identifiers, not wording, and are not changed for the
sake of it.

What each part does on iOS:

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
  `Splash.imageset` need (see the gotchas below for how those sizes actually map).
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

### How `nmea2log` runs on iOS (resolved)

[Python-Apple-support](https://github.com/beeware/Python-Apple-support) (BeeWare), used via
Briefcase -- see the list above. The alternatives considered but not needed:

- **[PythonKit](https://github.com/pvieito/PythonKit)** -- a nicer Swift-facing API over the
  embedded interpreter than the raw Python C API; worth adding later if writing directly against
  `Py_Initialize()`/the C API from Swift gets unwieldy, but not required to embed Python itself.
- Reimplementing the needed subset natively in Swift -- not needed; `nmea2log` imports as-is.

## Texts shared with the Android app

The strings both apps share (boat-mode status lines, import log lines, settings labels, ...)
live in the nmea2log repo's `src/nmea2log/app_texts.py` -- `translations.py` here only holds what exists
on iOS alone and merges the shared ones in. Change a shared wording there once; the Android app's
`strings.xml` is generated from the same file, so the two cannot drift apart again.

## Design choices worth knowing before changing this code

**Match the Android app exactly.** Asked for explicitly: same icons (toolbar icons *and* the app/launcher icon itself, e.g. the
book-with-course-line design already used for `ic_launcher_foreground.xml` on Android), same
logic, same everything as the Android app, wherever iOS lets it be the same. The Android app's
own [design notes](https://github.com/Ayuus/mysailinglogbook-android/blob/main/docs/developer-notes.md) and its
UI/settings/boat-mode behavior are the reference to build from -- not a fresh design. Only
diverge from it where the platform genuinely forces a difference (e.g. no Chaquopy equivalent,
different notification/background-execution rules, a
UI toolkit that can't reproduce something pixel-for-pixel); anything that *can* match, should.

Real gotchas found in practice, worth remembering:

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
