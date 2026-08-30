# Iceywing 0.4 Preview15

Focused automated validation release.

- Adds `iceywing self-test` as a project-independent local E2E check.
- Self-test validates the installed CLI/module version, incremental `up`, local Git + real Pop Flow push to a temporary bare remote, duplicate-run detection, `stop`, and cleanup.
- Self-test uses only temporary local resources; it does not contact GitHub or modify the user's project.
- Adds `ICEYWING_HOME` state-directory override so tests and automation can isolate Iceywing state cleanly.
- Keeps Preview14 setup, progress UI, `up`, run lifecycle, and Pop Flow behavior unchanged.
