> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# Beta35 technical manual — draft

Target: **2.0b35 generation 47**, frozen **FT245/F30D** payloads. This draft
records a source, ABI, example and command-context audit. Qualification uses a W65C02 instruction model;
native 816 execution, electrical interruptions and general route acceptance
are separate gates. ACIA and crypto remain deferred. The primary checkout's
v2.1 work is outside this document.

## CPU, banking and memory ownership

The CPU sees RAM below `$7F00`, board I/O at `$7F00–$7FFF`, and the selected
32 KiB flash bank B0–B3 at `$8000–$FFFF`. CPU addresses alone do not identify
flash contents without the selected bank. External SPI SRAM is accessed through
services, rather than directly mapped into the CPU address space.

| CPU bank-zero range | Ownership |
| --- | --- |
| `$0000–$00FF` | Zero page; monitor/private scratch and application ABI scratch have distinct contracts |
| `$0100–$01FF` | CPU stack |
| `$0200–$64FF` | Application RAM when optional services are active |
| `$6500–$66FF` | Optional-service reservation; usable by applications only when discovery permits |
| `$6700–$77FF` | Monitor/journal/staging workspace |
| `$7800–$7BFF` | Monitor worker/private staging |
| `$7C00–$7DFF` | Console lines, state, configuration and discovery |
| `$7E00–$7EFF` | RAM vectors and initialized public ABI |
| `$7F00–$7FFF` | Board I/O |
| `$8000–$FFFF` | Selected flash bank |

At `$7D04`, the `SV` discovery descriptor carries format, flags, a service
pointer and application-end limit. `$7D0C = $FF` reserves `$6500–$66FF` until
reset. Discover capability before accessing the service area: with EDU OFF it
may hold ordinary application bytes. A service failure does not release an
active reservation. Use the discovered limit instead of the public include's
historical `$66FF` constant. Loading utilities/ASM or a RAM installer can
replace application RAM; save/restore ownership must be explicit.

## Public ABI and interrupts

The ROM facade begins with a signature at `$F000`; its calls require the
resident flash bank visible. Initialized RAM ABI signature/descriptor begins
at `$7E60`. Its 13 call entries span `$7E64–$7E88`, allowing calls with any
flash bank selected. Applications must validate format/capabilities and obey
the include contract: IRQ disabled, decimal clear; on 816, E=1, D=0, DBR=0,
PBR=0. These are emulation-mode, non-reentrant calls.

Emulation interrupt pointers begin at `$7E00`, native pointers at `$7E10`.
Native vector support does not advertise native monitor-service calls. Native
handlers own widths, direct/data bank setup, interrupt source, stack frame and
RTI. Publish a native NMI pointer under the `$00F4` gate as documented; do not
overwrite live vectors while a campaign runner owns the machine.

## Persistent layout and configuration

The clean release's `layout.json` enumerates 13 owned payload ranges. It is
not an erase plan: unowned bytes within the same sector must be preserved.
B1 contains CLOCK storage and ASM pages; B2 contains XIP utilities and smaller
assets. B3 contains RTC/journal code, monitor slots A/B, configuration/wear
journals C/D, and recovery E/F. Mutable service records in B3 `$9C00–$9FFF`
are excluded from owned code ranges. B0, user-program areas, fallback A,
C/D and holes in B2 are not disposable package padding.

The RAM configuration copy is at `$7D80`, 16 bytes. Its durable source is the
latest valid committed C/D journal record, not a fixed pocket in F. WC records
contain sequence, settings/monitor preference and conservative erase counts;
validity includes format, CRC and commit marker. Monitor preference must name
a committed valid slot with matching generation. Backup manifests and full
bank hashes bind restoration to a specific source; unknown/stale inputs refuse.

## Staged transaction and wear-aware recovery

The frozen historical installer does not include the later append-only count
reservation helper. Separate **model-only** composition adds a 530-byte helper
and explicit three-byte JMP detour through a RAM wrapper without modifying the
sealed template or firmware payloads. It validates all bank preimages, appends
a reservation naming retained A, stages A in the opposite journal sector,
writes the payload sectors/monitor commits, then commits final B35 preference
in the original journal sector. Counts reserve all planned erase attempts
before the first erase. An interrupted run can overcount unattempted erases.

Receipt-bound restoration replays recorded mutations against the verified
original backup, carries forward durable count maxima and reserves additional
erases. Original bytes outside new C/D records return exactly; old backup
counters and historical sequence numbers are not replayed. Interrupted
restoration recovery accepts only its pinned saved lineage; it is not a
generic repair interface for arbitrary corruption.

Bounded polling/readback failures can halt in RAM after an erase, a partial
program or even a valid final preference commit. A reported failure does not
prove rollback. Preserve transcripts, actual flash, count records and the
original backup before determining next steps. The inherited installer banner
still names beta27; exact plan and payload hashes identify the composed beta35
test image. Neither that text nor a success message substitutes for full image
validation. No automatic live retry/reset is authorized in the campaign.

## RTC, outages and measurement limits

RTC calendar uses the UTC convention; local display uses a saved fixed offset.
Trim changes oscillator correction; offset changes display conversion. Device
identity binding and power-fail history are separate persistent evidence.
Down/up hardware captures are yearless and minute resolution. Beta35's shared
duration code anchors the up year, infers a prior year when the down date wraps,
validates calendar fields and reports estimated days/hours/minutes. It cannot
recover seconds, multiple elapsed years or unrecorded outages. Unknown input
must not be turned into a precise duration or lifetime uptime percentage.

Battery policy uses dated retained records; it does not measure voltage.
Backward-date detection can append an uncertainty record at boot/BATTERY.
QA35-006 verifies the expected append on an archived fixture and stable second
boot. Thus a boot/status path is not universally free of persistent effects.

The immutable four-board baseline and each fresh NIST sample retain acquisition
intervals. Propagate baseline and sample uncertainty when computing drift.
Offset ranks are not frequency rankings; a zero-containing rate interval does
not justify a trim change. Powered-off rate requires post-return evidence.

## Qualification boundaries and source

Archived and derived FT245/F30D fixtures have linked transaction, saved-state
boot, interruption and wear-aware restoration model evidence. Stock WDC,
legacy/core/ABI converters and A35-dependent active-B routes remain refused or
unimplemented. A35 native BATCH issue STR8N-007 requires a separate candidate.
Physical/native/electrical acceptance and full migration-route qualification
remain open despite the offline manual/example and review-kit checks. `release_qualified` and `installation_permitted`
stay false. The 2512 soak/RTC campaign continues independently; other boards
remain off and real clocks/trims/settings stay unchanged.

- [Public ABI](../../release/beta35/source/assembler/str8n-v2-public.inc)
- [Service discovery](../../release/beta35/source/core/service-eq.inc)
- [Core state and I/O definitions](../../release/beta35/source/core/str8n-v2-eq.inc)
- [Owned payload layout](../../release/beta35/layout.json)
- [Flash worker](../../release/beta35/source/migration/str8n-v2-flash-worker.inc)
- [Outage calculation](../../release/beta35/source/clock/outage-duration.inc)
- [Route evidence and exclusions](../STR8N_V2_BETA35_MIGRATION_MATRIX.md)
