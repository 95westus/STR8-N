# STR8-N SPI SRAM implementation plan

Recorded 2026-10-07. Add an optional shared SPI service and 23LCV1024 storage
provider while retaining the proven flash SAVE/RESTORE/TABLE path on every
board. EDU boards may use flash or SPI SRAM for saved programs and allocate
part of SPI SRAM as workspace. This plan specifies staged implementation and
qualification; it does not start implementation, board writes or installation.

Subsequent progress on 2026-10-07: the requested beta13/CLOCK 1.5 update passed
on all three boards, and [SPI Phase 1](STR8N_V2_SPI_PHASE1_2026-10-07.md) now
contains measured placement and interface proposals. SPI implementation and
RAM-prototype qualification passed in [Phase 2 on 2026-10-08](STR8N_V2_SPI_PHASE2_2026-10-08.md).
The [Phase 3 resident candidate](STR8N_V2_SPI_PHASE3_2026-10-08.md) also passes
models and offline update rehearsals; it has not been installed.
[Phase 4 named storage](STR8N_V2_SPI_PHASE4_2026-10-08.md) now adds an unflashed
standalone utility. [Phase 5](STR8N_V2_SPI_PHASE5_2026-10-08.md) now provides
the paired adjustable layout and workspace library in models. Physical
qualification and installation are next in Phase 6.

## Agreed requirements

- Target W65C02S assembly and optimize all new code for size. The same code
  supports W65C816SXB in emulation mode; native 816 support remains deferred.
- Keep one compact SPI transfer engine with device adapters above it. Use
  compact 65C02 instructions, loops and shared routines; measure ROM, board
  RAM, zero-page and stack costs at each phase. Preserve required timing.
- Keep flash storage available with or without EDU. Preserve existing flash
  record compatibility and default `R` behavior. Select SPI storage explicitly
  at first, so identical names across providers cannot change program selection.
- SPI SRAM contains saved program images and workspace. Programs restore into
  CPU-addressable RAM for execution; SPI capacity is not executable CPU RAM.
- Start with approximately 64 KiB for program storage and the remainder for
  workspace, with adjustable allocation. Management data consumes part of the
  128 KiB capacity; report usable bytes as well as gross region sizes.
- The user confirms a 23LCV1024 on each EDU. The EDU also has an ATECC608A
  crypto device on I2C. Account for future crypto transport requirements in
  the bus design; crypto commands, provisioning and key management are deferred.
- Keep RTC time, trim, outage history and identity binding intact. Missing EDU
  or unusable SPI storage must leave normal flash restore and recovery usable.
- Keep raw board backups, serial transcripts and qualification readbacks in
  ignored owner-local directories. Commit sources and reviewed documentation.

