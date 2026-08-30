# Iceywing 0.4 Preview 22

Preview22 fixes the Windows installer result handling exposed when pip reports
that the exact wheel version is already installed.

- Refreshes the completed PowerShell process and returns its exit code in a
  structured result, preventing an empty code from being rendered as a failure.
- Follows the established Poetry installer pattern: before invoking pip, checks
  whether the requested version is already installed and reports success when
  both the Python module and console launcher are healthy.
- Repeats those module and launcher checks as the final postcondition when pip's
  process result is unavailable or nonzero.
- Clears the native `Write-Progress` record before every durable `[OK]`,
  `[WARN]`, or `[FAIL]` line, preventing progress text from joining log output.
- Keeps installation in one window. An administrator run is mentioned only
  after the pip log explicitly reports a permission denial, and is never
  launched automatically.
- Adds a failing NeuroScape verification fixture that checks the exit code,
  useful output tail, and full log path are preserved.
- Locks `iceywing pop status` to read-only Git behavior: it reads only the local
  branch and working-tree state and cannot fetch, pull, switch, or create a
  branch.
