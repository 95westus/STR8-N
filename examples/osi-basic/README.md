# OSI BASIC through public Foundation calls — opaque B0 example

This is the OSI configuration of the
[Michael Steil Microsoft 6502 BASIC reconstruction](https://github.com/mist64/msbasic),
pinned at `2a0bc2fe0db13f8cf1b5c40b1d5617263cdb9cb4`. UPSTREAM.json checks every
vendored source byte. The upstream README declares 2-clause BSD and credits
the reconstruction contributors; it is retained verbatim in `vendor/README.md`.
Keep BSD-2-CLAUSE.txt and those credits. The original interpreter is Copyright
1977 Microsoft; Microsoft's separately released original source has its MIT
notice preserved in MICROSOFT-LICENSE.txt. These notices are separate from the
STR8-N adapter Copyright (c) 2026 95west.us/wlp1963, MIT.

This example identifies itself as an OSI-derived port, not an unchanged OSI ROM.
The binary prints Microsoft and STR8-N `(c)` notices. It uses the original
small/six-digit OSI configuration and retains its historical language behavior.

## Image layout

| Item | Contract |
| --- | --- |
| Foundation | Frozen 0.3.0 g00000001 / BASE1 / PR05; initialized public RAM facade |
| CPU | 65C02 or 65C816 emulation, D/DBR/PBR zero, IRQ masked; no native 816 |
| Opaque image | 8192 bytes for **B0:$8000–$9FFF**, entry **$8000** |
| Sector files | `osi-basic-b0-8000.bin` and `osi-basic-b0-9000.bin`, each 4096 bytes |
| BASIC owner RAM | `$0300–$66FF`; fixed exclusive top `$6700`, no RAM probing into system workspace |
| Adapter scratch | `$0200–$0202`, plus the CPU stack |
| BASIC ZP | Original OSI workspace/CHRGET below `$E0`; system `$E0–$FF` is excluded |
| Calls | Public PUTC `$7E6D`, GETC `$7E70`, RAW_POLL `$7E73`, RESET `$7E64` |

Only the two named B0 sectors are payloads. B0:$A000–$DFFF, containing current
ASM/DBG, are outside this example's allocation. This is not a complete B0 or
whole-chip programmer image, an AP/02 image, a RAM recovery BIN or a WDC ROM.
Other owners may already use B0:$8000/$9000; the example does not allocate them
automatically. Keep WDC/other owner backups on the PC before changing a sector.

## Foundation adapter

`adapter.s` checks the public `RA`, format 1, 13-call signature and initializes
the keyboard latch. The build redirects the OSI monitor functions to that
adapter, fixes BASIC's RAM top and omits its RAM-size/terminal-width prompts.
The original vendor files remain unchanged; preparation edits a staging copy.
No old OSI `$FFxx` monitor calls or private F entry points are used.

Output preserves A/X/Y and flags around Foundation PUTC. Blocking input and
the poll path preserve their required registers; polling retains an ordinary
key for the next blocking read. Ctrl-C stops a running program and returns to
the OSI `OK` prompt. Escape restarts through public Foundation RESET. BASIC's
LOAD/SAVE hardware hooks return an unavailable-operation error; no tape,
filesystem or automatic storage writer is implemented by this example.

## Install and choose B0

Use an idle, compatible board with original owner RAM and both target-sector
preimages saved. Keep recovery as default during installation. Use the matching
OPAQUE tool/host to install and independently verify the **two sector files**,
one sector at a time. Do not send the combined 8192-byte image to a one-sector
installer or F's raw `L`. Consult the Foundation installation/OPAQUE guides.

After both sectors and hashes match, load CONFIG and use:

```text
B 0 8000
C S
Q
```

`B 0 8000` enables the verified B0 entry. `C S` keeps recovery as saved default.
At REC, `0` launches BASIC once. After acceptance, CONFIG `C 0` saves B0 as the
permanent default; `C S` restores recovery as default. These are saved journal
changes, not byte installation commands. Escape resets through the saved
default, so a saved B0 default starts BASIC again.

## Try BASIC, then save your program on the PC

```text
PRINT 2+3
10 FOR I=1 TO 3
20 PRINT I*I
30 NEXT I
RUN
LIST
```

Expected arithmetic output is 5; RUN prints 1, 4, 9. Use uppercase BASIC source
and carriage-return line endings. To preserve a program, LIST it, save the
numbered source lines as plain text on the PC, then NEW and paste those lines
back at the BASIC prompt. Do not include prompts/echo in the saved source.
Escape does not promise to preserve program RAM, CPU registers or an execution
continuation. Foundation recovery helpers borrow RAM when loaded.

OSI PEEK/POKE/WAIT/USR are not sandboxed. Deliberate arbitrary memory/I/O access
can violate this layout; the adapter does not make such programs safe.

## Build and verify

Use external cc65 (`bin/ca65`, `bin/ld65`, `asminc/`) and the repository recipe:

```powershell
python -B tools/build_examples.py --out build/examples --cc65 C:/Tools/cc65
python -B tools/test_examples.py --build build/examples --kit build/components --cpu 65c02
python -B tools/test_examples.py --build build/examples --kit build/components --cpu 65c816-e
```

The tests execute the real B0 image with modeled public Foundation endpoints:
cold boot, arithmetic, FOR/NEXT, LIST, strings, Ctrl-C and Escape. They check
that system RAM `$6700–$7FFF`, ZP `$E0–$FF` and ROM remain unchanged by the
tested BASIC commands. Model results are not physical serial/flash acceptance.
F is never rebuilt or written by these recipes. cc65 tools stay external and
are not redistributed in the kit.
