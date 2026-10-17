# STR8-N ASM 0.5 guide — draft for bf1

Current acceptance policy and tonight's prerelease scope: [accepted gates](../STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md).

Target: **2.0bf1 generation 48, ASM 0.5 / 65C02 instruction set, also used on 65C816 in emulation mode**. The example passed assembly,
S-record export and execution in the serial-disabled offline model. Use that model during the
protected board campaign; loading ASM replaces application RAM.

## Edit and assemble

Launch the ROM assembler with `ASM`. Its prompt is `ASM>`. A numbered line
inserts or replaces source; entering the number alone deletes it. `LIST` shows
source. `NEW` starts a new source document. `PASTE` accepts a pasted source
session: enter unnumbered source lines, then a line containing only `.` to end
paste. Ctrl-C cancels paste, retaining already accepted lines. `ASM` assembles;
`DUMP` displays the successful output and `S19` emits S-records. `QUIT` returns
to the monitor. A successful assembly is required before exporting output.

Supported directives are `ORG`, `BYTE`, `WORD`, `TEXT`, `FILL`, and `END`, with
an optional leading dot. Labels use `name:`; constants use `name = value`.
A local `.name:` belongs to the preceding global label. Use the 65C02 opcode
set implemented by ASM 0.5; native 65C816 assembly is not advertised.

`ORG address[,fill]` changes the logical origin; the default fill is `$00`.
The output buffer remains at `$0200`. An origin different from the output
buffer is not automatic relocation of executable bytes to that address. Export
S19 and load at the intended origin before execution or storage. Keep gaps,
overlaps, branch range and output limits within the assembler's checks.

## Buffer ownership

| Range | ASM use |
| --- | --- |
| `$0200–$32FF` | Contiguous output buffer; default origin `$0200` |
| `$3300–$4EFF` | Source buffer |
| `$4F00–$62FF` | Symbols |
| `$6300–$64FF` | State, line/token buffers |
| `$00–$3F` zero page | Declared application scratch ceiling |

Those are ASM's buffers, not a general permission to overwrite monitor or
optional-service memory. Once a program exits ASM, later utilities may replace
its source, symbols or output. Preserve a source/export copy before loading
another program. The public include's historical `$66FF` application-end
constant does not supersede active optional-service discovery.

## A small draft program

This source illustrates default-origin RAM output and return through the
initialized RAM ABI. In the initialized STR8-N host it assembles to ten bytes
`78 D8 A9 41 20 6D 7E 4C 67 7E`, prints `A`, and returns through HOLD.
Flash, EEPROM, RTC and external SRAM stayed unchanged in the model.

```asm
10 ORG $0200
20 SEI
30 CLD
40 LDA #'A'
50 JSR $7E6D
60 JMP $7E67
70 END
```

At an authorized idle monitor, code at the default origin would be entered
with `G 0200` after `QUIT`. This example writes console output and changes CPU
RAM/register state; it does not set time or write persistent storage. Do not
execute it on 2604 while the soak owns RAM, or compete with RTC snapshots. A source session is not safe to
run merely because it assembled: validate its calls and memory effects first.

## Calling monitor services

Use the initialized `RA` RAM ABI after signature/format validation. The ROM
facade at `$F000` is visible only with its resident flash bank selected. RAM
entries support calls with any flash bank visible. Preconditions are IRQ
disabled and decimal mode clear; on 65C816 use emulation mode with direct page,
DBR and PBR zero. Calls are not native-mode or reentrant services. Native
interrupt vectors do not imply native application calls.

Common entries are `PUTC $7E6D`, `GETC $7E70`, `HEX_OUT $7E7C`,
`NEWLINE $7E7F`, `CAPS_QUERY $7E85`, `BOARD_QUERY $7E88`, and
`HOLD $7E67`. `HOLD` returns to the resident monitor; `RESET $7E64`
performs a different, disruptive operation. The include comments define each
query's returned registers/flags. Do not infer register preservation from this
short list; verify the called implementation and example receipt.

## Errors and reproducibility

Errors identify a line and category: syntax, opcode/mode, undefined or
duplicate symbols, range/branch, source/symbol/output space, phase, line,
expression depth, cancellation, layout or scope. Correct source and assemble
again before export. Do not treat previous output as the failed program's
result. Record the ASM version, source, origin and exported bytes when sharing
an example. Host WDC encoding comparisons are separate qualification evidence;
they do not make every host-assembler syntax valid in the board editor.

## Source and evidence

- [Editor, parser, diagnostics and help](../../release/candidates/batchfix-r1/source/assembler/asm-app.asm)
- [Buffer layout](../../release/candidates/batchfix-r1/source/assembler/layout.inc)
- [Public ABI constants and contract](../../release/candidates/batchfix-r1/source/assembler/str8n-v2-public.inc)
- [Technical manual](TECHNICAL_MANUAL.md)

The same firmware supports 65C02 and 65C816 emulation-mode runtime. Native
816 applications/testing, ACIA and crypto remain deferred. The existing startup
CPU detector briefly enters native mode before restoring emulation; this
startup exception was explicitly accepted by the owner.
