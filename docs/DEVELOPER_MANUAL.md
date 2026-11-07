# STR8-N DEV ASM / DBG — operator manual

DEV is a separate component group above frozen F, alongside MON and UTIL.
See [current source/releases](COMPONENT_GUIDE.md),
[BIN/S-record formats](FILE_FORMATS.md) and
[qualification scope](QUALIFICATION_SCOPE.md). The workflows below retain the
compact candidate4 memory/launch contracts; historical acceptance does not
qualify later rebuilt or renamed bytes automatically.

Current named-kit RAM packets are
`payload/str8n-dev-asm-0.6-dev-g00000002-ram.bin` and
`payload/str8n-dev-dbg-g00000002-ram.bin`. Historical `developer/ASM-RAM.bin`
and `developer/DBG-RAM.bin` paths below belong to the earlier candidate ZIP.
Use `COMPONENTS.json` and `NATIVE-COMPONENTS.json` for current hashes,
paired sectors and placement.

These are optional developer tools in the compact unified profile above
frozen Foundation 0.3.0 BASE1/PR05 and MON A/B g00000010. They are included
in this candidate, rather than postponed as a separate release. See the
[operator manual](NATIVE_UTILITIES_MANUAL.md) for installation/ownership and
[acceptance boundaries](QUALIFICATION_SCOPE.md) for remaining gates.

## Launch and return

At REC>, enter B or A. APPS lists ASM at B0:A000 and DBG at B0:C000.
`R ASM` / `APP ASM` opens the editor. `R DBG` / `APP DBG` asks for a RAM
start address $0200–$3FFF; Q cancels that chooser. ASM uses QUIT. Stopped
DBG uses X; program HOLD also returns to MON. Neither is a returning BATCH job.

Install ASM across B0:A/B and DBG across B0:C/D. The latter includes the exact
SF/1 source provider at D800–DFFF; do not substitute an old debugger tail.
The ASM and DBG AP/02 headers use CPU tag `$00` for the shared 65C02 and
65C816 emulation profile. Install the B3:E000 dispatcher first. It also accepts
older CPU-specific `$02` and `$16` headers on their matching CPUs. Load the
standalone DEV RAM packets through the recovery raw BIN loader.

## Assemble and run

For a complete game assembled by the current DEV ASM, see the
[Microchess worked example](EXAMPLES.md): attributed source parts, checked S19
exports, PC save/restore, AS/1 source persistence and a RAM-copy AP/02 wrapper.
The same guide links OSI BASIC as an opaque B0 Foundation-call example.

In ASM, type these numbered source lines:

```text
10 ; Print a marker, then return through Foundation HOLD.
20 ORG $0200
30 LDA #$23
40 JSR $7E6D
50 JMP $7E67
60 END
ASM
LST
SYMS
DUMP
QUIT
```

Expected bytes at $0200 are `A9 23 20 6D 7E 4C 67 7E`. At MON, `G 0200`
prints # and returns through HOLD. Source editing supports numbered-line
replacement/deletion and the tool's own help, labels/EQU, listings, symbols,
diagnostics, DUMP and S19 output. This is a **65C02 cross-assembler on both
CPUs**. Emitting an opcode does not make it appropriate for an 816.

Output is physically staged at $0200 even when ORG differs. For another
origin, place the exported S19 or deliberately copy output before running it.
A logical LST/DUMP address is not evidence of physical placement. SAVE may
borrow the output buffer; ASM again before running after a save.

## Debug the same program

Launch `R DBG`, enter `0200`, then:

```text
R
U 0200 3
S
N
C
```

S executes LDA and leaves PC=$0202. N steps over the nonblocking public PUTC
call, prints # and leaves PC=$0205. C runs the HOLD return. R shows registers;
register edits accept e.g. `R PC 0200` (optional `=`). Use the on-tool help
for the register and range grammar.

