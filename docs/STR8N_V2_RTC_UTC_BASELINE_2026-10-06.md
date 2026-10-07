# RTC UTC synchronization and drift baseline

Recorded 2026-10-06 America/Chicago. The user requested UTC synchronization
and a saved baseline for later drift checks. Both EDU-equipped boards were
synchronized through their installed beta5 clock service and verified advancing.
2512 has no EDU/RTC and was not changed.

| Board | Final SET operation, UTC on 2026-10-07 | Chicago time on 2026-10-06 | Completed-operation window, UTC |
| --- | --- | --- | --- |
| 2205 / COM3 | 04:12:26 | 23:12:26 CDT | 04:12:26.002465–04:12:26.239476 |
| 2609 / COM8 | 04:14:12 | 23:14:12 CDT | 04:14:12.001137–04:14:12.235843 |

These are reference-time brackets for the actual SET call, not a claim that
the chip's oscillator phase is aligned to a fraction of a second. RTC calendar
reads have one-second resolution. The saved initial offsets below include that
quantization, command latency, and estimated NTP reference uncertainty.

## Reference and evidence

Windows Time reported `not synchronized` when queried before these operations,
with its last successful sync at 18:55:37 Chicago time and configured source
`time.nist.gov,0x9`. The PC system clock was left unchanged. Fresh direct NTP
queries to `time.nist.gov` supplied the UTC reference instead. All accepted
responses reported stratum 1 and a synchronized leap indicator. Each operation
used three samples, a monotonic-time reference anchored to the lowest-delay
response, and a fresh final reference check.

The tool stores each raw response, server address, four NTP timestamps, measured
server-minus-host offset, network delay, root delay/dispersion and estimated
reference uncertainty. The offset/delay calculation follows
[RFC 5905, section 8](https://www.rfc-editor.org/rfc/rfc5905.html#section-8).
These measurements are practical drift baselines, not a calibrated accuracy
certificate.

2205 received calendar `2026-10-07T04:12:26Z`. The first 2609 SET at
`04:12:59Z` showed an initial lead. A separate recorded alignment correction
was made at reference time `04:14:12Z`, staging calendar `04:14:11Z` to
compensate for that observed whole-second lead. Final readbacks confirmed the
offset interval below. The earlier record remains preserved; the final 2609
baseline supersedes it for drift comparisons.

| Board | Final read-only baseline reference, UTC on 2026-10-07 | Initial RTC-minus-reference interval |
| --- | --- | --- |
| 2205 | 04:14:51.718014 | −0.411456 to +0.619258 seconds |
| 2609 | 04:14:17.449002 | −0.504003 to +0.255168 seconds |

Positive means RTC ahead. Intersected observation intervals estimate the
starting offset; they are not zero by assumption. Later drift is the change
from this initial offset, divided by elapsed reference time. The tool reports
an interval in seconds, seconds/day, and ppm rather than false fractional-second
precision from an integer calendar reading.

Original power-fail registers and the driver's retained outage capture were
saved before SET. SET clears the chip's power-fail flag as part of its calendar
write; the archived evidence and RAM capture remain available. Successful
post-SET reads reported flags `$37` (started, running, valid calendar, backup
enabled, continuity unknown). Control and trim bytes were preserved. No separate
ACK, alarm, calibration, flash, SRAM or EEPROM operation was issued.

The RAM-only 43-byte staging client was modeled against the installed service,
then loaded and read back exactly before execution. It stages ordinary program
RAM at `$2400` inside the protected SET request buffer; it does not bypass
monitor protection. SHA256:
`a1f6a9da7cb26debe90c8a4add2f1e91ec5143571e80bae0c56ed55aa1303714`.

Owner-local reports, raw result buffers and serial transcripts are under
`output/qualification/rtc-utc-sync-2026-10-06/`:

- `2205/report.json`: original UTC SET and first verification.
- `2205-baseline/report.json`: final read-only 2205 offset baseline.
- `2609/report.json`: first SET and observed initial lead.
- `2609-aligned/report.json`: final corrected SET and 2609 baseline.
- `baseline-index.json`: board/port, final sync and baseline references, report hashes.

## Later read-only drift check

Leave both RTC settings and trim unchanged during the measurement interval.
Keep the backup batteries fitted. Ordinary main-power loss may be recorded
separately; loss of time or another SET requires a new baseline. The driver
continues to flag continuity unknown and cannot certify battery condition.

An initial check after about 48 hours, followed by a longer check after a week,
will make slow drift easier to distinguish from the starting measurement width.
No scheduled automation has been created. With both serial ports available,
use fresh evidence directories and omit `--sync`:

```text
python tools/rtc_utc_baseline.py --board 2205 --port COM3 --out output/qualification/rtc-drift-2205-48h --baseline output/qualification/rtc-utc-sync-2026-10-06/2205-baseline/report.json
python tools/rtc_utc_baseline.py --board 2609 --port COM8 --out output/qualification/rtc-drift-2609-48h --baseline output/qualification/rtc-utc-sync-2026-10-06/2609-aligned/report.json
```

The default measurement path only READs RTC registers and obtains a fresh NTP
reference. It never sets the clock or acknowledges power-fail evidence.
Build the separate application fixture if needed with
`python tools/build_v2_rtc_sync_client.py`; installed flash is unchanged.
The builder retains the original 43-byte client and also builds the current
54-byte sampling client. Future drift checks use its private `$2440-$247F`
snapshot so the beta6 monitor's banner READ after HOLD cannot replace the sample
whose acquisition was bracketed by the host timing marker. Existing baseline
reports and their original offsets remain unchanged.

Follow-up: [CLOCK 1.0](STR8N_V2_CLOCK_1_0_2026-10-06.md) now supplies status,
UTC display and explicit SET through the public API, saved on all three boards
and launched with `R CLOCK`. No SET was confirmed during its hardware checks;
these drift baselines are unchanged. Versioned saved-record timestamps follow
next; SRAM/EEPROM and alarms remain deferred.
