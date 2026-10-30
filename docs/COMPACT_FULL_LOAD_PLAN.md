# Compact Foundation + MON/tools load

The 36 KiB figure below measures the current subset. It is not the footprint
or completion claim for the [unified b35-capable shipping release](UNIFIED_SHIPPING_RELEASE.md).
Full CLOCK/CONFIG and remaining b35 behavior are required there; their shared
module layout must be measured before claiming a final shipping size.

**Layout proposal, October 30, 2026. No erase, flash write, rebuild or new
qualification is authorized by this document.** Keep frozen STR8N-F v0.3.0
g00000001 / BASE1 / PR05. This budgets the current listed feature set; resident
ASM/DBG, advanced CLOCK, the full FLASH editor and merged CONFIG remain
separate development increments with additional space requirements.

## Current measured footprint

| Region | Component | Allocated bytes |
| --- | --- | ---: |
| B3:F | Foundation reset/bootstrap/recovery | 4096 |
| B3:C/D | Separate boot/wear journals, retaining each board's history | 8192 |
| B3:A/B | Two compatible MON g8 images | 8192 |
| B3:E | Services g4: maps, wear, APPS and tool dispatch | 4096 |
| B2:8/9/A | Shared WB5/SP1 bundle and loader | 12288 |
| **Total** | **Current full MON/tool profile** | **36864 (36 KiB)** |

The firmware payload is **28 KiB in seven 4 KiB sectors**; another 8 KiB is
journal reservation/data, not another firmware component. A generic kit must
not embed the lab's C/D records, wear counts or boot policy. Installation
preserves/provisions the target's own journal through the existing procedures.

The shared bundle supplies MAINT, bounded CLOCK, EDU selection, SRAM/WORK
queries, PROGRAM and flash Table/Store/Restore, and bounded BATCH. No separate
CLOCK/CLK/MAINT image is needed for this feature set. Flash Store uses its
own checked F byte-program adapter and an explicitly declared B0/B1 AREA;
it does not need the retained legacy B1/B2 firmware. It does not erase.
EDU-dependent services still need matching hardware and admitted pin ownership.

Current source/size authorities: services-g00000004, g00000008-r2 and
wb2-g00000005-r3 manifests under `monitors/candidates/`. Existing binary
formats and loader locations are retained; no optimization build is claimed.

## Preferred bank ownership

Pack the system in B3 and B2 before consuming B1 or B0:

| Bank | Proposed role |
| --- | --- |
| B3 | F, C/D journals, MON A/B and E dispatcher; 8/9 remain outside this profile |
| B2 | 8/9/A shared tools; B-F available for later admitted modules or owner images |
| B1 | Owner flash records/programs/apps; later development modules if needed |
| B0 | Optional WDC compatibility image or an owner's banked environment |

A clean installation would leave **92 KiB outside this 36 KiB footprint**:
64 KiB in B0/B1, 20 KiB in B2 and 8 KiB in B3. These are proposed allocations,
not declarations that the current boards' sectors are erased or disposable.
Their retained images remain owned until individually backed up and admitted
for replacement. PROGRAM SPI SRAM contents are separate from this flash budget.

The two monitor slots remain explicit. Both boards now contain MON A/B g8.
The [2609 MON A installation and acceptance](2609_MON_A_G8_ACCEPTANCE.md)
passed with one A erase and one D300 wear append, preserving its default S,
all 19 prior journal records and owner RAM/ZP. Its old PR04 A is archived on
the host. This completes the listed A/B profile without changing F.

## WDC is optional, not a hidden runtime dependency

The released migrator archives all four original banks on the host, then
updates the admitted B3:F/C/D targets. **It does not automatically copy
WDCMONv2 into B0.** A WDC image already present in B0 is retained in place.
See [the migration procedure](USER_MANUAL.md#wdc-loadable-ram-migration).

The development source now prompts for **Host / B0 / Both**; see
[backup choices and qualification](../migration-host/README.md#wdc-backup-destination--new-source-b0-live-qualification-pending).
It preserves mandatory host escrow, reviews B0 replacement separately and
budgets up to eight B0 erases before F/D/C. That new NFM2 route is not yet
live-qualified or part of the published kit; it adds no runtime dependency
to the 36 KiB MON/tool profile.

An optional WDC-to-B0 copy/boot check is a separate, CPU-correct compatibility
step. Its reset entry and bank-switching assumptions must be checked; simply
having vendor bytes in B0 does not qualify its Foundation boot path. Once
the chosen fallback/backup is verified and Foundation recovery plus the new
tools are accepted, WDC need not stay on chip. An approved erase can reclaim
that bank while retaining exact host backups. F and the current MON/tools
do not call WDCMONv2. This proposal performs no such copy, boot or erase.

The later [2512 RAM-only debugger handoff](2512_WDC_B0_HANDOFF_ACCEPTANCE.md)
passed using just the existing WDC **B0:F sector**, with FLASH at B0:8 retained.
For that pinned 65C02 debugger-entry mode, an optional WDC allocation adds
**4 KiB**, making the clean proposed profile **40 KiB** including journals,
with **88 KiB outside it**. This does not qualify physical reset/default boot,
reduce the required original-bank backup extent, or declare any current owner
data disposable. The main 36 KiB profile has no WDC runtime dependency.

The subsequent [saved-default WDC launcher trial](2512_WDC_DEFAULT_BOOT_ACCEPTANCE.md)
passed through a real Foundation RESET. Its standalone entry example adds
another 4 KiB sector (133 code/data bytes), so a profile with both the WDC
sector and this dedicated launcher budgets **44 KiB including journals**, with
**84 KiB outside it**. Sharing that small launcher with another environment
is a later packing option, not a measured saving. The trial restored the
original FLASH image and B default; it performed no allocation cleanup.

## Smaller targets and next work

The current profile already uses only B3 plus 12 KiB of B2. Its existing
loader expects a contiguous three-sector B2 bundle; moving pieces into
B3:8/9 would require a changed loader and fresh qualification. Moving bytes
does not itself reduce the 36 KiB sector footprint.

A 32 KiB all-B3 target would need at least one whole 4 KiB sector saving or a
different optional-feature budget. It is an optimization target, not a
measured result. Keep F frozen; audit sharing/packing above it before any
necessary single rebuild. Do not sacrifice independent MON A/B or journal
history merely to reduce a displayed file size.

CONFIG/OPAQUE and the preservation/migration programs currently remain host-
supplied RAM tools. Making them resident adds storage unless their functions
are deliberately merged. The Python terminal/manual stay host-side. A compact
release should describe its component writes and journal reservation, rather
than treating a padded 128 KiB file as the required firmware size.

At Foundation RESET, S selects REC>. An admitted MON's Q returns to REC>;
workbench Q returns to its active monitor. Use an admitted A/B image above F
and MAINT LOAD for the current shared tools. No bank cleanup follows from
opening these environments.
