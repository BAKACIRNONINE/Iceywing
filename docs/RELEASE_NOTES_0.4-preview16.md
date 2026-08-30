# Iceywing 0.4 Preview16

Preview16 hardens `iceywing self-test` on Windows.

- Isolates the Run / stop lifecycle probe from the caller's console process group.
- Prevents nested process cleanup from surfacing as `Cancelled.` in the parent self-test.
- Adds visible sub-stage hints for start, duplicate-run detection, and stop so a lifecycle check never looks frozen.
- Keeps the probe non-interactive with stdin detached.

No project runtime, `up`, Pop Flow, installer, or progress style behavior changed in this preview.
