# STR8-N 2.0 beta 4

STR8-N is a reset monitor and flash loader for the WDC W65C02SXB and
W65C816SXB boards. On the 816, the monitor runs in emulation mode.
Beta4 provides USB console access, RAM loading/execution, memory inspection,
guarded flash operations, RESTORE/SAVE/TABLE storage, startup settings,
erase-attempt accounting and a fixed recovery core with two monitor slots.

Current release: [v2.0b4](https://github.com/95westus/STR8-N/releases/tag/v2.0b4).
Download the [beta4 ZIP](https://github.com/95westus/STR8-N/releases/download/v2.0b4/str8n-v2-b4.zip)
and [SHA256 checksum](https://github.com/95westus/STR8-N/releases/download/v2.0b4/str8n-v2-b4.sha256).
Extract the ZIP and start with `STR8N_V2_BETA4_QUICK_START.md` or
`STR8N-2.0b4-Quick-Start.pdf`. The package includes both
migration paths and unchanged BANK MAINT 1.5. Both migrators install a saved
MAINT record in B3:8/9; enter `R MAINT` to restore/run it after RESET.
The package contains no stock monitor firmware or board backups.

## New since v2.0b1

Beta1 used the qualified a24c1 firmware and BANK MAINT 1.0. Beta4 adds:

- **Two monitor slots and independent recovery.** RESET validates slots A/B
  and supports a saved slot preference or a one-time boot selection. `U A`
  and `U B` update an inactive, unpreferred slot with a newer image. The
  separate recovery receiver remains available if both monitors are invalid.
- **RESTORE / SAVE / TABLE (RST).** Save RAM programs or data as labeled
  flash records, list them with `T`, and restore by label or address with
  `R`. RESTORE runs programs by default; its `L` option loads without running.
- **MAINT available after RESET.** The release installs BANK MAINT 1.5 as
  a saved record in B3 sectors 8/9. `R MAINT` restores and starts it without
  another host upload. SAVE/RESTORE are monitor commands; the utility retains
  its own editor commands.
- **Persistent journals, wear counts and richer maps.** Startup settings,
  slot preference and erase-attempt counts for all 32 flash sectors use
  checked journal snapshots. `W` reports counts; `M`, `M 1` and `M 3` show
  ranges, sector ownership and wear through MAINT. Maintenance protects
  B3:A-F, which hold the monitors, journals, storage services and recovery core.
- **Two migration paths.** Windows and Linux launchers migrate stock boards
  or upgrade STR8-N a24 and later, including a24c1/beta1. They verify a host
  backup and RAM installer before flashing, install the saved MAINT record,
  and check the result after physical RESET while preserving B0-B2.
- **Updated guides and qualification.** Six Markdown/PDF guides cover
  installation, operation, migration, RST and maintenance. COM3/COM8 hardware
  checks and linked-model failure checks are recorded in the
  [hardware acceptance report](docs/STR8N_V2_BETA4_HARDWARE_ACCEPTANCE_2026-10-06.md).

## Previous releases

| Release | Package and release information |
| --- | --- |
| [v2.0b1](https://github.com/95westus/STR8-N/releases/tag/v2.0b1) | Promotes the qualified a24c1 firmware unchanged; banners, launchers and installation confirmation retain a24c1. BANK MAINT is version 1.0. [Beta1 package](https://github.com/95westus/STR8-N/releases/download/v2.0b1/str8n-v2-b1.zip) and [release notes](https://github.com/95westus/STR8-N/blob/v2.0b1/docs/STR8N_V2_BETA1_RELEASE_NOTES.md). |
| [v2.0a24c1](https://github.com/95westus/STR8-N/releases/tag/v2.0a24c1) | Original a24c1 board-test release. Its release page retains the original package and installation information. |

For these releases, use their packaged `INSTALL-A24C1.ps1` or
`INSTALL-A24C1.sh` launcher and the guides at their version tag. Their
qualification applies to a24c1. For upgrades to beta4, use the beta4
STR8-N migration launcher. The existing release notes and packages remain
available at the links above.

## Beta4 documentation

| Guide | Contents |
| --- | --- |
| [Quick start](docs/STR8N_V2_BETA4_QUICK_START.md) | Choose the launcher, install, verify and load maintenance |
| [Migration guide](docs/STR8N_V2_BETA4_MIGRATION.md) | Stock board to beta4; STR8-N a24 and later to beta4; backups and failure handling |
| [Operator manual](docs/STR8N_V2_BETA4_MANUAL.md) | Commands, settings, slots, memory layout and recovery |
| [RESTORE / SAVE / TABLE](docs/STR8N_V2_BETA4_RST.md) | Save a RAM program, inspect its record and restore it |
| [BANK MAINT](docs/STR8N_BANK_MAINT_RECOVERY.md) | Existing utility commands and protected destinations |
| [Release notes](docs/STR8N_V2_BETA4.md) | Contents, qualification and build details |

Build and check the release without accessing a board:

```text
make -f Makefile.beta4 check
```

Building requires Python 3, WDC02AS and WDCLN. Model checks require `py65`.
The packaged launchers require Python 3 and `pyserial`; users do not need
the assembler/linker tools. PDF generation uses ReportLab.

The release build uses frozen sources in `src/v2-beta4` and launcher support
in `src/v2-beta4-launcher`. Generated files stay under `BUILD/v2-beta4`.
The build creates the release ZIP and its SHA256 file locally.

Keep stable power during installation. The migrator verifies and saves a
host backup before replacing B3 sectors, then checks each transfer and
performs a full B3 readback after physical RESET. An interrupted initial
reset-sector rewrite may require external flash programming.
