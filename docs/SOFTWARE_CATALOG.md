# STR8-N 1.29 / HIMON / ASM-F2 Software

The v1.33 package retains this software and the identical public console ABI.
Versioned software acceptance below remains the original v1.29 evidence.

This directory is the current, board-facing software shelf for the packaged
STR8-N 1.29, HIMON, and ASM-F2 stack. Files here are maintained applications,
utilities, demonstrations, or advanced tools. Pre-1.29 STR8-N releases and
regression/proof fixtures remain under `ARCHIVE` and are not presented here.

The retained `v1.2` text in R-YORS source history identifies the independent
R-YORS/AP generation, not an old STR8-N release. Packaged display names remove
that historical prefix where it is not part of the program's identity. The
STR8-N public ABI used by these tools is byte-identical between the accepted
1.23 baseline and 1.29.

## Ready-to-load S19 programs

From the HIMON `>` prompt, enter `L`, send one S19, then use the listed `G`
address:

| Program | Run | Purpose |
| --- | --- | --- |
| `GAMES/life-2000.s19` | `G 2000` | Interactive Conway's Life |
| `DEMOS/pia-led-show-2000.s19` | `G 2000` | Eight-LED PIA demonstration |
| `UTILITIES/bank-audit-2000.s19` | `G 2000` | Read-only all-bank CRC/role audit |
| `UTILITIES/bank-dump-2000.s19` | `G 2000` | Read-only sector/AP inspection and dump |

The utility board cards in `UTILITIES` contain the detailed operator flows.

## Maintained onboard ASM-F2 sources

`ASM-SOURCES` contains complete `.a` inputs for `ASM NEW`. Paste one complete
file, finish its documented `SEAL>` flow, and run/package it as directed by
its comments or board card.

The ten maintained sources are:

1. `asm-session-report-ap-2000.a`
2. `bank-audit-2000.a`
3. `bank-crc-all-3000.a`
4. `bank-dump-2000.a`
5. `flash-bank-dump-ap-2000.a`
6. `flash-bank-read-ap-2000.a`
7. `pia-led-show-2000.a`
8. `terminal-answerback-vt100-3000.a`
9. `vt102-exerciser-7000.a`
10. `vt525-exerciser-7000.a`

The terminal sources use the stable raw-console ABI retained by STR8-N 1.29.
Only one `$7000` terminal exerciser should be assembled/run at a time.

## Current-stack rebuild validation

The shelf is rebuilt from the current source stack, not accepted merely because
an older S19 exists. `make -C R-YORS/SRC asm-test` rebuilds and checks HIMON,
ASM-F2, APMAN, AP Store, the map-sensitive sources, host `.asm` counterparts,
and all ten onboard `.a` inputs. The test includes the STR8-N 1.29 public ABI,
current `$F010`/`$0203` read-only bank interface, ASM-F2's 64-symbol/source-line
limits, AP-v2 envelopes, terminal source layouts, and WDC host-assembly checks
where a host counterpart is defined.

`make -C R-YORS/SRC release-files` then rebuilds the four ready-to-load S19
programs and publishes the checked artifacts. The STR8-N `release-package`
target copies those exact files and validates their dense address ranges, S9
entries, package inventory, and SHA-256 list.

## Advanced persistent tools

`ADVANCED/APMAN` contains the APMAN manager, its initial dense Bank-2 carrier,
and the exact AP-v2 envelope. Follow `APMAN_V1_BOARD_TEST.md`; preparation is
destructive and requires its explicit confirmations.

`ADVANCED/AP-STORE` contains the current chain-install and Slice-6 catalog
packages. These are not ordinary HIMON `L` programs; use their documented
package/install workflow.

## Deliberately not on the active shelf

Expression rejection, rollback, opcode coverage, relocation, canary, linker
smoke, and symbol-capacity files are tests or proof fixtures. Historical
Life16/biorhythm and pre-split `$F003` writers are also excluded because they
are not current STR8-N 1.29 operator software.
