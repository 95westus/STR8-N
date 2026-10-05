# STR8-N experimental extensions

This branch, `codex/experimental-extensions`, preserves the manager, named RTS,
command/service registration, selective autoload, configuration, and related
post-beta1 code reductions. It is experimental development, not a beta2 release
or a commitment to the next release's design. Existing `v2-b2` paths, build
targets, firmware banners, and qualification records retain their original
names so tested artifacts remain traceable.

Beta1 maintenance continues separately on `codex/beta1-release`, based on
the published, qualified a24c1 firmware. Moving this work to a branch does not
change firmware already installed on a board.

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

The working source includes post-beta core reductions totaling 34 bytes, leaving
53 contiguous bytes at `$FF9B-$FFCF`. It preserves the beta 1 ABI and exact
S/R extension image; the published beta 1 package remains the qualified
release baseline. These source changes require fresh board qualification.

The latest installed experimental candidate implements [selective autoload](docs/STR8N_V2_B2_AUTOLOAD.md)
through `K AUTO`, independently of application boot C, with optional startup
registration messages. It is installed and checked on 2205 with C autostart off
and R/S/T/X/H selected. Startup dots precede registration messages and the
banner. F is 4,039 bytes (9 free), including named-command registration;
the public ABI, 21.5 KiB application and 2 KiB overlay ranges stay intact.

`COMMAND.REGISTER` v2 is installed and checked on 2205. HELLO/ECHO can be
called directly or through X; H lists both names. Existing v1 registration
remains compatible. See the [command extension guide](docs/STR8N_V2_COMMAND_EXTENSIONS.md).

The separate [2.0b2 manager/RTS candidate](docs/STR8N_V2_B2_MANAGER_RTS.md)
implements one optional manager, service lookup, command registration and named
S/R/T with automatic placement. Build with `python tools/build_v2_b2.py` and
test with `make v2-b2-check`. Application RAM ends at `$57FF`; K selects a
reserved configuration sector and persistent bank/sector masks. Missing or
invalid configuration disables RTS storage while core boot remains independent.
The preceding core/E image passed the scoped [board 2205 checks](docs/STR8N_V2_B2_2205_BOARD_TEST_2026-10-04.md)
on 65C02/FT245. The current host-tested command-catalog revision saves nine
F bytes (3,984 used, 64 free), exposes read-only built-ins through COMMAND.CORE
v1, and preserves the fixed ABI and RAM limits. It requires a matched E/F
update and is now installed and checked on 2205. Permanent H is an independent B3:C flash provider, adding zero
core/E bytes and using zero application/overlay RAM. Build and model-check it
with `make v2-b2-help-flash-check`; its sector S19 uses I, and the existing C
boot setting runs its initializer after reset. It uses a three-byte manager
RAM stub and one registry slot. Application RAM remains 22,016 bytes and the
2 KiB overlay workspace remains available. Permanent H was installed and
passed software-reset automatic registration on 2205, with full RAM/flash
readbacks confirming only B3:C and boot settings changed. Physical RESET and
power-cycle qualification remain pending; the earlier RAM H check is historical. 65C816/native and ACIA qualification, general maintenance
integration and release packaging remain pending.
The [consolidated design](docs/STR8N_V2_BETA2_DESIGN.md) records remaining
configuration and AP runtime work.

[Writing a command extension](docs/STR8N_V2_COMMAND_EXTENSIONS.md) walks through
a buildable, separate H+X flash example, single-letter commands with longer
subcommands, the changes needed for named top-level commands, and optional
ACIA driver integration. The example adds no core/E or application/overlay
RAM bytes. H+X is now installed on 2205, with software-reset autostart at C700;
full bank readbacks and restoration of temporary updater RAM passed. The
[service-provider proposal](docs/STR8N_V2_SERVICE_PROVIDER_PROPOSAL.md) describes
`SERVICE.REGISTER` v1, now implemented in a separate candidate with eight
dynamic entries. It requires reserved B3:B manager backing plus E, uses 49
table/count bytes, and reduces total occupied manager RAM by four bytes.
Core F and application/overlay limits are unchanged. This service revision is
now installed and checked on 2205: callable/data versions, duplicates,
descriptor copying, revalidation and reset withdrawal passed. Full readbacks
prove only B3:B/E changed and temporary RAM was restored. Optional console
binding remains unimplemented.

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
