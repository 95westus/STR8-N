# 2512 current-g4 AP/02 app launch: passed

October 30, 2026. **65C02 / FT245**, installed MON B g8 and services g4.
[Approved one-erase scope](2512_AP02_G4_SCOPE_REVIEW.md),
[public receipt](../monitors/validation/2512-ap02-g4-positive.json).

The existing 120-byte AP/02 example (88-byte body, PR05/CPU02, entry 9020)
ran directly from B0:9. Fresh native owner RAM/ZP double escrow and complete
bank double captures admitted the still-FF sector before programming. Fifteen
native !M commands installed the unsealed example without an erase. Header
CRC refusal passed; sealing 901C-901D then left payload CRC refusal intact.
Sealing 901E-901F admitted APPS inventory and `APP APPDEMO`. Help redisplayed;
bare Q returned through public HOLD to MON B g8/CPU02. Native Dump proved
the example/return path left original owner RAM0200-66FF and ZP00-DF intact.

The single approved B0:9 erase restored its original 4096 FF bytes. The
native reservation at **CC00/seq1042** changed its tracked count **14 to 15**.
All **28 old raw journal records** remain at their original locations; final
**29 valid records**. C/D/E/F remain **53/33/28/24**. Two ordinary append pages
remain CD00/CE00; CF00 remains reserved. Counts represent tracked attempts,
not lifetime totals. No C/D erase, F/MON/services/tool replacement, other image
write, boot-setting change, reset or power cut occurred.

Complete final banks were independently captured twice and matched the plan.
Original B0, including FLASH at 8 and WDC at F, is restored exactly. Original
default B/generation 8, mask 0F, entries 8000 and other policy/history fields
carry forward. Fresh owner RAM/ZP was restored, read back, then compared
again through the native monitor. Final MON B/B3>, COM4 released, no pending
restoration. APPDEMO was temporary and is no longer installed.

The unchanged native V/TIME sampler passed its RTC/NTP continuity burst and
exact serial trace audit. Existing clock settings, source/profile, historical
samples, baselines and schedule are retained. Native TIME does not freshly
measure trim or read full PF history; observed PF state is recorded without
acknowledgement. There were no SRAM/PROGRAM/WORKSPACE or EEPROM writes, no
clock SET/trim/PF command, no firmware build or CPU simulation. Other boards
were untouched; F, published downloads and release assets are unchanged.

This closes the current-g4 positive AP/02 case on 2512, complementing the
2609/65C816-emulation acceptance. A bounded soak remains the next proposed
checkpoint and is not started by this closeout. Private captures and owner
data remain under `output/qualification/2512-AP02-g4-*` in the parent project.
