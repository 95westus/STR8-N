# MEMORY acceptance summary

The earlier private live trial on one 65C02 board completed backup, reversible
test writes, restoration and an independent fresh-session comparison. Every
supported byte matched its original image. This summary contains no adapter
inventory, port assignment, raw memory capture or private evidence location.

| Region | Bytes | Earlier live result |
| --- | ---: | --- |
| Flash B0-B3, including F and boot/wear journals | 131,072 | Exact original match |
| SPI SRAM array | 131,072 | Exact original match |
| SPI addressing mode | 1 | Original restored |
| MCP79411 user EEPROM 00-7F | 128 | Exact original match |
| CPU owner RAM 0200-66FF | 25,856 | Exact original match |
| Owner zero page 0000-00DF | 224 | Exact original match |
| Total | 288,353 | No differences |

The trial exercised real changes in one erased flash sector, SPI SRAM, its mode,
one EEPROM page, owner zero page and owner RAM. Captures before helper upload
and independent post-restoration reads matched byte for byte and by SHA-256.
F received no write requests. Two flash erase attempts in the trial are recorded
in the retained private receipt; native journal bytes were restored exactly.
There were no resets, power cuts or RTC calendar/control writes.

"Full" means the supported owner ranges above. It excludes CPU registers,
volatile I/O state, helper-reserved RAM/zero page, and non-user EEPROM areas.
The private original evidence is retained separately; it is not distributed.

This is evidence for the earlier memory utility and tested hardware only.
Reproducing matching payload hashes and passing emulator tests do not qualify
new terminal host changes or all boards. The current named component kit still
requires its own live acceptance before installation. No new board test is
claimed by this export preparation.
