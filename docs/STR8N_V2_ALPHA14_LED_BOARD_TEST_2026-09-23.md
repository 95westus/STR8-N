# STR8-N v2-alpha14 LED board test — 2026-09-23

Status: guarded V2-to-V2 update, final bank layout, B1 handoff, and the live
LED-state code paths passed on board 2205 over COM3. The operator recorded the
physical LEDs; the serial transcript cannot independently judge their visual
appearance.

Alpha14 adds monitor-owned EDU LED states while leaving public character I/O
LED-neutral:

| Value | Meaning |
| --- | --- |
| `$01` | Monitor running or flash operation safely complete |
| `$43` | Waiting for FT245 input |
| `$41` | Waiting for ACIA input |
| `$07` | Input received |
| `$0B` | Output activity |
| `$F0` | Flash mutation or required verification active |
| `$00` | Display released to an application |

The image ends at `$FEFF`; `$FF00-$FFDF` remains erased. The public `PUTC`,
`GETC`, and `RAW_POLL` entries bypass the activity wrappers so an application
retains its LED display.

## Live update

Alpha13's `L` command loaded the 12 KiB updater at `$2000-$4FFF` and reported
`Entry 2000` without executing it. `G 2000` started the updater and proved its
new V2 signature preflight:

```text
STR8-N 2.0a14 B3 INSTALL
BACKUP B2:F; TARGET B3:F
TYPE BACKUP B2F> BACKUP B2F
BACKUP VERIFIED
SAFE PHY $17000-$17FFF; TARGET PHY $1F000-$1FFFF; SUM=$AE17
TYPE STR8-N 2.0a14> STR8-N 2.0A14
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 2.0a14 VERIFIED; RESET

STR8-N 2.0a14 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

The updater copied and verified alpha13 B3:F in B2:F before replacing B3:F.
Its flash unlock path asserted `$F0`, and successful verification restored
`$01` before output and reset.

## Final layout and handoff

After alpha14 booted, V2 loaded an all-`FF` image into B2:F. The erase and
verification completed with `Done`. Direct reads then showed:

```text
B2 $8000: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
B2 $E000: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
B2 $F000: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
B3 $F000: 53 4E 02 00 4C 51 F0 4C 9B F0 4C 53 FA 4C C0 FA
B3 $FF00: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
```

`J1` entered the preserved STR8-N 1.35 image and
`HIMON V 00.0915(2324)`. Confirmed HIMON `STR8`, selector `S`, and `J3`
returned to:

```text
STR8-N 2.0a14 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

The final bank roles remain B0 WDCMONv2, B1 R-YORS/HIMON with STR8-N 1.35,
B2 completely erased scratch, and B3 alpha14 in `$F000-$FFFF` with
`$8000-$EFFF` erased.

## Artifacts

| Artifact | SHA-256 |
| --- | --- |
| Clean B3 full-bank BIN | `21D888BFC02355BC32869BA716B640AC5AC5A92B425AAAA80F47BEAF47056574` |
| Guarded B3 top updater S19 | `173046897D3CD2395C186A702D338AED78A759E12CE5243B402E5F45B5CCD5E1` |
| B2:F all-FF cleanup S19 | `8672CE88FCA2642A18807D87F0F860971C63BE82485A2F8313F8AA4BA8BCC7CE` |
| Ignored COM3 JSONL transcript | `14780365DB312CFCF57B9FCCE1CE6388EA8BAADD548A3BF1D5C87CBC1B9826B3` |

`make v2-check` passed all build, boot, console, ACIA, migration, monitor,
loader, flash, configuration, timing, and interrupt-probe suites. The generic
v1.35 top updater retained SHA-256
`F9C18E424A8689C0F1C1CADDDCB585852EEF2F3A77E46A7F58928CD7AD30E846`.
