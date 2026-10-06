# STR8-N 2.0 beta 4

STR8-N is a reset monitor and flash loader for the WDC W65C02SXB and
W65C816SXB boards. On the 816, the monitor runs in emulation mode.
Beta4 provides USB console access, RAM loading/execution, memory inspection,
guarded flash operations, RESTORE/SAVE/TABLE storage, startup settings,
erase-attempt accounting and a fixed recovery core with two monitor slots.

The local release is `output/release/str8n-v2-b4.zip`. It includes both
migration paths and unchanged BANK MAINT 1.5. Both migrators install a saved
MAINT record in B3:8/9; enter `R MAINT` to restore/run it after RESET.
The package contains no stock monitor firmware or board backups.

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
