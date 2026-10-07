# Small monitor TIME command and read-only program example

The local beta10 candidate adds a monitor command:

```text
B3> TIME
UTC 2026-10-07 14:51:39
B3>
```

`TIME` performs a fresh clock read. It displays UTC, or the existing stopped,
invalid or unavailable status. It does not SET time, log/ACK an outage, or write
RTC/EEPROM/flash data. The existing `T` table command is retained; TIME takes no
arguments. `R CLOCK` remains the clock-management program, with no RTCC alias.

The command reuses the optional banner formatter. Its monitor hook is ten bytes;
total slot growth is twenty bytes including help and branch relaxation. Monitor
code is 3967 bytes per slot, within the 3968-byte budget. The formatter has a
separate read-only entry and mode, so invoking TIME cannot perform boot's
automatic power-fail processing. Its verified private header is now `BT`,1,3;
an older component cannot publish a callable pointer for the new entry.
Fixed F, E code size, public RTC/I2C entries and the RAM reservation are retained.
With optional software absent the command is unavailable; ordinary monitor
operation remains usable. With software installed but EDU absent, TIME reports
`RTC unavailable` and user RAM still ends at `$64FF` inclusive.

Build with `python tools/build_v2_rtc_time.py`. Candidate images and checks are
isolated under `BUILD/v2-rtc-time`. This candidate includes the selected shorter
RTCC boot messages. It has not been flashed or physically qualified.

## Runnable example

Source: [time-example.asm](../tools/v2-rtc/time-example.asm).
Build: `python tools/build_v2_time_example.py`.
Output: `BUILD/v2-time-example/time-example.s19`, 304 bytes at `$2000`.

At the monitor, use `L` and send that S19 as text. Then execute:

```text
B3> G 2000
UTC 2026-10-07 14:51:39
```

The example validates the `SV` descriptor, clock capability, gateway and RAM
limit, and the `RG` signature before calling `RTC_READ`. It checks carry, copies
the eight decoded binary calendar bytes into its own `MY_TIME` buffer, prints
them, then returns through the bank-safe HOLD entry. Copying protects its result
from subsequent monitor-banner reads. Errors print `UTC unavailable; error XX`;
80 is the example's unavailable-service code, and other codes come from the
clock service. The source has no SET or ACK call and never supplies intent keys.

Day of week uses **1 = Monday through 7 = Sunday** in the decoded calendar.
CLOCK automatically calculates it from the entered date when setting time;
the user does not enter DOW separately. The example reads the weekday without
changing it.

User programs are read-only clock clients. Time setting stays in CLOCK; automatic
power-fail handling stays in boot and journal-aware CLOCK commands. Existing
low-level SET/ACK entries remain for compatibility and internal administration;
they are not used by the user-program example.

The example works with the installed beta8 RTC service as well as this new
candidate. It supports foreground 65C02 and 816 emulation with D/DBR/PBR zero;
native execution is not qualified. It fits entirely in user RAM. With service
software installed, user RAM is `$0200-$64FF` inclusive even without EDU. Only
absent/rejected optional software on a cold boot can allow RAM through `$66FF`;
an active reservation survives later validation failures until RESET. Use the
validated descriptor's RAM limit rather than hardware presence.

Host checks execute TIME, TABLE parsing, all four example caller banks,
optional-device/software failures and stopped/invalid calendars, while checking
that live outage evidence is preserved and no data/flash writes occur. Existing
kernel, banner and journal checks cover the surrounding command integration.
