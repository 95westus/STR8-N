# RTCC boot messages — unflashed beta9 candidate

The owner selected these exact messages:

```text
RTCC: PF logged, ACK
RTCC: PF logging failed.
RTCC: PF logged, unverified ACK
```

`R CLOCK` remains the program name. No `R RTCC` alias is added. This candidate
is built and checked locally; no board is flashed or accessed for this change.
The accepted beta8 artifacts and hardware qualification records remain intact.

The journal records verified progress in transient byte $6BEE: bit 0 means a
committed EEPROM event was verified, and bit 1 means the chip's live flag was
verified clear after ACK. Boot selects its message from these facts, rather than
treating every error as a failed save. Failure to update the history clearance
byte after a verified ACK does not turn an already verified ACK into an
unverified one. The pending history marker remains conservative in that case.
The journal's private component header changes to `PJ`,2,1 so the new banner
cannot mistake an older component for one supplying these progress bits.
The published journal descriptor and EEPROM record layout remain unchanged.

Build with `python tools/build_v2_rtc_messages.py`; outputs are isolated under
`BUILD/v2-rtc-messages`. Run journal, kernel and banner checks with
`STR8_RTC_BUILD=BUILD/v2-rtc-messages`. The journal tests inject failed logging,
a flag that fails to clear after ACK, and a failed clearance-marker write after
a verified ACK. CLOCK 1.2 integration is checked against the new components.

## Reading UTC at the console

```text
B3> R CLOCK
CLOCK> TIME
CLOCK> Q
```

CLOCK displays UTC immediately on entry. `TIME` or `R` reads it again;
`STATUS` or `S` displays clock status and raw registers. `Q` returns to the
monitor. These read commands do not SET the clock or acknowledge an outage.
The monitor boot banner also displays UTC when the clock is usable. There is
currently no standalone monitor `TIME` command.
The later unflashed [beta10 TIME candidate](STR8N_V2_TIME_COMMAND_2026-10-07.md)
adds that command and a runnable read-only example; it includes these messages.

## Reading UTC from a program

Programs use the resident read service rather than executing CLOCK. First
validate the `SV`,1 descriptor at $7D04, its clock-available flag, gateway address
and RAM limit, and the `RG`,1,4 signature at $6500. The installed layout reserves
$6500–$66FF; ordinary program storage ends at $64FF. Missing EDU is a supported
read error, not a reason to assume a cached calendar is valid.
Both limits are inclusive. An absent EDU board alone does not release
`$6500-$66FF`: the installed software still owns that reservation. User RAM can
extend through `$66FF` only when optional service software is absent or rejected
on a cold boot. An active reservation remains until RESET after a later
validation failure. Use the validated descriptor's RAM limit, not hardware
presence or the result of RTC_READ, to determine available program RAM.

Call `RTC_READ` at $6504. Carry set means a coherent running calendar was read;
carry clear means unavailable/stopped/invalid time or another service error,
with the error code in A. The decoded binary calendar is at $66C2–$66C9:

| Offset | Field |
| --- | --- |
| 0–1 | Year, little-endian 16-bit |
| 2 | Month |
| 3 | Day |
| 4 | Weekday: 1 = Monday through 7 = Sunday |
| 5 | Hour |
| 6 | Minute |
| 7 | Second |

CLOCK calculates DOW automatically from the supplied date during SET; no
separate weekday entry is required. For example, 2026-10-07 gives DOW 3,
Wednesday. RTC_READ returns that numbering as a binary value.

After successful discovery, a caller can read and copy the result to its own
storage:

```asm
        JSR RTC_READ
        BCC NO_USABLE_TIME
        LDX #7
COPY_TIME:
        LDA RTC_TIME,X
        STA PROGRAM_TIME,X
        DEX
        BPL COPY_TIME
```

Use [kernel-rtc-api.inc](../tools/v2-rtc/kernel-rtc-api.inc) for the constants.
The service supports foreground 65C02 and 816 emulation with D/DBR/PBR zero;
native calls and IRQ/NMI calls are outside the supported ABI. Recheck discovery
after monitor reentry or software replacement. Clock continuity and battery
health are not established merely by a successful calendar read.
