# STR8-N

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

## Current development: beta23 generation 32

The current development image is **beta23 / CLOCK 1.6**, with MAINT 1.8,
EDU 1.2, SRAM 1.2 and WORK 1.2. It has passed independent functional,
interrupt, data-preservation and controlled-recovery qualification on
**2512, 2205, 2604 and 2609**. The published downloadable release remains
**beta4**; the extended soak and final RC ZIP are still outstanding.

### Features added since the published beta4 release

| Feature | Current behavior |
|---|---|
| Per-board EDU profile | Saved ON/OFF activates at cold RESET/J3. ON reserves `$6500–$66FF`; OFF releases all 512 bytes for standalone applications through `$66FF`, even with EDU physically attached. Pending changes show `RESET required: ON/OFF`. |
| UTC and local time | Monitor TIME and CLOCK provide decoded UTC, running/backup status and trim. Fixed signed offsets from −12:00 to +14:00 include half/quarter-hour zones and date rollover. Daylight-saving adjustment remains manual. |
| Explicit clock administration | Confirmed SET, normal signed TRIM and OFFSET apply immediately without reset. Alarm/coarse/output ownership and readback are guarded. |
| Outage history and RTC identity | Verified four-slot EEPROM outage journal, factory EUI display, remembered-identity comparison and explicit acceptance. Unknown retained formats are preserved rather than automatically cleared. |
| Resident SPI SRAM services | Versioned foreground discovery and bounded transfers to the 128 KiB external SRAM. Raw managed writes are protected; optional hardware failures report errors without releasing active reserved RAM. |
| Named SRAM programs | Save, table, CRC-verified restore/run, replacement, tombstone deletion and explicit reclaim. Named `R SRAM` preserves ordinary application RAM on entry/exit. Programs execute after copying into CPU RAM. |
| WORK workspace | 16/32/48/64 KiB program-region selection, four owner/epoch/ticket claims, bounded verified writes and stale-handle rejection after cold reset. WORK 1.2 runs at `$5000–$648A`, API `$5003`. |
| Flash/SRAM workflows | AUTO selects a verified erased flash extent without erasing occupied data. MAINT 1.8 copies named programs between flash and SRAM with verified destinations and source retention. |
| Compact boot and quiet return | Beta23 prints one local RTCC boot line; explicit TIME/CLOCK retain details. M1/HOLD return quietly. Clock is stored at B1:B000 and the local-display asset at B2:E000. |
| Technical documentation and examples | Complete boot/console/vector, RTC/I2C/SPI/SRAM and WORK contracts, plus assembled 65C02 examples for UTC, SRAM READ and WORK claim/write/read/restore/release. Examples are mandatory in the eventual release ZIP. |

Fixed F recovery, both A/B monitor slots, the bank-independent RAM console ABI
and the 816 native-vector contract are preserved. The 816 monitor/services use
emulation mode; native service calls are not advertised. The 2609 unattended
SPI startup issue is closed and beta23 was qualified independently of beta22.
MAINT 1.9's SPI-map experiment is not part of the frozen beta23 image.

Start with the [technical guide](docs/STR8N_V2_BETA23_TECHNICAL_GUIDE.md),
[operator guide](docs/STR8N_V2_BETA23_OPERATOR_2026-10-09.md),
[runnable 65C02 examples](examples/beta23/README.md) and
[four-board qualification](docs/STR8N_V2_BETA23_FOUR_BOARD_STORAGE_2026-10-09.md).
The new examples passed eleven linked-model checks; their physical execution
is a separate checkpoint. STR8N-001 ACIA receive on 2512/2205 remains deferred.
Native RTC/I2C, general external peripherals, alarms/MFP and crypto remain
outside the RC matrix. See [RC gates](docs/STR8N_V2_RELEASE_CANDIDATE_PLAN_2026-10-09.md).

### Time drift and continuing soak/retention validation

The October 10 pre-shutdown snapshot at **18:11 CDT** passed on all four boards.
Each has **21 retained checkpoints over approximately 24 hours**, plus its
baseline in a 22-point free-intercept fit. Last verified settings were EDU ON,
normal **TRIM 0**, unchanged control registers/identities and fresh NIST reference
checks. All rates below are estimated fast-clock drift; proposed corrections
remain **unapplied**.

