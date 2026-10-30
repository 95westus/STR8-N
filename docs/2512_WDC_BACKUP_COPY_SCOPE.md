# 2512 separate WDC backup-copy trial

Prepared October 30, 2026. The owner approved flashing and selected:
**“Keep F golden; prepare a separate 2512 backup-copy trial.”**
This case preserves the installed Foundation and all current journal records.
It is not a fresh-WDC factory migration or acceptance of the new NFM2 engine.
No power cut, F write, other-board access, push or download change is included.

## Exact bounded writes

| Step | Target | Data | Journal append |
| --- | --- | --- | --- |
| 1 | B0:8000 | Original preserved WDC bank's first sector | C400 / sequence 1034 |
| 2 | B0:9000 | Original preserved WDC bank's second sector | C500 / sequence 1035 |
| 3 | B0:8000 | Restore current owner FLASH sector exactly | C600 / sequence 1036 |
| 4 | B0:9000 | Restore current owner sector exactly | C700 / sequence 1037 |

**Four erases total: two each at B0:8 and B0:9.** No C/D erase, F write,
MON A/B/E rewrite or boot-setting change. The native OPAQUE RAM writer commits
each wear reservation before its target erase. No new firmware build is needed.
All 20 existing raw journal records remain at their original on-chip addresses.
The final journal has 24 records. Native append capacity was checked for these
four operations; the trial refuses any unexpected source or postimage.

Tracked B0:8 count goes **6 → 8**, B0:9 **12 → 14**. C/D/E/F stay **53/33/28/24**.
These are conservative tracked attempts, not lifetime totals. The original B
default, MON generation 00000008, bank enables/entries, unknown-history mask and
other saved fields remain unchanged. Restoration must retain the four new
reservations; reinstalling older counters is not a rollback option.

## Source and preservation

Use the exact retained **2512 pre-FLASH 65C02 WDC bank**, 32768 bytes:

`8c73a910ee02d86d25039e5189d379e80d45117a4fcbb2ae509f146d1aaa3616`.

This differs from the previously reviewed whole B3 migration-fixture bank:
that fixture also contained project monitor/tools sectors. The clean original
WDC bank differs from current B0 only at 8/9; the other six sectors, including
its F818 reset-vector sector, already match. This reduces this separate trial
to two copy erases and two restoration erases.

Freshly capture owner RAM 0200–66FF and ZP 00–DF twice through native MON Dump
before loading a helper. Independently read all four complete flash banks twice
and match the reviewed source hashes before any flash payload. Keep durable
private backups of the original banks, owner RAM/ZP and both overwritten sectors.

After copy, compare all 32768 B0 bytes with the standalone private host WDC
backup. Then restore original B0, independently compare all final banks twice,
and restore/read back owner RAM/ZP. Finish at MON B / B3>, COM4 released. The
shared serial lease yields to RTC collection; do not change its sampler, clock,
trim, power-fail flags, schedule or baseline. No SPI SRAM command or data write
is included; no full-SRAM comparison is claimed.

## Qualification boundary

This exercises the preserving host-to-B0 copy/readback/restoration workflow using
the existing frozen BASE1 OPAQUE RAM writer. The source is an archived lawful
vendor bank, not a fresh WDC debugger capture. Do not claim new NFM2 execution,
full WDC-source migration, WDC boot from B0, 65C816 acceptance or interruption
recovery from this case. Those gates remain separate.

Private sealed plan:
`C:\SRC\STR8-N\output\qualification\2512-WDC-backup-copy-scope-20261030-r1\plan.json`

Plan SHA-256:
`0952de2b671bca6bdad4caded9a2fbf6b48d05c30a8eb5d5b3210bd6d0b7803a`.

The live driver must perform fresh admission, never replay old captures as live
evidence. Any transfer/postimage failure stops without automatic flash retry;
retain the logs and originals for inspection and mark pending restoration.

## Preparation checkpoint

The plan and guarded driver are ready. The first execution attempt on October
30 stopped at the shared serial lease **before opening COM4**. No serial log,
board command, RAM helper upload, journal append or erase occurred. Its original
failed report is retained; a separate preparation receipt records that owner RAM
was untouched. Another operation's lease was not interrupted or bypassed.
Live copy/restoration acceptance remains pending. The existing flashing approval
is retained; a later attempt needs a fresh private output folder and full live
source admission, not a replay of assumed board state.
