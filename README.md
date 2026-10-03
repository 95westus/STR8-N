# STR8-N 2.0 beta 1

STR8-N is a standalone reset monitor and flash loader for the **WDC
W65C02SXB and W65C816SXB** boards. It provides a small foundation for
loading programs, inspecting memory, maintaining flash, and starting other
firmware. On the W65C816SXB, the monitor runs in emulation mode.

**Current release: [v2.0b1](https://github.com/95westus/STR8-N/releases/tag/v2.0b1).**
Beta 1 promotes the exact tested `2.0a24c1` firmware. Its banner, filenames,
launchers and installation confirmation retain a24c1; Bank Maintenance
remains 1.0. See the [beta notes](docs/STR8N_V2_BETA1_RELEASE_NOTES.md)
for qualification scope and remaining limits.

## What it does

The resident monitor occupies Bank 3's 4 KiB `$F000-$FFFF` sector. Its
flash-writing worker runs from RAM. The core needs no EDU daughterboard,
RTC, SPI SRAM, crypto hardware, HIMON, or other monitor. It uses the board's
FT245 USB console.

- Select any of the four flash banks and inspect its contents.
- Display memory, edit permitted RAM, load S19 programs into RAM, and execute them.
- Install aligned whole-sector S19 images and perform guarded flash edits.
- Boot another bank through its RESET vector.
- Save boot settings, including the target bank, address or RESET-vector target,
  startup delay, and whether autostart is enabled. Configuration lives in the
  core at `$FFD0-$FFDF`.
- Provide fixed RAM console and interrupt interfaces for application programs.

The separate **Bank Maintenance 1.0** RAM utility adds sector erase,
RAM/flash copies in all four directions, comparisons, and a buffered
4 KiB editor with sector read/write and CRC. It is included in the package.
See the [maintenance guide](docs/STR8N_BANK_MAINT_V2.md) for commands and limits.

## Download and start

**WARNING - power failure during flashing can be dangerous.** Loss of power
during flash erase/programming, including installation or a configuration
save, can corrupt firmware or boot vectors and leave the board unbootable.
Recovery may require an external flash programmer. STR8-N does not guarantee
power-loss recovery or automatic rollback. Keep power stable, retain a
recovery backup, and do not disconnect USB/power or press RESET/NMI until
the operation reports verified completion.

Download the
[beta 1 ZIP](https://github.com/95westus/STR8-N/releases/download/v2.0b1/str8n-v2-b1.zip)
and extract it. The ZIP contains the Windows and Linux launchers, the
matching BIN/S19 images, Bank Maintenance, the public assembly include,
and the current documentation. Start with `docs/QUICKSTART.pdf` or
`docs/QUICKSTART.md` inside the ZIP.

For a board with stock WDCMONv2 in Bank 3, run the launcher from the extracted
folder. On Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\INSTALL-A24C1.ps1
```

On native Linux, install Python 3 and pyserial, then run:

```sh
sh ./INSTALL-A24C1.sh
```

The launcher prompts for the serial port, physical RESET, and board type.
It loads the installer into RAM and verifies readback before execution.
The installer accepts a selected backup bank/range or an explicitly
confirmed no-backup choice, then installs the matching core image.
Console colors mark information in cyan, input and writes in yellow,
success in green, and failures in red.

For an already installed STR8-N board, follow the
[operator manual](docs/STR8N_V2_A24C1_MANUAL.md) for reconnecting and the
[configuration guide](docs/STR8N_V2_FLASH_CONFIG.md) for supported updates.

## Documentation

| Guide | Contents |
| --- | --- |
| [Quickstart](docs/STR8N_V2_A24C1_QUICK_START.md) | Installation, RESET timing, colors, first commands, and maintenance loading |
| [Operator and technical manual](docs/STR8N_V2_A24C1_MANUAL.md) | Monitor commands, startup settings, reconnecting, and application interfaces |
| [Detailed technical guide](docs/STR8N_V2_A24C1_TECHNICAL_GUIDE.md) | Mermaid maps, flows, diagrams, ABI, flash behavior, and acceptance checks |
| [Maps and charts](docs/STR8N_V2_A24C1_MAPS.md) | RAM/flash allocation, installation flow, and capacity |
| [Stock-board installer guide](docs/STR8N_V2_CONFIG_WDCMON_INSTALL.md) | Unified C02/816 installer, backup selection, verification, and recovery |
| [Configuration guide](docs/STR8N_V2_FLASH_CONFIG.md) | Core boot settings and guarded migration |
| [Bank Maintenance guide](docs/STR8N_BANK_MAINT_V2.md) | Utility commands, editor, copies, erase, and staging |
| [Package contents](docs/STR8N_V2_A24C1_RELEASE_ZIP_PROPOSAL.md) | The original kit inventory and beta additions |
| [Beta notes](docs/STR8N_V2_BETA1_RELEASE_NOTES.md) | Release identity, qualification and flashing disclaimer |
| [Manual index](docs/RELEASE_MANUALS.md) | Current guides and test records |

## Sources and validation

The current firmware sources are in [src/v2-config](src/v2-config).
Builds require Python 3 and the WDC assembler/linker on PATH:

```text
make v2-config-wdcmon
make bank-maint-v2
```

Validation targets are `make v2-config-check`,
`make v2-config-wdcmon-check`, and `make bank-maint-v2-check`.
`python tools/package_v2_a24c1.py` builds and verifies the release ZIP.
The [public assembly include](src/v2-config/str8n-v2-public.inc) defines
application entry addresses and interrupt pointers.

The firmware, installer, safety/recovery, maintenance, and offline launcher
checks passed. The owner also reported a successful
[native Linux run](docs/STR8N_V2_A24C1_LINUX_TEST_2026-10-02.md) on 2026-10-02.
The [C02 installation report](docs/STR8N_V2_CONFIG_COM3_INSTALL_2026-10-01.md)
records the detailed a24c1 board observations. The
[two-board acceptance record](docs/STR8N_V2_A24C1_TWO_BOARD_ACCEPTANCE_2026-10-03.md)
closes the beta 1 migration/reset milestone: owner-confirmed stock migration
and captured physical RESET/core readbacks on both CPU families.
The cold/configuration, practical regression and backup/recovery records
linked in the beta notes cover the subsequent two-board acceptance work.
Qualification remains scoped to those records, including the distinction
between modeled flash faults and physical RAM-fixture recovery checks.

Historical sources and dated board reports remain in the repository. Their
results apply to the versions tested. The a24c2 RAM layout is a proposal
and is not implemented in a24c1.

STR8-N is independent of WDC and R-YORS. See [LICENSE](LICENSE).
