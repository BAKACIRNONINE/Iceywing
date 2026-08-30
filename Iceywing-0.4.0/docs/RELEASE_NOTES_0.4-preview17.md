# Iceywing 0.4 Preview17

Preview17 hardens the Windows self-test lifecycle.

- The Run / stop self-test no longer launches a second nested long-running `iceywing run` process just to test duplicate detection.
- Tracked-run detection is verified directly against the same runtime state used by `iceywing run`.
- Finite self-test subprocesses now terminate their full process tree on timeout.
- Self-test cleanup stops tracked processes before deleting the temporary project and retries Windows cleanup briefly.
- Cleanup errors no longer hide the original test failure.
