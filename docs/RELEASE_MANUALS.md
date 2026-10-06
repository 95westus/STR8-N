# STR8-N 2.0b4 release manuals

These guides describe the beta4 release and its two migration paths.
The ZIP includes Markdown and PDF versions of all six guides.

| Guide | Contents | Printable copy |
| --- | --- | --- |
| [Quick start](STR8N_V2_BETA4_QUICK_START.md) | Select a launcher, install and verify | `STR8N-2.0b4-Quick-Start.pdf` |
| [Migration guide](STR8N_V2_BETA4_MIGRATION.md) | Stock WDC monitor and STR8-N a24-and-later upgrade paths | `STR8N-2.0b4-Migration.pdf` |
| [Operator manual](STR8N_V2_BETA4_MANUAL.md) | Commands, memory maps, startup and recovery | `STR8N-2.0b4-Operator-Manual.pdf` |
| [RESTORE / SAVE / TABLE](STR8N_V2_BETA4_RST.md) | Load, save, list and restore a RAM program | `STR8N-2.0b4-RST.pdf` |
| [BANK MAINT](STR8N_BANK_MAINT_RECOVERY.md) | Existing utility commands and protection | `STR8N-2.0b4-Bank-Maintenance.pdf` |
| [Release notes](STR8N_V2_BETA4.md) | Package contents, validation and limits | `STR8N-2.0b4-Release-Notes.pdf` |

Printable files are generated under `output/pdf`. The complete release is
`output/release/str8n-v2-b4.zip`, with a SHA256 file alongside it.
The package contains no stock firmware, vendor source or bank backups.
Local migration logs/backups stay outside the public release.

Use `make -f Makefile.beta4 check` to build the package and run its checks.
The [hardware acceptance report](STR8N_V2_BETA4_HARDWARE_ACCEPTANCE_2026-10-06.md)
records the completed COM3/COM8 migration checks and their qualification limits.
