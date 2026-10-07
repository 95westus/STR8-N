# RTC drift measurement, 2026-10-07

Read-only measurements against fresh `time.nist.gov` NTP samples and the
original UTC sync baselines. Both clocks were usable and advancing. No SET,
trim, ACK or flash operation was performed; original baseline hashes match.

| Board | Elapsed since baseline | Current RTC-minus-UTC offset | Drift since baseline | Rate bounds |
| --- | --- | --- | --- | --- |
| 2205 / COM3 | 8 h 34 min | +0.599 to +1.364 s | −0.021 to +1.775 s | −0.668 to +57.522 ppm |
| 2609 / COM8 | 8 h 36 min | −0.012 to +0.974 s | −0.267 to +1.478 s | −8.630 to +47.765 ppm |

Positive means ahead/fast. Drift subtracts the initial measured offset, rather
than assuming synchronization started with zero error. Both drift intervals
include zero. Their centers suggest a fastward trend, but neither measurement
establishes a nonzero rate at the present uncertainty; do not use the interval
centers as precise calibration values. A longer interval will better separate
crystal drift from one-second calendar quantization and reference/acquisition
uncertainty. The planned 48-hour and one-week checks remain appropriate.

Each measurement saves three initial NTP responses, a monotonic reference,
four RTC observations with varied sampling phase, and a final fresh reference
check. The application-owned snapshot at `$2440-$247F` preserves the sample
before the host timing marker; the monitor's subsequent banner READ cannot
replace it. Raw responses, serial logs, samples and report hashes are under
`output/qualification/rtc-drift-2026-10-07-1248/{2205,2609}` with a root
`summary.json`. The directory timestamp identifies the run's start in UTC.

This follows the earlier approximately 69-minute check in
[the power-fail update record](STR8N_V2_RTC_POWERFAIL_2026-10-07.md).
The [original UTC baseline](STR8N_V2_RTC_UTC_BASELINE_2026-10-06.md) remains
the comparison point, including across the confirmed power cycles and ACK.
