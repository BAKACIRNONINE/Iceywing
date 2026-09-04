# IceyWing clean setup

IceyWing requires Python 3.11 or newer.

## Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
just doctor
just test
just verify
```

If `py` is unavailable, use `python` instead.

## macOS / Linux shell

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
just doctor
just test
just verify
```

## Expected test chain

`just test` is the authoritative test entrypoint and runs:

```bash
python -m pytest
```

`just verify` runs compile validation first, then the authoritative test chain:

```bash
python -m compileall -q src tests
just test
```

## Common failures

- Python is too old: install Python 3.11 or newer.
- `just` is missing: install `just`, then rerun `just doctor`.
- `pytest` is missing: reinstall with `python -m pip install -e ".[test]"`.
- Editable install fails: upgrade pip and confirm you are in the repository root.
- Windows activation is blocked: run the venv Python directly with `.\.venv\Scripts\python.exe`, or adjust PowerShell execution policy for the current user.
- Old unittest/pytest mismatch: `just test` should now use pytest directly.

## Pytest temporary directory

IceyWing configures pytest to use `.pytest-tmp` as its temporary base.
This avoids Windows user-temp permission problems such as
`PermissionError: pytest-of-<user>` while keeping generated test state out of source.
