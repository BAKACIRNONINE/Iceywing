# Iceywing 0.4 Preview 24

Preview24 makes project verification summary-first without changing the project's verifier.

## Compact verification

- `iceywing pop verify` and verification inside `iceywing pop resume` keep the full child output in Iceywing logs and print a compact result by default.
- Vitest aggregate output is summarized as test-file and test counts across multiple workspaces.
- Successful Vite builds are summarized as `build OK`.
- The standard Vite large-chunk message (`Some chunks are larger than 500 kB`) is deduplicated into one warning category even if it appears more than once.
- Unknown verifier formats safely fall back to `Verify passed`; the project command exit code remains authoritative.

Example interactive result:

```text
* Resume · neuroscape-semantic-planner-v1

✓ Verify  27 files · 87 tests · build OK · 1 warning · 8.9s
✓ Commit  a1b2c3d4e5f6

Next: iceywing pop push
```

Redirected output and CI retain ASCII status markers such as `[OK]` and `[FAIL]`.

## Failure reporting

- Failed verification reports the detected stage (`lint`, `typecheck`, `test`, `build`, or generic `verify`).
- Iceywing shows only the useful error window (roughly 10-15 lines) plus the full log path instead of dumping the entire task output.
- The original verifier output is never discarded.

## Logs and machine-readable results

- Every summarized verification writes its complete `.log` file under the existing Iceywing state log directory.
- A sibling `.json` result records counts, duration, warning count, stage, and log path for future history/UI integrations.
- `--verbose` streams the same verifier run while it is being logged; it does not perform a second verification run.

## Architecture

Verification execution/parsing now lives in `iceywing.verification` and returns a reusable `VerifyResult`. Environment still delegates execution to the project task; Pop Flow only renders the result. This keeps project policy, execution, and presentation separate.
