# SRAM management and WORK services: RAM checkpoint

November 1, 2026. First increment toward the remaining b35 storage gates.
F remains golden. No monitor, utility image, boot record or published kit is
changed by this checkpoint. 2205/2604 are excluded.

The [read-only RAM trials passed on both boards and positive RAM trials passed
on 2512](SRAM_WORK_RAM_ACCEPTANCE.md). The later
[native R SRAM/R WORK installation](STORAGE_NATIVE_ACCEPTANCE.md) passed on both.

The combined RAM candidate ports the preserved b35 SRAM1.4 manager and WORK1.4
algorithms. It includes PROGRAM delete/tombstones, bounded reclaim, explicit
format, SS1/SS2 validation, layout fallback/repair/upgrade/resize and WORK
claim/release/read/write with owner, epoch, ticket and bounds validation.
It replaces old resident/XIP calls with the existing qualified addressed-byte
EDU SPI transport and the CRC-admitted MON quiet-return interface.

## Current artifact

`BUILD/sram-work-g1-ram-r2/manifest.json` identifies the successful build.
The first attempt stopped in the assembler because late zero-page EQU
declarations changed instruction widths between passes. Moving constants
before code fixed that toolchain issue; only this RAM module was rebuilt.
F and the installed modules were not rebuilt. No simulator was used.

The library is10,231 bytes at$2000-$47F6;4,873 bytes remain before its$5B00
context. The raw BIN also includes a bootstrap at$0200. Context/escrow is
$5B00-$5DFF; scratch is$6400-$6ACF. While this prototype is loaded, actual
CPU save/restore and API request/data buffers are restricted to$0200-$1FFF
to protect its own code. Mount/Table still accept larger existing records.
This temporary restriction does not replace the existing wide PROGRAM loader.

The module starts at `STORAGE>` in **read-only** mode. `S` opens `SRAM>`;
`W` opens `WORK>`. Submenu Q returns to STORAGE; top-level Q restores ZP and
the MON session and returns quietly. Full owner application RAM is restored
separately by the host trial. `PREP` acknowledges disabled VIA CB flags only;
it sends no SPI clocks. `EDU ON/OFF` selects the temporary wiring profile.

`UNLOCK` plus a separate live YES enables SRAM writes for this RAM instance;
`LOCK`, return to MON and a new load disable them. There is no flash writer
or WRMR operation in this module. Read-only write attempts return$4C before
the SPI WRITE opcode. FORMAT/resize/upgrade/repair retain their original keys
and confirmations. SRAM FORMAT refuses a valid SS2 layout; WORK owns that
layout's deliberate format operation. Query does not create a WORK epoch;
the first mutating WORK service begins a new manager session lazily.

## First live trial: read only, yield to NIST/RTCC

Use2512 first, with the same candidate later checked on2609's816 emulation
path. Use the shared non-priority serial lease; never interrupt a collector.
Check for pending collection between commands and restore borrowed RAM before
releasing the port at the next safe boundary. A busy port or collection is a
deferral, not permission to reset a board or bypass its guard.

- Capture fresh owner RAM/ZP before loading the candidate and retain exact
  recovery data. Admit current MON gD, installed providers and golden F.
- Capture the2 KB SRAM metadata area before/after, using the installed
  qualified read-only path. Run real Table/capacity queries, not just help.
- Exercise SRAM query API, wrong pointer/key/source bounds and a locked
  delete attempt against an existing record. It must return write-protected
  without changing its record or payload.
- Exercise WORK query API and capacity output, bad request rejection,
  SS1 upgrade-required handling and a correctly keyed FORMAT attempted while
  locked. It must refuse before a storage write. Cancel both format dialogs.
- Verify quiet return, owner ZP and unchanged B3, including all boot/wear
  records/settings and F. Restore/read back full owner RAM$0200-$66FF and
  ZP$00-$DF, then release the port in its original prompt context.

This first trial sends no UNLOCK, YES or FORMAT SRAM confirmation. Zero flash,
journal, SRAM-data/WORKSPACE or RTC-setting writes are allowed. No reset or
power cut is included. It cannot close positive mutation gates.

The later bounded positive fixture passed on 2512, with complete SRAM and
owner RAM/ZP restoration; see the acceptance receipt linked above. That is
separate evidence from this original read-only plan. Installing named
R SRAM/R WORK routes in flash used a later, separately reviewed scope; see
the subsequent installed acceptance linked above.
