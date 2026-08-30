# Iceywing 0.4 Preview 21

Preview21 fixes the Windows installer fallback exposed by a Python 3.14.2
installation test.

- Removes automatic UAC elevation and the second PowerShell window.
- Retries a failed normal pip upgrade with `--user` in the original window when
  the Python user site is available.
- Uses the matching user scripts directory when verifying a user-scoped
  `iceywing.exe` launcher.
- Displays the real pip failure tail and log path in the original window if both
  attempts fail.
- Cleans stale pip artifacts in both the default and user site-packages paths.
- Selects only the wheel matching Preview21, so leftover wheels from an older
  extracted folder cannot be installed accidentally.
- Keeps native `Write-Progress` and the concise NeuroScape verification output
  introduced in Preview20.
