# Iceywing 0.4 Preview 26

Preview26 fixes the self-contained Windows release archive.

## Fixed

- Release ZIPs now include the exact same-version installer wheel under `dist/`, so `Setup.bat` can install directly from an extracted release.
- Other local `dist/` artifacts remain excluded from the source ZIP.
- The missing-wheel error no longer contains the stale hard-coded `Preview23` wording.
- Added a release-archive contract test that opens the final ZIP and verifies the installer wheel is present at the path expected by `bootstrap.ps1`.

## Release automation

The built-in `iceywing release preview` flow from Preview25 remains unchanged, but the ZIP it uploads is now directly installable on Windows.
