# STR8-N v1.32 reset-source board test — 2026-09-07

STR8-N v1.32 passed guarded installation and reset-source integration on the
W65C02SXB/EDU at COM4, 115200 baud. The test covered the new leading CR/LF,
`RST H` and `RST S`, the cooperating HIMON reset client, and the simplified
HIMON cold/warm RAM-policy output.

## Exact artifacts

| Artifact | SHA-256 |
| --- | --- |
| Bank-3 `$F000-$FFFF` BIN | `5447E9F197ED8FE7AB90FEEEBF25318FBBDCA721612356050F600CDE2268425E` |
| Guarded top updater S19 | `B961C3CAC05511E4390F1A8A6887BDC840535297FACD39197D57F2C9BA92A266` |
| Production worker S19 | `CBD477AD62A0FF7FC14DE22F3575C7B05834C973A5DF622A6678DEF6C4577713` |
| HIMON Bank-3 C-E install S19 | `DB3CB9EF4B9FF3BACD3FE2D24B17720875B03685C45539F4B66D78F9560274F5` |

The linked resident is `$F000-$FD45` (3,398 bytes), with ten erased bytes at
`$FD46-$FD4F` before the fixed 608-byte worker at `$FD50-$FFAF`. The public
selector prefix remains `$0200-$0228`; the public ABI hash is
`599CBC6E5EBF7C68DD7680FDB298C4F12A967A084D4188B00631EDC47317CEFF`.

## Guarded update

The v1.32 updater copied live Bank-3 sector F to protected B1:F and reported
`BACKUP VERIFIED`, with source/destination receipt sum `$4137`. Only after the
exact `STR8-N 1.32` confirmation did it erase and rewrite B3:F. It reported
`STR8-N 1.32 VERIFIED; RESET`; that cooperating restart then printed a leading
CR/LF, `RST S`, and the v1.32 identity before timing out through `BOOT WARM`.

## Reset-source and HIMON integration

An unmarked `G F000` entry printed the leading CR/LF and `RST H`. The current
HIMON C-E image was then installed through STR8-N's guarded `I B3 C-E` path;
STR8-N reported `OK`, and `W` entered `HIMON V 00.0907(0637)` with
`BOOT WARM`.

HIMON's confirmed `STR8` command identified its wrapper at `$C15A`, committed
the one-shot `RS` record, and produced `RST S`. From the STR8 prompt, `C`
entered the destructive path and printed `BOOT COLD` followed directly by the
HIMON banner; the retired `RAM ZERO OK` line was absent.

A final receive-only capture used TX=0 with DTR and RTS deasserted. The operator
pressed the physical RESET button. The board emitted `RST H`, `STR8-N 1.32`,
and the selector, then timed out through `BOOT WARM` to the same HIMON image.
This closes the physical-reset classification gate independently of the
unmarked software-entry check.

The compact transcript is
[STR8N_V1_32_RESET_SOURCE_BOARD_TRANSCRIPT_2026-09-07.txt](STR8N_V1_32_RESET_SOURCE_BOARD_TRANSCRIPT_2026-09-07.txt).
The owner-local append-only session JSONL is
`BUILD/v1.32/local/reset-source-board-session.jsonl`, SHA-256
`34B9CFC9C03468A4924F1E60CDBA138B6DDD69C12B705FE631F77C9DE3DF94B6`.
The independent receive-only physical-reset JSONL is
`BUILD/v1.32/local/reset-source-physical-reset.jsonl`, SHA-256
`7816C1EC816D4865A87DE9D9AF370EE46F549322C1A699E2F0F13074F7BEA819`.

Factory WDCMONv2 migration remains a separate acceptance gate; this test used
the already installed STR8-N/HIMON system and guarded in-place update paths.
