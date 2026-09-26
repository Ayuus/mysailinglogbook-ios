# My Sailing Logbook (iOS)

iOS counterpart to [mysailinglogbook-android](https://github.com/Ayuus/mysailinglogbook-android): syncs
voyage data from a boat's [Actisense W2K-2](https://actisense.com) NMEA 2000-to-WiFi gateway,
builds the same HTML sailing logbook the desktop [nmea2log](https://github.com/Ayuus/nmea2log)
CLI produces, shows it in-app, and (optionally) publishes it to a WordPress site or over SFTP --
same feature set as the Android app, same underlying `nmea2log` Python package, different
platform.

## Status

**Nothing built yet.** This repo exists to hold the project once there's Mac hardware available to
build it on (Xcode is required; there is no way to build/sign an iOS app without it) -- see the
Android app's own README for the reasoning behind reusing `nmea2log`'s Python code directly rather
than reimplementing the NMEA 2000 decoding/trip-building/HTML-generation logic a second time.

## Open question: how does `nmea2log` run on iOS?

The Android app embeds real CPython via [Chaquopy](https://chaquo.com/chaquopy/), a Gradle
plugin -- there is no iOS equivalent of Chaquopy. Options to look into once work actually starts,
roughly in order of how well-trodden they are:

- **[Python-Apple-support](https://github.com/beeware/Python-Apple-support)** (BeeWare) -- builds
  CPython as an XCFramework for iOS; the toolchain BeeWare's own Briefcase and Kivy's `kivy-ios`
  both build on. Most likely starting point.
- **[PythonKit](https://github.com/pvieito/PythonKit)** -- Swift/Python interop layer, built on
  top of a Python runtime like the above rather than a replacement for it.
- Reimplement the needed subset natively in Swift instead of embedding Python at all -- the
  fallback if embedding CPython on iOS turns out to be impractical, at the cost of a second
  implementation of the decode/trip-building logic to keep in sync with the Python one by hand.

Whichever way this goes, the goal stays the same as the Android app's own: `nmea2log`'s Python
code is the single source of truth for the actual logbook logic, not something this repo
reimplements from scratch if it can be avoided.

## Related repos

- [nmea2log](https://github.com/Ayuus/nmea2log) -- the shared Python core (decoding, trip
  building, HTML generation, desktop CLI).
- [mysailinglogbook-android](https://github.com/Ayuus/mysailinglogbook-android) -- the Android app this
  one mirrors; a useful reference for the overall app design (UI flow, settings, boat mode,
  publishing) even where the platform-specific implementation has to differ.
