# STR8-N v2-alpha15 lean LED board test — 2026-09-23

Status: accepted on board 2205 over COM3. Alpha15 removes the resident
per-character and console-wait LED animation introduced in alpha14. The
resident retains `$01` while the monitor owns the display, `$F0` during flash
mutation and verification, and `$00` at application handoff. The RAM-only
guarded updater retains its visible wait, receive, transmit, and flash states.

The resident shrank from 3840 to 3810 bytes; its last byte is `$FEE1` and
`V2_END` is `$FEE2`. This restores 30 bytes before the enforced erased
`$FF00-$FFDF` expansion reserve. The RAM worker remains 541 bytes.

## Live update

Alpha14 loaded the 12 KiB updater at `$2000-$4FFF`. `G 2000` accepted the
installed V2 signature, copied and verified B3:F into temporary B2:F backup,
and installed alpha15 after both exact confirmations:

```text
STR8-N 2.0a15 B3 INSTALL
BACKUP B2:F; TARGET B3:F
TYPE BACKUP B2F> BACKUP B2F
BACKUP VERIFIED
SAFE PHY $17000-$17FFF; TARGET PHY $1F000-$1FFFF; SUM=$9D66
TYPE STR8-N 2.0a15> STR8-N 2.0A15
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 2.0a15 VERIFIED; RESET

STR8-N 2.0a15 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

The temporary B2:F backup was erased through V2 `I F000 FFFF`. Readback
showed all `$FF` at B2 `$8000`, `$E000`, and `$F000`. B3 readback showed the
`53 4E 02 00` signature at `$F000` and all `$FF` at `$FF00`.

`J1` reached the preserved STR8-N 1.35 and HIMON payload. HIMON `STR8`, its
confirmation, selector `S`, and `J3` returned to the alpha15 B3 prompt. The
final roles remain B0 WDCMONv2, B1 R-YORS/HIMON with STR8-N 1.35, B2 fully
erased scratch, and B3 alpha15 with `$8000-$EFFF` erased.

## Artifacts

| Artifact | SHA-256 |
| --- | --- |
| Clean B3 full-bank BIN | `5128A082EFC6508B90FBE54BF54A9A0092751017E0B3578DAE62A3660531D39A` |
| Guarded B3 top updater S19 | `2C525671188069DBC24A870388605BAA31DC64EF72824FDA983AA0AF39818332` |
| B2:F all-FF cleanup S19 | `8672CE88FCA2642A18807D87F0F860971C63BE82485A2F8313F8AA4BA8BCC7CE` |
| Ignored COM3 JSONL transcript | `E8F5207C08F056CFE60752ACE3953D9F8BB926CC966D0CB204E7A794B8827912` |

`make v2-check` passed all build, boot, console, ACIA, migration, monitor,
loader, flash, configuration, timing, and interrupt-probe suites. The generic
v1.35 top updater retained SHA-256
`F9C18E424A8689C0F1C1CADDDCB585852EEF2F3A77E46A7F58928CD7AD30E846`.
