# Storage timings: 2609, beta17, nominal 8 MHz

Measurements use board 2609 in W65C816 emulation with EDU. The resident
W65C02S-compatible SPI code and installed flash worker are unchanged. Three
repeats per SRAM size/pattern and three full flash program/erase pairs were
measured. These are storage-transfer timings, excluding terminal payload upload
and saved-program/workspace administration.

| Operation | Payload | Time |
| --- | ---: | ---: |
| Flash sector erase | 4,096 bytes | approximately 16 ms |
| Flash fresh-sector program and verify | 4,096 bytes | approximately 160–176 ms |
| SPI SRAM WRITE | 1 byte | 0.628–0.633 ms |
| SPI SRAM WRITE | 32 bytes | 2.80–2.96 ms |
| SPI SRAM WRITE | 64 bytes | 5.05–5.37 ms |
| SPI SRAM WRITE | 256 bytes | 20.15–21.43 ms |
| SPI SRAM WRITE | 1,024 bytes | 80.58–85.70 ms |
| SPI SRAM WRITE | 4,096 bytes | 322.31–342.79 ms |

SRAM ranges span $00/$55/$FF payloads; their bit-loop paths differ slightly.
For $55, medians were 0.6300, 2.8814, 5.2054, 20.7899, 83.1369 and 332.5481 ms.
The resident service accepts 64 bytes per request, so 256/1024/4096-byte writes
use 4/16/64 calls. Each call includes dispatch, argument/ownership checks,
command/address bytes, sequential-mode handling and restoration. Readback
verification is performed afterward and is excluded from the timing. WORK's
metadata validation, handles, verified writes and saved-record journaling add
further overhead and are not represented by these low-level WRITE figures.

## Timer and model method

A RAM-only probe borrows idle VIA Timer 2 with interrupts masked. It restores
ACR and the idle timer count after each run. An atomic high/low/high counter
read and modulo-65536 accumulation sample between each bounded SRAM call.
The linked cycle model bounds the largest warm call at 42,299 cycles, safely
below a 65,536-cycle sampling interval. No GPIO output or interrupt handler is
added for timing. The result includes small probe bookkeeping costs.

The counter measures CPU clocks; milliseconds are cycles/8000 at nominal 8 MHz.
The oscillator was not independently calibrated. The independently modeled
driver, without probe bookkeeping, gives roughly 0.57 ms for one byte,
4.96–5.28 ms for 64 bytes, and 317.76–338.24 ms for 4096 bytes at that clock.
Thus the real timer measurements agree with the linked-driver model.

Timer 2's continued decrement after underflow is documented in the
[WDC W65C22 datasheet, section 2.9](https://www.westerndesigncenter.com/wdc/documentation/w65c22.pdf).

## Flash method and precision limit

Flash measurements retain the unmodified polling/verification worker. They
bracket G command submission and a completion marker before HOLD output, using
a host monotonic clock. Matching no-op probes measure command/parser/USB
overhead, including the same staging fill for programming. The median baseline
was about 160 ms. That baseline is subtracted from each flash observation.

The three adjusted sector-program observations were 159.92, 159.48 and 175.93 ms;
adjusted erases were 15.99, 15.82 and 16.00 ms. USB latency produces visible
roughly 16-ms quantization. These flash results are coarse operational estimates,
not precise chip-only timings or worst-case guarantees. The 4-KiB writer programs
all bytes as $55 into an erased sector and verifies the sector; its separate erase
and durable wear-counter update are excluded. The
[Microchip SST39SF010A datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/MPD/ProductDocuments/DataSheets/SST39SF010A-SST39SF020A-SST39SF040-Data-Sheet-DS20005022.pdf)
specifies a 25-ms maximum internal sector erase; software and transport timings
are separate from that device specification.

## Preservation and evidence

B2:D000–DFFF was read back and verified empty before use. It was programmed,
verified and erased three times, then the entire B2 image matched its pre-test
image. Each erase was durably counted; the B2:D wear counter advanced by three.
Configuration and all other counters remained the same. Firmware sectors,
monitor slots, identity slots and recovery F remained byte-identical.

The SRAM window $18000–$18FFF was backed up, tested, restored and read back
exactly. No formatting, claim, resize, RTC SET, trim, CLOCK ACK or EEPROM
administration was performed. Raw board backups and serial logs remain ignored
under `output/qualification/storage-timing-2026-10-08-2609-run2`; `report.json`
records individual timer samples, host baselines, observations and preservation.
The earlier attempt stopped at the monitor's protected-I/O read refusal before
writing any test data.

Builders/model probes are `build_v2_storage_timing.py`,
`test_v2_storage_timing.py` and `measure_v2_storage_cycles.py` under tools.
`measure_v2_storage_hardware.py` performs the preserving hardware test and checks
board identity, idle timer ownership, scratch-sector contents and restoration.
Running it again performs three additional recorded scratch-sector erases.
