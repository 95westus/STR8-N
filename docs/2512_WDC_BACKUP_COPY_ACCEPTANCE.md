# 2512 separate WDC backup-copy acceptance: passed

October 30, 2026, 65C02 / FT245. The approved [four-erase scope](2512_WDC_BACKUP_COPY_SCOPE.md)
passed using the existing frozen BASE1 OPAQUE RAM writer. The
[sanitized receipt](../monitors/validation/2512-wdc-backup-copy.json) records
the device evidence and independent preservation audit. This qualifies the
separate archived-WDC copy/readback/restoration workflow. It does **not** qualify
the new NFM2 engine, full WDC-source factory migration or WDC boot from B0.

## Observed sequence

1. Native MON Dump captured fresh owner RAM 0200–66FF and ZP 00–DF twice before
   any helper upload. Both captures agreed. BASE1 READBACK then independently
   read all four banks twice and matched the sealed source hashes.
2. The preserved original 32768-byte 2512 WDC bank was saved as a standalone
   private host backup. Its two differing sectors were copied to B0:8/9. Each
   native wear reservation committed before its erase. Sector readback and
   complete bank hashes passed after each operation.
3. The complete B0 copy was independently read and compared byte-for-byte with
   the standalone host backup, SHA-256
   `8c73a910ee02d86d25039e5189d379e80d45117a4fcbb2ae509f146d1aaa3616`.
4. Original B0:8/9 contents were restored using two separately reserved erases.
   Two complete final read passes matched every expected bank. Original B0/B1/B2
   were exact; B3 differed only by the four admitted journal appends.
5. Original owner RAM/ZP were restored and read back through BASE1, then checked
   again through native MON Dump. The board finished at MON B / B3>, COM4
   released, with no pending flash or RAM restoration.

All 20 prior journal records remain byte-for-byte at their original addresses:
C000–C300 and D000–DF00. New records at C400/C500/C600/C700 have sequences
1034–1037. Saved default B, MON generation 00000008, bank entries/enables,
unknown-history mask and all other latest-record fields remain unchanged.

## Final tracked accounting

| Item | Before | Final |
| --- | ---: | ---: |
| B0:8 count | 6 | 8 |
| B0:9 count | 12 | 14 |
| C / D / E / F counts | 53 / 33 / 28 / 24 | Unchanged |
| Committed records | 20 | 24 |
| Latest sequence | 1033 | 1037 |

Counts are decimal conservative erase-attempt reservations, not lifetime wear
measurements. Exactly four target erases were requested and verified. There
were **zero F writes, C/D erases, MON A/B/E rewrites, resets or power cuts**.
No firmware build or CPU simulation ran. Frozen F and published downloads
remain unchanged; all source commits stay local.

## Host preparation interruptions

Earlier attempts stopped at the shared lease or restricted-shell COM4 access
before any board command. The first direct-device run completed its captures
but stopped on a duplicate host backup filename before any erase. Its finally
path restored and verified owner RAM/ZP. The filename was corrected and a fresh
run performed the four approved erases. The original failed reports remain
unchanged; no extra erases were spent on those interruptions.

## Preserved services and limits

The existing `MON-G8-NATIVE-TIME` admission remains valid. The RTC sampler,
settings, trim, power-fail flags, schedule and baselines were not changed.
No SPI SRAM command/data write or WORKSPACE write occurred; no full-SRAM
comparison is claimed. Other boards remained outside this trial.

The copied source was an archived original vendor bank, not a fresh live WDC
debugger capture. WDC execution/reset from B0, NFM2 factory migration, 65C816
and interruption remain separate gates. Original B0 is restored; this case
does not leave the temporary full WDC copy installed.

Private live evidence:
`C:\SRC\STR8-N\output\qualification\2512-WDC-backup-copy-trial-20261030-r5`.

Original B0 final SHA-256:
`5b72e8041c01f1fab145f8926a01b2be02ba807c654525bc04eed450a48c245f`.

Final B3 SHA-256, including retained history and four new reservations:
`b442b0b9dbee952992cf16a07504665b9a220d54d4d7b46fc852a6b1118caa3e`.