| Command | Use |
| --- | --- |
| S / N / C | Logical step / step over / continue |
| R / U | Registers / disassemble |
| D / M | Dump / modify admitted RAM |
| B address / B | Set breakpoint / list breakpoints |
| BC address / BC / BC * | Clear one / clear all |
| X | Exit stopped debugging and restore hooks/patched bytes |

All eight breakpoint slots, cleanup paths, BRK services and stopped-register
publication have dated acceptance. X publishes stopped ZP edits; HOLD preserves
live program ZP under the accepted return contract. Keep IRQ masked. Continue
is not a sandbox for arbitrary I/O, code or processor-mode changes.

The 816 emulation checks cover the common 8-bit subset and refusal of
reassigned/unsupported opcodes for S/N. RMB/SMB/BBR/BBS emitted by the assembler
must not be executed as those instructions on an 816. Native 816 debugging and
hardware IRQ debugging are outside this candidate.

## Save and reload source

`SAVE SRAM name` / `LOAD SRAM name` use AS/1 records in formatted PROGRAM.
`SAVE FLASH name` / `LOAD FLASH name` use paired SF/1 flash-source storage.
Flash saves propose a specific blank extent, require YES and do not implicitly
erase/overwrite another image. Admit that exact target first. Use new names
for revisions. Dirty LOAD asks before discarding edits. WORKSPACE is not used.

Positive AS/1/SF/1 write trials were performed on 2512 with exact temporary
data restoration. 2609's targeted emulation/installed checks do not relabel
those fixtures as physical 816 source-write tests. Existing formatted source
records are not preloaded into the new kit.

## Raw RAM BINs and memory use

F2/F4 can load `developer/ASM-RAM.bin` from REC>. It starts the editor.
`developer/DBG-RAM.bin` is the qualification entry packet: it stops at its
seed BRK near $1000. It is **not** the installed start-address chooser. Use
its register command to select a known admitted fixture, or launch the
installed AP/02 tool for the normal chooser.

ASM uses output $0200–$1FFF, source $2000–$37FF, symbols $3800–$3FFF,
code $4000–$63B7 and state $6500–$66FF. DBG admits targets $0200–$3FFF,
uses code $4000–$508A, tables $5F00–$6407 and state $7000–$744F. Launch
borrows $6700–$69FF; PROGRAM providers use $6B00–$77FF. The SF/1 provider
loads at $7000–$77FF from B0:D800–DFFF.

ASM-RAM's flash-source operations need that installed paired provider; this
RAM packet is not self-contained for SAVE/LOAD FLASH. Full REC MAINT/FLASH
are separate self-contained tools. Switching overlapping tools borrows RAM
and cache. Save application work before interactive use; Q/QUIT is not an
automatic owner-RAM restore. Qualification escrowed/restored application RAM,
ZP, cache and hooks independently.

## Historical evidence

The original evidence and candidate ZIP names below describe their exact
tested artifacts. Raw/private evidence is not bundled with the current named
kit. Current public limits are recorded in [qualification scope](QUALIFICATION_SCOPE.md).

65C02 RAM/installed/extracted developer candidate2 checks passed on 2512.
Thirteen RAM groups and installed checks passed on 2609 in emulation; the
2604 rollout retained the CPU02 tools. The subsequent compact cleanup retained
the executable bodies and APPS routes and accepted REC tools on all three
boards. Evidence summaries in `evidence/QUALIFICATION.json` separate these
passes from packaging checks. Candidate4's exact extracted ASM/DBG RAM packets
subsequently passed on 2512: assembly/list/symbols/dump/S19/run/HOLD, register
and disassembly checks, stepping/step-over/continue, breakpoints and cleanup.
Owner RAM/ZP/cache/hooks were restored. See `UNIFIED_CANDIDATE_STATUS.md` and
the companion `ACCEPTANCE-2512.json`; this adds no new816 qualification.
No firmware compilation was required for this acceptance.
