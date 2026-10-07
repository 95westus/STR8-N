# Drift check, outage banner and CLOCK 1.1

Recorded 2026-10-07 America/Chicago. The user requested an immediate drift
check, then outage indication/times on boot and an updated CLOCK utility.
The local candidate is beta7 generation 16 with CLOCK 1.1.

## Read-only drift check before updates

Fresh NIST NTP comparisons used the original UTC baselines and the private
sampling client. No SET, ACK or trim change occurred during measurement.

| Board | Elapsed since baseline | Change in RTC-minus-reference offset |
| --- | --- | --- |
| 2205 | 68.9 minutes | −0.825 to +1.164 seconds |
| 2609 | 68.8 minutes | −0.869 to +0.899 seconds |

Both intervals include zero. No measurable drift is established yet; this
does not prove zero drift. RTC calendar quantization, serial acquisition windows
and NTP uncertainty dominate such a short interval. The corresponding bounds
are approximately −200 to +282 ppm and −211 to +218 ppm, too wide for sensible
calibration. Keep the original settings and take the planned longer checks.
Original sync/baseline reports retain their hashes. ACK does not reset the
clock, so acknowledgment does not create a new drift baseline.

Evidence is in `output/qualification/rtc-drift-2026-10-07`, including NTP
packets, serial logs, result snapshots and the comparison summary. 2205 was
initially still in CLOCK; that attempt issued no clock writes and is retained
separately. The utility was exited and measurement completed from the monitor.

## Boot and CLOCK display

While the chip's power-fail flag is latched, the banner appends the marker and
prints its recorded fields:

```text
UTC 2026-10-07 05:30:00 [power-fail]
Power down: 10-07 05:03
Power up:   10-07 05:04
B3>
```

The sample current time illustrates layout. The event fields shown are the
archived 2205 event. The indicator and outage fields also appear when current
time is stopped/invalid, provided the register read succeeded. Unavailable
hardware still gives `RTC unavailable`; unavailable software omits the line.
Boot, ordinary READ, STATUS and CLOCK entry do not clear the latch.

