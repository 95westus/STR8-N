# Qualification scope

The current firmware bytes reproduce the qualified named-component reference:
34 payloads, including frozen F. All 32 non-F inputs rebuild from source and
are compared by size and SHA-256 before use. The current source/Git/archive
workflow has passed 68 CPU-model tests on 65C02 and 65C816 emulation, 29 host
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
