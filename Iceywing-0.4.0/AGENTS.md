# Iceywing Development Instructions

## Product definition

Iceywing has two first-class subsystems:

1. Environment
   - prepare and validate one project's isolated runtime environment
2. Pop Flow
   - safely orchestrate patch -> verification -> diff -> commit -> optional push -> history

Keep them internally separate even though they ship as one CLI.

## Core rules

1. Git remains authoritative for source history.
2. `just` is the preferred project task interface.
3. Do not reimplement package managers or Git.
4. Do not store third-party binaries in this repository.
5. Project repositories store environment descriptions and lockfiles, not generated environments.
6. Push must remain explicit.
7. Protected branches block Pop Flow writes.
8. AI-provided arbitrary executable commands are not trusted automatically.
9. Optional integrations must stay optional.
10. Environment and Pop Flow should remain extractable into future libraries/plugins.

11. Interactive command progress uses a colored Unicode row that updates in place without adding a runtime dependency. Redirected output, CI, `ICEYWING_PROGRESS=plain`, and unsupported terminals must retain concise plain-ASCII `[OK]`, `[WARN]`, and `[FAIL]` lines. The Windows installer may use native `Write-Progress` with the same durable completion-line requirement.

## Preview18

Keep installation standard: pip package + console script + `python -m iceywing` + Python API. Prefer simpler/faster behavior over custom package-management layers.

Use mature dependencies only when they remove meaningful platform-specific code or failure modes. `psutil` owns process-tree lifecycle; Git/just/npm/uv remain delegated executors. Self-tests must use finite fixtures rather than recursively launching long-lived Iceywing CLI sessions.
