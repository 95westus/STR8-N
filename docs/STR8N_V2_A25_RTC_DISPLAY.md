# Alpha25 EDU date/time display candidate

The owner requested a 24-hour time line before the `B3>` prompt and chose
a two-digit month. The current E-only revision uses this layout:

```text
STR8-N 2.0a25 B3 65C02
ABI 65C02 | 816E | 816N-VEC
EDU KIT       DETECTED
  RTC         Wed 26-09-30 18:40:16
B3>
```

The EDU/RTC lines appear once on monitor startup or warm reentry. They use the
MCP79411 at I2C `$6F` and convert either chip hour mode to 24-hour output.
The three-letter English weekday (`Mon` through `Sun`) comes from the chip's
`RTCWKDAY` register, mapped as 1=Sun through 7=Sat. The MCP79411 defines
weekday numbers as user-settable; board 2205 uses the Sunday-first mapping. These names follow Unicode CLDR English short weekday forms; ISO
8601 specifies weekday numbers, not English abbreviations.
It displays the time only after checking valid BCD/date fields, ST and
OSCRUN, and an exact one-second advance within a bounded poll. The chip
provides a two-digit year. Its power-fail flag does not suppress an
otherwise valid running time. If the EDU, E extension, or valid running
RTC is absent, the E extension prints `EDU KIT       INCONCLUSIVE` and
reaches the prompt. If E itself is absent, startup reaches the prompt
without an EDU line. An RTC failure does not prove the whole EDU absent.

The status reader occupies 892 bytes at Bank 3 `$E000`; the S/R/T entry table remains
at `$E800`, with its existing entry addresses. The F-sector hook checks the
`RT` version-1 descriptor before calling E. F ends at `$FFDC`, leaving
three erased bytes before the vectors. The v2 ROM and RAM public entry
addresses remain fixed. The reader borrows `$7D90-$7D9F` only during
startup; S/R/T uses that area later. The VIA1 PA0/PA7 pins are restored
after the read attempt. No RTC register data is written.

Build and host checks:

```text
make v2-a25-rtc-check
```

The build emits `BUILD/v2-alpha25/str8n-v2-alpha25-e000-ffff.s19`, separate
E and F BINs, and `build.json` with addresses and hashes. The tests execute
the linked 65C02 code with snapshots for valid, stopped, invalid, 12/24-hour,
leap-day, and all seven RTC weekday values. Boot tests cover erased E, absent RTC, display placement,
and an S/R save/restore smoke check. Board 2205 supplied the 65C02
electrical check; W65C816 execution still requires board evidence.

Board 2205 installed and read back the first a25 RTC display; see the
[physical EDU result](STR8N_V2_A25_2205_EDU_INSTALL_2026-09-30.md).
The [E-only status update](STR8N_V2_A25_2205_EDU_STATUS_2026-09-30.md)
subsequently passed guarded installation, exact E/F readback, and physical
RESET on the same board.
The [weekday update](STR8N_V2_A25_2205_DOW_2026-09-30.md) passed guarded
E-only installation, full readback, and physical RESET after correcting the
board's weekday mapping. The W65C816 EDU path remains unqualified. The
combined E/F S19 is a flash image, not a RAM updater.

The standalone [RAM reader](../tools/v2-rtc-test/README.md) remains useful
for checking the attached EDU before a firmware update.
