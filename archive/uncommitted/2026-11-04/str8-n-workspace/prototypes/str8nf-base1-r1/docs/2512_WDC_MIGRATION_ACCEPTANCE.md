# 2512 WDC-to-BASE1 migration acceptance: passed

October 28, 2026 local time (October 29 UTC), 65C02 / FT245 / Windows.
The owner explicitly approved the expanded current-chip trial: six sector
erases, two each in B3:F/D/C, including temporary WDC fixture preparation.
No other board was accessed; 2205 remained excluded. No F rebuild, CPU/flash
simulation, programmer whole-chip erase or deliberate F/C/D interruption ran.

The [sanitized receipt](../validation/2512-wdc-migration-acceptance.json) binds
the actual serial logs, source hashes, captures and restoration evidence.
Private evidence and original chip/RAM backups remain at:
`C:\SRC\STR8-N\output\qualification\2512-closeout-20261028-r1\wdc-current-live`.
The [reviewed B3 scope](2512_WDC_B3_SCOPE_REVIEW.md) describes the exact writes.

## Observed hardware sequence

1. Two fresh full-bank captures matched the reviewed post-B0-test checkpoint.
   The RAM-only NFX1 setup engine passed its own image/plan, all-bank source
   and BF/B5 chip checks. It committed the DD00 erase reservation before the
   first payload, then programmed and verified the declared WDC F/D/C fixture.
2. Physical RESET reached the real WDC debugger, identity
   `535842322c010000c8000000` (SXB2). The unchanged read-only archiver captured
   all four banks twice. Every byte matched the reviewed fixture. Another
   physical RESET reconnected to WDC and independently rechecked all of B3.
3. A fresh source-bound first-journal plan imported the tracked setup counts.
   The unchanged public NFM1 engine was uploaded through the WDC RAM protocol
   and independently read back before execution. Its image/plan/all-bank/chip
   checks passed. It programmed and verified frozen BASE1 F, then D and C,
   with journal commits last. All final bank guards passed.
4. Physical RESET displayed `STR8N-F 0.3.0 g00000001`, `BASE1 / PR05`, and
   reached REC>. The public callback independently read all four banks and
   restored/read back the WDC pre-archiver RAM/ZP snapshot.
5. A separate source-bound RAM helper appended the exact original 2512 policy
   at C100, retaining current counters. It did not execute incompatible MON.
   Two further complete bank reads matched the exact expected final images.
   Original pretrial owner RAM 0200-66FF and ZP 00-DF were restored and read
   back byte-for-byte. Final REC>, COM4 released, no pending restoration.

The WDC pre-archiver snapshot was captured after temporary fixture setup;
it is distinct from the earlier original 2512 owner escrow. Both restoration
steps were verified separately. The final board contains the original 2512
owner RAM, not the setup engine or WDC working snapshot.

## Actual final accounting

Counts below are decimal tracked erase reservations, not lifetime totals.

| Item | Before trial | Final |
| --- | --- | --- |
| Journal sequence | 961 | 965 |
| Committed records on chip | 29 old records | 3 new records: D000/963, C000/964, C100/965 |
| Old raw journal | Present on chip | Full original chip archive retained on host |
| B3:C / D / F counts | 47 / 27 / 22 | 49 / 29 / 24 |
| B0:9 count | 9 | 9; all other counts unchanged |
| Prior-history unknown mask | FFFFFFFF | FFFFFFFF |
| Default / enable mask / entries | B / 0F / all 8000 | Restored exactly |
| Configuration and pinned MON generation | Original | Restored exactly |
| B0-B2 and B3:8/9/A/B/E | Original | Byte-for-byte original |
| F source and release binary | Frozen BASE1, 4096 bytes | Unchanged; exact same bytes installed again |

This authorized conversion replaced the old C/D records on chip. Their full
raw bytes remain privately archived; latest tracked counts were imported
without regression, with all six new erase reservations included. It is not
a byte-for-byte restoration of the old journal sectors or a counter rollback.

F SHA-256:
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
Every frozen input still matches F_FREEZE.json. Existing release kit ZIPs and
assets were independently checked against their receipt and remain unchanged.
Source acceptance notes/receipts were updated; no publication occurred.

## Qualification limits

This closes the 2512/65C02/FT245 WDC migration happy path for the declared
non-SNBT lab C/D fixture, including first-journal provisioning, verbose device
progress, physical vendor/BASE1 resets and final preservation. It does not
qualify every vendor-occupied layout, 65C816, ACIA, electrical/EDU/SPI/RTC
effects, deliberate interrupted F/C/D recovery, or the separate live entry
after programmer-installed F. Legacy retained MON/FLASH execution remains
unqualified. Catch S on later resets when recovery is intended.

The [earlier B0 power-loss case](2512_B0_POWERCUT_ACCEPTANCE.md) remains a
separate pass at a chip-idle incomplete-image checkpoint. The leading FF in
the raw BASE1 reset capture is also present in the earlier baseline evidence;
its cause remains unestablished.
