# STR8-N ASM 0.5 guide — rc1 candidate

Release scope and limitations: [rc1 qualification](README.md#rc1-qualification).

Target: **2.0rc1 generation 49, ASM 0.5 / 65C02 instruction set, also used on 65C816 in emulation mode**. The example passed assembly,
S-record export and execution in the serial-disabled offline model. Use that model during the
protected board campaign; loading ASM replaces application RAM.

The [DBG1 extension](DEBUGGER_GUIDE.md) adds explicit `BRK xx` operands and
automatic RAM debugging in **generation 50**. The title still says ASM 0.5;
use `VERSION` and the matching candidate package to identify this extension.
The debugger examples below require DBG1. Native assembly/debugging is outside
scope; the 816 examples use E=1 with direct page, DBR and PBR zero.

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

## A small example program

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

## Debugging RAM programs with DBG1

ASM accepts `BRK $12`, `BRK #$12` and bare `BRK`, emitting `00 12`, `00 12`
and `00 00` respectively. A signature expression must fit one byte (`$00-$FF`);
`BRK $100` is a range error. It is a two-byte instruction, so a label following
it is two bytes later. `$00-$7F` stop, `$80-$84` are implemented services, and
other signatures stop unless a permitted callback is registered.

For each example, start a new ASM document with `NEW`, enter its numbered
lines, `ASM`, optionally inspect `DUMP`/export `S19`, then `QUIT` and `G 0200`.
The default output buffer and origin are both `$0200`, so no relocation is
needed. Use only an idle board whose application RAM you may replace; keep
source/export copies. The debugger does not reserve application bytes or
change the [ASM buffer layout](#buffer-ownership).

### C, S and N example

<!-- debugger-example: steps -->
```asm
10 ORG $0200
20 SEI
30 CLD
40 LDX #$00
50 BRK $01
60 INX
70 JSR sub
80 INY
90 JSR sub
100 BRK $02
110 JMP $7E67
120 sub: INX
130 RTS
140 END
```

The first stop is PC=`0206`, X=`00`. At `DBG>`:

| Command | Expected result |
| --- | --- |
| `S` | INX: X=`01`, PC=`0207` |
| `S` | Enter JSR: PC=`0213`, SP=`FD` |
| `S` | Subroutine INX: X=`02`, PC=`0214` |
| `S` | RTS: PC=`020A`, SP=`FF` |
| `N` | INY: Y increases once, PC=`020B` |
| `N` | Run JSR through RTS: X=`03`, PC=`020E`, SP=`FF` |
| `C` | Stop after BRK 02: PC=`0210` |
| `C` | Return through HOLD to the monitor |

Initial Y is unspecified in this example. `R` displays it. `D 0206 0214`
and `U 0206 08` inspect the program without changing it. See the
[command reference](COMMAND_REFERENCE.md#dbg1-debugger-context) for register
editing, shared M and the full command list.

### Eight-breakpoint loop

<!-- debugger-example: eight-breakpoints -->
```asm
10 ORG $0200
20 SEI
30 CLD
40 LDX #$00
50 LDY #$00
60 BRK $01
65 NOP
70 loop: INX
80 INX
90 INX
100 INX
110 INX
120 INX
130 INX
140 INX
150 INY
160 CPY #$02
170 BNE loop
180 BRK $02
190 JMP $7E67
200 END
```

At the first `DBG>` stop (PC=`0208`, before NOP), set all eight:

```text
B 0209
B 020A
B 020B
B 020C
B 020D
B 020E
B 020F
B 0210
B
```

`B 0600` is a ninth distinct request: it must return `?` and retain the eight.
Use `C` sixteen times. Each stops before the next INX; addresses `0209` through
`0210` appear twice, X=`00..0F`, with Y=`00` on pass one and `01` on pass two.
`D 0209 0210` while paused shows eight original `E8` bytes. One more `C` reaches
BRK 02 with X=`10`, Y=`02`, PC=`0218`. `BC 020C` leaves seven; `BC *` leaves
none; `C` reaches HOLD. Reload/run and use X with eight entries set to exercise
abort cleanup. Breakpoints persist through C/S/N, and clear at HOLD/X/reset.

### User registration example

This program registers `$C1`, calls it, and stops with saved A=`42`. The
handler returns with RTS and writes `$7002`, the saved application A field.
Live callback A/X instead identify the saved context; changing live A alone
does not set the application's return value.

<!-- debugger-example: user-registration -->
```asm
10 ORG $0200
20 SEI
30 CLD
40 LDA #<request
50 LDX #>request
60 BRK $81
70 BCC failed
80 BRK $C1
90 BRK $01
100 LDA #$C1
110 BRK $82
120 BRK $02
130 JMP $7E67
140 failed: BRK $7F
150 JMP $7E67
160 request: BYTE $C1
170 WORD handler
180 BYTE 0
190 handler: LDA #$42
200 STA $7002
210 RTS
220 END
```

At the first stop, `F` lists `$C1` and its handler. `C` unregisters it and
stops after BRK 02 with A=`00`, C=1; `F` then omits `$C1`. Another `C` returns
through HOLD. The four-byte request is ID, handler-low, handler-high, zero
flags. There are sixteen user slots (64 bytes) and four separate system slots
(16 bytes); user registration cannot consume/replace system or built-in IDs.
All registrations clear at HOLD/X/reset. Read the
[complete BRK ABI and system registration example](ABI_REFERENCE.md#dbg1-brk-functions-and-registrations)
before implementing callbacks.

The 816 debugger steps/disassembles the supported common instruction subset;
it refuses repurposed 65C02 bit instructions and unsupported 816-only
encodings. These examples do not enter native mode. See
[execution limits](DEBUGGER_GUIDE.md#inspecting-saved-memory-and-execution-limits)
and [board versus offline coverage](DEBUGGER_BOARD_RESULTS.md).

## Errors and reproducibility

Errors identify a line and category: syntax, opcode/mode, undefined or
duplicate symbols, range/branch, source/symbol/output space, phase, line,
expression depth, cancellation, layout or scope. Correct source and assemble
again before export. Do not treat previous output as the failed program's
result. Record the ASM version, source, origin and exported bytes when sharing
an example. Host WDC encoding comparisons are separate qualification evidence;
they do not make every host-assembler syntax valid in the board editor.

## Source and evidence

- Editor, parser, diagnostics and help (repository reference: `release/candidates/rc1/source/assembler/asm-app.asm`)
- Buffer layout (repository reference: `release/candidates/rc1/source/assembler/layout.inc`)
- Public ABI constants and contract (repository reference: `release/candidates/rc1/source/assembler/str8n-v2-public.inc`)
- Explicit BRK operand patch and debugger (repository reference: `release/candidates/rc1-debugger/build.py` and `source/debugger.asm` in that candidate)
- [Technical manual](TECHNICAL_MANUAL.md)

The same firmware supports 65C02 and 65C816 emulation-mode runtime. Native
816 applications/testing, ACIA and crypto remain deferred. The existing startup
CPU detector briefly enters native mode before restoring emulation; this
startup exception was explicitly accepted by the owner.


## Complete uChess source session

See [uchess.a: ASM 0.5 and S/T/R walkthrough](UCHESS_ASM_SESSION.md) for the
qualified full-game PASTE/assembly, Store, Table, load-only Restore and run example.
