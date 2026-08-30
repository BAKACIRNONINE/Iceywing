# Iceywing 0.4 Preview 25

Preview25 adds a built-in GitHub release flow so publishing no longer depends on the separate `gh` CLI.

## Built-in release

```powershell
iceywing release preview --dry-run
iceywing release preview
```

The release flow:

- keeps the project verifier authoritative and runs it before release;
- builds a wheel and clean source ZIP under `dist/`;
- pushes the current branch and version tag;
- creates or resumes the matching GitHub Release;
- marks alpha versions such as `0.4.0a25` as pre-releases;
- uploads the ZIP and wheel while safely skipping assets that already exist.

## Authentication

No `gh` installation is required. Iceywing looks for credentials in this order:

1. `GITHUB_TOKEN`
2. `GH_TOKEN`
3. the existing Git credential for `github.com` (including Git Credential Manager on Windows)

The credential is used in memory only and is never written to Iceywing logs or configuration.

## Safety and recovery

- Release requires a clean Git working tree by default.
- `--commit` is an explicit opt-in to commit current changes with the release message.
- `--dry-run` shows repository, branch, tag, release type, tree state, and artifact names without Git or GitHub writes.
- Existing matching tags/releases/assets are reused, making a partially completed release safe to resume.
- A tag that already points to a different commit is rejected instead of being moved.

## Example

```text
* Release · Iceywing 0.4 Preview25

✓ Source   a1b2c3d4e5f6
✓ Verify   73 tests · 4.2s
✓ Build    Iceywing-0.4-preview25.zip · iceywing-0.4.0a25-py3-none-any.whl
✓ Push     origin/main
✓ Tag      v0.4.0a25
✓ Release  GitHub · pre-release
✓ Upload   zip · wheel

Done: v0.4.0a25
```