| Board | Fitted rate, ppm | Compatible measurement bounds, ppm | Fitted seconds/day | Nominal proposed trim |
|---|---:|---:|---:|---:|
| 2205 | +18.36 | +10.43 to +24.26 | +1.59 | −18 |
| 2512 | +12.43 | +4.28 to +18.86 | +1.07 | −12 |
| 2604 | +12.47 | +7.14 to +20.49 | +1.08 | −12 |
| 2609 | +14.98 | +7.92 to +20.91 | +1.29 | −15 |

Bounds include one-second RTC quantization, serial acquisition, NTP reference
and baseline uncertainty; they are not statistical confidence intervals.
Short cumulative estimates share a baseline, so their sample SD is not clock
jitter. Power-state/temperature effects have not been isolated.

**Soak and retention validation continues for 2604/2609**, with completed
read-only exercise runs and planned post-outage verification. All four boards
were confirmed main-power-off at **18:13 CDT October 10**, with backup batteries
connected; the current segment is a battery-backed retention interval. A
powered-on 48–72-hour soak is not claimed complete. The finite drift schedule
has ended, and the next measurement is due after power returns. 2512/2205 retain
functional qualification without a claimed extended soak. 2604's foreign EEPROM
history remains preserved with HISTORY error $90 and its power-fail latch.

See the [drift/soak summary](docs/STR8N_V2_BETA23_DRIFT_SOAK_2026-10-10.md) for
measurement limits, outage timing and acceptance status. Clean source rebuilds
match all 17 frozen artifacts; final RC source/package verification and the
extended soak remain release gates. Board backups and raw transcripts remain
owner-local and excluded from Git/release packages.

## Historical development checkpoints (beta12–beta22)

The optional MCP79411 RTCC work is implemented in the development tree and
qualified on boards 2512 (W65C02SXB, no EDU), 2205 (W65C02SXB, EDU) and 2609
(W65C816SXB, EDU). This section records earlier placement/tests, not the current
installed image. The published download above remains beta4; beta15 is not
yet a packaged release.

- **UTC access:** `TIME` displays time at the monitor. `R CLOCK` starts CLOCK
  for time/status, EUI and outage-history inspection, with confirmed administrative
  operations. Dates retain `YYYY-MM-DD hh:mm:ss`. DOW is **1 = Monday through
  7 = Sunday**; CLOCK calculates it automatically from the entered SET date.
- **Optional hardware and program access:** the versioned RTC/I2C service fails
  safely when EDU is absent. User programs read decoded time and check success;
  a [runnable read-only example](tools/v2-rtc/time-example.asm) is supplied.
  RTC/I2C calls support 65C02 and 816 emulation with D/DBR/PBR zero.
- **RAM ownership and EDU mode:** `R EDU` views/saves ON or OFF. With ON active,
  installed service software reserves `$6500-$66FF`, so user RAM ends at
  **`$64FF`, inclusive, even without EDU**. Explicit OFF at RESET disables
  RTC/I2C/SPI/SRAM and returns all 512 bytes, allowing user RAM through **`$66FF`**.
  Mode changes stay pending until RESET; monitor return never reinstalls over
  reclaimed RAM. Device failures never select OFF. Programs use the validated
  discovery descriptor's capabilities and limit. See
  [EDU mode](docs/STR8N_V2_EDU_MODE_2026-10-08.md).
- **Persistent power-fail history:** four 32-byte slots use the chip's ordinary
  EEPROM. Boot saves, verifies and commits an event before acknowledging it.
  CLOCK provides `HISTORY`, `SHOW n`, `CLEAR n` and `CLEAR ALL`; clearing history
  is separate from power-fail ACK and leaves UTC unchanged.
- **RTC identity:** boot and CLOCK show the protected factory EUI-48. Remembered
  identities use spare space in existing B3 sector 9, with `unbound`/`changed`
  indications and explicit `ACCEPT EUI`. No additional sector is allocated.
- **Placement and qualification:** RTC/I2C code is in B3:8, outage/identity
  services in B3:9, MAINT 1.7 in B1:8/9 and CLOCK in B2:8/9. Fixed recovery F
  remains unchanged. Beta12's full monitor, ABI, loader/restore, guards, RTC/I2C,
  CLOCK/history and physical BRK/IRQ/NMI regressions passed on all three boards.
  2609 also passed native BRK/NMI. Beta13's scoped update checks are recorded
  below; native RTC/I2C calls remain deferred.

