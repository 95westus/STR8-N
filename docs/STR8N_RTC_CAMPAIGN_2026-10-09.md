# Restarted three-RTC drift campaign

Superseded later October 9 by the user-authorized
[four-board zero-trim UTC campaign](STR8N_RTC_ZERO_TRIM_CAMPAIGN_2026-10-09.md).
2512 now has EDU installed and enabled. The schedules below were canceled;
their evidence remains historical and is excluded from the new collection.

The user's corrected campaign scope is 2609, 2604 and 2205. Board 2512 is
excluded because it has no fitted EDU/RTC; scheduled status checks do not open
its port. Existing RTCs were already enabled. UTC, trim, CONTROL, EUI/binding,
firmware and stored data were not changed.

Fresh read-only time-zero baselines passed NIST and final consistency checks:

| Board | Time zero, October 9 CDT | Retained trim | UTC offset measurement bounds, seconds |
|---|---|---|---|
| 2609 | 17:11:10 | -14 | -0.174 +/- 0.333 [-0.507, +0.159] |
| 2604 | 17:11:55 | -16 | -0.467 +/- 0.618 [-1.085, +0.152] |
| 2205 | 17:12:33 | -18 | -0.314 +/- 0.560 [-0.874, +0.246] |

Owner-local evidence is `output/qualification/rtc-campaign-2026-10-09-221008Z`.
Its baseline index hashes each new report while preserving the original sync
evidence and older campaigns. Rates, mean/median/sample SD, fitted slope,
residuals and trim predictions are unavailable at time zero; they are not zero.
Only subsequent unique verified readings using these baselines enter statistics.

The finite randomized schedule has local checkpoints at 17:44, 18:17, 19:26,
21:04, 21:59, 23:14 and midnight October 10. Planned gaps are 31, 33, 69, 98,
55, 75 and 46 minutes. The old three-hour heartbeat was replaced by the first
one-off checkpoint; six additional one-off thread heartbeats complete the plan.
Each performs one attempt and deletes itself. This is not a daily recurrence.
The user's "12pm tonight" was interpreted as midnight tonight, 00:00 October 10
America/Chicago. Raw schedule and saved automation checks are retained in
`random-schedule.json` and `schedule-verification.json`.

`output/qualification/active-rtc-campaign.json` selects and hashes this index.
`python tools/analyze_rtc_drift.py` uses it by default; an explicit
`--baseline-index` remains available. Every scheduled check retains the detailed
uncertainty, historical statistics, compatible-line fit, trim proposals,
prediction CSVs and PNG/SVG graphs. No proposal is applied. Port/measurement
failures retain evidence and do not substitute old samples. Earlier failed
preflight evidence remains in the preceding campaign-attempt directories.
