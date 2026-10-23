# Source development workbook: SXB and EDU

## Current 2604 workflow and historical demo material

On 2026-10-21, 2604 received EQU, LST, SYMS and source-aware error reporting.
The saved SXB/EDU demos and uChess were removed from flash, B0:8-F was verified
erased, and the board was left idle. The loop and source-record descriptions
below record the earlier demonstration campaign; they do not describe the
current running program or current stored records.

For a current non-LED onboarding example, use the
[EQU, listings, symbols and save/store walkthrough](ASM_SAVE_STORE.md).
Its ten-byte program defines BASE/PUTC/HOLD/CHAR with EQU, prints A and returns.
After ASM, LST shows `80 0202 A9 41` for its LDA and SYMS .ready reports
`0202 START.READY`. Replacing line 80 with `80 LDA MISSING` produces
`Error line 80: Undefined symbol`, the failing source and `Symbol: MISSING`.
Restore the line and assemble again before inspecting output.

SAVE SRAM HELLOSRC and LOAD SRAM HELLOSRC preserve editable source when an
initialized SRAM allocation is available; each source operation requires a new
ASM before LST/SYMS/export. Monitor Store preserves the executable instead.
Keep source on the host or in configured SRAM to retain empty B0. The optional
SAVE FLASH exercises below intentionally consume B0 and are historical recipes,
not commands performed by this documentation update.

## Earlier SXB/EDU source campaign

This workbook covers the named source development cycle and its SXB/EDU
samples. Appendix F gives exact debugger commands, stop addresses and register
values. Appendix G records the combined MAINT/ASM build and the separately
authorized board 2604 trial. Source-save commands require that candidate;
the released r9 monitor alone does not provide them.

For the **historically tested looping EDU program on 2604**, use Appendix I's complete
named-constant listing and Appendix J's debugger walkthrough. The bounded
samples in Appendices A/B/F are retained for comparison. The loop's cleanup
stop is `$0293`, with the unchanged two-chunk delay (about 20.4 seconds/pass).

All constants use `name = expression` definitions at the top, including
`LED_CRA = $7FA1`. Instruction operands and pattern data use those names;
`Bxx` denotes a literal byte value. Definitions emit no machine-code bytes.
Each revised SXB source save uses one sector; EDU needs two consecutive
sectors. Existing saved records retain the earlier source edition.

## The two source documents

| Sample | Target | Display |
| --- | --- | --- |
| [SXB source](../../examples/source-cycle/sxb-cs-patterns.asm) | Bare SXB or SXB + EDU | Eight different CS0–CS3 animations, 64 frames |
| [EDU source](../../examples/source-cycle/edu-led31.asm) | SXB + EDU enabled | 31 named LED animations, 248 frames |

The owner confirms **no hardware is attached to CS0–CS3**. Their base addresses
are `$7F00`, `$7F20`, `$7F40`, `$7F60`. The SXB program repeatedly **reads** selected
windows; it never writes them. Each table byte is a four-bit mask: bit 0 selects
CS0, bit 1 CS1, bit 2 CS2, bit 3 CS3. Repeated strobes create the visible pattern;
several selected LEDs are rapidly interleaved rather than latched on together.
The returned read data is ignored. These I/O reads are unrelated to programming
the flash chip. Reassess the reads if hardware is later attached to the windows.

The eight CS sequences are forward chase, reverse chase, bounce, alternating
pairs, fill/drain, outside/inside pairs, all blink and adjacent-pair chase.

The EDU program writes only the existing active-high LED data register `$7FA0`.
It checks current rc1 EDU discovery and the PIA's data-register selection first,
then saves the entry LED value. It restores that value before its final debugger
stop, both after completion and after Ctrl-C. It does not change CRA or DDRA.
On a bare SXB it prints `E` and returns without accessing the EDU PIA.
Here "entry value" means the value sampled by the application after launch;
the monitor can set its own LED status during launch and return.

The 31 EDU sequences are:

| No. | Pattern | No. | Pattern |
| --- | --- | --- | --- |
| 1 | Walking one | 17 | Split chase |
| 2 | Walking zero | 18 | Outer bounce |
| 3 | Reverse one | 19 | Gray ramp |
| 4 | Reverse zero | 20 | Binary ramp |
| 5 | Wigwag | 21 | Mirrored binary |
| 6 | Checkerboard | 22 | Alternating fill |
| 7 | All blink | 23 | Alternating drain |
| 8 | Fill left | 24 | Paired blink |
| 9 | Drain left | 25 | Nibble count |
| 10 | Fill right | 26 | Center pulse |
| 11 | Drain right | 27 | Edge pulse |
| 12 | Expand pairs | 28 | Comet |
| 13 | Contract pairs | 29 | Reverse comet |
| 14 | Two-dot chase | 30 | Sparkle |
| 15 | Three-dot chase | 31 | Crossfade halves |
| 16 | Four-dot chase | | |

