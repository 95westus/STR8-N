# v1g labels and qualification status

`v1g` is an internal DBG1 firmware build label, not a new public version. The firmware remains generation 50, `2.0rc1`, ASM 0.5 and BRK ABI 1. Distribution `r7` adds verified owner-stopped soak/drift evidence and documentation without changing firmware or the installer.

| Build | Change | Recorded status |
| --- | --- | --- |
| v1e | Original DBG1 candidate | Historical evidence; later MAINT guard mismatch |
| v1f | Strict MAINT compatibility guard fix | Earlier hardware acceptance; owner-stopped partial soak, 2 h 33 min 11.859 s; restoration/drift passed; not a six-hour pass |
| v1g | v1f plus $82 invalid-ID and $84 text-end fixes | Offline and both-board/both-slot hardware requalification passed, including rollback/reinstall |

The owner stopped the expanded v1g R6 continuation cleanly after **12,803.703 seconds (3 h 33 min 23.703 s) of monitored/active workload**. 2604 passed **61 cycles, 38,430 LED frames, 610 completed patterns and 976 breakpoint hits**; 2609 passed **60 cycles, 37,800 frames, 600 patterns and 960 hits**. Both original full 25,344-byte RAM images were restored and reread after final preserving drift; all four flash banks/settings were unchanged. No actual workload failure or snapshot retry occurred. The verified worker exited; no workload or RTC sampler was restarted. **Promotion remains held; native applications/debugging remain excluded.**

See [soak closeout](DBG1_SOAK_CLOSEOUT.md) for all ten patterns, exact workload/final-closure durations, separate history, inherited/new test scope and drift intervals. Earlier candidates and partial runs are not substituted for R6 acceptance.

The [board results](DEBUGGER_BOARD_RESULTS.md) identify the exact image and both boards' receipts. The [ASM/BRK supplement](ASM_DBG1_REQUALIFICATION.md) records coverage alongside the byte-identical tested manuals. See [install/rollback](../../INSTALL_ROLLBACK.md) for future authorized operations; the closed soak does not authorize another installation, rollback or workload. Extracting or verifying this archive opens no port and starts no job.
