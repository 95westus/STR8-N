# R-YORS Integration Boundary

STR8-N owns all current STR8 source, worker code, payload tooling, protected
top-sector layout, and ABI documentation. R-YORS must not compile or carry a
second live copy of those files.

`make` publishes these integration artifacts:

```text
BUILD/bin/str8n-bank3-f000-ffff.bin
BUILD/s19/str8n-worker-0200.s19
BUILD/str8n-manifest.json
```

R-YORS consumes the 4096-byte top-sector BIN. Its dependency lock records the
exact STR8-N Git commit and SHA-256. The R-YORS build verifies the manifest,
image length, protected layout, fixed gates, ABI version/capabilities, vectors,
and hashes before combining the top sector with HIMON and ASM.

For a two-folder VS Code workspace, R-YORS receives the sibling STR8-N path in
`STR8N_HOME`. A release or clean-clone build must check out the locked commit,
run `make` in STR8-N, and then build R-YORS. R-YORS never silently accepts a
different or dirty STR8-N artifact.

Historical V1.02 board transcripts, archived TopWriter samples, and frozen
release records remain in R-YORS as evidence. They are not current build input.
