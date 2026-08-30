# Iceywing 0.4-preview24

**Iceywing = Environment + Pop Flow**

Iceywing is a thin Python package and CLI that coordinates proven local tools instead of reimplementing them.

```text
Iceywing
├── Environment
└── Pop Flow
```

## Install on Windows

Double-click:

```text
Setup.bat
```

Setup uses the current Python 3.11+ installation and performs a normal pip upgrade. If that location is not writable, setup retries for the current user in the same window. It never opens an administrator window.

Preview24 keeps `psutil` as the only runtime dependency. The Windows setup uses native PowerShell `Write-Progress`, so no UI package is installed.
During installation, the native progress view updates its elapsed time while pip output is written to the install log. The progress view clears when setup finishes, leaving only the concise completion lines below.

If the exact Preview24 version is already installed, setup treats that verified state as success. It suggests a manual administrator run only when the final pip log explicitly reports a permission denial.

Expected output stays short:

```text
* Iceywing Setup

[OK] Check Python 3.11+
[OK] Install / upgrade
[OK] Verify

[OK] Iceywing 0.4.0a24 ready
```

Iceywing remains available in all three forms:

```powershell
iceywing --version
python -m iceywing --version
```

```python
from iceywing import Project
```

## Daily workflow

```powershell
iceywing up
iceywing run
iceywing pop apply change.patch
iceywing pop push
```

The command itself expresses intent. `pop push` pushes immediately; use `--dry-run` when you only want preflight.

## Dynamic command progress

In an interactive PowerShell or terminal, Environment, Pop Flow, and self-test
steps use a colored Unicode row that refreshes in place and shows elapsed time
without installing a UI package:

```text
⠹ Verify project         ██████░░░░░░  1/2    3.2s
```

The same row becomes a green `✓` on success, yellow `!` when paused, or red `✗`
on failure. Redirected output and CI automatically use durable plain-ASCII
lines. Set `ICEYWING_PROGRESS=plain` to request that format in a terminal.

## Compact project verification

Preview24 keeps project verification authoritative while making Iceywing's view summary-first.
The configured `just verify` or `[tasks].verify` command still runs unchanged and its complete
stdout/stderr is saved under the Iceywing state log directory.

```text
* Resume · neuroscape-semantic-planner-v1

✓ Verify  27 files · 87 tests · build OK · 1 warning · 8.9s
✓ Commit  a1b2c3d4e5f6

Next: iceywing pop push
```

Vitest totals, Vite build completion, and warnings are parsed only for presentation. If Iceywing
does not recognize a verifier format, it safely falls back to `Verify passed`; the child process
exit code remains authoritative. Failed verification shows a focused error window and the full
log path. Use `--verbose` to see raw verifier output from the same run.

## Fast environment setup

```powershell
iceywing up
```

Or from anywhere:

```powershell
iceywing up E:\path\to\project
```

`up` is idempotent. If the environment is healthy and its dependency fingerprint has not changed, installation is skipped.

```text
* Iceywing Environment

[1/3] Check project          [OK]
[2/3] Environment unchanged  [OK]
[3/3] Ready                  [OK]

[OK] Environment ready in 0.8s
```

Iceywing delegates project-specific work to the existing project interface, preferably `just`. Python projects may use `uv` when the project has no explicit setup task and uv is available. uv is an optional adapter, not a required Iceywing runtime.

## Process lifecycle

```powershell
iceywing run
iceywing stop
iceywing run --replace
```

Preview18 replaces platform-specific process-tree code with `psutil`.

Iceywing records both PID and process creation time, which protects against accidentally treating a reused PID as the old project process. Stop operations recursively terminate only the tracked process tree and wait for it to exit.

The normal run view stays compact:

```text
* Iceywing Run

[1/2] Check project  [OK]
[2/2] Start project  [....]

[OK] Recorder   http://127.0.0.1:8787
[OK] Planner    enabled
[OK] Frontend   http://localhost:5173/
[OK] API        http://127.0.0.1:8000

[OK] Project running - Ctrl+C to stop
```

Use `--verbose` for raw child-process output.

## Self-test: smoke first, full only when needed

Preview18 no longer tests long-lived lifecycle behavior by recursively launching another `iceywing run` command.

Default smoke test:

```powershell
iceywing self-test
```

It checks finite, isolated primitives:

```text
CLI
Environment + cached `up`
Local Git
psutil process lifecycle
Cleanup
```

For the heavier integration checks:

```powershell
iceywing self-test --full
```

`--full` additionally performs a real Git push to a temporary local bare remote and validates recursive parent/child process cleanup. It never pushes to GitHub.

Run only the failed area:

```powershell
iceywing self-test --only process
iceywing self-test --only git --full
```

List checks:

```powershell
iceywing self-test --list
```

Machine-readable output:

```powershell
iceywing self-test --only process --json
```

Failed self-tests preserve their temporary test directory instead of allowing cleanup errors to hide the original failure.

## Python API

```python
from iceywing import Project

project = Project(".")
project.up()
project.run()
project.stop()
project.verify()
project.pop_apply("change.patch")
project.pop_push()
```

## Output rules

- default: only major stages, elapsed time, service state, and useful warnings
- `--verbose`: underlying tool output
- `--quiet`: final results and errors only
- long steps show elapsed-time heartbeats instead of fake percentages
- failures show the failed command, useful output tail, and log path

## Preview18 architecture rule

Iceywing should stay thin:

```text
Detect -> Decide -> Delegate -> Summarize
```

Use mature tools where they reduce code and failure modes:

```text
Git      -> source history and push
just     -> project task interface
npm/uv   -> project package/environment work
psutil   -> cross-platform process lifecycle
pytest   -> Iceywing development test suite
```

Do not require every adapter for every project. Do not reimplement package managers, Git, or a generic process manager inside Iceywing.

## Self-test cleanup

Self-test artifacts are isolated. Cleanup is best-effort: a transient Windows file lock does not turn passing checks into a failed self-test. If cleanup is deferred, Iceywing prints the retained path. Use `iceywing self-test --keep-temp` when you want to inspect the fixture deliberately.
