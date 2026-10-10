# SPI Phase 4: named SRAM program storage

Recorded 2026-10-08. The beta14 resident candidate and standalone SRAM 1.0
utility now provide explicitly selected named SPI storage alongside the existing
flash provider. This is linked-model qualification and offline preparation;
**no boards were accessed or flashed**. Boards 2512, 2205 and 2609 retain
beta13/CLOCK 1.5. No commit or push is part of this phase.

Subsequent [Phase 5](STR8N_V2_SPI_PHASE5_2026-10-08.md) extends this candidate
with SRAM 1.1 and WORK 1.0. The sizes and fixed split below record Phase 4;
the current utility guide describes v2 layouts and updated RAM placement.

## Result and workflow

The resident monitor and service prefixes are already full. Named storage is
therefore a separate runnable utility rather than another resident command
parser or another service sector. The existing monitor `R`, `S` and `T` keep
their flash behavior. The utility's `SRAM>` prompt explicitly selects SPI;
missing/corrupt SPI storage never falls back to a same-named flash program.

`SRAM>` provides `S name start end entry`, `R name`, `G name`, `T`, `D name`,
`C` reclaim, strongly confirmed `F` initialization, and `Q`. Entries retain
their original load address and run entry; `0000` disables run. Names accept
1-16 uppercase letters, digits, hyphen or underscore. Detailed examples,
hex results, ownership and exact layouts are in
[the utility guide](../tools/v2-spi/SRAM_STORE.md).

The S19 loads at `$4000-$4D3F`; `G 4000` relocates the manager to monitor
staging RAM. Loading the utility overwrites its load range, so preserve an
existing image there first. A normal saved flash record can later provide
`R SRAM`; provisioning that record on boards remains a deployment step.
The model saves and starts that exact utility through the existing flash path.
It uses ordinary program storage when persisted, not a third resident service
sector. No flash location has been assigned or changed on a board.

The first split allocates 65,536 gross bytes to programs, including 2,048
management bytes, leaving **63,488 payload bytes**. Payload allocation uses
248 contiguous 256-byte pages. There are eight metadata slots for live images,
old versions and deletion tombstones. Workspace reserves **65,504 bytes**;
the final 32 array bytes remain the probe reservation. Workspace access and
adjustable boundaries are Phase 5 work.

## Publication, restore and reclaim

Every operation rereads the versioned layout and directory. Invalid retained
contents are refused, never silently formatted. Committed metadata has a
CRC-16/CCITT seal, checked destination/extent/name fields and a final `$A5`
completion marker. Metadata overlaps and ambiguous highest sequences fail.

Save uses a fresh extent and free metadata slot, verifies the entire payload
CRC and the metadata, then writes/verifies the final marker. The previous
version remains committed and allocated. Directory or extent exhaustion
refuses replacement without touching the old record. Free-byte counts report
unused pages; fragmentation can still prevent a contiguous allocation.

Restore validates the entire SPI payload and the current CPU destination
before copying. A second CRC and completed-count checks cover the copy. A
failure after copying starts reports partial completion and prevents execution;
it does not claim CPU-RAM rollback. Programs always execute from CPU RAM.

Deletion first publishes a higher-sequence tombstone. Explicit bounded reclaim
verifies a selected newer payload before releasing its older versions. It
clears old deleted references before removing the deletion tombstone, and
never relocates data. No automatic compaction or collection is performed.

The Phase 3 gateway initialization is tightened: public SRAM WRITE is denied
from cold boot, including after RESET. Public READ/PROBE and the general
mikroBUS profile remain available. The foreground manager uses a private
write authorization path and restores denial on return. This is cooperative
ownership; direct RAM access is not a security boundary. IRQ/NMI service
callers and concurrent managers remain unsupported.

## Measured size and memory

| Item | Bytes / range |
| --- | --- |
| Manager instructions | 3,049 at `$6C00-$77E8` |
| Tables and local state | 240 at `$6800-$68EF` |
| Directory, transfer backup, bitmap, request and line state | `$6900-$6AE7` within existing staging |
| Bootstrap, page padding, code and data in saved R image | 3,392 at `$4000-$4D3F` |
| Ordinary flash record including 24-byte header | 3,416 |
| Maximum modeled foreground stack | 25 bytes, including caller and resident service; NMI handler excluded |
| Resident SPI provider / helpers / main | 2,299 / 1,262 / 3,070; unchanged size |
| RAM gateway code / reservation | 319 / 512; unchanged size |

The current monitor sector-staging area is `$6800-$77FF`, and its worker
starts at `$7800`. The utility avoids that worker and the active journal/SPI
scratch at `$6B00-$6BFF`. It borrows staging only while active; reload the
utility after monitor return, RESET or other staging users. This is not a new
permanent RAM reservation or a public staging API.

The resident reservation remains `$6500-$66FF`; **user RAM ends at `$64FF`,
inclusive, even on a board without EDU**. The 64-byte service transfer window
at `$6400-$643F` is saved/restored through save and pre-copy verification;
restore copies directly to its destination afterward. Zero page `$D0-$D7`
is clobbered. The manager uses W65C02S instructions and shared bounded loops.

## Qualification

The linked utility executes with the real resident bit-level SPI model for
basic mount, format, save, readback, replacement, restore, delete/reclaim and
hardware-absence checks. A separate ABI-level transfer fault model runs the
same assembled manager for exhaustive storage interruption and capacity cases.
This distinction is recorded in the generated test report.

Checks cover unformatted/invalid layout refusal, exact format confirmation,
header/payload checksums, names, inclusive `$64FF`, protected/wrapped ranges,
entry bounds, transfer-window preservation, ambiguous
sequences, stale RAM directory state, full directory and all 248 payload pages.
There are 68 replacement write-cut cases, all 74 format-write cut points,
partial/error/short-count restores, failed payload writes, corrupt replacement
reclaim refusal and every deletion/reclaim marker cut. Unrelated names and
the old committed image are retained where required.

Console checks exercise save, table, restore, run, cancellation/input bounds,
reload after HOLD and `R SRAM` from a standard saved flash record. A named
program saved in flash and SPI restores identical bytes and executes the same
entry behavior. Raw public writes remain denied after initialization/reset;
missing or stuck SRAM is a bounded refusal. No-EDU flash behavior remains in
the resident regression suite.

The changed cold-start policy reruns SPI and all RTC/kernel, journal, TIME,
banner, CLOCK/history, EUI binding/interruption and normal trim models. All
three exact-source six-sector SPI update recipes are freshly rehearsed against
archived images, preserving B0/B1/B2, fixed F and EUI tails. These recipes
install the resident service only; utility provisioning and SRAM initialization
are separate Phase 6 actions. No recipe formats SRAM.

Build/test entry points:

```text
python tools/build_v2_spi_resident.py
python tools/build_v2_spi_resident_example.py
python tools/build_v2_sram_store.py
python tools/test_v2_sram_store.py
python tools/qualify_v2_spi_candidate.py
python tools/audit_v2_sram_store.py
python tools/check_no_board_backups.py --history
```

Generated images and qualification reports stay ignored under
`BUILD/v2-spi-resident/store`. Its `candidate-check.json` binds the utility,
source hash, test report and qualified resident artifacts. Raw board backups
remain owner-local and untracked. Physical retention, installation and integrated
board regressions remain Phase 6; adjustable partition/workspace is next.
