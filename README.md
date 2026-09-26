# My Sailing Logbook (iOS)

iOS counterpart to [mysailinglogbook-android](https://github.com/Ayuus/mysailinglogbook-android): syncs
voyage data from a boat's [Actisense W2K-2](https://actisense.com) NMEA 2000-to-WiFi gateway,
builds the same HTML sailing logbook the desktop [nmea2log](https://github.com/Ayuus/nmea2log)
CLI produces, shows it in-app, and (optionally) publishes it to a WordPress site or over SFTP --
same feature set as the Android app, same underlying `nmea2log` Python package, different
platform.

## Design principle: match the Android app exactly

Asked for explicitly: same icons, same logic, same everything as the Android app, wherever iOS
lets it be the same. The Android app's own README (its "Design choices worth knowing before
changing this code" section) and its UI/settings/boat-mode behavior are the reference to build
from -- not a fresh design. Only diverge from it where the platform genuinely forces a
difference (e.g. no Chaquopy equivalent, different notification/background-execution rules, a
UI toolkit that can't reproduce something pixel-for-pixel); anything that *can* match, should.

## Status

**Proof of concept confirmed working, real app not started yet.** Validated directly, on a
Scaleway Apple Silicon Mac mini, using [Briefcase](https://github.com/beeware/briefcase) (the
"officially supported" way to use Python-Apple-support -- generates and builds the Xcode project
for you, see its own `USAGE.md`):

- Xcode 26.5 + the iOS 26.5 Simulator runtime build and run a Briefcase-scaffolded app.
- `nmea2log` itself (zero third-party dependencies, `requires-python = ">=3.10"`) builds as a
  pure-Python wheel and **imports and runs correctly inside that app on the iOS Simulator** --
  confirmed on-screen, not just in the build log.
- Needed Python 3.14 specifically to match `nmea2log`'s own `requires-python` and Chaquopy's
  Python version on the Android side (installed via [uv](https://docs.astral.sh/uv/), no sudo
  needed on a fresh Mac instance -- Homebrew needs admin rights this account didn't have).
- One real gotcha, worth remembering: a fresh macOS instance with no one ever logged in at the
  GUI (only ever SSH'd into) could download the Simulator runtime but never got it past
  "Verifying" / registered as a usable `simctl` runtime -- logging in once via VNC/Screen Sharing
  fixed it. CoreSimulator (and likely other Xcode-adjacent frameworks) appear to need a real,
  logged-in Aqua session at least once, not just SSH access.

Not started yet: an actual UI, W2K-2 download, settings storage, publishing, boat mode -- the
proof of concept above only proves the toolchain itself works, not that the app is built.

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
