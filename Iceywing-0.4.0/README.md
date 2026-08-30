# Iceywing

**Environment + Pop Flow for local projects and AI-generated code changes.**

Iceywing is a thin Python CLI that coordinates the tools your project already trusts — Git, `just`, package managers, test runners, and local processes — then keeps the terminal output focused on what matters next.

```text
Detect -> Decide -> Delegate -> Summarize
```

## Install

Download the latest release ZIP and extract it.

### Windows

Run:

```text
Setup.bat
```

The release ZIP is self-contained and includes the matching installer wheel under `dist/`.

### macOS / Linux

Run:

```sh
chmod +x bootstrap.sh
./bootstrap.sh
```

> **Platform status:** Windows is the currently verified release platform. macOS and Linux use the same Python core and bootstrap path, but are still pending full native compatibility validation.

## Quick start

```sh
iceywing up
iceywing run
iceywing pop apply change.patch
iceywing pop push
```

Check the installed version:

```sh
iceywing --version
```

## What Iceywing does

### Environment

`iceywing up` detects the project and delegates setup to its existing task interface. Re-running it is cheap when the environment has not changed.

### Run lifecycle

```sh
iceywing run
iceywing stop
iceywing run --replace
```

Process trees are tracked through `psutil` instead of platform-specific kill logic.

### Pop Flow

Iceywing keeps AI-generated changes behind explicit checkpoints:

```sh
iceywing pop apply change.patch
iceywing pop resume
iceywing pop push
```

### Compact verification

The project's own `just verify` or configured verify task remains authoritative. Iceywing preserves the full log while showing a concise summary by default:

```text
* Resume · neuroscape-semantic-planner-v1

✓ Verify  27 files · 87 tests · build OK · 1 warning · 8.9s
✓ Commit  a1b2c3d4e5f6

Next: iceywing pop push
```

Use `--verbose` when you need the raw verifier output.

## Release automation

Iceywing can publish itself without requiring the separate GitHub CLI:

```sh
iceywing release publish --dry-run
iceywing release publish
```

The release flow verifies the project, builds the package, pushes the current branch and version tag, creates the GitHub Release, and uploads one self-contained ZIP. Credentials are reused from `GITHUB_TOKEN`, `GH_TOKEN`, or the existing Git credential and are never persisted by Iceywing.

A dirty working tree is rejected by default. Use `--commit` only when you explicitly want the current changes included in the release commit.

## Self-test

```sh
iceywing self-test
iceywing self-test --full
```

The smoke suite covers CLI behavior, environment setup, local Git behavior, process lifecycle, and cleanup. `--full` adds heavier integration checks.

## Python API

```python
from iceywing import Project

project = Project('.')
project.up()
project.run()
project.stop()
project.verify()
project.pop_apply('change.patch')
project.pop_push()
```

## Requirements

- Python 3.11+
- `psutil>=7.0`
- Git for Git-backed workflows
- `just` recommended for project task delegation

## Release notes

- [Iceywing 0.4.0](docs/RELEASE_NOTES_0.4.0.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](docs/ROADMAP.md)

## License

AGPL-3.0-or-later
