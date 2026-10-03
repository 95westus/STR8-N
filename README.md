# STR8-N

STR8-N v2 is a standalone reset monitor and flash loader for WDC SXB boards,
intended as a base from which others can begin their own board projects.
It occupies Bank 3's `$F000-$FFFF` sector and provides the basic tools to
load programs, maintain flash, and hand control to other firmware.

Development took a different branch through alpha36, exploring board
discovery, hardware information, and a broader midrange/mainframe feel.
That was a false start for the core product: the useful direction is a
small, dependable foundation that others can understand and build on.
Alpha36 remains part of the project's history. The current working baseline
is **2.0a24c1**, built from the tested alpha24 base.

The core should stand on its own. Additional board hardware is optional;
RTC, SPI SRAM and crypto hardware are not prerequisites. Configuration
belongs to the core flash sector.

## RAM bank maintenance utility

`make bank-maint-v2` builds a `$2000` S19 utility with bank/sector erase,
all four RAM/flash copy modes, a buffered 4 KiB editor, and sector read/write.
B3:F writes require two confirmations. See the
[command guide and validation limits](docs/STR8N_BANK_MAINT_V2.md).

## Current development baseline: 2.0a24c1

The alpha24-derived `2.0a24c1` candidate moves configuration to
`$FFD0-$FFDF`, keeping saved boot settings in the core. Build with `make v2-config`; validate with `make v2-config-check`.
COM3 installation, readback and software handoffs passed; physical reset and
cold-power checks remain pending. See the [layout, ABI and guarded migration guide](docs/STR8N_V2_FLASH_CONFIG.md).
Run the current stock-board launcher from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\INSTALL-A24C1.ps1
```

On Linux, install Python 3 and pyserial, then run `sh ./INSTALL-A24C1.sh`.
Use `/dev/ttyUSB0` or the actual detected device with serial-access permission.
Linux offline tests pass. The owner reported a successful native Linux run
on 2026-10-02; see the [Linux test record](docs/STR8N_V2_A24C1_LINUX_TEST_2026-10-02.md).

It prompts for COM port and physical RESET, confirms the board, and supplies
the matching installer/core/maintenance files. Console colors identify
information (cyan), input and writes (yellow), success (green), and failure
or refusal (red). See the [current manual](docs/STR8N_V2_A24C1_MANUAL.md),
[current maps and diagrams](docs/STR8N_V2_A24C1_MAPS.md), and
[release ZIP proposal](docs/STR8N_V2_A24C1_RELEASE_ZIP_PROPOSAL.md).

For stock boards, build the [unified C02/816 WDCMON to a24c1 installer](docs/STR8N_V2_CONFIG_WDCMON_INSTALL.md)
with `make v2-config-wdcmon`. Its C02 model checks are available via
`make v2-config-wdcmon-check`; physical qualification remains pending.

Use the [quick start](docs/STR8N_V2_A24C1_QUICK_START.md) for installation
and the [detailed technical guide](docs/STR8N_V2_A24C1_TECHNICAL_GUIDE.md)
for memory maps, Mermaid flows, charts, interfaces and board acceptance checks.
Successful verified stock migration and physical RESET into STR8-N establish
the beta 1 milestone. Record remaining tests separately for each CPU family.
The [local board-test ZIP](output/release/str8n-v2-a24c1-board-test.zip) includes
both colored launchers, bank maintenance, the public include and documentation.
The a24c1 sources and board-test ZIP are maintained on `codex/v2-flash-config`.
The ZIP is available from the repository; this remains a board-test candidate.

## Historical sources and board tests

Earlier sources, tags and board-test records remain available for reference.
The repository's current package is a24c1; old RC and alpha build packages
have been removed locally. Historical results do not qualify the current image.

- [Alpha24 source tag](https://github.com/95westus/STR8-N/tree/v2.0a24)
- [816 alpha24 board result](docs/STR8N_V2_A24_2609_RESTORE_REMIGRATE_E_2026-09-30.md)
- [02SXB board 2205 result](docs/STR8N_V2_A24_2205_NO_EDU_2026-09-30.md)
- [a24c1 C02 installation result](docs/STR8N_V2_CONFIG_COM3_INSTALL_2026-10-01.md)
- [Manual index](docs/RELEASE_MANUALS.md)

STR8-N is independent of WDC and R-YORS; see [LICENSE](LICENSE).
