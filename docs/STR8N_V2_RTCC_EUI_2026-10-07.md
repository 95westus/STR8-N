# Read-only EUI at boot and in CLOCK — unflashed beta11

The owner requested the full MCP79411 factory EUI-48 at boot and in CLOCK.
The local beta11 / CLOCK 1.3 candidate displays it as a separate boot line:

```text
STR8-N 2.0b11 B3 65C816
ABI 65C02 | 816E | 816N-VEC
RTCC: EUI 54:10:EC:B6:64:D3
UTC 2026-10-07 14:51:21
B3>
```

The identity line appears on boot, including when RTC time is stopped, invalid
or unreadable. Ordinary TIME commands and monitor/program returns do not repeat
it. When the identity is unavailable or all-zero/all-FF, the line is
`RTCC: EUI unavailable`. No board identity is invented from a cached value.

CLOCK 1.3 displays the same line on entry and with `S` / `STATUS`. Its new
read-only `EUI` command reads the identity again without requiring usable UTC.
`R CLOCK` remains the program name; no `R RTCC` alias exists. TIME stays compact.

The protected factory identity is at EEPROM F2–F7, six bytes in stored order.
The first two bytes at F0–F1 are not part of EUI-48. The saved inventories show:

| Board | Factory EUI-48 |
| --- | --- |
| 2205 | `54:10:EC:B6:64:AF` |
| 2609 | `54:10:EC:B6:64:D3` |

These identify the fitted RTC chips. Replacing or moving the EDU/RTC changes
which identity is associated with the base board. 2512 has no EDU or EUI.
See [Microchip's datasheet, section 6.4.1](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf).

## Implementation and qualification

The journal's private component format 3 adds one EUI read operation. It reads
exactly F2–F7 through the private EEPROM transport without scanning, clearing or
initializing the ordinary outage allocation. The transport permits that one
protected read range and still rejects writes at or above 80. Factory unlock
and status-register writes are not implemented. Public raw EEPROM access stays
denied. The verified banner format is `BT`,2,3 to avoid invoking incompatible
older components. The public RTC/I2C entries and EEPROM journal layout remain
unchanged; old incompatible optional pieces fail closed.

The transient result uses the existing journal scratch verification buffer.
TIME and user programs remain read-only time clients; SET/ACK administration
stays in CLOCK and boot. With optional software installed, user RAM still ends
at $64FF inclusive even without EDU; $6500–$66FF remains reserved. Only absent
or rejected optional software on a cold boot can allow RAM through $66FF, and
an active reservation remains until RESET after later validation failure.

Build with `python tools/build_v2_rtc_eui.py` and
`python tools/build_v2_clock_eui.py`. Outputs are isolated under
`BUILD/v2-rtc-eui` and `BUILD/v2-clock-1.3`. Monitor size remains 3967 bytes per
slot, fixed F remains byte-identical, E remains 1754 bytes, and CLOCK is 5094
bytes in its existing two-sector allocation. The candidate includes the shorter
RTCC power-fail messages and the small TIME command.

Host checks cover boot and CLOCK identity display with healthy/stopped/invalid/
absent RTC, no EDU, zero/erased identity, rejected protected writes, and unchanged
factory data, ordinary EEPROM, RTC registers and flash. Journal/CLOCK checks
retain history, save/ACK ordering and bank preservation. No boards are accessed
or flashed for this work. Physical qualification remains pending.
