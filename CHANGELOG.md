# Changelog

All notable user-facing changes to Iceywing are documented here. Preview-era notes remain available under `docs/` for development history.

## 0.4.0 — 2026-08-30

### Added

- Stable `release publish` workflow with dry-run support and built-in GitHub Release creation.
- Compact structured verification summaries for Vitest, TypeScript, and Vite.
- Self-contained release ZIPs with the matching installer wheel embedded under `dist/`.
- Cross-platform process lifecycle management through `psutil`.

### Changed

- Stable release tags now follow `vMAJOR.MINOR.PATCH`.
- Successful verification is summary-first; complete logs remain available for debugging.
- Release assets are simplified to one user-facing ZIP.

### Fixed

- Release archives now always contain the wheel required by Windows setup.
- Vite large-chunk warnings are deduplicated in summaries.
- Verification parsing cannot change the verifier's authoritative exit result.
- Installer error messages no longer contain stale preview-version wording.

### Compatibility

- Windows: supported and release-tested.
- macOS/Linux: shared Python core and bootstrap installer available; full native validation is still in progress.
