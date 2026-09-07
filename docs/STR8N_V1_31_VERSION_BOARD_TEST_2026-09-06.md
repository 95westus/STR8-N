# STR8-N v1.31 version-promotion board test — 2026-09-06

> **Historical candidate:** the current v1.31 image adds private `$07`/`$0B`
> I/O activity. Its exact artifact and board proof are in the
> [activity report](LED_IO_ACTIVITY_BOARD_TEST_2026-09-06.md).

STR8-N v1.31 passed its guarded in-place update and focused board smoke test
on the W65C02SXB/EDU at COM4, 115200 baud. The promotion changes the displayed
version from 1.30 to 1.31. No feature, address, layout, ABI, worker, or LED
instruction changed.

## Exact artifacts

| Artifact | SHA-256 |
| --- | --- |
| Bank-3 `$F000-$FFFF` BIN | `3E1F63035C3CA63C73830AD628D89B8C5B591F6768CA3E80788097928A65C015` |
| Guarded top updater S19 | `8F2F6F243EB1C4F573664B7802192E7424CF796077532477AB7E190F1221FF74` |
| Production worker S19 | `CBD477AD62A0FF7FC14DE22F3575C7B05834C973A5DF622A6678DEF6C4577713` |

The linked resident remains `$F000-$FD0E` (3,343 bytes), the erased margin
remains `$FD0F-$FD4F` (65 bytes), and the 608-byte worker remains stored at
`$FD50-$FFAF`. The public selector prefix remains `$0200-$0228`.

A byte-for-byte comparison against the board-proven v1.30 host-presence top
found exactly one difference: file offset `$C6D`, CPU address `$FC6D`, changed
from ASCII `0` (`$30`) to ASCII `1` (`$31`). The regression checker permits
that exact transition and continues to compare every other resident-data
byte. The public ABI file and worker hashes are unchanged.

## Board result

Physical RESET first exited the temporary PWE# RAM probe used by the preceding
test. The operator observed `$00` after normal warm HIMON handoff.

The v1.31 updater copied the live Bank-3 sector F to protected B1:F and
reported `BACKUP VERIFIED`, with source/destination receipt sum `$4998`. Only
after the exact `STR8-N 1.31` confirmation did it erase Bank 3 sector F. It
then reported:

```text
STR8-N 1.31
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 1.31 VERIFIED; RESET
```

RESET displayed `STR8-N 1.31`, allowed the selector to time out through
`BOOT WARM`, and reached HIMON `00.0902(1707)`. Entering `$F000` again and
selecting `S` displayed `STR8-N 1.31`; the operator confirmed `$43` at the
installed `STR8-N>` prompt. Command `W` then completed the normal warm HIMON
handoff.

The preceding v1.30
[host-presence report](LED_HOST_PRESENCE_BOARD_TEST_2026-09-06.md) directly
proved PWE# high/low transitions `$21 → $43` on this board. Because the v1.31
top differs only at the identity digit, that hardware predicate and the
minimal `$00`/`$01`/`$F0` ownership proof apply unchanged. Factory WDCMONv2
migration remains a separate, operator-deferred acceptance gate.

The compact retained transcript is
[STR8N_V1_31_VERSION_BOARD_TRANSCRIPT_2026-09-06.txt](STR8N_V1_31_VERSION_BOARD_TRANSCRIPT_2026-09-06.txt).
The owner-local append-only JSONL is
`BUILD/v1.31/local/version-bump-board-session.jsonl`, SHA-256
`7B1170350B16020C64B58991A610B80DED3EFEB4FD0B855BF4D31BDB7B11FC88`.