WDC documents SPI clock on VIA PB0, MOSI on PB1, MISO on PB5, SRAM select on
PB2 and mikroBUS SPI select on PB3. I2C uses VIA PA0/PA7. The CR2032 supplies
backup to the RTC and serial SRAM. The ATECC608A uses I2C.
[WDC EDU datasheet, sections 3.1, 3.3, 3.5 and 3.7](https://www.wdc65xx.com/wdc/documentation/W65C02EDU.pdf).

## Phase 1 Footprint and interface design

Inventory installed beta12 and the unflashed beta13/CLOCK 1.5 candidate as
separate baselines. Measure available flash, gateway RAM, zero-page and stack
space before selecting placement. The current monitor is 3,967 bytes against
a 3,968-byte limit; its launcher is 1,754 bytes against 1,760. Parser additions
and another service cannot be assumed to fit. Do not allocate another sector
as a default solution. Produce measured placement alternatives first, with
fixed recovery F unchanged as the initial goal.

Specify versioned SPI discovery, request/result fields, supported device
profiles, transfer bounds, chip-select lifetime, buffer checks and failure
semantics. Use one complete transaction per public call. Support transmit,
receive with a defined filler byte, and full-duplex exchange without requiring
clients to toggle chip-select themselves. Begin with the SRAM's supported SPI
mode; expose unsupported modes as explicit refusals rather than implied support.
Coordinate SPI and I2C ownership of the VIA and preserve unrelated state.

Specify the SRAM block API separately, using three address bytes with a checked
range of $00000-$1FFFF. Set command/storage-selection syntax only after measuring
dispatcher fit. Review the I2C design for a later crypto adapter's wake timing,
bounded execution waits/polling and packet lengths. Preserve the current I2C
ABI; identify any required versioned additions without implementing crypto.

Installed optional software currently reserves $6500-$66FF and limits user RAM
to $64FF, inclusive, even without EDU. A device's absence does not free a
software reservation. Measure any additional SPI reservation and publish the
resulting RAM limit through validated discovery before enabling clients.

**Completion:** a documented ABI/ownership proposal and measured placement
report, including selected transfer limits, CPU/bank/interrupt contracts,
software versus hardware discovery, and explicit storage selection.

## Phase 2 SPI and SRAM prototype in board RAM

Build a small RAM-loaded prototype and exercise the SPI engine before changing
flash. Preserve caller bank, documented processor state and unrelated VIA state.
Keep SRAM and mikroBUS selects inactive when idle; only the selected target may
receive a transaction. Bound each operation and release select on exit. Reuse
the existing foreground calling restrictions and bank/NMI discipline.

SPI has no I2C-style address ACK. A completed transfer proves clocks were sent,
not that SRAM exists. Establish SRAM usability through checked mode handling
and read/write/readback tests. Reserve a probe area, preserve its contents and
avoid probing over saved records. Never initialize the full array implicitly.

Test sequential block transfers in both halves of the array, especially
$0FFFF/$10000, $1FFFF, CPU-buffer boundaries and end-of-array overflow. The
23LCV1024 sequential counter wraps at the array end, so reject an out-of-range
request before issuing it.
[Microchip 23LCV1024 datasheet, section 2](https://ww1.microchip.com/downloads/en/DeviceDoc/23LCV1024-1Mbit-SPI-Serial-SRAM-with-Battery-Backup-and-SDI-Interface-20005156B.pdf).

**Completion:** host models and scoped RAM-prototype checks pass on 2205 and
2609; 2512 demonstrates bounded no-EDU handling. Save exact image hashes,
measured sizes, bank/VIA restoration and repeated SRAM readbacks.

## Phase 3 Optional resident SPI and SRAM service

Integrate the measured prototype using a small RAM gateway and flash-resident
code. Discover SPI independently of RTC and discover SRAM usability separately
from the SPI transport. Keep requests bounded and caller buffers within the
published application-RAM limit. Activation must not erase or format SRAM,
change RTC settings or access crypto.

Protect installed gateway/state RAM from monitor, loader, restore and MAINT
operations. Keep ownership stable until RESET, including after a peripheral
error. Provide a small runnable block-read/write example. Restore/run clients
must recheck descriptors after RESET or monitor reentry.

**Completion:** linked-code models pass optional-software rejection, absent
hardware, all caller banks, busy refusal, malformed requests, preservation and
RTC/I2C regressions. Deliver a matched unflashed candidate with a size report
and installation recipe; qualify that recipe before the hardware rollout.

## Phase 4 Saved programs in SPI SRAM

Add a storage provider with a versioned region layout, named directory and
saved-image metadata: original load address, entry/run behavior, length,
sequence/version, checksum and final completion marker. Reuse proven flash
record semantics where practical. Keep flash formats and default lookup intact;
add explicit provider selection for save, restore and table operations.
An explicit SPI request reports unavailable/corrupt storage rather than silently
executing a same-named flash program.

Begin with the default split. Reserve management bytes within the program area
and expose accurate used/free counts. Save and verify payload and metadata
before publishing the completed record. Replacement must retain the previous
valid image until the new image is committed, or refuse for insufficient space.
Deletion and bounded space reclamation must not disturb unrelated records.

Restore validates the complete record, checksum and destination against the
current CPU-RAM limit before overwriting application RAM. A transfer failure
after copying begins must report partial completion and prevent execution;
do not promise rollback without sufficient staging RAM. Never execute directly
from SPI SRAM. Invalid retained storage must not trigger silent formatting.

**Completion:** host checks cover incomplete/corrupt records, duplicate names,
replacement, deletion, full storage, stale directories, invalid destinations
and interrupted transfers. Demonstrate one named program saved/restored from
flash and SPI SRAM with identical loaded bytes and existing run behavior.

## Phase 5 Adjustable allocation and workspace

Make the program/workspace boundary configurable in coarse allocation units
chosen for small code and metadata. Grow/shrink only when records and active
workspace allocations permit it. Refuse conflicting changes; keep automatic
relocation and compaction deferred initially. Protect the layout with a version,
checksum and completion marker so an interrupted update cannot expose
overlapping regions.

Provide a small workspace API for claim, release, read, write and capacity query.
Use region-relative offsets or handles with bounds and owner/generation checks.
Track live claims across normal monitor reentry. RESET invalidates temporary
workspace handles; saved-program records remain eligible for validation and
reuse. Session recovery for assembler workspace is later work.

Supply a small metadata-table client showing a board-RAM cache backed by SPI
workspace. Measure transfer costs and cache RAM. This proves the workspace
interface without starting the separate assembler/runtime implementation.

**Completion:** resize refusal/preservation, allocation exhaustion, stale
handles, overlapping requests, RESET cleanup and cached metadata access pass
models. Report ROM and RAM costs of allocation separately from the SPI engine.

## Phase 6 Board qualification and installation

Prepare migrations from exact verified installed images, including the choice
of retaining installed CLOCK 1.4 or incorporating the separate CLOCK 1.5
candidate. Preserve RTC identity tails and saved flash records. Back up complete
flash and retained SRAM contents locally before hardware mutation. Installation
uses the qualified recipe and is a separate action from adopting this plan.

| Board | Qualification focus |
| --- | --- |
| 2512 COM4, no EDU | Flash-only save/restore/table, absent SPI storage, boot/recovery and guards |
| 2205 COM3, EDU | W65C02S SPI/SRAM, both storage providers, workspace and RTC/I2C preservation |
| 2609 COM8, EDU | Same service in 816 emulation, all caller banks and preserved interrupt behavior |

Check both monitor slots, CLOCK/MAINT return, memory guards, representative
program execution, full-address SRAM access and exact final flash readbacks.
Check physical RESET and main-power-cycle retention on EDU boards while
preserving RTC time, trim, EEPROM history and EUI binding. Battery-removal
behavior is modeled as untrusted/lost contents; physical removal is outside
this plan. Retention testing does not establish remaining battery life.

**Completion:** transcripts, hashes, models and board readbacks agree for the
selected matched candidate. Record any untested device profiles explicitly.
An external mikroBUS device is not qualified solely by testing the SRAM.

## Phase 7 Documentation and delivery

Publish the SPI and SRAM APIs, provider-selection commands, saved-record and
allocation layouts, actual usable capacities, runnable examples, error/partial
completion behavior and recovery procedures. Publish assembled size reports
and the final user-RAM limit, including the absent-EDU reservation rule.
Update README and TASKS with the qualified firmware/CLOCK combination.

Keep development candidates distinct from packaged releases. Run the board
backup exclusion audit before committing or publishing. Package sources and
generated firmware only; retain raw backups and hardware evidence locally.

**Completion:** documentation matches the measured/qualified artifacts and
clearly identifies deferred crypto, native 816, assembler integration and
additional SPI-device work.

## Phase dependencies

Proceed in order: placement/ABI, RAM prototype, resident service, named storage,
adjustable workspace, board rollout, then delivery. Hardware checks for the
prototype and integrated candidate may identify changes to earlier contracts;
repeat only the checks affected by those changes. Phase 1's measured proposal
and Phases 2-3 are now complete for RAM qualification and the resident candidate;
Phase 4's named SRAM program storage is complete in the linked models;
Phase 5's adjustable allocation/workspace is complete in the linked models;
Phase 6's physical qualification/installation is the next implementation step.

Related contracts: [shared I2C API](../tools/v2-rtc/I2C_API.md),
[current RTCC binding](STR8N_V2_RTCC_BINDING_2026-10-07.md),
[normal trim service](STR8N_V2_TRIM_EEPROM_POLICY_2026-10-07.md),
[assembler direction](STR8N_V2_LAYERED_ASSEMBLER_PROPOSAL.md) and
[runtime linking direction](STR8N_V2_RUNTIME_LINKING_DIRECTION.md).
