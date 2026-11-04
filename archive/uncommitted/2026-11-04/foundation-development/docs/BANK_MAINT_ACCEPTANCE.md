# BANK MAINT acceptance: 2512 and2609

October31,2026. **Passed and left installed** on2512/W65C02SXB and
2609/W65C816SXB in emulation. Both ports are released at B3>.

Enter `R MAINT` for **STR8-N BANK MAINT2.4 / BASE1 PR05 g1**, `BM>`.
The [operator manual](BANK_MAINT_BASE1.md) lists commands and examples.

## Live operation

Both boards ran the same sealed12 KB MAINT image and the same WB2 gC/services
gB/native-loader revision3 images. Each passed:

- Actual R MAINT launch from board flash, help, VERSION and quiet Q.
- Board NAME query/cancel in RAM, then confirmed NAME CLEAR and restoration
  of its original board name on the installed app.
- TABLE/T compact native and legacy rows, with the committed/CRC distinction.
- RAM copy, overlap handling, compare match/mismatch and cancellation.
- Independent4096-byte editor: read, dump, patch, fill, create and CRC;
  buffer contents survived maps, VERSION and TABLE.
- Positive RAM-to-flash copy, flash/RAM comparison, full-sector editor W,
  fresh-byte patch and erase through the accounted worker path.
- Exact B0:9 restoration: FF on2512, original occupied WDC bytes on2609.
- Read-only BATCH through R MAINT, editor/CRC and Q; existing CLOCK, FLASH,
  workbench/PROGRAM Table, APPS, maps, wear and dynamic STATUS routes.
- Independent image/history/settings readback and full fresh owner RAM/ZP
  restoration/readback. No claim is made for untested legacy binary execution.

## Reviewed budget met

The [approved scope](BANK_MAINT_2512_2609_SCOPE.md) allowed17 erases total.
Actual final wear counts and sequences match it exactly:

| Board | Image / fixture erases | Wear / BN appends | Old rows retained | Final sequence / rows | C / D / F counts |
| --- | --- | --- | ---: | --- | --- |
| 2512 | 7 / 1 | 8 / 2 | 20 | 1105 / 28 | 55 / 35 / 24 |
| 2609 | 7 / 2 | 9 / 2 | 22 | 1061 / 31 | 79 / 48 / 31 |

All old boot/wear rows remain byte-for-byte on chip. Names2512/2609, -05:00
offsets, saved B/gC defaults, masks, entries and unknown-prior-wear masks are
preserved. No F write, C/D erase, power cut, RTC-setting/history write or
SRAM-data/WORKSPACE write occurred. 2205 and2604 were not accessed.
The previous HELLO0200/UCHESS B1:8-A records were archived on the host and
replaced by MAINT as explicitly approved. B1:B-F stays exact.

Both B1 banks now hash to
`5b6d99ade31a79fe362e5ff7869f89bf9b8e89fcf89190b25523ffcd2b1b63b8`;
both B2 banks hash to
`54879c0fbe70ab0da018f8839ab4462c589be79cc016010cfbd9b575c28f979d`.
B3 differs in each board's settings/history. Frozen F remains
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.

The existing RTC/NTP driver code, baseline and cadence remain unchanged;
post-install campaign preflight admits both boards. No fresh NTP sample is
claimed by that read-only admission check.

## Evidence and remaining limits

Private composite receipt:
`C:\SRC\STR8-N\output\qualification\BANK-MAINT-closeout-20261031-r1\final-receipt.json`.
Per-board installed receipts are under
`2512-BANK-MAINT-installed-20261031-r1` and
`2609-BANK-MAINT-installed-20261031-r1` in output/qualification.
RAM trials and exact old-sector archives remain beside these receipts.

Native MAINT linked once (8,957 bytes;3,297 sealed-slot free bytes), WB2 once
and services once. The services build's post-link path-reporting error was
repaired without reassembling its already-emitted images; the manifest records
that recovery. No CPU simulation, repeat build or full-board backup campaign
was used. Published Foundation/preview downloads and release kit are unchanged.

Old X named flash/PROGRAM transfer, a new per-sector naming format, factory
restoration and ASM/DBG are outside this checkpoint. Positive CLOCK setting
qualification remains separate. 2609 has filled its current ordinary journal
append pages; its next mutating operation needs native peer rotation, which
was not included in this trial. Existing old history is still intact now.
