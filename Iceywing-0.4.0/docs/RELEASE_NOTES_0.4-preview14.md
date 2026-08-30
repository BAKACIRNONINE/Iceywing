# Iceywing 0.4 Preview14

Focused run-management release.

- Adds `iceywing stop [path]`.
- Adds `iceywing run [path] --replace`.
- Tracks the root process and discovered services for each Iceywing-run project.
- A second `iceywing run` reports an already-running tracked project instead of silently starting another copy.
- `Ctrl+C` and `iceywing stop` terminate the tracked process tree.
- Runtime summaries recognize Frontend, API, Recorder, and Planner endpoints/status.
- Port-collision output such as `EADDRINUSE` is surfaced as a concise warning.
- Setup, `up`, progress styling, and Pop Flow UX remain unchanged from Preview13.
