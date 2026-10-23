# ASM development extension on board 2604

This local candidate combines console editing and source storage with EQU,
assembly listings, symbol lookup and source-aware error reports. It retains
the ASM 0.5 banner and generation 50; use the build and hardware receipts to
identify the candidate. It is separate from the published r9 archive.

Installed and physically tested on **2604, Monitor B, 2026-10-21**. EQU,
LST, global/local symbol lookup, undefined/duplicate/range/branch diagnostics,
console editing and DBG1 execution passed. All four flash banks matched the
planned target after RESET and remained unchanged during command testing.
Original application RAM was restored; the board was left at the idle B3
monitor. Board 2609 was not accessed.

Offline command tests passed both CPU models and both monitor slots, including
the full 256-symbol table and source save/load. The capture-bound installer
passed both CPU models with reserved erase counts and exact target readback.
ASM ends at `$FC9D`, leaving 835 bytes before the vector pocket. Local reports
are in `BUILD/rc1-asm-dev` and the private qualification run
`output/qualification/rc1-asm-dev-2604-20261022-020417Z`.

At `ASM>`:

```text
10 BASE EQU $0200
20 ORG BASE
30 start: LDA #$42
40 .again: NOP
50 BRK $01
60 JMP $7E67
70 END
ASM
LST
SYMS
SYMS start
SYMS .again
```

`name EQU expression` and `name .EQU expression` are case-insensitive aliases
of `name = expression`. They emit no bytes. Existing constant-expression,
duplicate-definition and local-scope rules apply. A constant used by another
constant must already be defined.

`LST` requires a successful assembly of the current document. It reassembles
the document and prints pass-two source line numbers, logical addresses,
up to four bytes per row, and source text. Longer data/fill output continues
on additional address/byte rows. Blank, comment and non-emitting lines also
appear. An ORG line shows the location before processing that directive;
the next emitting line shows the new origin. Logical addresses differ from
physical output-buffer addresses when ORG differs from $0200. Ctrl-C cancels;
reassemble after cancellation before export or execution.

`SYMS` displays addresses/values and names from the last successful assembly.
`SYMS name` selects an exact global name, case-insensitively.
`SYMS .name` displays matching local names across all scopes. Local symbols
print as `PARENT.NAME` so identically spelled locals can be distinguished.
Lookup does not create a symbol. Source edits, NEW, SAVE and LOAD invalidate
the assembled result; assemble again before LST, SYMS, DUMP or S19.

Assembly failures retain the existing error class and numbered line, then
show the failing source text. Undefined and duplicate-symbol errors also
print the symbol name. Branch-range errors explain the allowed signed
displacement, -128 through 127 bytes. Source-editor/paste failures retain
their existing error reporting; their input line need not be an assembly
record.

The extension stays within the existing ASM RAM allocations and B1:E/F
ROM sectors. Existing assembler/table addresses and the debugger image
remain unchanged. It supports 65C02 and 65C816 emulation mode.

## Board 2604 cleanup

The requested target erases the demo source records E311, E312, CS1 and CS2
from B0:8-B, leaving the entire B0:$8000-$FFFF bank erased. It also erases
the independent UCHESS record in B1:8. Source save/load support remains
installed in B1:9, and DBG1 remains in B1:A. The LED demo is stopped and is
not restarted. Flash erase counts are reserved and recorded by the RAM
installer's journal transaction.

The repository's onboarding, ASM, source-save/store manuals and example
sources remain available as reference material. Removing the board's saved
demo records does not remove those documents. The captured original flash
and RAM remain in the private qualification directory for recovery.

Only board 2604 is authorized for this update. Board 2609 is unchanged.
The final hardware report determines installation and readback status;
an offline build alone does not establish a completed installation.
