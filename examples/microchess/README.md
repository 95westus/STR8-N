# Microchess: assemble, save/restore and make AP/02

Microchess **(c) 1976–2005 Peter Jennings, benlo.com**. Daryl Rictor added the
serial chessboard interface (2002); Bill Forster corrected OCR errors (2005).
The STR8-N port is Copyright (c) 2026 95west.us/wlp1963; MIT. These port terms
do not replace Jennings's engine license. Keep LICENSE.txt, UPSTREAM.json,
the original source and these credits with source and binaries. The original
redistribution notice/disclaimer is preserved unchanged in LICENSE.txt.

The author publishes the [original source](https://benlo.com/files/Microchess6502.txt)
and [licensing/history](https://benlo.com/microchess/). This example adapts the
previously preserved STR8-N port, retaining its public PUTC `$7E6D`, GETC
`$7E70` and HOLD `$7E67` calls. Both the engine and port `(c)` notices are in
the executable and appear at startup. No direct ACIA or private F ROM calls
remain. F is unchanged.

## Source files and current ASM limits

`microchess-readable.asm` is the full descriptive reference. The generated
`microchess-part1.asm` through `microchess-part4.asm` contain real instructions
and compact labels for the unchanged DEV ASM source/symbol buffers. Each
fits the 6144-byte packed source limit; the full reference does not.

Each part has a logical ORG and explicit EQU values for references outside
that part. Those addresses bind this exact reference build. Editing code
lengths requires regenerating the parts and checking their external symbols;
this example is not a general multi-module linker. EXAMPLES.json gives the
exact part origins, lengths, final RAM range and SHA-256.

The output buffer is always physically `$0200`, even for later logical
origins. Export each part before assembling the next; do not execute a
single partial output buffer. The provided complete RAM BIN/S19 and AP/02
are alternative ways to run the verified combined result.

## Assemble using DEV ASM

Preserve owner RAM first. From a matching installed MON:

```text
R ASM
NEW
PASTE
```

After the paste message, send `microchess-part1.asm` as paced ordinary ASCII
text, then a line containing only `.`. At `ASM>`:

```text
ASM
LST
S19
```

Save only the emitted S0/S1/S9 record lines on the PC as `part1.s19`, without
the echoed command, prompts or listings. Repeat NEW/PASTE/ASM/S19 for parts
2, 3 and 4, saving `part2.s19` through `part4.s19`. Keep all four exports.
The on-board source can also be saved with `SAVE SRAM UCP1` (and UCP2–UCP4)
in an already admitted/formatted PROGRAM store. `LOAD SRAM UCP1` restores
that source; run ASM again afterward. These commands save source, not the
compiled game or its current board position, and use real owner storage.

From an extracted kit root, join and independently compare the exports:

```powershell
python examples/tools/example_images.py join-s19 part1.s19 part2.s19 part3.s19 part4.s19 --entry 0200 --expect examples/payload/microchess-ram.bin --out my-chess
```

From a repository checkout use `tools/example_images.py` and the corresponding
example-build reference path instead. The join rejects checksums, overlaps,
gaps, unsupported record types and a missing entry. It creates `program.bin`,
`program.s19` and a SHA-256 manifest in a new directory; it opens no port.

## Restore and play the RAM program

QUIT returns from ASM to MON. Enter `S19`, wait for the RAM S0/S1/S9 prompt,
then use Terminal Shift+F2/F3 to send `my-chess/program.s19`. Check successful
completion before `G 0200`. This loads the complete logical image without
running it automatically. Keep the combined BIN/S19 and manifest on the PC;
reload the same S19 to restore overwritten executable RAM.

The game initializes a new position at every launch. Its saved executable
is not a suspended game. The program owns its documented low zero-page
working arrays and CPU stack; it avoids system ZP `$E0–$FF` and returns through
HOLD. Do not expect ASM editor state to survive execution: reopen/load the
source when needed.

- `P`: computer plays; the first opening move is 13 to 33.
- `6343` followed by Enter: example human pawn move using printed hex squares.
- `E`: exchange sides; `C`: reset the position.
- `Q`, Escape or Ctrl-C: return through public HOLD.

Single-key commands do not need Enter. The original engine's chess/rules
limitations remain; this is a historical program, not a modern rules library.

## Make or use AP/02

From the kit root, package the actual assembled RAM BIN:

```powershell
python examples/tools/example_images.py ap02 --ram my-chess/program.bin --load 0200 --entry 0200 --base 8000 --name UCHESS --out my-chess-ap02
```

The shared envelope requires the updated AP/02 dispatcher and works on both
CPUs. The output is one 4096-byte sector for **B1:$8000**. Its entry `$8020`
copies the game to RAM and jumps to `$0200`. The same file is available in
`examples/payload/`. The helper rejects RAM programs that exceed the
one-sector wrapper.

Inventory B1:$8000, save its exact preimage and confirm ownership before
using the matched OPAQUE installer. Do not install it over a stored program
or a WDC backup. After approved installation and independent readback, MON
`APPS` should list UCHESS. Use `R UCHESS` or `APP UCHESS` to launch it. The model check validates headers/CRCs and runs the real AP entry;
physical MON admission/installation remains a separate trial. No example
build, join or AP/02 command opens a port or flashes anything.

## Rebuild and verification

From the repository, with WDC tools plus external cc65 installed:

```powershell
python -B tools/build_examples.py --out build/examples --cc65 C:/Tools/cc65
python -B tools/test_examples.py --build build/examples --kit build/components --cpu 65c02
python -B tools/test_examples.py --build build/examples --kit build/components --cpu 65c816-e
```

The tests drive actual DEV ASM NEW/PASTE/ASM/S19 for all parts, compare the
combined bytes with the independent readable WDC build, play moves and run
the AP/02 entry. Public console/return endpoints are modeled; no board or
F assembly is involved. The kit carries the two CPU reports and exact hashes.
