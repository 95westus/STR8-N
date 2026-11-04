# 2512 interrupted C/D recovery: B3 scope review

The owner approved this exact scope and the
[2512 hardware trial passed](2512_CD_RECOVERY_ACCEPTANCE.md). The original
preparation and authorization are retained in the private evidence. The tables
below describe the reviewed budget and checkpoints; actual results have a
separate acceptance receipt. F remained golden, images/boot settings/owner RAM
were preserved, and 2205 and the release kit remained excluded.

## Exact persistent footprint

| Region | Proposed action |
| --- | --- |
| B3:F000-FFFF | No erase or programming. Exact frozen 4096-byte BASE1 remains the recovery anchor. |
| B3:C000-CFFF | Journal record writes and exactly **one sector erase**, after a committed D-sector intent. |
| B3:D000-DFFF | Journal record writes and exactly **one sector erase**, after a committed C-sector intent. |
| B0-B2 and B3:8/9/A/B/E | No writes; independent byte-for-byte preservation checks. |
| Owner RAM 0200-66FF / ZP 00-DF | Borrowed by RAM tools, then restored from the prior verified original escrow and read back. |

Total: **two sector erases, one each in C and D; zero F erases/writes; six
controlled USB power cycles**. No chip removal or external programming.
All planned cuts occur at verified chip-idle checkpoints, not during a flash
pulse. This does not claim electrical brownout coverage.

F remains STR8N-F 0.3.0 g00000001 / BASE1 / PR05, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
No F build, production CONFIG change, CPU model or release-kit update is used.

## Starting point and boot policy

The reference is the last independently verified
[2512 WDC checkpoint](2512_WDC_MIGRATION_ACCEPTANCE.md): three valid records,
latest C100 sequence 965, default B, mask 0F, entries all 8000, tracked decimal
counts C=49, D=29, F=24. Original records are C000/964, C100/965 and D000/963.
These are prior captures, not a fresh device read. Execution must first read
all four banks twice and match the exact reviewed source bytes.

Before the first cut, append temporary default S at C200/966, preserving mask,
entries, configuration and counts. Verify it independently. Every power return
then goes to golden F and REC>, even if the chooser has already timed out.
The final C300/996 record restores the original B policy and pinned generation.
The incompatible legacy MON is never executed.

## Six interruption cases

| Cut | Exact checkpoint | Record selected after restart | Admitted recovery |
| --- | --- | --- | --- |
| 1 | C300 candidate 967: first 128 bytes programmed, commit FF | C200/966 | Inspect exact partial bytes, finish missing bytes, verify and commit last |
| 2 | C400 candidate 968: all 255 payload bytes verified, commit FF | C300/967 | Recompare payload and complete commit only |
| 3 | C500/969 committed and verified, before completion acknowledgement | C500/969 | Recognize exact committed record; no programming, append or erase |
| 4 | Native rotation wrote CF00/979 intent and erased/verified D blank | CF00/979 | Restore original D000/963, then publish current snapshot at D100/980 |
| 5 | D200 candidate 981: first 128 bytes programmed, commit FF | D100/980 | Inspect exact partial bytes, finish missing bytes, verify and commit last |
| 6 | Native rotation wrote DF00/994 intent and erased/verified C blank | DF00/994 | Restore original C000/964 and C100/965, then publish current snapshot at C200/995 |

Bounded same-policy snapshots fill C600-CE00 and D300-DE00 so the actual native
rotation path reaches its reserved final-page intents. Each rotation commits
and verifies its erase reservation before reclaiming the peer. The RAM lab
copy pauses only after native erase/blank verification. Ordinary CONFIG and F
are unchanged. All intermediate records are privately archived before reuse.

## Inspected recovery admission

The RAM JCR1 tool is a separate source-bound lab component loaded with REC> L.
Its sealed image/parameters, exact F fingerprint, all four source-bank guards,
BF/B5 chip, selected committed record and target preimage must pass before Y.
Its only write destinations are C/D. The default unrendered template refuses.

The general host classifier continues refusing damaged/ambiguous journals.
There is no force switch, blank initialization or broad damaged-history bypass.
For these known uncommitted pages, the repair packet admits only the exact
captured preimage and intended valid record. Every byte must already match
the intended value or be FF. An unexpected programmed bit, committed conflict,
wrong count, source change or wrong selected record stops without writes/retry.
Identical bytes are skipped; all 255 bytes are compared before commit 00.

After a peer erase, only the three original snapshot fingerprints may be
reinstated at their original addresses. A newer surviving intent remains
authoritative while those older rows are restored. The next current snapshot
keeps its reserved erase count, so restoring history does not roll counters or
boot policy backward. Both RAM-tool completion and cut-ready return LEDs to 01.

## Required final result

| Item | Reference | Expected final |
| --- | --- | --- |
| Latest sequence | 965 | 996 (000003E4 hex) |
| Valid records on chip | 3 | 20; all three originals retained at original addresses |
| C / D / F counts, decimal | 49 / 29 / 24 | 50 / 30 / 24 |
| Other 29 counters / unknown-history mask | Original | Unchanged |
| Default / mask / entries / application config / pinned generation | Original B / 0F / all 8000 | Restored exactly |
| Owner images and frozen F | Original | Byte-for-byte original |
| Owner RAM / ZP | Previously verified original escrow | Restored and independently read back |
| Final context | REC>, COM4 released | REC>, COM4 released, no pending restoration |

Old intermediate rotation snapshots may be reclaimed normally; their complete
raw bytes remain in private captures. The original three record bytes must be
present at the final original addresses. New erase reservations are retained.

Original RAM authority is the pre-helper escrow repeatedly restored and last
verified in the WDC case. Raw L overwrites its own prefix, so this procedure
does not claim a fresh original-prefix read. No intervening owner program has
been reported. Stop if that provenance is no longer applicable.

Private 19-phase byte-exact previews, packets and driver are under:
`C:\SRC\STR8-N\output\qualification\2512-cd-recovery-20261028-r1`.
The preview remains reference-only until fresh live admission. The final JCR1
template SHA-256 is
`b92853d16b34c98c339a4f87396cfd740b230b53e112af0d50a8b6c3e4e5c0a5`.
The named chip-idle interruption cases passed on 65C02/FT245. This does not
qualify every damaged layout, flash pulse, CPU or adapter. The transport stop
after cycle 2, read-only inspection and bounded host continuation are documented
in the acceptance report. No flash operation was retried, and no extra erase
or counter rollback occurred.
