# Iceywing 0.4-preview18

Preview18 is a reduction-oriented runtime and self-test refactor.

## Runtime

- Added `psutil>=7.0` as the cross-platform process-lifecycle backend.
- Removed `taskkill`/`pkill` process-tree logic from the runtime path.
- Run state now records process creation time as well as PID to guard against PID reuse.
- Stop recursively terminates and waits for only the tracked process tree.

## Self-test

- Default `iceywing self-test` is a finite smoke test and no longer recursively launches a long-running `iceywing run`.
- Added `iceywing self-test --full` for local push and recursive process-tree checks.
- Added `--list`, repeatable `--only CHECK`, and `--json`.
- Failed test artifacts are retained so cleanup errors cannot hide the primary failure.

## Install

- Standard pip installation remains the canonical model.
- Installer no longer forces a reinstall on every preview upgrade.
- Dependencies are installed normally so `psutil` is handled by pip.
- Administrator elevation remains fallback-only.

## Philosophy

Keep the fast working pieces already proven in Preview12-17. Integrate mature tools only where they remove custom platform logic or repeated bugs.
