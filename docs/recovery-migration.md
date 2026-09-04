# IceyWing recovery and migration

This project uses a recovery-first migration flow.

## Recovery package contents

A recovery directory should contain:

```text
inventory/
history/
working-tree/
artifacts/
private-local/
manifest/
checksums/
```

## Important files

- `history/iceywing-history.bundle`: portable Git history backup.
- `working-tree/iceywing-working-tree-sanitized.zip`: sanitized working-tree source snapshot.
- `working-tree/iceywing-untracked-source.zip`: untracked source files that are safe to transfer.
- `manifest/manifest.json`: machine-readable recovery metadata.
- `checksums/SHA256SUMS.txt`: SHA-256 integrity records.
- `private-local/`: private-file inventory only. Anything marked `PRIVATE_LOCAL_ONLY` or `DO_NOT_UPLOAD` must not be uploaded.

## Restore on a new computer

```powershell
git clone path\to\iceywing-history.bundle iceywing
cd iceywing
git fsck --full
```

Then restore the sanitized working-tree snapshot and untracked source snapshot if needed.

After restore, verify:

```powershell
git status --short --branch --untracked-files=all
git branch --all
git tag --list
git log --oneline --decorate -n 20
```

## Clean setup after restore

Windows:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
just doctor
just test
just verify
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
just doctor
just test
just verify
```

## Safety rules

Do not upload:

- `.env*`
- tokens
- API keys
- passwords
- private keys
- machine-local config
- anything under `private-local/`
- anything marked `DO_NOT_UPLOAD`

Do not treat any old external GitHub repository as canonical unless it has been explicitly verified and accepted.
