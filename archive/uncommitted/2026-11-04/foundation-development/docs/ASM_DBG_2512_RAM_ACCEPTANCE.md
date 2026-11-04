# First BASE1 ASM/DBG RAM acceptance on 2512

November 2, 2026. The initial paired ASM/editor/source service and DBG1 port
passed a live RAM workflow on2512/65C02/FT245, using installed MON B g10 above
golden Foundation0.3.0 g1 BASE1/PR05. At this historical checkpoint the tools
were RAM-only. The later [flash preview](ASM_DBG_FLASH_PREVIEW.md) records
normal launch integration and installation separately. They are not part of
Candidate3 or any published download.

| Live check | Result |
| --- | --- |
| Resident editor/assembler | Numbered source, EQU, global/local labels, assembly, LST/SYMS, DUMP/S19 passed |
| Diagnostics/editing | Undefined-symbol diagnostic, invalid-result refusal, backspace editing and line deletion passed |
| Source guards | Unsaved LOAD cancellation and explicit RAM1 flash-source unavailability passed; no stored record was written |
| Output/run | Independently dumped8 emitted bytes, executed the assembled marker program and returned through public HOLD |
| Debugger | BRK frame, register display/A edit, disassembly, S/N, one user breakpoint, RAM D/M and C passed |
| Cleanup | Program HOLD and X restored the five original public BRK/HOLD hook bytes and original breakpoint byte |
| Preservation | Full owner0200-66FF, ZP00-DF and borrowed cache7000-74FF restored/read back; B3/F/images/settings/history exact |

The debugger trial used BRK at1000, two single steps, step-over of a RAM JSR,
a real breakpoint at100C, memory read/edit at1800, A register editing, an
original BRK step and program-HOLD return. A second activation exercised X.
This is not a claim of exhaustive register, all-eight-breakpoint, callback,
boundary, failure or816 qualification.

## Exact candidates

- ASM/source: `BUILD/asm-base1-g1-r6/ASM-BASE1-RAM.bin`,24,829 bytes,
  SHA-256 `b05b71cf95019fb860bce175302d24a39664676d54bb1ee8b21c742f556fe12b`.
- DBG: `BUILD/dbg-base1-g1-r5/DBG-BASE1-RAM.bin`,25,096 bytes,
  SHA-256 `f55b7edddbf5ed783734e6247aa073d367dffdbe3ad3fc54f465c482a4306e12`.
  The unchanged r4 binary was reused after exact equality of the paired
  opcode/length tables was checked against the corrected assembler link.

The tools use independent RAM packets with overlapping code ranges. They
are launched through the reviewed driver/preload, not yet normal R/APPS
front doors. No Foundation, MON or workbench rebuild and no CPU simulation
was performed. Required port/link corrections and older failed candidates
remain archived; they are not labeled as accepted artifacts.

## Recorded interruptions

The first ASM packet entered its shell, but the expanded help string exceeded
the legacy8-bit printer-index limit. `?` looped before reaching the next
prompt; Ctrl-C could not escape that printer. The owner pressed2512 RESET
once after the recovery receiver was armed. Golden recovery, B3/F readback
and exact cache/hooks/owner restoration passed. The printer now advances its
page pointer when Y wraps. Only the affected assembler/source pair needed
relinking; debugger bytes remained identical.

The next trial passed the main assembler workflow, then stopped at a host
diagnostic assertion: replacing the global label triggered a legitimate
orphaned-local-label error before the expected undefined-symbol error. Cache
and owner restoration passed. Correcting the test input preserved that label;
the subsequent complete RAM workflow passed with the same corrected binaries.

The first and final escrows for owner RAM, owner ZP, cache and original hooks
are byte-identical. The successful trial used zero resets; the full sequence
includes the one owner-operated recovery RESET. There were zero flash,
journal, PROGRAM/WORKSPACE, EEPROM, RTC time/trim or power-fail ACK writes,
zero power cuts and no other-board access. RTC baselines and measurement
segments remain unchanged; the CPU reset is recorded as a host event.

Private receipts relative to the workspace root:

- `output/qualification/2512-ASM-help-recovery-20261102-r1/report.json`
- `output/qualification/2512-ASM-DBG-BASE1-RAM-20261102-r3/report.json`
- `output/qualification/2512-ASM-DBG-BASE1-RAM-closeout-20261102-r1/completion.json`

Final REC>,COM4 released, restoration/worker/reset guards clear and2512
RTC-host admission passed without another board connection.

## Remaining before installation or shipping

The subsequent [AS/1 PROGRAM source save/load and failure trial passed](ASM_AS1_PROGRAM_ACCEPTANCE.md)
under its separately approved320-byte scope, with exact original restoration.
Flash source persistence still needs its BASE1 adapter.
Normal MON/APPS/R entry, final ROM/RAM allocation and flash installation need
their own occupied-sector/journal review. Broader debugger guard/cleanup cases,
the816-sensitive path and a later extracted developer kit remain separate.
The reduced RAM trial buffers are not the final ROM tool memory budget.