Each sequence has eight frames. Pattern numbers print in hexadecimal: `01–08`
for SXB, `01–1F` for EDU. The exact frame tables are in the source, with decimal
pattern numbers in comments, and [patterns.json](../../examples/source-cycle/patterns.json).
Each program makes one bounded pass. `G 0200` starts another pass.

## ABI and memory contract

Both use ASM 0.5's 65C02 instructions, including on 65C816 **E=1**. They start
with SEI/CLD; the 816 also requires D, DBR and PBR zero on entry. The initialized
`RA`, format 1, 13-call descriptor at `$7E60` is checked before any ABI call.
An invalid descriptor stops in a local loop, without calling an unverified ABI.
The monitor's normal initialized application entry satisfies this check.

| Existing entry | Use |
| --- | --- |
| `$7E76 CHECK_CANCEL` | Carry set requests cleanup; tested once per frame |
| `$7E7C HEX_OUT`, `$7E7F NEWLINE` | Pattern number display |
| `$7E6D PUTC` | EDU-absent message |
| `$7E67 HOLD` | Return to the resident monitor |
| `BRK $01`, `BRK $02` | Ready and finished debugger stops |

There is **no public LED or chip-select ABI** in this release. The two small
hardware adapters are explicitly direct I/O; EDU discovery addresses are a
current-build contract. All monitor calls above are existing public ABI entries.
See [ABI reference](ABI_REFERENCE.md). No speculative v2.1 service is used.

Code, tables and two state bytes live contiguously at `$0200` in application
RAM. No application zero-page scratch is required. Stack and monitor calls use
their existing allocations. The samples do not write RTC, EEPROM, SRAM, flash,
bank PCR, PIA control or data direction. Source `SAVE FLASH` is a separate editor
operation that deliberately programs a new B0 source record.

## Complete edit–save–assemble–debug–edit cycle

Use an idle board only after the hardware admission and installation in the
[test plan](SOURCE_HARDWARE_TEST_PLAN.md). The same steps already execute in
the offline CPU harness. They replace application RAM and the current editor
document. Keep the host source text as the master copy.

1. At `B3>`, enter `ASM`, then `NEW`. Send the complete
   [SXB paste text](../../examples/source-cycle/sxb-cs-patterns.paste.txt),
   including its first `PASTE` and final `.` lines. It contains unnumbered
   source; the editor numbers lines in tens. `LIST` displays it. Alternatively,
   send the [numbered text](../../examples/source-cycle/sxb-cs-patterns.numbered.txt)
   directly at `ASM>` without using PASTE.
2. At `ASM>`, enter `SAVE FLASH CS1`. Expect `Source saved`. This writes a new
   name in erased space within B0:`$8000–$DFFF`. It never erases a
   sector. Confirm the arena has space in the board-specific test allocation
   before this step. Keep every preexisting occupied sector.
3. Enter `ASM`. Expect `OK`. Optionally inspect `DUMP`; `S19` exports executable
   S-record text. SAVE and LOAD use the output buffer as scratch, so **assemble
   after the last SAVE or LOAD** before executing or exporting the program.
4. Enter `QUIT`, then `G 0200`. Expect `DBG>` after `BRK $01`. `R` shows the
   saved registers. Use `U <PC> 04`, substituting the displayed PC, to see the
   ready NOP and following cancellation call. `S` executes the NOP and stops
   again. `C` runs all eight patterns and stops after `BRK $02`. A second `C`
   returns through HOLD to `B3>`. The display goes idle when reads stop.
5. Re-enter `ASM`, then `LOAD FLASH CS1`. Expect `Source loaded`. The loader
   replaces source only after validation; confirm with `YES` if a dirty-document
   prompt appears. `LIST` must reproduce the saved source, independent of the
   previous program's RAM use.
6. Find `BURST_BATCHES = $40` in the numbered text/LIST. Replace that numbered line
   with `BURST_BATCHES = $20` to shorten the dwell. With the supplied source, enter
   `170 BURST_BATCHES = $20`. Save as `SAVE FLASH CS2`; new-name-only
   storage deliberately refuses a second `CS1` with status `$50`.
