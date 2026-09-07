# STR8-N v1.31 I/O activity LED board test — 2026-09-06

The private STR8-N I/O activity slice passed on the W65C02SXB/EDU at COM4,
115200 baud. The installed image publishes `$07` for STR8-owned receive
activity and `$0B` for STR8-owned transmit activity. Public `CHARIN`,
`CHAROUT`, `CHAR_READY`, and public record parsing remain LED-neutral.

HIMON and ASM were not changed by this slice. STR8-N publishes `$00` before
handing control to them, so their future activity states must be implemented
and measured in their own private I/O paths.

## Exact artifacts

| Artifact | SHA-256 |
| --- | --- |
| Bank-3 `$F000-$FFFF` BIN | `9CA8573C48F7FEE34FA9A83A7D61672DCA77ECC2CA91A611C76EFADDE54E6C2E` |
| Guarded top updater S19 | `45A936A7C7DDD8B27325158E686A911F0E03949A6501406667D1A5158C515B75` |
| Production worker S19 | `CBD477AD62A0FF7FC14DE22F3575C7B05834C973A5DF622A6678DEF6C4577713` |
| Local nine-byte TX probe S19 | `E79770A1640E29B393FEB8951F52547A0068591EEED2DF8582A56046C20B2026` |

The linked resident occupies `$F000-$FD27` (3,368 bytes). The worker occupies
`$0200-$045F` and is stored at `$FD50-$FFAF` (608 bytes), leaving 40 erased
bytes at `$FD28-$FD4F`. The activity slice adds 25 resident bytes to the
board-accepted host-presence image. The layout checker now deliberately
preserves a 32-byte minimum and still rejects overlap. The public selector
prefix remains `$0200-$0228`.

## Host qualification

`make all` passed. The resident regression checks prove that:

- the public raw console routines remain byte-identical to the frozen image;
- the public record entry bypasses the private receive wrapper;
- the line editor preserves the input byte while writing `$07`;
- private S19 receive calls publish `$07` before entering the common parser;
- the private output wrapper preserves A, writes `$0B`, and tail-calls the
  unchanged raw CHAROUT routine;
- all compact message calls use the correct `$FC` or `$FD` page after growth;
- the 608-byte worker, directory, configuration, and vectors are unchanged;
  and
- all 1,560 linked range-parser cases still pass.

The canonical and promoted STR8-iN/65 top images are byte-identical. The
console ABI probe artifact is unchanged at SHA-256
`51FBB33CE2B9397EFE28BD63ED8B97B93E3A36B9E27C31F5EA04C8DBE06ACDD4`.

## Guarded installation

The updater was loaded through the installed STR8-N `L` command. It verified
the B1:F backup, required `BACKUP B1F`, reported target checksum `$4999`, and
required `STR8-N 1.31` before mutation. It then reported:

```text
STR8-N 1.31
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 1.31 VERIFIED; RESET
```

The automatic reset printed the expected STR8-N 1.31 identity. A selector
timing retry was needed after the first `S` arrived after the live selector
window; re-entering `$F000` and sending `S` on the exact prompt reached the
installed `STR8-N>` shell.

## RX activity result

At the normal `$43` command wait, the host sent printable `X` without Enter.
STR8-N accepted and echoed the byte, then waited for the rest of the line. The
operator observed `$07`. Because line echo deliberately uses raw CHAROUT, it
did not overwrite the receive state; `$07` remained latched until Enter.

## TX activity result

A local RAM-only probe was loaded through `L`. Its nine executable bytes were:

```text
78 D8 A9 54 20 F2 FB 80 FE
```

This exact-image probe executes `SEI`, `CLD`, loads ASCII `T`, calls the
installed private output wrapper at `$FBF2`, and loops. The wrapper emitted
`T`; the operator observed `$0B` remaining latched. The probe does not write
flash. A physical RESET returns from the deliberate RAM loop.

The compact retained serial record is
[LED_IO_ACTIVITY_BOARD_TRANSCRIPT_2026-09-06.txt](LED_IO_ACTIVITY_BOARD_TRANSCRIPT_2026-09-06.txt).
The complete append-only owner-local JSONL remains at
`BUILD/v1.31/local/io-activity-board-session.jsonl` and is excluded from
published release artifacts.
