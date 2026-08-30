# Iceywing 0.4.0

Released on 2026-08-30.

Iceywing 0.4.0 is the first stable release of the 0.4 line. The focus is a small orchestration layer that delegates to proven local tools and keeps successful workflows concise without hiding the logs needed for debugging.

## Highlights

- **Summary-first verification.** `pop verify` and `pop resume` keep the project's verifier authoritative while reducing successful output to the useful totals, warnings, build state, and elapsed time.
- **Built-in GitHub publishing.** `iceywing release publish` can verify, build, tag, push, create a GitHub Release, and upload the release ZIP without requiring the `gh` CLI.
- **Self-contained Windows release ZIP.** `Setup.bat` installs from the exact matching wheel embedded under `dist/`.
- **Safer local automation.** Release, patch, baseline, resume, and push flows retain explicit checkpoints and fail with focused diagnostics plus a full log path.

## Added

- Stable `iceywing release publish` command with `--dry-run` planning.
- GitHub authentication through `GITHUB_TOKEN`, `GH_TOKEN`, or the existing Git credential without persisting tokens.
- Structured Vitest, TypeScript, and Vite verification summaries.
- Focused verification failure windows with links to complete logs.
- Release-archive contract tests that verify the installer wheel is actually present in the ZIP.

## Changed

- Stable releases use semantic version tags such as `v0.4.0` and are published as normal GitHub Releases rather than pre-releases.
- GitHub Releases expose one user-facing ZIP asset; the installer wheel remains embedded inside the ZIP.
- Successful verifier output is summarized by default; `--verbose` exposes the original output from the same run.
- `release preview` remains as a compatibility alias for scripts created during Preview25/26.

## Fixed

- Fixed release ZIPs that could omit the wheel required by `Setup.bat`.
- Removed stale Preview23 wording from installer errors.
- Deduplicated multi-line Vite large-chunk warnings into a single warning summary.
- Parser failures can no longer override the verifier process exit code.

## Install

### Windows

1. Download `Iceywing-0.4.0.zip`.
2. Extract the archive.
3. Run `Setup.bat`.
4. Verify with `iceywing --version`.

### macOS / Linux

From the extracted archive:

```sh
chmod +x bootstrap.sh
./bootstrap.sh
```

## Compatibility

| Platform | Status |
| --- | --- |
| Windows | Supported and release-tested |
| macOS | Python/bootstrap path available; full native validation pending |
| Linux | Python/bootstrap path available; full compatibility validation pending |

Additional requirements:

- Python 3.11+
- `psutil>=7.0`
- Git for Git-backed workflows
- `just` recommended, but not required for every project

## Verification

- Full Python test suite passes for the release source tree.
- Release archive contract verifies that the matching `0.4.0` wheel is embedded in the ZIP.
- Windows setup uses concise progress output and preserves a detailed install log on failure.

## Upgrade notes

Users upgrading from Preview24-26 do not need to migrate project configuration. Install 0.4.0 over the existing version and verify with:

```sh
iceywing --version
```

Full changelog: `v0.4.0a24...v0.4.0`
