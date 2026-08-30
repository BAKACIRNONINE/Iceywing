# Iceywing 0.4-preview13

Preview13 freezes the first unified CLI UX pass.

## Changes

- adds top-level `iceywing run [path]`
- hides routine child-process output during normal runs while keeping full logs
- discovers and surfaces common service endpoints such as frontend, API, and recorder URLs
- suppresses repetitive HTTP access logs in normal mode
- adds global `--verbose` and `--quiet` flags that work before or after subcommands
- `iceywing pop push` now pushes immediately; no redundant Y/N confirmation
- adds `iceywing pop push --dry-run`
- Pop Flow resume reuses a successful verification checkpoint when the working-tree fingerprint is unchanged
- interrupted post-apply verification records a resumable checkpoint
- Git commit success output is kept concise
- progress status uses the same `[....]`, `[OK]`, `[WARN]`, and `[FAIL]` vocabulary

## Safety boundary

Destructive recovery operations still require confirmation. Remote push does not, because invoking `iceywing pop push` is itself an explicit remote-write command.
