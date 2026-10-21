# STR8-N

STR8-N is a monitor, assembler and utility system for WDC SXB boards, using
one firmware set for **65C02 and 65C816 emulation-mode runtime**.

**[Download rc1 v1g r9 (DBG1 generation 50)](https://github.com/95westus/STR8-N/releases/download/v2.0rc1-v1g-r9/str8n-v2.0rc1-dbg1-v1g-r9.zip)**
([SHA-256 checksum](https://github.com/95westus/STR8-N/releases/download/v2.0rc1-v1g-r9/str8n-v2.0rc1-dbg1-v1g-r9.zip.sha256))

## What is in rc1 v1g r9?

- Exact generation-50 reference firmware and DBG1 debugger BINs, with the
  MAINT compatibility correction and BRK `$82`/`$84` edge fixes.
- A uniform, source-aware upgrade command supporting the registered WDCMONV2,
  beta4 and rc1 sources, including already-installed generation-50 candidates.
  It goes directly to v1g without a manual generation-49 rollback.
- RC1 manuals and quick starts, RAM debugger/ASM/BRK ABI documentation,
  credited uChess source, and ASM, registration and ten-pattern LED diagnostics.
- Matching debugger and qualification source, machine-readable offline,
  hardware, soak and register-edit evidence, and a board-free package verifier.
- A complete file manifest and `SHA256SUMS.txt`, plus the adjacent ZIP checksum.
- Exact full-system, F-sector, MON and ASM component BINs, programmer offsets,
  and a reclaim guide explaining shared sectors and ASM/DBG1 dependencies.

Both boards (2604 and 2609) passed MON A/B R-register qualification: **5,752
parser checks, 220 resume cases and 132 expected unsafe-PC refusals**, with
zero hardware failures, original RAM restored and unchanged flash/settings.
R9 adds physical direct WDCMONV2 → v1g and beta4 → v1g trials on **both boards**,
with both monitor slots, 128 debugger hits in total, complete original RAM,
EEPROM/SRAM/settings preservation and already-current no-write checks. One
beta4 host protocol check failed during qualification; it was corrected and its
failed receipt retained. No firmware/device verification failed. The firmware
is byte-identical to r8; its register and soak evidence is inherited. See the
[uniform upgrade guide](docs/rc1/UNIFORM_UPGRADE.md) and
[current scope](docs/rc1/V1G_RELEASE_STATUS.md).
The archive and extracted package verified 464 files and 189 documentation
links; 42 integrity/scope checks passed. See the
[distribution identity and hashes](release/candidates/rc1-debugger-brkfix-r1/distribution-r9.json).

**Native applications/debugging are excluded. RTC drift is outside release
qualification and is not a promotion gate.** Historical RTC records remain
integrity-protected evidence; they do not supply release-acceptance criteria.
The firmware still displays `2.0rc1` and `ASM 0.5`; `VERSION` generation
`00000032` identifies the DBG1 generation-50 build.

## Verify and install

Check the adjacent ZIP SHA-256, extract into a new directory, then run
`python -B verify_package.py`. Verification opens no board ports. The archive
contains `INSTALL_ROLLBACK.md` with the exact supported source and workflow.

Use `upgrade/upgrade.py` from the extracted r9 package. It detects exact source
bytes, captures private recovery data, plans and verifies the direct update,
then requests physical RESET after verified programming. At an idle monitor
prompt `J3` can restart the monitor; the completed RAM installer is halted and
cannot accept it. Exact current v1g uses a verified no-write path without RESET.
The new live host workflow is qualified on Windows. The archived `install/`
generation-49 kit remains historical reference, and the reference BIN alone
does not perform a preserving upgrade. R8 and earlier downloads remain unchanged.
Private board backups, original RAM/flash captures, serial logs and secrets
are excluded from the download.

- [RAM debugger guide](docs/rc1/DEBUGGER_GUIDE.md) / [Board results](docs/rc1/DEBUGGER_BOARD_RESULTS.md)
- [ASM examples](docs/rc1/ASM_GUIDE.md#debugging-ram-programs-with-dbg1) / [BRK registration ABI](docs/rc1/ABI_REFERENCE.md#dbg1-brk-functions-and-registrations)
- [Quick start](docs/rc1/QUICK_START.md) / [Migration/recovery](docs/rc1/QUICK_START_MIGRATION.md) / [All manuals](docs/rc1/README.md)
- [Current scope](docs/rc1/V1G_RELEASE_STATUS.md) / [Firmware layouts](docs/rc1/RELEASE_PATHS.md)
- [Optional applications and flash reclaim limits](docs/rc1/FLASH_RECLAIM.md)
- [Previous beta4](https://github.com/95westus/STR8-N/releases/tag/v2.0b4) / [Previous bf1](https://github.com/95westus/STR8-N/releases/tag/v2.0bf1)

This installation workflow starts no soak or RTC sampler; recorded workload durations are not
relabeled as fixed-duration endurance passes. Future **v2.1** ABI/metadata,
[LED and dual-VIA timer ABI plans](docs/STR8N_V2_1_ABI_METADATA_ROADMAP.md),
ACIA and crypto remain separate development work.