Outage timestamps contain month/day/hour/minute, without year or seconds.
They are the chip's RTC-time convention, UTC for the known synchronized events;
the firmware does not invent a timezone marker or year. Valid 12-hour fields
are converted to 24-hour display. Invalid BCD/ranges print `invalid fields`;
CLOCK retains raw diagnostics. February 29 is allowed because the event has
no year to determine leap status. No exact outage duration is inferred.
See [Microchip's datasheet, section 5.7.1](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf).

## Explicit acknowledgment

Launch `R CLOCK`; commands now include `ACK` alongside R/TIME, S/STATUS,
SET, HELP and Q/QUIT. ACK reads and displays the event, asks the user to record
important evidence, explains that RAM capture can be lost on RESET, and requires
exact `YES` (case-insensitive). Cancellation, short/trailing confirmation,
Ctrl-C, Escape and overflowing input do not authorize it. If no event is latched,
ACK reports `nothing cleared` and issues no data write.

Confirmed ACK uses the existing managed service, which captures evidence before
clearing the chip's flag and timestamp registers. CLOCK reads status afterward
and verifies the latch cleared. It reports failure without automatically retrying.
The time/calendar, weekday, backup enable, control and trim remain unchanged.
The retained RAM event is still decoded in STATUS after the chip fields clear.
This is not persistent outage storage; record/archive important evidence first.

The chip requires the old flag to be cleared before it logs a new outage. ACK
therefore rearms capture for the next event; it is not cosmetic suppression.
SET still clears the flag as part of explicit calendar setting and continues
showing/capturing evidence before confirmation. No SRAM/EEPROM, alarm ownership,
automatic clock initialization or persistent outage journal is added.

## Build and verification

```text
python tools/build_v2_clock_powerfail.py
python tools/build_v2_rtc_powerfail.py
python tools/test_v2_powerfail.py
```

The separate outputs are `BUILD/v2-clock-1.1` and `BUILD/v2-rtc-powerfail`.
Earlier qualified CLOCK 1.0 and beta6 outputs are retained. CLOCK 1.1 occupies
3673 bytes in RAM `$2000-$2E58`; its 24-byte saved header plus body fits one
B2 sector. The optional private banner/decoder occupies 721 bytes at B3 `$8900`.
The common RTC/I2C provider, gateway allocation (512 bytes), public entries and
fixed F recovery core remain unchanged. Monitor slots remain 3960 bytes and
E launcher/kernel code 1754 bytes.

Machine-code checks cover all supported years/calendar boundaries from CLOCK,
yearless month/day validation, malformed stamps, every 12/24-hour conversion,
healthy/stopped clock outage display, absent software/hardware, canceled ACK,
confirmed ACK, no-event ACK, capture retention, unchanged time/control/trim,
bank/VIA preservation, stale pointers, RST/MAINT and legacy compatibility.

Fresh complete backups and independent repeats bind each exact upgrade.
The RAM installer models stale-preimage/corrupt-payload refusal and performs
per-sector device verification. B2 CLOCK is written with an uncommitted header,
then committed only after its whole sector verifies. B0, B1/MAINT, B3 sector 9,
fixed F and other B2 bytes are preserved. Configuration/wear snapshots retain
settings, retag valid slot preference to generation 16 and preaccount the six
planned erase attempts, including CLOCK replacement.

Owner-local update, event archive and qualification evidence is under
`output/qualification/rtc-powerfail-2026-10-07`. Raw/vendor backups remain
excluded from Git/release artifacts. The final acceptance audit also binds the
drift report and original baseline hashes.

## Hardware acceptance and 2609 LED observation

All three boards passed physical power-cycle restart, A/B/A selection, saved
CLOCK 1.1 restore/launch, MAINT return and exact complete flash readback.
2512 without an EDU reports bounded unavailability and refuses ACK before
confirmation. Both EDU boards display `[power-fail]` and the decoded recorded
down/up fields. Boot and canceled/no-event paths make no acknowledgment write.

The original events were archived before confirmed live ACK on 2205 and 2609.
CLOCK verified the latch clear, retained and decoded its RAM capture, preserved
backup enable/control/trim, and left the advancing calendar within the elapsed
operation window. The chip's timestamp registers then read zero, while retained
RAM evidence still matched the archive. The marker disappeared on normal return
to the monitor. A second ACK with no event issued no clear operation. No SET
or calibration was performed; the original UTC drift baseline hashes remain
unchanged. The next new outage can now be logged.

| Board | Archived power-down | Archived power-up | Final latch |
| --- | --- | --- | --- |
| 2205 | `10-07 05:03` | `10-07 05:04` | Cleared by confirmed ACK |
| 2609 | `10-07 05:04` | `10-07 05:04` | Cleared by confirmed ACK |
| 2512 | No EDU/RTC response | No EDU/RTC response | Not applicable |

The user reported four red LEDs on 2609 during the restart. COM8 was initially
absent briefly, then re-enumerated with its expected FTDI identity and the board
responded normally at `B3>`, printing UTC and outage times. The firmware uses
`$F0` for the flash indicator, which is consistent with a four-bit flash pattern;
the exact observed transient was not captured and its cause is not proven.
Both monitor slots and the full four-bank images verified; no persistent boot
failure was found. A verified RAM-only PIA probe read LED port/control `$00/$34`,
not the `$F0` flash pattern, and returned normally. The ordinary D command
correctly denied direct I/O reads; that denial was not a board failure. The
observation and probe are retained in `2609/led-check`.

## User-reported subsequent outage and next wording change

The user supplied a beta7/65C816 transcript showing a new recorded event with
power down `10-07 12:56` and power up `10-07 12:59`. CLOCK STATUS reported raw
`56 12 07 70 59 12 07 70`, with the power-fail latch set. ACK was canceled at
confirmation. After a reported second power failure, the banner at UTC 13:13:11
still showed the same event. This is consistent with the chip's preservation
rule: an uncleared latch retains the original timestamps and prevents a new
timestamp pair from being logged. ACK rearms future logging; it cannot recover
the unrecorded second outage. UTC time continues independently of that latch.
This is user-supplied evidence, not an additional agent-operated board test.

For the next CLOCK update, the user requested this exact replacement wording:

> ACK clears the power-fail flag and outage timestamps. UTC time keeps running unchanged.

The change is recorded in the backlog; the currently installed CLOCK 1.1 image
has not been changed by this documentation update. No hardware command, SET or
ACK was issued while recording this follow-up.
