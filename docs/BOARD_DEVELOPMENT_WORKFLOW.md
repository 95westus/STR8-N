# Practical resident development — Phase 12

Phase 12 is the preparation and offline rehearsal of this workflow. The kit
lets us practice editing, assembling, debugging and returning source to the
host. No current firmware is edited or installed, and neither board is
contacted. An actual board trial is a later, separately authorized step with
fresh admission and preservation checks.

## Prepare the host kit

With the existing verified build and model dependencies available, use a new
output directory:

```powershell
python -B tools/board_development.py prepare --build BUILD/phase11 --out BUILD/board-development
```

The kit provides known source/binary references for a small RAM program and the
resident VERSION candidate, plus the information needed to compare returned
source. Its generated files are development inputs; `src/current` remains the
authoritative firmware tree. The kit is bound to the reviewed Phase 11 revision
2 starting point.

## Choose and admit the board later

The frozen receipts record these historical states:

| Board | Recorded image | Recorded monitor | Development implication |
| --- | --- | --- | --- |
| 2604 / `A10MQGVHA` / 65C02 | `asm-dev`, with capture-specific cleanup | B | Expected to have the current ASM features; verify fresh state first |
| 2609 / `A10MPQXCA` / 65C816 | Earlier `console-edit` image | A | That pinned image lacks `LST` and `SYMS`; do not assume the full lane is available |

These are historical receipts, not a live assertion about either board. A
VERSION banner, CPU type or generation number alone does not identify the ASM
application. The future trial must match the physical USB/board identity,
actual application/image identity, required commands, available RAM, monitor
state and debugger state. The existing preserving installer/capture path is
the reference for identity, ownership, coordination and recovery checks; this
kit creates no replacement serial or installation route. Follow the existing
[capture and recovery checks](../tools/installer/README.md), including owned
system sectors, the ASM component, recorded cleanup and preserved owner data.

For the full lane, confirm the admitted ASM supports `PASTE`, `LIST`, `ASM`,
`LST`, `SYMS` and `S19`. ASM's `65C02` banner describes its instruction language,
including when it runs on the 816; it does not identify the board's CPU mode.
The 816 calling conditions remain emulation mode, decimal clear and zero direct
page/DBR/PBR. Preserve existing RAM work before opening ASM, which claims
`$0200–$64FF` and application zero page. Unsupported admission stops that board's
trial; it does not authorize an update or silently select an older workflow.

## First lane: edit and execute a tiny RAM program

The following are prepared console instructions, rehearsed in models during
this phase. They are not commands to either physical board now.

From an admitted monitor, enter `ASM`. At the assembler prompt, enter `PASTE`,
paste these **13 unnumbered lines**, then enter a line containing only `.`:

```asm
BASE EQU $0200
PUTC EQU $7E6D
HOLD EQU $7E67
CHAR EQU $41
ORG BASE
START: SEI
CLD
LDA #CHAR
BRK $01
JSR PUTC
BRK $02
JMP HOLD
END
```

This is kit unit `hello-a`. PASTE numbers its records 10 through 130. The
program assembles to 14 bytes at `$0200`, with entry `$0200`:
`78 D8 A9 41 00 01 20 6D 7E 00 02 4C 67 7E`.

At `ASM>`, use these commands in order:

```text
LIST
ASM
LST
SYMS
S19
```

Save the complete LIST and S19 captures separately on the host. `LIST` returns
numbered source; `ASM` compiles; `LST` checks the listing; `SYMS` shows symbols;
`S19` exports code. Confirm the successful result is 14 bytes with logical
origin `$0200`. Any edit or failed assembly requires a fresh successful ASM
before the result is used.

Collect and verify this known capture into a new host draft directory:

```powershell
python -B tools/board_development.py collect --kit BUILD/board-development --base hello-a --expect hello-a --list captures/hello-a.list.txt --s19 captures/hello-a.s19.txt --out BUILD/hello-a-return
```

After the capture is preserved, the RAM/debug path is:

```text
QUIT
G 0200
R
U 0206 03
N
C
C
```

`QUIT` returns to the monitor. `G 0200` reaches BRK `$01`, stopping with PC
`$0206` and A `$41`. At `DBG>`, `R` inspects registers and `U 0206 03`
disassembles three instructions starting at `$0206`. `N` steps over `JSR PUTC`,
prints `A` and stops at `$0209`.
The character has no newline, so it can appear immediately before the next
debugger PC report.
The first `C` reaches BRK `$02`, with PC `$020B`; the second continues through
`JMP HOLD` back to the monitor. The top-level exit is `JMP $7E67`: monitor G is
a jump handoff, not a subroutine call with an RTS return frame.

To practice a source change, reenter ASM and restore `hello-a` from its host
source using PASTE. Then enter:

```text
40 CHAR EQU $42
LIST
ASM
LST
SYMS
S19
```

The numbered edit changes the character from `A` to `B`; it is kit expectation
`hello-b`. Capture both outputs again and collect them separately:

```powershell
python -B tools/board_development.py collect --kit BUILD/board-development --base hello-a --expect hello-b --list captures/hello-b.list.txt --s19 captures/hello-b.s19.txt --out BUILD/hello-b-return
```

Review the returned source change and replay its source from the host. The
same RAM/debug sequence should now print `B`, with A `$42` at the first stop.
No firmware package or installer is needed for this edit/compile/debug loop.

## Second lane: develop VERSION source and export it

