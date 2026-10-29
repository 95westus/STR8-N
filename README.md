# STR8N-F v0.3.0 — BASE1 / PR05

**[Download N-F v0.3.0 — BASE1 / PR05](https://github.com/95westus/STR8N-F/releases/tag/v0.3.0)**

> 4KB of firmware. One board. Up to four boot environments.

For WDC W65C02SXB and W65C816SXB (65C816 emulation), with optional matching
W65C02EDU/W65C816EDU add-ons. BASE1 boot/recovery does not require EDU.
Compatible, user-supplied images run one at a time on shared CPU, RAM and peripherals.

The kit includes the Python serial terminal, verbose WDC RAM migration programs,
CONFIG, OPAQUE, MAP, READBACK and DEMO. F stays **STR8N-F 0.3.0 g00000001 /
BASE1 / PR05**, exactly 4096 frozen bytes. The manual covers opaque-image
installation/readback and saving an enabled bank as the default boot.

[User manual](https://github.com/95westus/STR8N-F/blob/main/docs/USER_MANUAL.md) /
[4KB F.bin](https://github.com/95westus/STR8N-F/releases/download/v0.3.0/F.bin) /
[operator ZIP](https://github.com/95westus/STR8N-F/releases/download/v0.3.0/STR8N-F-BASE1-0.3.0.zip) /
[N-F source and release scope](https://github.com/95westus/STR8N-F).

## Full-system STR8-N and historical development

The 2512 FLASH and 2609 F-up development now share the
[unified STR8N-F source/build](bootstrap-opaque/docs/UNIFIED_SYSTEM.md), with
one CONFIG and toolset and profiles preserving each board's layout and settings.
The published RC1 workflow below remains a separate firmware line.

The [October 28 board inventory](docs/BOARD_INVENTORY_2026-10-28.md) records
all four boards and private WDCMONv2 backups. The planned
[b16 message journal](docs/STR8N_B16_MESSAGE_JOURNAL_PLAN.md) uses only optional
SPI SRAM WORK space and preserves formatted program storage.

The separate experimental b14/b15 boot/recovery work on 2512 is documented in the
[boot, recovery and configuration guide](docs/STR8N_B14_BOOT_AND_RECOVERY_GUIDE.md).
It covers F, boot records, RAM tools, examples and implemented/planned status;
these prototype instructions are separate from the released RC1 workflow below.

Full-system STR8-N development uses [its source tree](src/current/README.md).
Run `python -B tools/build_current.py` or `make` for a clean offline build.
The build verifies the selected Monitor A/B and fixed-F size candidate byte for byte
against its qualified target fixture. Phase 1/2 baselines remain preserved. This includes
EQU/LST/SYMS/diagnostics, fixed-F journal branch shortening/vector packing,
recovery status initialization, and further internal branch/refusal cleanup
(204 contiguous plus 76 internal free bytes), with the original CRC implementation;
published-release installation instructions below remain the r9 workflow.
Current development installers use [one profile-driven workflow](tools/installer/README.md)
through `python -B tools/install_current.py`; its verification is offline.
Obsolete development paths are retired into [a verified, restorable archive](archive/README.md).
See [the active tool map](tools/README.md) for the retained example and release support.

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
