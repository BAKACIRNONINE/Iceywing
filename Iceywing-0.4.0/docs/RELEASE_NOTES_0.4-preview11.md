# Iceywing 0.4-preview11

Windows installer reliability fix.

- Cleans stale pip uninstall artifacts such as `~ceywing*` before and after install.
- Treats pip stderr warnings as diagnostics, not installation failure.
- Uses pip's exit code as the authoritative success/failure signal.
- Keeps the standard pip/wheel + CLI + `python -m iceywing` + Python API architecture.
