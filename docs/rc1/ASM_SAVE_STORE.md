# ASM source SAVE and executable Store

These examples target the local ASM development extension installed on board
2604 on 2026-10-21. It adds EQU, LST, SYMS and source-aware errors to ASM 0.5.
The banner and generation number alone do not identify the extension. Published
r9 and board 2609 do not acquire these commands from a documentation update.

The examples below are instructions to follow when wanted. This documentation
update opens no board ports and writes no board storage. The completed cleanup
left B0:8-F empty and removed uChess from B1:8. Host text is the default source
copy; the optional flash-source SAVE section deliberately consumes B0 space.

## 1. Enter a program using EQU

At `B3>`, enter `ASM`. At `ASM>`, enter `NEW`, then these numbered lines.
Keep the same source text in a host file for later editing.

<!-- asm-doc-example: hello -->
```asm
10 BASE EQU $0200
20 PUTC EQU $7E6D
30 HOLD EQU $7E67
40 CHAR EQU $41
50 ORG BASE
60 start: SEI
70 CLD
80 .ready: LDA #CHAR
90 JSR PUTC
100 JMP HOLD
110 END
```

EQU defines a constant without generating a byte. `name .EQU expression` and
`name = expression` have the same meaning. Names are case-insensitive. Define
a constant before another constant uses it. The local label `.ready` belongs
to `start`; symbol output calls it `START.READY`.

## 2. Assemble, list and look up symbols

At `ASM>`:

```text
ASM
LST
SYMS
SYMS start
SYMS .ready
```

Assembly reports `OK 10 bytes, origin $0200, buffer $0200`. The emitting rows
in LST are shown below; spacing is shortened here. LST also prints the EQU,
ORG and END source lines, which emit no bytes in this example.

```text
60 0200 78          start: SEI
70 0201 D8          CLD
80 0202 A9 41       .ready: LDA #CHAR
90 0204 20 6D 7E    JSR PUTC
100 0207 4C 67 7E   JMP HOLD
```

SYMS displays the following values in symbol-table order:

```text
0200 BASE
7E6D PUTC
7E67 HOLD
0041 CHAR
0200 START
0202 START.READY
```

`SYMS start` selects the global START entry. `SYMS .ready` selects matching
locals and includes their parent names. `SYMS absent` reports
`No matching symbols` without creating a symbol. LST prints up to four bytes
per row; longer data output continues on more address/byte rows. It reassembles
the source. Ctrl-C cancels listing; assemble again before using its output.

## 3. Preserve editable source

The host text copy preserves source without using board storage. On a board
with the external SRAM service and an initialized program allocation, this
optional source cycle preserves the numbered document, including EQU lines:

```text
SAVE SRAM HELLOSRC
ASM
LST
SYMS .ready
```

To demonstrate source recovery, enter NEW, then LOAD SRAM HELLOSRC. NEW marks
the empty source document dirty, so LOAD asks for confirmation. Type YES at
that prompt. After `Source loaded`, enter ASM, LST and SYMS .ready again. In
other sessions, type YES only when requested; do not send it as an extra shell
command. SRAM needs retained power. SAVE can replace
the same SRAM name by publishing a new version, subject to available capacity.
Allocation, formatting and reclamation are separate SRAM-manager operations.

SAVE and an attempted LOAD use the output buffer as scratch and invalidate the
assembled result. Source edits and NEW also invalidate it. Run ASM after the
last SAVE, LOAD or edit before LST, SYMS, DUMP, S19 or executable Store. A failed
LOAD preserves live source. If LST or SYMS says `Assemble successfully first`,
run ASM and resolve any reported errors.

### Optional flash-source archive

To keep B0:8-F empty, use host text or the SRAM path above. If you later choose
to archive source in flash, these commands are available at `ASM>`:

```text
SAVE FLASH HELLOSRC1
ASM
LST
SYMS start
```

This writes a source record in B0:$8000-$DFFF. Small sources reserve one whole
erased 4 KiB sector; larger ones need two consecutive sectors. Names must be
new: use HELLOSRC2 for an edited edition. No sector erase, replacement or
automatic reclaim is supplied by SAVE FLASH. LOAD FLASH HELLOSRC1 restores
source, after a dirty-document confirmation when needed; then assemble again.
Source flash names do not appear as executable programs in monitor T.

## 4. Inspect or run the assembled RAM program

After the last source operation, use these commands at `ASM>`:

```text
ASM
LST
SYMS start
DUMP
S19
QUIT
```

DUMP shows the ten bytes `78 D8 A9 41 20 6D 7E 4C 67 7E`. S19 exports an
executable image; save that terminal output on the host if wanted. At `B3>`,
`G 0200` prints A and returns through HOLD. This example uses the initialized
RAM ABI on an idle board. It uses no LED registers or persistent-storage calls.
On 65C816, enter in emulation mode with D, DBR and PBR zero.

## 5. Optional executable Store, table and restore

This is a separate flash write at the monitor prompt. Assemble after the last
source SAVE/LOAD, inspect LST and the ten bytes above, then QUIT. Inspect `T 1`
before choosing an unused executable name. To store that verified RAM image:

```text
S 1 AUTO 0200 0209 HELLO
T 1
R 1 HELLO L
D 0200 0209
G 0200
```

S stores an executable with an inclusive RAM range, so ten bytes starting at
$0200 end at $0209. AUTO selects admissible erased space in bank 1 and refuses
if no suitable extent exists. It does not erase occupied records. In the
cleaned 2604 layout, B1:8 is available; this example would consume flash space
there while leaving B0 empty. Existing firmware/source/debugger sectors remain
reserved. The stored record contains a 24-byte header plus the ten code bytes.

R with the final L loads without running. Check D before G; the program prints
A and returns. R without L loads and runs in one command. Store preserves
executable bytes, not EQU definitions, labels, source lines or an editor
session. Recover those from the host file or source SAVE/LOAD.

## 6. Read an error, fix the line, then assemble again

At `ASM>`, try this independent example:

<!-- asm-doc-example: undefined -->
```text
NEW
10 ORG $0200
20 LDA MISSING
ASM
```

The error identifies both the source and unresolved name:

```text
Error line 20: Undefined symbol
LDA MISSING
Symbol: MISSING
```

Replace line 20 with `20 LDA #$41`, then run ASM, LST and SYMS again. The
replacement emits `A9 41`. This two-byte diagnostic fragment has no return
instruction; inspect it without executing it.

Other independent examples begin with NEW:

| Numbered source | Report and next step |
| --- | --- |
| `10 X EQU 1` then `20 X EQU 2` | Duplicate symbol, source `X EQU 2`, and `Symbol: X`. Delete line 20 or choose a different name. |
| `10 ORG $0200` then `20 LDA #$100` | Value out of range and source `LDA #$100`. An immediate byte must fit $00-$FF. |
| `10 ORG $0200` then `20 BRA $0400` | Branch out of range, source `BRA $0400`, and `Branch displacement must be -128..127 bytes`. Use a nearby label or an appropriate absolute jump to a valid target. |

After a failed assembly, LST, SYMS, DUMP and S19 refuse stale results until a
successful ASM. Error examples are inspection exercises, not programs to run.

See the [ASM manual](ASM_GUIDE.md), [development command details](ASM_DEVELOPMENT.md),
[command reference](COMMAND_REFERENCE.md) and [onboarding quick start](QUICK_START.md).
