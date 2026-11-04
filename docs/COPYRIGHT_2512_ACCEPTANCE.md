# Copyright component build: 2512 live acceptance, November 4, 2026

**PASSED on 2512, 65C02, FT245/COM4.** The owner authorized flashing and
testing a board; 2512 was selected because its preceding preservation trial
and recovery state were known. Repositories, release tags and visibility were
not changed. Foundation was not programmed.

The installed component bytes are from `BUILD/str8n-copyright-r2` and match its
component/sector manifests. A fresh complete supported-memory backup preceded
all writes. Ten differing image sectors were installed using the qualified
native OPAQUE writer, including its durable erase accounting. One planned
peer-journal rotation erased B3:D. All four complete post-install flash banks
matched the exact image/journal forecast, both before and after UI tests.

| Updated flash | Components |
| --- | --- |
| B3:A, B3:B | STR8-N MON A/B, compact copyright in identity/VERSION output |
| B0:A–B | STR8-N DEV ASM, notice-bearing banner and expanded data |
| B0:C–D | STR8-N DEV DBG launch wrapper; paired source provider retained |
| B2:9 | STR8-N UTIL MAINT workbench name/seal |
| B2:B–D | STR8-N UTIL CLOCK identity/notice and shared readonly month tables |

The original Foundation SHA-256 remained:
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
Boot policy stayed default B. The native journal sequence advanced from 1201
to 1212, with 23 valid records after the planned peer rotation. Erase counters
and current bank identities were refreshed in the private board inventory.
The earlier raw B0:E attempt evidence remains separate and is not erased by
this accounting update.

## Physical checks

- Entered both monitors and checked their VERSION copyright notices.
- Entered installed CLOCK, checked VERSION, read actual local/UTC time and
  STATUS: oscillator running, calendar valid, backup enabled, no power-fail
  latch. No time, trim, calendar or battery setting was written.
- Loaded the installed MAINT workbench, checked its identity and queried SRAM
  and WORK without writing either.
- Entered installed ASM, observed the notice and assembled a real program;
  LST contained the expected `A9 23` instruction bytes.
- Entered installed DBG and exercised safe cancellation.
- A separate debugger smoke continued from the initial entry stop to a real
  BRK: `PC=1004 A=2A`. Continue executed the program's HOLD, returned to MON,
  and restored the original public BRK/HOLD hooks. B3 was unchanged by this test.
- Loaded new CONFIG, FLASH and full MAINT as raw RAM tools, checked their
  identity/available VERSION output and read-only commands, and returned
  through Foundation. They were not installed in flash.
- Loaded the new OPAQUE wrapper, observed its notice and verified a read-only
  sector transfer. The installation itself used the accepted original writer.
- Loaded the new MEMORY agent in a fresh session. Complete SPI SRAM (128 KiB),
  addressing mode, user EEPROM (128 bytes), CPU owner RAM (0200–66FF) and owner
  zero page (00–DF) matched the pre-install originals exactly.
- Restored and read back owner RAM after both main and debugger trials. Final
  state was `REC>`, with COM4 and the shared serial lease released.

## Evidence

Private original images, exact target/journal forecasts, serial transcripts,
writer/readback input hashes, driver snapshots and the main 16-check report:

`output/qualification/copyright-2512-install-20261104-r1/`

The additional three-check BRK/register/resume trial and its RAM cleanup:

`output/qualification/copyright-2512-DBG-smoke-20261104-r2/`

The first debugger smoke read the expected initial-entry stop as though BRK had
already executed. Its assertion failed; RAM was restored and its receipt was
retained in the sibling r1 directory. The corrected test issues Continue before
inspecting the BRK capture. This was a test expectation correction, not a firmware
change or a flash retry.

## Limits

This is one-board positive component acceptance. There was no physical RESET,
power interruption, Foundation replacement, migration, publication or repo
consolidation. Foundation software return and monitor selection were exercised.
MAP/DEMO/READBACK wrappers retain their model acceptance; this run did not
exercise those new wrappers physically. FLASH/MAINT write functions retain
their earlier component evidence; the new copies received read-only UI checks.
The named ZIP was not used as an extracted interactive operator session.

CPU preservation covers the documented owner ranges, not active stack,
registers, system zero page, monitor workspace or I/O. No SPI SRAM, EEPROM or
RTC setting writes were requested. Other physical boards and 65C816 hardware
remain outside this acceptance.