Resident ASM handles one prepared component at a time: at most 7,168 packed
source bytes, 12,544 output bytes, 256 symbols and 120 characters per source
line. VERSION fits with 304 records, 4,637 packed source bytes, 636 output bytes
and 65 symbols. The full firmware build, linking and packaging stay on the host.
See the [resident build contract](RESIDENT_BUILD_CONTRACT.md) for supported
syntax and preparation rules.

Use the kit's `version-fast` source to work on VERSION itself. Enter a fresh
ASM session, paste its prepared source, inspect `LIST`, then use `ASM`, `LST`,
`SYMS` and `S19`. Preserve the captures before leaving the session.

The source has 304 records. Practice a real command-path change at record 520:

```text
520 JSR BN_SHOW
ASM
LIST
SYMS
S19
```

This produces kit expectation `version-control`: the command uses the original
reader/check wrapper instead of the cached entry. It remains a 636-byte body
with 65 symbols because the private `BN_SHOW_CACHED` label remains in the
source. The control is a known comparison lesson; it retains the verified
newline tail call and does not change current firmware.

Save these LIST and S19 responses and collect the known change:

```powershell
python -B tools/board_development.py collect --kit BUILD/board-development --base version-fast --expect version-control --list captures/version-control.list.txt --s19 captures/version-control.s19.txt --out BUILD/version-control-return
```

Restore the cached path in the same session:

```text
520 JSR BN_SHOW_CACHED
ASM
LIST
SYMS
S19
```

The result should again match `version-fast`, including its source and exported
bytes. Capture and compare the restored result before leaving the editor.

VERSION's logical origin is `$6E00`; its executable entry is `$6E04`. The
assembler still writes its 636 output bytes to physical `$0200`. Its S19
records describe logical addresses, and S9 contains origin `$6E00`, which is
different from executable entry `$6E04`.

This lane compiles and exports. It does not run the raw output at `$0200`,
execute an unplaced `$6E04`, load a new image into flash, or make a firmware
installer. Executing the full command requires its correct placement and
initialized monitor/bootstrap services, as exercised separately by the
packaged-candidate CPU proofs.
The [cached VERSION contract](VERSION_CACHED_CANDIDATE.md) defines the stable
journal and no-interleaved-writer conditions for any later placement and
execution. This lane remains compilation and export only.

For an exploratory resident edit without a known kit expectation:

```powershell
python -B tools/board_development.py collect --kit BUILD/board-development --base version-fast --list captures/version-edit.list.txt --s19 captures/version-edit.s19.txt --out BUILD/version-edit-draft
```

Omitting `--expect` produces an **unverified draft**, not a qualified firmware
change. Preserve the source, returned bytes and provenance together. Review and
reconcile the intended change into the authoritative files through the host
workflow later. Flattened resident source cannot automatically reconstruct the
original includes, comments, aliases and WDC directives. Do not overwrite the
existing source tree with the captured intermediate source.

## Session and capture rules

- Opening ASM resets its source-end pointer and starts an empty logical
  document. A previous session's bytes remaining in RAM do not preserve it.
- `NEW` discards the document without dirty confirmation; `QUIT` also has no
  unsaved-edit confirmation. Preserve LIST/source captures first.
- PASTE appends after the last record in steps of ten. Use a deliberately empty
  document when replaying a complete source. A numbered line replaces that
  record; a bare number deletes it.
- LIST contains line numbers and text, with no built-in checksum, record count
  or end marker. Cancellation or missing terminal output can leave a plausible
  partial listing. Known `--expect` references provide a comparison; generic
  collection remains an unverified draft. Do not infer capture completeness
  solely from a returned prompt.
- Preserve returned line numbers in the host records. PASTE replay may renumber
  edited documents; source text/order and record identity are separate checks.
  A 120-character PASTE line can exceed the typed-line limit once a number
  prefix is added.
- `SAVE` uses the output buffer as scratch and invalidates compiled output;
  `LOAD` restores source, requiring reassembly. A dirty LOAD asks for `YES`.
  Reassemble after source-storage activity before exporting or running code.

The default lane uses host source capture and replay. Optional SRAM SAVE/LOAD
belongs only in a later admitted trial with a known available allocation and
reviewed name. It must not format SRAM, erase owner data or use flash source
storage. The assembler's printed `S 1 AUTO ...` suggestion is executable-storage
guidance and is excluded from this RAM workflow.

The prepared recipes and host collection are the practical Phase 12 foundation.
Physical-board admission and execution remain separate from the offline proof.

## Completed offline verification

Phase 12 passed 33 host checks and eight linked-firmware model profiles:
65C02 and 65C816 emulation mode, monitor slots A/B, and bare/EDU configurations.
The runs include 16 RAM debugger executions, 32 verified LIST/S19 capture pairs,
source replay after ASM reentry, and VERSION fast/control/fast editing and
export. Separate models cover four SRAM save/cancel/load cases and four
bare-board storage refusals. Default sessions make no SRAM transfers; all four
modeled flash banks remain unchanged.

The models retain the existing FT245, discovery/delay and optional SRAM ABI
fixtures. Physical USB pacing, live board admission and hardware execution
remain for the later board trial. The [Phase 12 receipt](../tests/baselines/phase12.json)
records the preserved inputs and complete captures.

To repeat the checks using fresh output directories and the existing model
dependencies:

```powershell
python -B tools/test_board_development.py --mode host --build BUILD/phase11 --kit BUILD/board-development --out tmp/my-phase12-host
python -B tools/test_board_development.py --mode runtime --build BUILD/phase11 --kit BUILD/board-development --out tmp/my-phase12-models
```
