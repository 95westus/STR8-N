# Broader DBG checks on2512

Passed17 real-CPU RAM groups on November2,2026. This is an increment above frozen Foundation0.3.0
g1/BASE1/PR05 and MON A/B g10. The later separately reviewed
[DBG g2 installation and installed checks](DBG_G2_2512_INSTALLED_ACCEPTANCE.md)
also passed. The source FLASH gate remains installed and accepted.

## Reproduced findings

The safe baseline used the accepted g1 RAM core. It reproduced four defects:
X did not publish stopped logical ZP edits; program HOLD could overwrite live
user D0 during breakpoint removal; bare BC did not clear all breakpoints;
and rejecting a JSR outside admitted RAM had already modified logical stack
bytes. All eight actual breakpoint slots hit and restored their opcodes.
Original owner RAM/ZP/cache and all borrowed hooks were restored afterward.

The g2 candidate separates stopped X cleanup from live program HOLD. HOLD
captures user ZP before unpatching; both paths restore the appropriate00-DF
image before returning. BC and BC* clear all user slots; BC address clears
one, with trailing arguments checked. Calls validate target and return bounds
before logical stack changes. Indirect pointer bytes and decoded operands
are range-checked before reading outside the admitted user window.

Resume preflights PC, IRQ mask and every pending breakpoint before patching.
CLI, unmasking PLP/RTI, WAI/STP, unknown and truncated step operations are
refused. N admits returning nonblocking public PUTC, HEX, newline, nibble,
caps and board-query entries; arbitrary ROM/I/O and blocking GETC targets
remain refused. F and its ABI are unchanged.

## Broader RAM acceptance

The live receipt records completion of these17 groups:

- X stopped-ZP and HOLD live-ZP cleanup.
- Register edits, widths, PC and IRQ-mask refusal.
- Logical ZP/stack, atomic byte limits and memory bounds.
- All eight breakpoint hits, capacity, BC and duplicate temporary patches.
- Relative/bit branches, indexed and page-crossing logical indirect jumps.
- JSR/RTS/RTI and atomic rejected stack/return cases.
- Unsafe instruction, truncated decode and I/O-pointer refusal.
- Public PUTC/HEX/query step-over, unsafe/blocking call refusal.
- Built-in query/trace, callback register edits and nested BRK behavior.
- All16 user callback slots, capacity, duplicate and namespace guards.
- Bad callback PC and complete breakpoint preflight before mutation.
- Ctrl-C, backspace, long input and X argument handling.
- Existing BRK/HOLD-owner refusal and exact hook restoration.
- Four private system-registration slots and descriptor/active guards.
- All four flash banks, settings/history, owner RAM/ZP/cache preservation.

The implementation uses real2512/65C02 execution, not CPU simulation.
RAM fixtures borrow0200-66FF, ZP00-DF, provider cache6B00-77FF and the five
owned public BRK/HOLD bytes. They make no flash, SPI-data or RTC-setting write
and require no reset or power cut. RTC collection retains serial priority;
other boards and published downloads remain outside this increment.

This is not a sandbox for arbitrary code: C runs the admitted user program,
which must keep IRQ masked and return through HOLD. Native816 operation,
hardware interrupt debugging, blocking public-call stepping and self-changing
user breakpoint code are outside this acceptance.

Workspace evidence:

- `output/qualification/2512-DBG-broad-baseline-RAM-20261102-r1/report.json`
- `BUILD/dbg-base1-g2-r1/manifest.json`
- `output/qualification/2512-DBG-broad-RAM-20261102-r1/report.json`
- `output/qualification/2512-DBG-broad-RAM-closeout-20261102-r1/completion.json`

The ASM tables, AP loader adapter and exact D800-DFFF SF/1 source provider
are reused. The new core remains RAM4000-508A with its tables5F00-6407 and
state7000-744F. DBG still occupies the same two sectors, B0:C/D; this
increment adds no flash allocation. Separate utility retirement/reclamation
has since changed the board's overall occupied footprint.

## Installation decision

The separate FLASH/MAINT retirement and legacy reclamation have closed.
A fresh read-only capture verifies sequence 1199 and 26 valid journal rows.
The [fresh installation review](2512_DBG_G2_FLASH_SCOPE.md) now requires only
two erases at B0:C/D and two append-only wear reservations, with every old
row retained at its original address. The earlier rotation estimate is
obsolete. That review made no flash writes. The owner subsequently approved
the two-erase installation; its [installed acceptance](DBG_G2_2512_INSTALLED_ACCEPTANCE.md)
is now closed on2512/65C02.

F, MON A/B/default, ASM, the exact source provider, settings, SPI data, RTC
and owner RAM remain preserved. The fresh capture restored and verified
owner RAM/ZP/full provider cache and released COM4 at REC>.
