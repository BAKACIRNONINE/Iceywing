# Iceywing 0.4 Preview 5

Preview 5 is a Windows reliability hotfix for the simplified Preview 4 flow.

## Windows output decoding

- Captured subprocess output no longer depends blindly on the Windows Python locale (for example GBK/CP936).
- Iceywing now decodes UTF-8 first, falls back to the OS preferred encoding, and safely replaces undecodable mixed bytes.
- This fixes baseline verification failures such as `gbk codec can't decode byte ...` when npm/Node/Git emit UTF-8.

## Debuggability

- Pop Flow now shows `Baseline verification` as the active Preflight sub-step.
- Quiet task output remains logged; failures show the failed step, useful tail output, and full log path.
- The repository is still left unchanged when baseline verification fails before patch application.
