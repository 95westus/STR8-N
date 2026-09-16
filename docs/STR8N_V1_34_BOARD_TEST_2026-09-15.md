# STR8-N v1.34 board test — 2026-09-15

Status: COM4 passes for guarded top update, exact live readback, physical and
software reset, cold/warm HIMON handoff, ASM-F2 entry/return, console ABI,
BRK dispatch, and J3. This is partial hardware qualification; the remaining
tests below are not implied by these results.

## Image identity and preservation

| Artifact | SHA-256 |
| --- | --- |
| Canonical v1.34 top BIN | `9538D97854BA9D5D76143CBA0FEDB3B2E7CE18F977CE89557406E63404026CB7` |
| v1.34 RAM top updater S19 | `247B7213A2E3CC970620C5E731BA3057895525CA5BE77803D7E7ED65B306412D` |
| Pre-update live top readback | `5DDDC4D0EC70AFA5D154CF1FFCCAB8C2D70BF72B21CD49F3B99C4C9FD55099A0` |
| Post-update and final live top readback | `D9A418127C870E5DFDB535B20EDFAE276124D86AAB4616B3B28581392BADACB0` |
| Raw received serial bytes | `16E3BD932A6F74CC2EE325929278DAB242D4CA0D6BE8D1BAF08D1455D92E76D2` |

The pre-update code, configuration, and vectors matched the frozen canonical
v1.33 image exactly. Only its live directory differed. Before programming,
the complete live top was saved off-board and the RAM updater verified its
fresh B1:F backup, reporting sum `$16D2`.

The normal updater preserved all 64 directory bytes at `$FFB0-$FFEF`.
All 4,096 bytes of each post-update readback match the canonical v1.34 image
with exactly that saved directory substituted. The live hash therefore
differs from the distributed empty-directory BIN. The final readback after
all tests is identical to the first post-update readback. Hardware-vector
bytes are `CF F0 00 F0 E3 F0`: NMI `$F0CF`, RESET `$F000`, IRQ/BRK `$F0E3`.

## Observed results

- The existing resident loaded the checked updater through `L`. It reported
  `BACKUP B1:F; TARGET B3:F`, `BACKUP VERIFIED`, and
  `STR8-N 1.34 VERIFIED; RESET` after the two explicit confirmations.
- Update completion produced `RST S`, the immediate 1.34 banner, and a
  timeout warm handoff to `HIMON V 00.0910(2121)`.
- Explicit reset-selector `C` and `W` both returned to HIMON successfully.
- `ASM` entered `ASM-F2 00.0910(1709)`; `.` returned with `ASM BYE`.
- HIMON's `STR8` command produced `RST S`; selector `S` entered the resident.
- The rebuilt console probe loaded through `L` and passed query/init,
  raw lowercase `$71` input and `$0D` Enter, CHAROUT, CHARIN, and
  CHAR_READY empty/ready/register/carry checks. Actual BRK dispatch passed.
  The probe verified handoff LED `$00` and application LED `$A5` ownership
  through raw I/O and BRK. These are register checks, not visual observations.
- The operator pressed physical RESET while receive-only capture was active.
  It produced `RST H`, the 1.34 banner, and timeout warm HIMON recovery.
- Resident `J3` reported `J B3`, entered RESET, and recovered warm HIMON.
  This exercises the relocated stored-worker selector copy on the board.

The board was left at the HIMON prompt. COM4 was closed after the final dump.

## Evidence and limits

The [receive transcript](STR8N_V1_34_BOARD_TRANSCRIPT_2026-09-15.txt) retains
all three complete top-sector dumps; only line endings are normalized and
non-ASCII bytes escaped. Append-only TX/RX events and binary readbacks are
retained locally under `BUILD/v1.34/board/`.

Not repeated: power-cycle startup, actual NMI and IRQ dispatch, Bank 0-2
guest boots, resident flash installation, the optimized worker's destructive
program/erase probe, visual LED timing, update failure/recovery injection,
directory refresh, or full factory migration. The top updater uses its own
RAM flash routines; its success does not qualify the optimized resident
worker's program/erase operations. Existing host differential results remain
separate evidence for those paths. Historical reports retain their original
version and hash scope.

## Subsequent session

The separate [follow-up report](STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md)
records power-cycle startup, physical NMI, timer IRQ, and optimized-worker
flash testing performed after this session. This report and its transcript
retain their original scope.