**Alarm 0, Alarm 1 and MFP output configuration are deferred**, along with RTC
SRAM, saved-record
timestamps and native RTC calls. Longer clock-drift measurements remain pending;
current UTC baselines are retained without automatic time or trim adjustments.
[CLOCK 1.5 normal trim](docs/STR8N_V2_TRIM_EEPROM_POLICY_2026-10-07.md)
provides confirmed signed `TRIM` adjustments with coarse mode OFF.
[Beta13 installation checks](docs/STR8N_V2_TRIM_HARDWARE_2026-10-07.md) passed
on all three boards; UTC and zero trim were retained. EEPROM protection remains
unchanged. SPI's [RAM prototype passed Phase 2](docs/STR8N_V2_SPI_PHASE2_2026-10-08.md)
on all three boards, preserving complete EDU SRAM contents and flash/RTC state.
The [Phase 3 resident candidate](docs/STR8N_V2_SPI_PHASE3_2026-10-08.md) passes
models and offline update rehearsals without another sector or RAM reservation.
It is not installed. [Phase 4 named SRAM storage](docs/STR8N_V2_SPI_PHASE4_2026-10-08.md)
adds a separate `SRAM` utility with verified save, restore/run, table, deletion
and bounded reclaim. Monitor storage defaults remain flash; commands at the
utility's `SRAM>` prompt select SPI explicitly. The initial payload capacity is
63,488 bytes, with 65,504 bytes available to the
[Phase 5 workspace library](docs/STR8N_V2_SPI_PHASE5_2026-10-08.md). WORK adds
16/32/48/64 KiB program-region selection, four checked workspace claims,
verified writes and a runnable two-row metadata cache. Claims survive monitor
return; RESET invalidates their handles. Public raw SRAM writes stay blocked.
Beta14 and the paired SRAM 1.1/WORK 1.0 utilities are
[installed on all three boards](docs/STR8N_V2_SPI_PHASE6_2026-10-08.md).
Storage/retention and automated regressions pass. After correcting the button
selection, 2609's captured physical S2/RESB reset also passed. Both complete original SRAM arrays were restored;
new layout initialization remains explicit in WORK. No packaged beta14 release
or commit/push is part of this installation.
The installed **WORK 1.1** console accepts `P 16`, `P 32`, `P 48`,
and `P 64` directly in KiB, reports readable decimal capacities, and uses
a plain prompt with help on entry/`HELP`. Resize previews the split and asks
`Apply? [y/N]`; Enter cancels. The API retains 1-4 allocation units.
[WORK's current interface](tools/v2-spi/WORKSPACE_API.md) documents its application
RAM range. Beta15, WORK 1.1 and EDU 1.0 were installed on all three boards:
2512 is OFF with RAM through `$66FF`; 2205/2609 are ON with RAM through `$64FF`.
Both mode transitions, both monitor slots, reclaimed-RAM S19/run, unavailable
services, RAM ABI and BRK/VIA1 timer IRQ checks pass. The EDU boards also pass
WORK's readable resize UI and RTC/EEPROM preservation checks; all temporary
SRAM changes are restored.
The active outage journal requires ordinary EEPROM protection off.

The **beta16 / EDU 1.1 status candidate** implemented the selected
boot layout: separate RAM and EDU lines, RTCC UTC before EUI, and validated
SSRAM program-payload/workspace capacities. `R EDU` displays that block before
its prompt and shows pending mode changes independently. Allocation reads leave
SRAM metadata, live handles and caller transfer bytes intact. The shared sealed
formatter fits spare space in existing B2 sector C and borrows only monitor
staging RAM. [Status layout and local checks](docs/STR8N_V2_STATUS_DISPLAY_2026-10-08.md).
That display is included in the installed beta17 update below.

**Beta17 is installed on 2512, 2205 and 2609**, incorporating that display and moving
WORK 1.2 to `$5000-$648A` (API `$5003`), supporting programs from `$0200` through
`$4FFF` while WORK is loaded. Its named `R SRAM` loader preserves `$0200-$64FF`.
`S bank AUTO start end label` selects/displays a safe erased flash extent;
flash-only MAINT 1.8 adds verified named copies between flash and SPI SRAM,
retaining each source. MAINT now needs three flash sectors. There is no new
permanent RAM reservation. [Commands, placement and local checks](docs/STR8N_V2_STORAGE_TOOLS_2026-10-08.md).
Installed utilities are WORK 1.2, SRAM 1.2, MAINT 1.8 and EDU 1.2; CLOCK stays
1.5. DEMO/DEMO2 are omitted. Full flash readbacks, both slots, ABI/IRQ, retained
UTC/trim/EEPROM/EUI and both complete SRAM arrays pass.
[Installation evidence and limits](docs/STR8N_V2_STORAGE_HARDWARE_2026-10-08.md).
2609's disabled VIA CB flags can block SPI SRAM after RESET; verified idle-port
acknowledgment restores access. [STR8N-003](docs/issues/SPI_2609_DISABLED_CB_FLAGS.md)
tracks that startup limitation.

[Storage timings](docs/STR8N_V2_STORAGE_TIMINGS_2026-10-08.md) record preserving
2609/beta17 measurements at nominal 8 MHz: about 16 ms for sector erase,
160â€“176 ms for a fresh 4-KiB flash program/verify, and 322â€“343 ms for a chunked
4-KiB SRAM WRITE. Flash estimates include the documented USB-baseline precision
limit; SRAM uses the VIA timer. WORK administration adds further overhead.

| Development guide | Contents |
| --- | --- |
| [RTCC/CLOCK operation and identity binding](docs/STR8N_V2_RTCC_BINDING_2026-10-07.md) | Commands, boot messages, existing-sector identity storage and ownership |
| [TIME and program example](docs/STR8N_V2_TIME_COMMAND_2026-10-07.md) | Compact monitor command and read-only program access |
| [Shared I2C interface](tools/v2-rtc/I2C_API.md) | Discovery, transaction buffers, bounded errors and managed-device policy |
| [Beta12 hardware installation](docs/STR8N_V2_RTCC_BINDING_HARDWARE_2026-10-07.md) | Verified updates, EUI acceptance and preservation checks |
| [Beta13 hardware installation](docs/STR8N_V2_TRIM_HARDWARE_2026-10-07.md) | CLOCK 1.5, retained trim/UTC, both slots and exact flash checks |
| [Beta12 on-board regression](docs/STR8N_V2_BETA12_BOARD_REGRESSION_2026-10-07.md) | Physical coverage, results and limits |
| [Latest drift comparison](docs/STR8N_V2_RTC_DRIFT_POST_BETA12_2026-10-07.md) | UTC offsets, baseline changes and measurement uncertainty |
| [SPI SRAM phased plan](docs/STR8N_V2_SPI_SRAM_PHASED_PLAN_2026-10-07.md) | W65C02S size targets, optional SPI, flash/SRAM program storage and adjustable workspace |
| [SPI Phase 1](docs/STR8N_V2_SPI_PHASE1_2026-10-07.md) | Measured size reductions, existing-sector target, proposed ABI and ownership |
| [SPI Phase 2](docs/STR8N_V2_SPI_PHASE2_2026-10-08.md) | Qualified W65C02S RAM prototype, full SRAM preservation and revised size placement |
| [SPI Phase 3](docs/STR8N_V2_SPI_PHASE3_2026-10-08.md) | Matched resident candidate, discovery/guards and offline update recipes |
| [SPI Phase 4](docs/STR8N_V2_SPI_PHASE4_2026-10-08.md) | Named SRAM utility, transactional publication, reclamation and model checks |
| [SRAM utility and record layout](tools/v2-spi/SRAM_STORE.md) | Explicit provider selection, commands, capacities, RAM lease and failure behavior |
| [SPI Phase 5](docs/STR8N_V2_SPI_PHASE5_2026-10-08.md) | Adjustable layout, workspace lifecycle, interruption models and measured costs |
| [WORK API and cache example](tools/v2-spi/WORKSPACE_API.md) | Handles, owner/epoch checks, region bounds, library RAM and metadata cache |
| [Beta15 saved EDU mode](docs/STR8N_V2_EDU_MODE_2026-10-08.md) | Reset-only ON/OFF, reclaimed 512 bytes, saved utility and hardware checks |
| [Unflashed boot/EDU status layout](docs/STR8N_V2_STATUS_DISPLAY_2026-10-08.md) | Separate RAM/EDU lines, RTCC UTC/EUI, read-only SSRAM allocation and EDU 1.1 |
| [SPI Phase 6 installed qualification](docs/STR8N_V2_SPI_PHASE6_2026-10-08.md) | Fresh archives, installed utilities, exact preservation, retention and open RESET observation |
| [SPI and SRAM API](tools/v2-spi/SPI_API.md) | Bounded transactions, managed policy, returns and runnable example |

Development sources/builders are under `src/v2-rtc-kernel` and `tools/v2-rtc`.
Generated images and raw qualification records stay owner-local under `BUILD`
and `output/qualification`; they are not release downloads or board backups
included in Git. Development upgrade scripts are bound to verified source
images and must not be substituted for the published beta4 migration launcher.
Before committing or publishing, audit tracked files, reachable history and
release ZIP entries with `python tools/check_no_board_backups.py --history`.

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
