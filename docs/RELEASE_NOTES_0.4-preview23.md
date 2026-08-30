# Iceywing 0.4 Preview 23

Preview23 moves the requested dynamic progress from the Windows installer into
Pop Flow itself.

- Interactive Environment, Pop Flow, and self-test steps use one colored Unicode
  progress row that updates in place, including `pop apply`, `pop verify`,
  `pop resume`, and `pop push`.
- The spinner and elapsed time continue moving while project verification or a
  remote push runs, while successful child output remains in the task log.
- Completion changes the same row to a green check; pause and failure states use
  yellow and red markers.
- Redirected output, CI, verbose mode, unsupported terminals, and
  `ICEYWING_PROGRESS=plain` retain the durable plain-ASCII representation.
- The renderer is implemented in Iceywing itself and adds no runtime dependency.
- The Windows installer improvements from Preview22 remain unchanged.
