# EDU RTC read test

Build and check:

```text
python tools/build_v2_rtc_test.py
python tools/test_v2_rtc_test.py
```

Under STR8-N v2 alpha24, use `L` to load
`BUILD/v2-rtc-test/str8n-v2-rtc-test-2000.s19`, then `G 2000`.
The 1,104-byte program occupies `$2000-$244F` and returns to the monitor.
It requires the initialized v2 RAM ABI. On an 816, enter through STR8-N
in emulation mode with D, DBR and PBR zero.

Example output (illustrative, not a board capture):

```text
DATE YY-MM-DD 26-09-30  TIME 14:35:09
DATE YY-MM-DD 26-09-30  TIME 14:35:10
EDU detected (RTC valid and advancing)
```

Detection requires ACK, valid BCD/calendar fields, ST and OSCRUN set, and
an observed advance of exactly one second, including 59-to-00 rollover.
The year is the chip's two-digit year. Leap-year validation uses its
two-digit four-year cycle. A responding RTC is evidence of the expected
EDU configuration, not a unique identification of the whole daughterboard;
disconnect external I2C devices for this check.

An invalid or stopped RTC reports `EDU detection inconclusive`. I2C error
`01` means bus not idle, `02` means NACK, and `03` means SCL was held low.
No clock-stretch wait is attempted. All bus routines are bounded; the
advance check makes at most 80 additional reads, with a fixed delay of
roughly 41 ms per read at 8 MHz. This is a diagnostic, not a calibrated timer.

The probe reads RTC registers `$00-$06` through VIA1 PA0/PA7. It sends the
RTC address-pointer byte but never writes register data or sets the clock.
It uses local RAM and the existing console ABI. It restores VIA DDRA and
the original driven pin levels; hidden output-latch bits on pins that were
inputs cannot be recovered by reading the VIA. Run with the I2C bus idle
and without another interrupt/NMI handler using these pins.

## Board checks still required

1. With EDU absent, run once and require an inconclusive result and a prompt.
2. With power off, attach the matching EDU. Validate/set its date/time with
   the shipped EDU firmware first, as agreed in TASKS.md.
3. Boot STR8-N, load the probe, and require correct date/time, an advancing
   second, and the detection line. Repeat on each SXB CPU family.
4. Retain the serial transcript and build/test receipts. Physical timing,
   816 execution, and presence detection remain unqualified until these runs.

The host suite executes the assembled 65C02 image. It injects positive RTC
snapshots and checks read sequencing at byte boundaries; absent/stuck-bus
cases execute the bit-bang routines. It does not model positive electrical
I2C timing. This RAM test leaves alpha24 F/E binaries and ABI unchanged.
The optional E-sector HAL/startup integration remains a later step.

## Sources

Adapted from the Codex-authored R-YORS `edu-rtc-read-7000.a` reader.
Its older board evidence showed a readable but stopped RTC; that evidence
does not qualify this v2 port.

- [Microchip MCP79410/11/12 data sheet](https://ww1.microchip.com/downloads/en/devicedoc/20002266h.pdf)
- [WDC W65C816EDU pin mapping](https://www.wdc65xx.com/wdc/documentation/W65C816EDU.pdf)
- [WDC W65C02EDU pin mapping](https://www.wdc65xx.com/wdc/documentation/W65C02EDU.pdf)
