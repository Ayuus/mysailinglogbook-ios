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

**Texts:** the strings both apps share (boat-mode status lines, import log lines, settings labels, ...)
live in the nmea2log repo's `src/nmea2log/app_texts.py` -- `translations.py` here only holds what exists
on iOS alone and merges the shared ones in. Change a shared wording there once; the Android app's
`strings.xml` is generated from the same file, so the two cannot drift apart again.

## Status

**Real app; download/build/view/settings/appearance/language/publish/boat mode are all done and
working.** The `mysailinglogbook/` directory in this repo is
the actual [Briefcase](https://github.com/beeware/briefcase)/[Toga](https://github.com/beeware/toga)
app (`com.ayuus.mysailinglogbook`, same applicationId as Android):

- The toolbar has all 6 of Android's own buttons, in the same order (download, build, publish,
  view logbook, boat mode, settings), using the same icon shapes as Android's own vector
  drawables (`ic_download_24`, `ic_refresh_24`, `ic_upload_24`, `ic_article_24`, `ic_sailboat_24`,
  `ic_settings_24`) -- rasterized from hand-written SVGs that reproduce Android's `pathData`
  verbatim, and the same tight, icon-only spacing (Settings pinned to the far right behind a
  flexible spacer, no visible text label -- tooltip text only, same as `iconButton()`). Icons are
  tinted via UIKit's "always template" rendering mode (`_template_tint_icon()` in `app.py`) so
  they switch between black and white with Light/Dark mode the same way the title text next to
  them already does -- found in practice: left untinted, they render as solid black regardless of
  appearance, invisible against a dark toolbar.
- **Download/Build**: call the same `nmea2log.android_entry.build_from_local_files()`/
  `sync_from_w2k2()` functions Android calls via Chaquopy -- plain Python calling Python here, no
  language boundary to cross. Runs on a background thread; UI updates marshal onto the main
  thread via `loop.call_soon_threadsafe()`.
- **View**: toggles the toolbar's content area between the log and a `toga.WebView` showing
  `logbook.html`, same `set_content(root_url, html)` technique as `loadLogbookIntoWebView()`, and
  the toolbar itself stays visible/usable throughout (including while a sync is running), matching
  `viewLocalLogbook()`'s own documented behavior.
- **Settings**: mirrors `SettingsActivity.kt` field-for-field (W2K-2 login, boat identity,
  publish method, boat-mode section, cache-clear buttons, and an Appearance section -- see below).
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
- A real test suite (`tests/`, run via Briefcase's own `briefcase run iOS --test`) covers the pure
  logic: `network.py`'s private-IPv4 classification (mirrors Android's own
  `HotspotDetectorTest.kt`), `settings_store.py`, and `translations.py`.
- The app's own launcher/app icon matches Android's design exactly (navy `#0D3358` background,
  cream `#F5F1E6` book-with-course-line glyph) -- rendered from one shared SVG
  (`resources/icons-svg/app-icon.svg`) at every size Xcode's `AppIcon.appiconset` and
  `Splash.imageset` need (see "Real gotchas" below for how those sizes actually map).
- **Publish**: uploads the just-built logbook to a WordPress site over REST
  (`upload_via_rest()`, `_publish_logbook()` in `app.py`), same REST-preferred-over-SFTP choice as
  Android's own `LogbookPublisher.kt`. SFTP itself can't be ported to iOS at all (no
  `cryptography` wheel available for iOS), so picking it shows a clear "not supported" error
  instead of silently failing.
- **Boat mode**: drives the same `nmea2log.bootmode.BootModeMachine` state machine Android's own
  `BootModeController.kt`/`W2kBootExecutor.kt` drive (`boot_mode_controller.py`), foreground-only
  -- no background-service equivalent, no persisted state across an app close (see that file's own
  doc comment). The screen stays awake while it's active (`UIApplication.idleTimerDisabled`).
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

## Related repos

- [nmea2log](https://github.com/Ayuus/nmea2log) -- the shared Python core (decoding, trip
  building, HTML generation, desktop CLI).
- [mysailinglogbook-android](https://github.com/Ayuus/mysailinglogbook-android) -- the Android app this
  one mirrors; the reference for the overall app design (UI flow, settings, boat mode,
  publishing) even where the platform-specific implementation has to differ.
