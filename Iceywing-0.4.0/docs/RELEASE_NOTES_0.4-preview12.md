# Iceywing 0.4 Preview12

Focus: fast, quiet, resumable project setup.

## Changes

- Added `iceywing up <project-path>`.
- Added environment fingerprints and external state caching.
- Healthy unchanged environments skip installation on repeat runs.
- Existing healthy environments are adopted without an unnecessary first reinstall.
- Added `iceywing up --fresh` and `--repair`.
- Added lightweight elapsed-time heartbeats for long silent tasks.
- `iceywing up` now prints total elapsed time.
- Improved no-project error with current path and a valid command example.
- Windows Setup uses standard pip without administrator permission first, with UAC fallback only on install failure.
- Installer removes the obsolete Preview7/8 user launcher after successful verification.

## Validation

- 18 Python tests passed.
- Wheel installed successfully in a clean virtual environment.
- `python -m iceywing --version` and `iceywing --version` both returned `0.4.0a12`.
- Incremental test: first setup executed once; second `up` skipped setup and completed in under one second in the test project.
