# Qualification scope

## Published combined RC3 prerelease

The combined RC3 flash payloads passed readback comparison on boards 2205,
2512, 2604 and 2609. The published final RC3 kit retains all 44 BIN/S19/S29/S-record
payloads from unified RC3 byte for byte, including the frozen 4 KiB F.
Its PC RTC sampler passed live collection on both supported CPU modes.
Confirmed SET passed on 65C02 from Stage 2 and on 65C816 emulation from
Stage 3, using identical RTC tool and sampler bytes.

The packaged TRIM routine passed controlled −12 → −11 → −12 on 65C02
and −14 → −13 → −14 on 65C816 emulation, with the original trim and owner
RAM/zero page restored. Both used explicit owner-selected test targets.
Calibration-driven CLI decisions retain their measurement gates. The
[combined RC3 release record](RC3_RELEASE.md) gives archive identities,
the SET accuracy limit, published downloads and the completed package procedure.
The final offline review verified source identity, manifests, checksums, links,
launcher help and nine RTC host tests. Published archives remain unchanged.

## Earlier source-consolidation checkpoint

At this earlier checkpoint, firmware reproduced the qualified named-component
reference of 34 payloads, including frozen F. All 32 non-F inputs rebuilt from
source and were compared by size and SHA-256 before use. The source/Git/archive
workflow passed 68 CPU-model tests on 65C02 and 65C816 emulation, 29 host
unit tests and a hidden fake-worker Tk smoke. Repository consolidation changes
source organization/docs and history; it does not add a physical board trial.

Earlier named component bytes have scoped live acceptance. The earlier full
MEMORY backup/restore trial on one 65C02 board is summarized in
MEMORY_ACCEPTANCE_SUMMARY.md, including supported owner RAM/zero-page ranges,
flash, SPI SRAM/mode and user EEPROM. It is not a claim to capture CPU registers,
volatile I/O, helper-reserved storage or every board/CPU combination.

The optional-profile terminal host changes are tested offline and have no new
physical-board acceptance. Historical releases retain their original CPU,
layout, profile, generation and qualification limits; do not assume a historical
full-system image is interchangeable with BASE1 or a current RAM/AP component.

No new flash/erase/reset, serial-port connection or F assembly is part of the
repository merge. F remains SHA-256
8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1.

The optional [Microchess and OSI BASIC examples](EXAMPLES.md) have separate
65C02/65C816-emulation model reports tied to their exact payloads. These cover
actual DEV ASM source assembly, gameplay/AP02 entry, and BASIC's public-ABI
adapter with reserved-RAM checks. Their Foundation endpoints are modeled;
physical serial/installation, arbitrary source edits and native 816 execution
are not qualified by those reports. Example images are never auto-installed.
