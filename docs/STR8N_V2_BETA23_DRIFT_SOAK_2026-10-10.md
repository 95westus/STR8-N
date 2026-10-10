# Beta23 drift and soak status — October 10, 2026

This is a publication summary of reviewed owner-local receipts. It does not
include board images, raw serial transcripts or private qualification archives.
The firmware target is frozen beta23 generation 32 / CLOCK 1.6.

## Latest drift results

Fresh pre-shutdown acquisition completed **18:11:05–18:11:57 CDT October 10**.
All four boards passed EDU ON, running oscillator, backup enabled, normal TRIM 0,
unchanged control/EUI/binding, baseline hashes and final fresh-NIST checks.
No UTC SET or trim change occurred during acquisition. The reference was
NIST 132.163.96.6; each original zero-trim baseline remains unchanged.

Each board has **21 retained checkpoints** spanning approximately 23.9 hours,
plus its original baseline in a **22-point absolute-offset fit**. The very short
immediate sample and failed/incompatible observations are excluded by the
campaign's hash-bound history policy. Older calibrated campaigns are not mixed
with this zero-trim campaign.

| Board | Elapsed hours | UTC offset bounds, seconds | Fitted ppm | Feasible ppm bounds | Fitted s/day | Nominal trim proposal |
|---|---:|---:|---:|---:|---:|---:|
| 2205 | 23.909 | +1.129 to +1.788 | +18.36 | +10.43 to +24.26 | +1.59 | −18 |
| 2512 | 23.872 | +0.713 to +1.882 | +12.43 | +4.28 to +18.86 | +1.07 | −12 |
| 2604 | 23.926 | +1.223 to +2.403 | +12.47 | +7.14 to +20.49 | +1.08 | −12 |
| 2609 | 23.900 | +0.546 to +1.321 | +14.98 | +7.92 to +20.91 | +1.29 | −15 |

Positive slope means the clock is gaining time. These nominal proposals are
**not applied**; all boards were last verified at TRIM 0. Uncertainty-implied
correction ranges are −24…−10 (2205), −19…−4 (2512), −20…−7 (2604) and
−21…−8 (2609), so the nominal integer is not a proven optimum.

The fit allows a free initial UTC intercept. It uses least-squares midpoints
projected into the set of constant-rate lines compatible with every reading's
bounds. Bounds include RTC quantization, serial brackets, NTP reference and
baseline uncertainty; they are deterministic measurement bounds, **not 95%
confidence intervals**. Residual RMSE is approximately 0.135, 0.141, 0.140 and
0.161 seconds for the table's board order. Residuals and the sample SD of
correlated cumulative-rate estimates are not independent clock-jitter measures.
The data does not establish an isolated battery-mode or temperature effect.

## Power intervals and continuing validation

The extended soak scope is **2604 (65C02) and 2609 (816 emulation)**. Functional,
interrupt, preservation and controlled-recovery checks remain qualified on all
four boards. No 48–72-hour extended soak is claimed for 2512 or 2205.

Three additional read-only MAINT/time exercise windows passed on the soak pair
on October 10: 11 rounds each, then 83/82 rounds on 2604/2609, then 146 each.
Their final window completed about **05:44:50 CDT**. Complete flash hashes,
clock/trim/identity state and ready monitor returns passed. These were bounded
exercises, not completion receipts for a 48–72-hour run.

Soak/retention validation remains ongoing. User-reported main-power intervals
include approximately 03:39–04:16 and 12:18–14:16 CDT October 10. Exact electrical
transition times were not measured, and the comparison intervals include
powered-on portions. Hardware power-fail timestamps are not used to infer
second-precision cycle timing or a standalone battery slope.

After the latest fresh snapshot, the user confirmed **all four boards powered
off at 18:13:03 CDT**, keeping RTC backup batteries connected. This is the
confirmation-received time, not an exact measured switch-off time. The current
validation segment is battery-backed retention, not an active powered-on command
loop. The finite drift collection schedule has ended; no further snapshot is
scheduled. On power return, retain startup/outage evidence and take a fresh
post-outage check against the original baselines before considering calibration.

2604's foreign ordinary EEPROM history is deliberately preserved. HISTORY
reports $90 and its power-fail latch was retained; clock and SRAM retention
checks passed. Do not clear/accept/format evidence just to hide the condition.

## Acceptance and provenance

The **48–72-hour powered-on hardware soak is still an open acceptance gate**.
This summary records continuing exercises/retention work rather than certifying
that duration. After power returns, the final acceptance record must state the
actual powered-on observation period, planned outages, checks, failures and
preservation results. Final RC ZIP/installer verification also remains pending;
the published downloadable release remains beta4.

Owner-local source receipts are:

- `output/qualification/rtc-residual-drift-2026-10-10-231032Z/summary.json`
- `output/qualification/rtc-zero-trim-campaign-2026-10-09-231026Z/baseline-index.json`
- The campaign's `history-exclusions.json` and `power-cycle-events.jsonl`
- `output/qualification/short-soak-2026-10-10-093104Z`
- `output/qualification/short-soak-2026-10-10-093550Z`
- `output/qualification/short-soak-2026-10-10-100243Z`

See the [technical guide](STR8N_V2_BETA23_TECHNICAL_GUIDE.md),
[four-board qualification](STR8N_V2_BETA23_FOUR_BOARD_STORAGE_2026-10-09.md),
[campaign policy](STR8N_RTC_ZERO_TRIM_CAMPAIGN_2026-10-09.md) and
[RC gates](STR8N_V2_RELEASE_CANDIDATE_PLAN_2026-10-09.md).
