# STR8-N

STR8-N is a monitor, assembler and utility system for WDC SXB boards, using
one firmware set for **65C02 and 65C816 emulation-mode runtime**.

**[Download v2.0rc1 â€” one complete release ZIP](https://github.com/95westus/STR8-N/releases/download/v2.0rc1/str8n-v2.0rc1-release.zip)**

Includes the full-system BIN, B3 boot/core BIN, MON A/B/F components, all apps
and S/R/T, Windows/Linux migration and recovery tools, manuals/quick starts,
public ABIs/diagrams, and credited uChess source with an ASM/S/T/R example.

- [Quick start](docs/rc1/QUICK_START.md) Â· [Migration/recovery](docs/rc1/QUICK_START_MIGRATION.md) Â· [All manuals](docs/rc1/README.md)
- [Firmware layouts](docs/rc1/RELEASE_PATHS.md) Â· [Reproducible rc1 source build](release/candidates/rc1/README.md)
- [Published beta4 archive and instructions](https://github.com/95westus/STR8-N/releases/tag/v2.0b4) Â· [Previous bf1](https://github.com/95westus/STR8-N/releases/tag/v2.0bf1)

Scripted migration admits the exact supported WDCMONV2 or published beta4
source in B3 with erased B0/B1/B2; read the guide before installing. No vendor
firmware or private board data is distributed. Raw BINs are provisioning images.

rc1 is source-built and installed/checked on 2604/2609, including the
[power-fail UTC label correction](docs/STR8N_RC1_UTC_BOARD_UPDATE_2026-10-18.md).
RTC qualification/known continuity issue, native 816 apps/tests, ACIA and crypto
are deferred. Soaks and RTC sampling remain stopped; recorded soak results are
accepted as recorded, without claiming full endurance qualification.

Published release: **v2.0rc1 generation 49**. The local **DBG1 generation-50
candidate** is installed/tested on 2604 (65C02) and 2609 (65C816 E=1), both
MON A/B, with original RAM and preferences restored. Start with the
[RAM debugger guide](docs/rc1/DEBUGGER_GUIDE.md),
[ASM examples](docs/rc1/ASM_GUIDE.md#debugging-ram-programs-with-dbg1),
[BRK registration ABI](docs/rc1/ABI_REFERENCE.md#dbg1-brk-functions-and-registrations)
and [board results](docs/rc1/DEBUGGER_BOARD_RESULTS.md). The published release
ZIP/tag remains unchanged; native debugging is outside scope. Future **v2.1**
organizes ABIs/metadata; [planned LED and dual-VIA timer ABIs](docs/STR8N_V2_1_ABI_METADATA_ROADMAP.md)
remain development work.
