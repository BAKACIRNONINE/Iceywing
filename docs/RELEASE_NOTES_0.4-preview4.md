# Iceywing 0.4 Preview 4

Preview 4 focuses on a simpler install and safer interaction model.

## Simple setup

- `Setup.bat` now shows only the major install phases.
- Full command output is written to the Iceywing log directory instead of flooding the terminal.
- On failure, the failed step, last useful output, and full log path are shown.
- `iceywing env up` uses the same quiet-success / detailed-failure approach.

## Pop Flow interaction

Normal `pop apply` no longer asks routine Y/N questions.

A successful apply now follows:

```text
inspect -> preflight -> apply -> verify -> commit
```

Push is still separate and explicit:

```text
iceywing pop push
```

The push prompt requires explicit `Y/YES` or `N/NO`. Pressing Enter alone does nothing and asks again.

## Recovery

`iceywing pop resume` resumes the latest applied operation by re-running verification and committing it when ready.

If verification fails, the working-tree change remains local and Iceywing prints the resume command.

## History and cleanup

- Push failures are recorded as `PUSH_FAILED`.
- Source patch cleanup is delayed until a confirmed successful push.
- A successful apply prints a compact status summary instead of the full working-tree listing.

## Compatibility

- Existing Preview 3 commands remain available.
- `--commit` is accepted for compatibility, but Preview 4 already commits automatically after successful verification.
