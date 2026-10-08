# Read-only UTC/drift comparison after beta12

Measured 2026-10-07 using fresh NIST NTP at 132.163.96.6. Original sync/baseline
reports remain byte-identical. No SET, ACK, trim or calibration change was issued
by the measurement. The fixed RAM sampling client copies its result before HOLD
so the monitor's subsequent time read cannot replace the timed sample.

| Board | Reference UTC | Elapsed since baseline | RTC minus UTC | Change since baseline |
| --- | --- | --- | --- | --- |
| 2205 | 17:46:56 | 13.535 hours | +0.915 to +1.629 s | +0.296 to +2.040 s |
| 2609 | 17:48:46 | 13.575 hours | +0.013 to +0.730 s | -0.242 to +1.234 s |

The current offset comparison places 2205 about 0.186–1.616 seconds ahead of
2609. The samples were sequential, not a simultaneous subsecond phase reading.
Ranges include one-second RTC quantization, serial acquisition brackets and NTP
reference uncertainty. Initial NTP requests had intermittent timeouts; failed
attempt evidence is retained. Successful retries used bounded, spaced retries
and passed fresh final-reference consistency checks.

2205's drift-change interval is positive: this observation supports a fastward
change relative to its original baseline. Its broad rate interval is +6.07 to
+41.88 ppm (+0.52 to +3.62 seconds/day). 2609's rate interval is -4.96 to +25.24
ppm (-0.43 to +2.18 seconds/day) and includes zero, so a definite nonzero rate
is not established for 2609. The 48-hour/week checks remain useful before trim
adjustment; no adjustment is made here.

Evidence is under `output/qualification/rtc-drift-2026-10-07-post-beta12`.
`summary.json` pins both successful report hashes and verifies the original
baseline/sync report hashes. Matching factory identity was also checked during
the hardware qualification, with both EUI values accepted in flash explicitly.

## Requested ppm check, later on 2026-10-07

Fresh sequential NIST-reference measurements completed at 22:26:14 UTC (2205)
and 22:27:12 UTC (2609), approximately 18.2 hours after the original baselines.

| Board | RTC minus UTC | Drift since original baseline | Drift rate |
| --- | --- | --- | --- |
| 2205 | +1.244 to +1.760 s | +0.625 to +2.172 s | +9.54 to +33.16 ppm |
| 2609 | +0.454 to +1.226 s | +0.199 to +1.730 s | +3.03 to +26.39 ppm |

Positive ppm denotes gaining time. Both intervals are positive at this
measurement precision, but they remain broad due to one-second calendar
quantization and initial baseline uncertainty. No trim or time adjustment was
made. Both OSCTRIM registers read 00 and CONTROL reads 80; the post-measurement
factory identities, protection status and complete ordinary EEPROM histories
matched the prior regression archives. Original sync/baseline report hashes
remain unchanged.

Evidence: `output/qualification/rtc-drift-2026-10-07-222515/summary.json` and
the individual successful reports and read-only post-measurement archives.
CLOCK 1.4 offers no trim, oscillator-source, output-mode or EEPROM-protection
command. Its explicit administrative operations remain SET, power-fail ACK,
history CLEAR and ACCEPT EUI. SET starts/enables the clock and backup and uses
24-hour format while preserving control/trim.
