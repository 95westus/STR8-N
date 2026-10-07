# Beta12 / CLOCK 1.4 hardware installation

The owner authorized flashing all three boards. All eight-sector installations
completed device verification. Restarted monitors were observed on all three;
live qualification and the final evidence audit passed.

| Board | Port | Hardware | Installation |
| --- | --- | --- | --- |
| 2512 | COM4 | W65C02SXB, no EDU | PASS; EUI/time unavailable; acceptance refused |
| 2205 | COM3 | W65C02SXB, EDU | PASS; remembered EUI `54:10:EC:B6:64:AF` |
| 2609 | COM8 | W65C816SXB, EDU | PASS; remembered EUI `54:10:EC:B6:64:D3` |

Owner-local evidence is under `output/qualification/rtc-binding-2026-10-07`.
Complete four-bank backups matched independent repeats. Fresh read-only RTC and
EEPROM archives matched repeated EEPROM reads and the known factory identities.
No SET or ACK was issued during preparation, and no EEPROM data was written.

Exact-source models executed each installer, checked final bank images and
CLOCK's final commit, and refused stale preimages or corrupt payloads before
mutation. Plans retain current startup settings, preferred slot and erase counts;
the eight planned erases were preaccounted in configuration metadata.

Changed sectors are B3 C, 8, 9, E, B, A and B2 8, 9. Already-installed MAINT 1.7
matches the candidate and is retained, so B1 is unchanged. B0 and fixed B3 F are
also unchanged. CLOCK is published only after its complete two-sector image
verifies. Initial identity storage is empty; prior beta8 has no binding records.
The compatible-tail merge is used in preparing the replacement journal sector.

Post-restart checks verified both slots, RAM discovery and bounds, monitor TIME,
the read-only RAM example, CLOCK EUI/history/status, maintenance-sector refusal,
and complete flash readbacks. On each EDU board, initial identity acceptance was
checked against its archived factory EUI and explicitly confirmed through CLOCK.
Cancellation wrote nothing and matching reacceptance returned without another
confirmation. 2512 refused unavailable identity acceptance. Exact final bank
images matched the planned installation plus one independently reconstructed
32-byte identity record on each EDU board. B0/B1/F stayed byte-identical.

Both EDU ordinary EEPROM arrays matched their pre-update archives exactly;
factory bytes and protection status also matched. All existing outage records
were retained. UTC and control/trim were unchanged, and the original drift
baseline report hashes passed the final audit. The read-only example ran on all
three boards; 2609 remains qualified in 816 emulation, not native RTC calling.
Installer `$F0` LEDs reflected its flash-operation state while halted in RAM;
this was identified in the source before restart.

The requested [post-update drift check](STR8N_V2_RTC_DRIFT_POST_BETA12_2026-10-07.md)
used fresh NTP references without SET, ACK or trim adjustment. Hardware evidence
is bound in the evidence root's `acceptance.json`; the timing comparison is
under `output/qualification/rtc-drift-2026-10-07-post-beta12`.

With service software installed, user RAM remains `$0200-$64FF`, inclusive, even
without EDU; `$6500-$66FF` remains reserved. Missing/rejected optional software
on a cold boot can permit RAM through `$66FF`. Active reservations survive later
validation failures until RESET. The date/time format remains unchanged.
