# v1g labels and qualification status

`v1g` is an internal DBG1 firmware build label, not a new public version. The firmware remains generation 50, `2.0rc1`, ASM 0.5 and BRK ABI 1. Distribution `r5` adds hardware evidence and documentation without changing firmware or the installer.

| Build | Change | Recorded status |
| --- | --- | --- |
| v1e | Original DBG1 candidate | Historical evidence; later MAINT guard mismatch |
| v1f | Strict MAINT compatibility guard fix | Earlier hardware acceptance; owner-stopped partial soak, 2 h 33 min 11.859 s; restoration/drift passed; not a six-hour pass |
| v1g | v1f plus $82 invalid-ID and $84 text-end fixes | Offline and both-board/both-slot hardware requalification passed, including rollback/reinstall |

A separate **three-hour v1g soak is in progress** at this snapshot. Its completion and final drift review remain pending. Earlier candidates' results are not reused as v1g soak evidence. Promotion remains held. Native applications/debugging remain excluded.

The [board results](DEBUGGER_BOARD_RESULTS.md) identify the exact image and both boards' receipts. The [ASM/BRK supplement](ASM_DBG1_REQUALIFICATION.md) records coverage alongside the byte-identical tested manuals. See [install/rollback](../../INSTALL_ROLLBACK.md) for future authorized operations; do not run them while the current soak owns the boards. Extracting or verifying this archive opens no port and starts no job.
