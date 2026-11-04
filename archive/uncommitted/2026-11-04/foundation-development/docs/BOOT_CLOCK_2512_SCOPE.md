# 2512 BOOT/CLOCK positive trial: review ready

November 1, 2026 local. **Approved and accepted.** The trial used exactly the
reviewed three erases, nine boot/wear appends and three CLOCK metadata rows.
Original settings/images/EEPROM and owner RAM/ZP are restored;2512 is at REC>,
COM4 free and eligible for RTC collection. See
[the acceptance and remaining limits](BOOT_CLOCK_2512_ACCEPTANCE.md).
The reviewed proposal below is retained as its scope history.
Current firmware is MON A/B g00000010 above frozen Foundation0.3.0 g1
BASE1/PR05. Other boards and published downloads remain untouched.

Concrete private scope:
`output/qualification/2512-BOOT-CLOCK-scope-20261101-r2/review-document.md`.
Its immutable plan pins the existing images, metadata, EEPROM rows, exact journal
forecast and small opaque fixture. The incomplete r1 forecast was retained;
its invalid delay1 was rejected by the native field validator before any
trial execution. Original delay is0A hex; valid temporary delay is0B.

| Write | Limit / purpose | Final state |
| --- | --- | --- |
| B0:9 | Eight programmed fixture bytes, then one cleanup erase | Original4096 FF bytes restored |
| B3:D | One native journal rotation | Counts carried forward;16 old D rows archived on host |
| B3:9 | Three32-byte CLOCK metadata appends, then one restoration erase | Original provider and all14 metadata rows exact |
| Boot/wear journal | Six policy appends, two cleanup reservations, one intent | seq1177,20 rows;11 original C rows retained on chip |
| F / MON A/B / B2 | Zero writes | Exact current images |
| RTC data / EEPROM / SPI SRAM | Zero writes | Time,trim,latch and every history/data byte preserved |

All27 current C/D rows are archived before rotation. Expected erase counts:
B0:9=26, B3:9=21, C/D/E/F=57/38/37/24. Three erases total; no implicit retry
or additional erase allowance. No CPU reset or power cut is included.

BOOT checks: OFF1 and disabled RUN1 refusal, re-enable original B1 entry,
DELAY0B storage/readback and restore0A, temporary B0 entry9000 and positive
RUN0, marker47 at escrowed owner RAM18FF, public HOLD return to MON B, then
restore entry8000. Default B/g10, all enables/entries and delay finish original.

CLOCK checks: accept the observed real EUI54:10:EC:B6:74:3C; write display
offset-05:00; write battery warning/replacement limits13/25 while preserving
the installation date. Verify real committed rows and EUI/OFFSET no-op
repeats. Archive those temporary rows, then restore the original full B3:9
sector. This restores unbound EUI, offset-06:00 and limits12/24 exactly.

**DELAY limitation:** frozen BASE1 uses a fixed three-second startup chooser.
The legacy stored byte must be at least0A hex but does not alter that chooser.
Positive DELAY acceptance therefore means committed field/readback only.
It does not establish an adjustable startup countdown; F is not thawed.

The real PF latch is clear. Preserve the three real outage events and sequence4
tombstone in all128 EEPROM bytes. No SET, changed TRIM, ACK, EEPROM CLEAR/
DELETE or fabricated hardware outage is in this live trial. Latched SET/ACK
and changed-trim fault cases still need isolated RAM work; a no-event/no-op
reply does not close a positive writer gate. Existing installed SET evidence
with a clear PF latch remains separate.

Capture fresh owner RAM0200-66FF/ZP00-DF, preserve every other image/setting,
restore and read back exactly. RTC owns the lease and due window; resume its
unchanged g10 readers after cleanup. No time/trim change means no new baseline,
segment, collector code or other-board admission change. All original history
and calibration data remain. End REC>, COM4 released.
