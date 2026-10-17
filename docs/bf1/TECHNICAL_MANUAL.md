# bf1 technical manual — draft

Current acceptance policy and tonight's prerelease scope: [accepted gates](../STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md).

Target: **2.0bf1 generation 48**, pinned **FT245/F30D** candidate payloads. This draft
records a source, ABI, example and command-context audit. Qualification uses a W65C02 instruction model;
native 816 is deferred outside this candidate’s acceptance scope; electrical
interruptions and general route acceptance are separate gates. ACIA and crypto remain deferred. The primary checkout's
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
RTI. These native-interrupt details are descriptive and unqualified; native
816 is deferred. The architectural contract says to publish a native NMI pointer under the `$00F4` gate as documented; do not
overwrite live vectors while a campaign runner owns the machine.

## Persistent layout and configuration

The candidate build pins 19 artifacts, including distinct A and B monitors.
The transaction plan identifies the sector overlays and protected holes; it is
not a blanket erase plan: unowned bytes within the same sector must be preserved.
B1 contains CLOCK storage and ASM pages; B2 contains XIP utilities and smaller
assets. B3 contains RTC/journal code, monitor slots A/B, configuration/wear
journals C/D, and recovery E/F. Mutable service records in B3 `$9C00–$9FFF`
are excluded from owned code ranges. B0, user-program areas, the transaction’s selected fallback,
C/D and holes in B2 are not disposable package padding.

The RAM configuration copy is at `$7D80`, 16 bytes. Its durable source is the
latest valid committed C/D journal record, not a fixed pocket in F. WC records
contain sequence, settings/monitor preference and conservative erase counts;
validity includes format, CRC and commit marker. Monitor preference must name
a committed valid slot with matching generation. Backup manifests and full
bank hashes bind restoration to a specific source; unknown/stale inputs refuse.

## Staged transaction and wear-aware recovery

bf1 uses a separate 585-byte RAM reservation helper that validates A0 or B0
fallback and matching generation. The original beta35 helper remains unchanged.
The composed installer validates all four bank preimages before mutation and
reserves planned erase attempts before its first erase. It then stages the
opposite journal, writes preserved sector overlays, commits payload headers
last and activates only a coherent target.

The proven 2604 source route installs bf1 B while retaining original A40, then
installs bf1 A while retaining verified bf1 B. Original-payload restoration
first restores A40 retaining bf1 B, then restores B35/shared assets retaining
A40. Startup/EDU settings remain unchanged. The retained monitor is a console
fallback; partial shared providers do not promise working native applications.

Recovery requires the exact backup, bank hashes and replayable mutation lineage.
It retains newer sequences and conservative wear counts. It never copies old
C/D counters over newer history. Complete clean states produce a write-free
no-op; a torn journal still requires validated repair. A reported failure does
not imply rollback, including after a late final commit. Preserve all current
bytes and transcripts before deciding on recovery. No automatic live retry,
reset or rollback is authorized by these guides.

The bounded offline continuation passed 49 cut states (12 A-install, 12
A-restoration, 25 original-B/shared restoration), 42 CPU transport tests and 27
planner/replay refusals. Every selected cut booted and recovered. This is not
every programming byte or an electrical interruption proof. Owner-authorized
2604 B/A installations and 11 initial hardware groups per slot are separately
recorded. On 2609, both slots passed 12 initial check groups each with 14
E=1 runtime observations in total, zero DBR/PBR/direct page, I=1 and D=0.
The final firmware ranges match 2604 and the pinned payloads. The 2609 offline
route passed 28 board-specific model checks; 2604 cut/restoration results are
not relabeled as fresh 2609 tests. 2609 subsequently passed original A40/B35 payload restoration and two
owner-controlled power cuts at verified transfer boundaries, with exact recovery,
E=1 checks and original RAM restoration. Mid-erase/program loss, arbitrary byte
timing and 2604 electrical behavior remain unqualified.

## RTC, outages and measurement limits

RTC calendar uses the UTC convention; local display uses a saved fixed offset.
Trim changes oscillator correction; offset changes display conversion. Device
identity binding and power-fail history are separate persistent evidence.
Down/up hardware captures are yearless and minute resolution. The inherited shared
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

The qualified evidence is tied to exact pinned FT245/F30D images and the
captured 2604 and 2609 lineages, each with a separate board-specific route. It does not admit arbitrary stock/legacy/core/private-ABI
conversions. Native 816 and optional ACIA/crypto are deferred outside bf1’s
current acceptance scope. Physical electrical interruption/restoration,
long-term accumulation and explicit release acceptance remain open.
`release_qualified` and general `installation_permitted` remain false.
2604 continues its preserving bf1 soak; 2512 and 2609 remain RTC-only; 2205
remains off. Real clocks, trims and settings are unchanged.

- [Public ABI](../../release/candidates/batchfix-r1/source/assembler/str8n-v2-public.inc)
- [Service discovery](../../release/candidates/batchfix-r1/source/core/service-eq.inc)
- [Core state and I/O definitions](../../release/candidates/batchfix-r1/source/core/str8n-v2-eq.inc)
- [Candidate source builder and artifact ownership](../../release/candidates/batchfix-r1/build.py)
- [Flash worker](../../release/candidates/batchfix-r1/source/migration/str8n-v2-flash-worker.inc)
- [Outage calculation](../../release/candidates/batchfix-r1/source/clock/outage-duration.inc)
- [Route evidence and exclusions](../STR8N_BF1_2604_INSTALL_RECOVERY.md)

The same firmware supports 65C02 and 65C816 emulation-mode runtime. Native
816 applications/testing, ACIA and crypto remain deferred. The existing startup
CPU detector briefly enters native mode before restoring emulation; this
startup exception was explicitly accepted by the owner.
