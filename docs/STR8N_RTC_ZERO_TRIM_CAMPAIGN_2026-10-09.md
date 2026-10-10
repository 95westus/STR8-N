# Four-board zero-trim UTC campaign

The user superseded the earlier campaign and explicitly authorized EDU ON for
newly equipped 2512, zero normal trim on all boards, fresh UTC synchronization,
an immediate drift check, a check in ten minutes and randomized collection until
06:00 October 10 America/Chicago. Earlier evidence is archived, not deleted.

2512's saved EDU setting was enabled and activated with the documented cold J3
restart. Its service RAM now ends user RAM at 64FF, as on the other EDU boards.
All four TRIM 0 operations were verified before any UTC SET. Factory EUI and
binding state were preserved; 2512 and 2604 remain unbound. No ACCEPT EUI,
firmware update, SRAM format or explicit power-fail ACK command was performed.

All four UTC SETs used fresh NIST 132.163.96.6 and passed independent final
reference checks. Initial successful sync attempts remain archived. Measured
one-second alignment corrections and 2512's oscillator-start settling were
recorded; only final verified sync reports form the baselines.

| Board | EDU | Normal trim | CONTROL | Baseline UTC |
|---|---|---|---|---|
| 2512 | ON | 0 | 80 | 2026-10-09 23:18:44 |
| 2205 | ON | 0 | 80 | 2026-10-09 23:16:51 |
| 2604 | ON | 0 | 00 | 2026-10-09 23:16:04 |
| 2609 | ON | 0 | 80 | 2026-10-09 23:17:58 |

The campaign index and setup evidence are in
`output/qualification/rtc-zero-trim-campaign-2026-10-09-231026Z`.
`output/qualification/active-rtc-campaign.json` selects and hashes this index.
The shared analysis tools now enroll 2512 when present in the index; they no
longer treat its board ID as proof of unavailable RTC hardware. Four-board plots
and CSVs include it normally. Previous campaign reports do not enter statistics.

The immediate read-only check passed under
`output/qualification/rtc-residual-drift-2026-10-09-231933Z`: all RTCs running,
backup enabled, trim/control/EUI verified, fresh NIST checks passed. Its very
short elapsed intervals provide no actionable trim calibration. Every board
has one cumulative-rate sample, unavailable sample SD and a two-point offset
fit; zero residuals are automatic, not stability evidence. Retain zero trim.

Later October 9, the user excluded that very short immediate sample and
requested offline recalculation without board access. Its raw evidence remains
archived. `history-exclusions.json` in the campaign root pins the four excluded
report hashes to the unchanged baseline-index hash. Both automatic history
selection and direct plotting honor this policy. Recalculated results from the
ten-minute and latest saved checkpoints are in
`output/qualification/rtc-recalc-2026-10-10-010743Z`; there are two retained
rate samples per board and three offset points per fit including the baseline.
No new measurements, COM-port access or hardware changes occurred.

The old random checkpoints were deleted. Ten new one-off thread checkpoints
are saved for 18:32, 19:57, 21:55, 23:04, 23:39 on October 9, then 00:14,
01:24, 02:43, 04:21 and 06:00 on October 10 (CDT). The first is the ten-minute
check; later gaps are 85, 118, 69, 35, 35, 70, 79, 98 and 99 minutes.
Each attempts one detailed read-only check and deletes itself. There is no
daily recurrence or automatic application of trim suggestions.

Every remaining checkpoint explicitly requires EDU ON on all four boards
before acquisition and rechecks it afterward. Status evidence records the
active latch (01), valid SV RTC descriptor and `edu_mode=ON`. Separate preflight
and final records are retained. An OFF/invalid mode or missing service stops
the complete checkpoint and requests user action; it is not silently omitted
or automatically changed/reset during read-only collection. A fresh guard
check passed on all four boards under `edu-on-guard-check` in the campaign root.

`campaign-summary.json` pins the baseline index, immediate evidence and saved
automation IDs. Random schedules, interval checks, normal/coarse/identity state,
quantization/serial/NTP/baseline bounds, statistics, feasible free-intercept fits,
residuals and hardware-supported trim predictions remain separate. A hardware
or NTP failure preserves evidence and is not replaced with stale measurements.
This RTC enrollment does not by itself broaden firmware/RC qualification.

The user extended collection through 12:00 noon October 10, 2026 CDT.
Existing checkpoints remain unchanged. Additional randomized checkpoints are
07:29, 08:53, 10:10 and 12:00, with gaps of 89, 84, 77 and 110 minutes after
the 06:00 checkpoint. All remaining one-off prompts retain the four-board EDU
guards, unchanged zero-trim baselines and immediate-sample exclusion. Scheduling
this extension did not access or change any board. `noon-extension.json` records
the added checkpoints; the active campaign endpoint is now noon.
