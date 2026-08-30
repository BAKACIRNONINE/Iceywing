# Iceywing 0.4 Preview 19

Preview 19 makes self-test cleanup best-effort instead of treating temporary-directory deletion as a product failure.

- Cleanup is no longer counted as a capability test stage.
- A successful self-test remains successful if Windows briefly keeps a temp directory locked.
- Retained temp artifacts are reported as a warning with their path for later debugging.
- Failed checks retain their isolated artifacts and report the path alongside the primary failure.
- `iceywing self-test --keep-temp` intentionally preserves artifacts.
- JSON output reports `temp_retained` and `temp_path`.

This follows the same principle used by mature test runners: preserve the primary test result and treat cleanup as housekeeping/debug support.
