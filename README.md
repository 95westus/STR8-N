# STR8-N

STR8-N is a monitor, assembler and utility system for WDC SXB boards, using
one firmware set for **65C02 and 65C816 emulation-mode runtime**.

**[Download rc1 v1g r8 (DBG1 generation 50)](https://github.com/95westus/STR8-N/releases/download/v2.0rc1-v1g-r8/str8n-v2.0rc1-dbg1-v1g-r8.zip)**
([SHA-256 checksum](https://github.com/95westus/STR8-N/releases/download/v2.0rc1-v1g-r8/str8n-v2.0rc1-dbg1-v1g-r8.zip.sha256))

## What is in rc1 v1g r8?

- Exact generation-50 reference firmware and DBG1 debugger BINs, with the
  MAINT compatibility correction and BRK `$82`/`$84` edge fixes.
- The tested, source-bound installer/rollback kit: nine firmware sectors and
  eleven transfers per transaction.
- RC1 manuals and quick starts, RAM debugger/ASM/BRK ABI documentation,
  credited uChess source, and ASM, registration and ten-pattern LED diagnostics.
- Matching debugger and qualification source, machine-readable offline,
  hardware, soak and register-edit evidence, and a board-free package verifier.
- A complete file manifest and `SHA256SUMS.txt`, plus the adjacent ZIP checksum.

Both boards (2604 and 2609) passed MON A/B R-register qualification: **5,752
parser checks, 220 resume cases and 132 expected unsafe-PC refusals**, with
zero hardware failures, original RAM restored and unchanged flash/settings.
The package passed full/extracted verification of 249 files, 179 documentation
links and 24 scope/tamper checks. See the
[distribution identity and hashes](release/candidates/rc1-debugger-brkfix-r1/distribution-r8.json).

**Native applications/debugging are excluded. RTC drift is outside release
qualification and is not a promotion gate.** Historical RTC records remain
integrity-protected evidence; they do not supply release-acceptance criteria.
The firmware still displays `2.0rc1` and `ASM 0.5`; `VERSION` generation
`00000032` identifies the DBG1 generation-50 build.

## Verify and install

Check the adjacent ZIP SHA-256, extract into a new directory, then run
`python -B verify_package.py`. Verification opens no board ports. The archive
contains `INSTALL_ROLLBACK.md` with the exact supported source and workflow.

The r8 kit admits exact generation-49 sources; it cannot directly update an
already-installed generation-50 candidate. The reference BIN is not a
preserving updater. For the original WDCMONV2/beta4 migration route, retain the
[previous complete generation-49 release](https://github.com/95westus/STR8-N/releases/tag/v2.0rc1)
and its matching migration/recovery tools. R8 does not replace that tag or ZIP.
Private board backups, original RAM/flash captures, serial logs and secrets
are excluded from the download.

- [RAM debugger guide](docs/rc1/DEBUGGER_GUIDE.md) / [Board results](docs/rc1/DEBUGGER_BOARD_RESULTS.md)
- [ASM examples](docs/rc1/ASM_GUIDE.md#debugging-ram-programs-with-dbg1) / [BRK registration ABI](docs/rc1/ABI_REFERENCE.md#dbg1-brk-functions-and-registrations)
- [Quick start](docs/rc1/QUICK_START.md) / [Migration/recovery](docs/rc1/QUICK_START_MIGRATION.md) / [All manuals](docs/rc1/README.md)
- [Current scope](release/candidates/rc1-debugger-brkfix-r1/release-policy.json) / [Firmware layouts](docs/rc1/RELEASE_PATHS.md)
- [Previous beta4](https://github.com/95westus/STR8-N/releases/tag/v2.0b4) / [Previous bf1](https://github.com/95westus/STR8-N/releases/tag/v2.0bf1)

Soaks and RTC sampling remain stopped; recorded workload durations are not
relabeled as fixed-duration endurance passes. Future **v2.1** ABI/metadata,
[LED and dual-VIA timer ABI plans](docs/STR8N_V2_1_ABI_METADATA_ROADMAP.md),
ACIA and crypto remain separate development work.
