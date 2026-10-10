# Beta13 CLOCK 1.5 board installation

Recorded 2026-10-07. Board-specific, backup-bound installers verified beta13
generation 22 and CLOCK 1.5 on 2512, 2205 and 2609. Post-restart checks and the
complete evidence audit passed. UTC was not set and trim was not adjusted.

| Board | Port | Result |
| --- | --- | --- |
| 2512, W65C02SXB, no EDU | COM4 | PASS; TIME/EUI/TRIM fail safely without hardware |
| 2205, W65C02SXB, EDU | COM3 | PASS; EUI 54:10:EC:B6:64:AF retained; CONTROL/OSCTRIM 80/00 |
| 2609, W65C816SXB, EDU | COM8 | PASS in emulation; EUI 54:10:EC:B6:64:D3 retained; CONTROL/OSCTRIM 80/00 |

Each complete four-bank backup matched independent repeat reads. Rehearsed
installers refused stale source images and corrupt staged payloads before
mutation, then produced exact expected four-bank images. Eight sectors were
updated: B3 C/8/9/E/B/A and B2 8/9. CLOCK's saved record was committed only
after both sectors verified. Current B0, B1, fixed B3 F and the entire EUI
binding tail remained byte-identical. Settings and erase counts were carried
forward and planned attempts preaccounted.

2609's B0 was already erased before this update, and its configuration/wear
journal contained later valid records than the previous regression archive.
The fresh backup was authoritative for those mutable regions; immutable beta12
firmware still matched its qualified source. B0 remained erased throughout.

2512 and 2205 responded after RESET button presses. 2609 remained silent after
two reset rounds, then responded following the owner-performed power cycle.
The reason for the reset-only silence is not established. Its new outage was
saved and acknowledged by normal boot behavior: slot 3, sequence 7, power down
and up 10-08 03:33 UTC at minute precision. The archived prior EEPROM remains
available locally; only the selected ring slot changed and all other slots,
factory bytes and protection status matched. No explicit CLOCK ACK was issued.
2205's complete ordinary EEPROM and factory/status bytes were unchanged.

Post-update checks covered both monitor slots, service discovery/RAM bounds,
all four RTC caller banks, public I2C reads, TIME and the runnable example,
byte-exact CLOCK restore, CLOCK 1.5 TRIM/status/help, malformed requests,
cancellation, MAINT return and RAM/sector guards. Each EDU confirmed its already
matching zero-trim value: this path performs no register write. Coarse remained
OFF and clocks advanced. A too-short initial sample pair on 2205 was repeated
with a full-second interval; no time setting was used.

Installed and final full-bank readbacks matched each modeled plan exactly.
The audit also verified the original UTC sync/baseline report hashes. Native
816, new physical NMI tests and nonzero trim calibration were not part of this
update. SPI and crypto were not accessed.

Owner-local evidence is under `output/qualification/rtc-trim-2026-10-07`.
Its `acceptance.json` binds the final results. Recheck with
`python tools/audit_v2_trim_hardware.py --root output/qualification/rtc-trim-2026-10-07`.
Raw backups and transcripts remain ignored and are not release artifacts.

User/program RAM remains $0200-$64FF inclusive, even without EDU, while the
service software is installed; $6500-$66FF remains reserved. See
[the trim commands and calibration policy](STR8N_V2_TRIM_EEPROM_POLICY_2026-10-07.md)
and [SPI Phase 1](STR8N_V2_SPI_PHASE1_2026-10-07.md).
