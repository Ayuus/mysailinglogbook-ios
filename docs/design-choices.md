# Notes for developers

What to know before changing this code. The README is the user manual; this is the part for whoever changes the app.

## Texts shared with the Android app

The strings both apps share (boat-mode status lines, import log lines, settings labels, ...)
live in the nmea2log repo's `src/nmea2log/app_texts.py` -- `translations.py` here only holds what exists
on iOS alone and merges the shared ones in. Change a shared wording there once; the Android app's
`strings.xml` is generated from the same file, so the two cannot drift apart again.

## Design choices worth knowing before changing this code

**Match the Android app exactly.** Asked for explicitly: same icons (toolbar icons *and* the app/launcher icon itself, e.g. the
book-with-course-line design already used for `ic_launcher_foreground.xml` on Android), same
logic, same everything as the Android app, wherever iOS lets it be the same. The Android app's
own [design notes](https://github.com/Ayuus/mysailinglogbook-android/blob/main/docs/design-choices.md) and its
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