7. Enter `ASM`, `QUIT`, `G 0200` again. Step the initial NOP with `S`, then `C`
   to observe the shorter dwell and `C` to return. Re-enter ASM and load `CS2`
   to confirm the edit survives. The offline tests compare reassembled bytes
   before and after the edit and verify reloads byte-for-byte.

Repeat with the [EDU paste text](../../examples/source-cycle/edu-led31.paste.txt)
or [EDU numbered text](../../examples/source-cycle/edu-led31.numbered.txt).
Use new names `E311` and `E312`; enter `290 DWELL_OUTER = $80` to change the
supplied `DWELL_OUTER = $FF` definition.
At the finished BRK stop, the entry LED value has already been restored.
During a running display, Ctrl-C requests cleanup at the next frame boundary
and reaches that same finished stop; `C` then returns to the monitor.

`X` at the **ready** stop is safe: no CS reads or LED writes have begun. For the
EDU display, use Ctrl-C while running and then `C`; an arbitrary debugger `X`
in the middle of the LED-writing loop bypasses application cleanup. Do not
assume that debugger abort can execute a program's cleanup routine.

With initialized EDU SRAM, `SAVE SRAM name` and `LOAD SRAM name` provide the
same source workflow and permit same-name replacement. They do not initialize
or format SRAM. Flash works on both configurations and is the tutorial default.
Normal monitor `R` loads executable `SR` images, not these `SF` source records.

## Offline reproduction and evidence

Current firmware and installer checks use [the authoritative build](../../src/current/README.md)
and [shared installer](../../tools/installer/README.md). Sample generation/tests
remain active and default to `BUILD/current`. The older prepare/test/summary
commands below apply in a [restored historical workspace](../../archive/README.md);
their evidence paths describe the original source-store trial.

```text
python -B tools/build_rc1_dev_samples.py
python -B tools/test_rc1_dev_samples.py
python -B tools/test_rc1_dev_samples.py --cpu 65c816-e
python -B tools/prepare_rc1_source_installer.py --out BUILD/rc1-source-installer
python -B tools/test_rc1_source_installer.py
python -B tools/summarize_rc1_source_development.py
```

Installer directories must be fresh; these commands refuse to overwrite them.
Use the existing local Python/CPU dependencies. WDC tools are required for the
source-store firmware build, but these sample tests invoke the actual onboard
assembler in the CPU model. Results and executable exports are under
`BUILD/rc1-dev-samples`; installer evidence is under
`BUILD/rc1-source-installer-tests`. These are peripheral models, not physical
LED observations, electrical timing or hardware interruption qualification.

The long display tests reduce dwell-loop counts while executing the actual
frame tables, I/O, ABI and cleanup instructions. Each configuration also runs
one full original dwell routine without acceleration. Physical visibility and
timing remain observations to record in the hardware plan.

### Results from this preparation

Both CPU profiles, MON A/B and EDU OFF/ON passed: 16 source-development cases,
12 complete display executions, four EDU-absent refusals and 12 unaccelerated
single-dwell checks. All 16 S19 exports match the assembled program bytes;
console pattern numbers were checked. EDU completion and Ctrl-C paths restore
the application entry LED value before the finished stop.

| Program | Emitted RAM image, including tables/state | Packed source |
| --- | --- | --- |
| SXB, eight CS patterns | 201 bytes | 2,514 bytes |
| EDU, 31 LED patterns | 403 bytes | 5,034 bytes |

These tools/examples add **zero firmware ROM bytes**. The source-store prototype
remains unchanged at 2,758 added ROM bytes including its CRC, with 1,433 bytes
free in B1:9. The preserving installer passed 18 checks, including eight linked
install/restore executions across both CPU/EDU profiles and preservation of
newer settings/B0 data on restore.

Receipts: [combined result](../../BUILD/rc1-dev-samples/development-status.json),
[installer result](../../BUILD/rc1-source-installer-tests/report.json),
[installer manifest](../../BUILD/rc1-source-installer/installer-manifest.json).
The executed sample harness is archived under
`BUILD/rc1-dev-samples/qualification-sources`. A subsequent export-filter-only
correction excludes the echoed `S19` command from standalone S-record files;
the summary tool checks that exact correction and validates all exported
records, checksums, entry addresses and bytes. CPU test logic is unchanged.
