# CLOCK software fault acceptance on 2512

November 1, 2026 local. All14 cases passed on2512's physical65C02 using
CPU-RAM device fixtures. No CPU simulator was used. The installed CLOCK
binary supplied the command front end; the normal RTC encoding/SET/ACK,
managed-EEPROM validation/trim and journal logic ran from relocated RAM.
The real device transport was absent from the fixture.

| Case | Observed result |
| --- | --- |
| Latched SET | Archived and read back the committed event before the first RTC attempt; changed the shadow clock to leap day2028-02-29; marked the archived event cleared |
| Latched ACK | Same archive-before-write ordering; cleared the shadow latch without changing calendar/time |
| EEPROM data NACK | SET refused; no RTC write attempt |
| EEPROM commit NACK | ACK refused; no RTC write attempt |
| EEPROM verification mismatch | SET refused; no RTC write attempt |
| EEPROM write protection | ACK refused; no EEPROM or RTC write attempt |
| RTC SET NACK | Verified committed event remained pending; clock/latch unchanged |
| RTC ACK NACK | Verified committed event remained pending; clock/latch unchanged |
| Changed trim and restoration | Control84->80 before OSCTRIM0C->8D; next request restored0C; calendar/latch/stamps unchanged |
| Alarm/square-wave output active | Trim refused before any write |
| Fine-trim write NACK | Failure reported; coarse clear remained applied, fine value remained0C |
| Fine-trim readback mismatch | Failure reported after the shadow value changed; no false success |
| Foreign EEPROM layout | SET refused without a device write |
| No-event ACK | No write and no false positive-writer claim |

Before the first shadow RTC write, the independently captured EEPROM mirror
contained the new event with valid CRC, commit A5 and pending state FF. The
post-commit verification had already occurred. Its raw outage stamps and
pre-SET UTC/quality fields remained exact. The three older committed events
were unchanged. The fourth-slot tombstone was reused with event sequence4.
The injected weekday write cleared the live shadow timestamps, deliberately
testing the need for the prior archive. This is a controlled device response,
not a claim about every physical chip's post-ACK register behavior.

Every intended case avoided the flash-write denial stub and log overflow.
Borrowed discovery bytes and BATCH magic were restored after every fixture.
Two earlier host preparation stops occurred before fixture execution: an
active-A/B admission assumption and an oversized RAM packet. The latter's
borrowed owner RAM/ZP were restored and verified before the corrected trial.
The corrected bootstrap stages its gateway within the existing loader limit;
the already linked RTC/journal logic and installed CLOCK body were reused.

## Preservation and closeout

Real EEPROM00-7F, live outage registers and trim/control matched before/after.
The real clock kept running. The entire B3 bank matched exactly, including F,
MON images, settings, metadata and boot/wear history. No flash erase/program,
journal append, RTC/trim/ACK, EEPROM, SPI PROGRAM/WORKSPACE write, reset or
power cut occurred. Fresh owner RAM0200-66FF and ZP00-DF were restored and
read back exactly. Other boards and published downloads were untouched.

Boot default B/g10 and seq1177/20 journal rows remain unchanged;
C/D/E/F counts remain57/38/37/24. Final REC>, COM4 released and all restore/
worker guards clear. RTC host eligibility passed without another board
connection. No collector, baseline or sampling segment was changed.

Receipt and sealed software closeout, relative to the workspace root:

- `output/qualification/2512-CLOCK-fault-RAM-20261101-r3/report.json`
- `output/qualification/2512-CLOCK-fault-RAM-20261101-r3/completion.json`

## Limits and shipping work

This closes the isolated software-decision/order cases. It does not claim
physical latched-event SET/ACK, changed hardware trim, electrical fault
handling, endurance, or816 execution. Existing successful physical SET
receipts with PWRFAIL clear remain separate evidence. Real history and
calibration were deliberately preserved for RTC collection.

FLASH's full-source DELAY help is corrected to identify0A-FF as a stored legacy
byte and Foundation's chooser as fixed3s. The later
[provenance check](FLASH_HELP_PROVENANCE.md) established that the installed
compact builder replaces this entire paragraph and already omits the false
tick claim. Its transformed sources are identical; no help-only build or
install is needed. Foundation remains frozen.
Physical terminal-key, extracted-kit and targeted held816 acceptance remain
separate. Factory restoration and ASM/DBG retain their explicit scope.
