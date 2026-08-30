# Iceywing 0.4-preview3

Real-project fixes from the first NeuroScape E2E test:

- Windows command resolution for npm/npx/pnpm/yarn `.cmd` shims
- safe subprocess failure handling when stdout/stderr are not captured
- untracked-file aware Pop Flow diff, fingerprint, history, and undo
- clean-baseline verification before patch application by default
- `iceywing pop baseline` command
- `--skip-baseline` escape hatch
- mixed runtime descriptors via `runtimes = ["node", "python"]`
- ASCII step progress bars for Environment and Pop Flow
- color suppression for child tools where possible

The default remains: push is a separate explicit command.
