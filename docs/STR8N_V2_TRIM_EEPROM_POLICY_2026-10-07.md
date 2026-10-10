# Normal-trim CLOCK candidate and EEPROM protection policy

Owner direction: keep coarse mode OFF and use normal digital trim in CLOCK.
Alarm 0/1 and MFP output configuration remain deferred. EEPROM protection is
discussion only. Beta13/CLOCK 1.5 is installed and verified on all three boards
with OSCTRIM $00 and coarse mode disabled. No calibration was applied; see
[the installation record](STR8N_V2_TRIM_HARDWARE_2026-10-07.md).

Beta13 / CLOCK 1.5 provides:

| Command | Behavior |
| --- | --- |
| `TRIM` | Read/display signed trim steps, coarse mode and raw OSCTRIM |
| `TRIM +n` | Speed up by n normal trim steps, after exact YES |
| `TRIM -n` | Slow down by n normal trim steps, after exact YES |
| `TRIM 0` | Disable correction and ensure coarse OFF, after exact YES |
| `STATUS` | Include the same trim information alongside normal status |

Accept 1-3 decimal digits and an optional sign, in the range -127 through +127.
Unsigned nonzero input means positive. Signed zero is normalized to zero.
Malformed input, extra text and out-of-range values are rejected without writes.
`COARSE ON/OFF` commands are not provided. Reads and canceled requests never
change hardware. A confirmed TRIM request disables and verifies coarse mode
before writing a new trim value, preserving all other CONTROL bits. It then
verifies CONTROL and OSCTRIM. A matching trim with coarse already OFF performs
no writes. Any enabled alarm or square-wave output causes refusal.

The signed command uses a direction convention: **positive speeds up, negative
slows down**. MCP79411 OSCTRIM is sign/magnitude, not a signed two's-complement
byte: positive nonzero requests set bit 7; negative requests clear bit 7; zero
uses $00. This differs from the sign of measured drift: a fast clock with positive
drift needs a negative correction. Changes leave UTC/calendar, DOW, backup,
power-fail flag/timestamps, EEPROM history, factory EUI and flash binding intact.
No trim adjustment is automatic at boot or during reads. A failed update may
have partly changed CONTROL/OSCTRIM; CLOCK reports an unverified update and
directs the user to inspect STATUS. User programs remain read-only time clients.

## Calibration without test instruments

Normal trim applies once per minute at approximately 1.017 ppm per step,
with roughly +/-129 ppm available. It remains active on battery backup.
Coarse mode applies much larger corrections and stays OFF for normal use.
[Microchip datasheet, section 5.6](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf).

1. Use a reliable UTC reference and retain timestamped offset measurements.
   Our existing zero-trim baselines can support the initial calibration; avoid
   resetting the RTC in the middle of a drift observation interval.
2. Measure drift over several days; longer periods reduce one-second sampling
   uncertainty. Account for reference uncertainty and temperature changes.
3. For an initially untrimmed clock, correction steps are approximately
   `round(-measured_drift_ppm / 1.0172526)`. A clock gaining 20 ppm would use
   about `TRIM -20`; one losing 20 ppm would use about `TRIM +20`.
4. Record the setting and UTC time at which it was applied, then start a new
   drift interval. These commands set an absolute value, not an increment.
   On a later measurement, adjust the existing setting by the residual error.

Examples above are illustrative, not applied board settings. At zero trim,
all boards retain the original measured behavior. The EEPROM journal still
owns all 128 ordinary bytes; no calibration record or new flash sector is added.

## EEPROM protection

The ordinary 128-byte EEPROM has two nonvolatile block-protection bits in its
STATUS register at FF. Hardware supports these ranges:

| BP1:BP0 | Protected addresses | Effect on the four-slot allocation |
| --- | --- | --- |
| 00 | None | All four slots can be updated |
| 01 | 60–7F | Slot 4 protected |
| 10 | 40–7F | Slots 3 and 4 protected |
| 11 | 00–7F | All four slots protected |

Protection prevents writes, not reads. It is separate from the protected factory
EUI region at F0–F7. Both current boards read BP=00. Their factory bytes and
ordinary journal data remain unchanged.
[Microchip datasheet, section 6.2.1](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf).

The current firmware is conservative: **any nonzero BP value refuses all
journal writes**, rather than rotating only through remaining unprotected slots.
Failed logging keeps the RTC power-fail flag latched. History remains readable;
its write/clear paths do not bypass protection. Normal logging therefore requires
BP=00 under the accepted all-128-byte journal layout.

Recommendation: leave BP=00. The software already denies public raw EEPROM
transactions, restricts private writes to the ordinary range/page bounds, and
uses explicit confirmation for user administration. The EUI is never unlocked
or written; its remembered flash binding is independently protected. No EEPROM
protection command or temporary automatic unlock/relock policy is added.

Build with `python tools/build_v2_rtc_trim.py` and
`python tools/build_v2_clock_trim.py`. Model-test with
`python tools/test_v2_trim.py`. Outputs are isolated under
`BUILD/v2-rtc-trim` / `BUILD/v2-clock-1.5`; beta12 artifacts remain intact.
The public service ABI, $6500-$66FF reservation and existing flash placement
are unchanged. With EDU mode ON and the software installed, user RAM ends at
$64FF even without an EDU board. Beta15's explicit EDU OFF disables these
services at RESET and permits RAM through $66FF; see
[saved EDU mode](STR8N_V2_EDU_MODE_2026-10-08.md).
CLOCK still fits its two stored sectors. Upgrade preparation must
preserve the identity tail. Physical qualification and installation passed on
2512, 2205 and 2609; the original zero-trim drift baselines are retained.
