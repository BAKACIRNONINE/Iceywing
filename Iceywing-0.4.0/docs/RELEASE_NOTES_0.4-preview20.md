# Iceywing 0.4 Preview 20

Preview20 keeps installation lightweight while improving the Windows setup and
NeuroScape verification experience.

- Uses native PowerShell `Write-Progress` during Windows installation; no new
  Python UI dependency is added.
- Runs pip as a tracked child process so the installer progress status and
  elapsed time keep updating while full pip output is written to the install log.
- Keeps successful `pop verify` and `pop baseline` child output quiet by default.
  `--verbose` remains the explicit way to stream npm, TypeScript, and other
  project output.
- Preserves detailed failure tails and full log paths.
- Warns when another `iceywing` executable appears before the newly installed
  launcher on `PATH`, which makes mixed installations easier to diagnose.
- Adds regression coverage proving that `pop diff` does not verify or mutate a
  project.
- Builds release archives from a clean source tree without caches, `build/`, or
  stale package metadata.

