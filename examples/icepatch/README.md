# `.icepatch` example

Create a ZIP with:

```text
manifest.toml
change.patch
```

Rename the ZIP extension to:

```text
.icepatch
```

Then:

```bash
iceywing pop inspect example.icepatch
iceywing pop apply example.icepatch
```
