# Native TIME live trim: 2512 / 2609

October31,2026. **Approved, installed and accepted on both boards.** Each
passed A/B live TIME, MAINT return, same-B default startup, exact B3 readback
and owner RAM/ZP restoration. The shared collector passed nine live NTP/TIME
samples per board and is registered on the unchanged hourly schedule, retaining
all249 earlier campaign points, events and baselines. The older16 D rows on2609
were archived and replaced exactly as approved. See [operator notes](MON_TIME_TRIM.md).
Private final receipt: output/qualification/MON-trim-closeout-20261031-r1/final-receipt.json.
The exact approved version of this scope is retained as approved-scope.md beside
its pinned review/approval JSON. The remaining text describes the pre-install plan.

MON gC TIME reads calendar registers00-06. Its campaign readers consequently
carry the last verified trim/control from the baseline and mark trim unverified.
The gD candidate reads registers00-08 and then seconds again, bounded to three
coherence attempts. It reports fresh OSCTRIM and control with every TIME sample:

```text
RTCC: 2026-10-31 23:35:55 flags $28 trim $0C ctrl $80
```

OSCTRIM is signed magnitude, not two's complement. The new shared collector
decodes $0C as-12 and $0E as-14; bit7 denotes positive correction. Control bit2
is coarse mode. The collector verifies both registers across all nine reads,
records the observed values, and refuses a TIME response lacking them. It
does not substitute the baseline. Coarse-mode correction recommendations stay
withheld rather than applying the fine-mode step size.

The MON calendar/raw layout used by STATUS stays fixed. The two extra bytes
use the existing private snapshot buffer. TIME and all status reads leave
RTC data, trim, control, power-fail flags, EEPROM history and SRAM unchanged;
I2C register-pointer writes and temporary VIA bus ownership are necessary reads.

## Build and live RAM evidence

One gD build emitted A, B and RAM variants. Each ROM body is3957 bytes,
one byte smaller than gC, inside its unchanged4096-byte slot. Two cancellation
messages share their data string to make room. Foundation F was not rebuilt.

Both RAM trials passed real TIME advancement, trim/control raw-byte readback,
agreement with independent existing CLOCK STATUS/TRIM, unchanged B3/F/history
and complete owner RAM/ZP restoration. Observed values:

| Board | Trim steps | OSCTRIM | Control | Coarse |
| --- | ---: | --- | --- | --- |
| 2512 | -12 | 0C | 80 | OFF |
| 2609 | -14 | 0E | 80 | OFF |

The first2512 host script expected the wrong CLOCK text label and stopped
before running the candidate; RAM/ZP was restored. Only its parser was fixed.
No firmware rebuild or CPU simulation followed. Qualification receipts are
under output/qualification/2512-MON-trim-RAM-20261031-r2 and
2609-MON-trim-RAM-20261031-r1.

## Exact proposed flash scope

Replace **B3:A and B3:B only** with identical-command MON gD, then append
CONFIG C B once to retain default B with its new generation binding. No boot
bank enable, entry, timezone/name or RTC-setting change. F, utilities and all
B0/B1/B2 images stay exact. Preserve and read back fresh owner RAM/ZP.

| Board | Image erases | Journal-sector erases | Total | Journal appends | Final seq / rows | Final C / D / F counts |
| --- | ---: | --- | ---: | ---: | --- | --- |
| 2512 | 2 (A/B) | 0 | 2 | 3 | 1108 / 31 | 55 / 35 / 24 |
| 2609 | 2 (A/B) | 1 (D) | 3 | 4 | 1065 / 19 | 79 / 49 / 31 |

Total: **five erases, zero F writes, zero C erases, seven appended records**.
Final A/B tracked counts:2512=45/52,2609=54/57. All other counts stay exact
except the stated2609 D increment48->49. No power cuts or retry erases.

2512 has exactly the three needed ordinary C pages: CC00/seq1106 and
CD00/seq1107 wear reservations, then CE00/seq1108 B-generation binding.
All28 existing records remain byte-for-byte on chip.

**2609 history decision:** its current C has no ordinary append room and D
contains16 old valid records. Native rotation first commits CF00/seq1062 with
both the A erase and D erase counts reserved, erases D once, and commits
D000/seq1063. B's reservation is D100/seq1064; binding is D200/seq1065.
All31 old rows are archived on the host before any erase. The16 old D rows
are replaced on chip; the15 old C rows remain byte-for-byte, every wear count
and the latest boot policy carry forward. This needs explicit approval under
the preserve-history requirement. No C rotation or F operation is included.

## Acceptance and collection

After independent readback, test TIME's raw trim/control on both A and B,
R MAINT/Q with unchanged UI/1, and the retained software default B/gD.
Restore owner RAM/ZP and release COM4/COM8. Qualify the new read-only native
TIME/NTP collector on each board, then register it for the existing schedule.
Keep all historical points, events, baselines, cadence and old reader code.
Only new samples receive trim_verified=true; old observations are not relabelled.
The collector never sets time/trim, acknowledges PF or writes firmware.

2205 and2604 are excluded. F remains STR8N-F0.3.0 g1 / BASE1 / PR05,
SHA256 `8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
Published downloads and release kit stay unchanged.

Exact per-board image hashes, journal forecast and full private original/target
B3 files are in
`C:\SRC\STR8-N\output\qualification\MON-trim-scope-20261031-r1\review.json`.
Recheck current B3 against its reviewed hash before execution. Unexpected
preimages, erase failures or a scope increase stop for review.
