> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# bf1 accepted soak, RTC and prerelease policy

Owner accepted October 17, 2026. Target: **2.0bf1 generation 48**, CLOCK 1.11,
FT245/F30D; one pinned firmware set for 65C02 and 65C816 emulation runtime.
The unchanged startup CPU detector exception is accepted. Native 816 applications
and tests, ACIA and crypto remain deferred.

## Automated gates

| Gate | Accepted criteria |
|---|---|
| 2604 endurance | Both 72 monitored hours and 300 complete 34-unit workload cycles; continue running afterward. |
| 2609 pilot endurance | One four-hour monitored preserving soak, with complete workload coverage, no unexplained failures, and verified original application RAM restoration at safe shutdown. It then returns to RTC-only collection. |
| Functional preservation | No unexplained crashes, hangs, resets, assertions or BATCH failures; no unexplained persistent changes. Every LED sequence restores its original state. |
| RTC duration | At least 168 hours of measurements within each uninterrupted powered segment. Original four-board baseline remains immutable. |
| RTC performance | Entire uncertainty interval within -5 to +5 ppm, with uncertainty halfwidth no larger than 2 ppm. Five ppm is 0.432 seconds/day. |
| RTC collection | Three-hour snapshots on 2512/2604/2609; investigate sample age or collection gaps exceeding four hours. Retain failed/skipped attempts. |
| Closure | Exact candidate hashes, complete receipts, no unresolved failure or pending RAM restoration. |

Normal snapshot yields count toward the monitored soak window. Unmonitored
downtime does not. The checker flags receipt coverage gaps for review, rather
than inferring uninterrupted coverage from a PID alone. It uses actual reports,
not extrapolated cycle counts or combined totals across boards.

RTC estimates retain acquisition uncertainty and separate segments at reported
power returns. The seven-day gate starts with measurements in the current
powered segment; this does not replace the original baseline. Insufficient
duration or precision is pending; a target-overlapping interval is inconclusive
and requires longer collection. A stable rate outside the target calls for clock
performance review, without automatically attributing it to firmware. Clocks and
trims remain unchanged throughout these measurements.

## Tonight's GitHub prerelease

The owner authorized a **GitHub prerelease in 95westus/STR8-N** after the 2609
four-hour soak and verified RAM restoration pass, and subsequently required
**both 2512 WDCMONV2-to-bf1 and published v2.0b4-to-bf1 migration routes** to
pass separate offline and hardware qualification before publication. Both
routes have passed separate offline, hardware and restoration qualification
for their exact staged source profiles. The publication automation is
active again after the additional final 2512 bf1 load and preserving RTC
snapshot passed. The 2604
worker must remain healthy and required powered-on RTC streams fresh. The release must disclose that the
72-hour/300-cycle 2604 gate and seven-day RTC gates remain pending.

This is a scoped pilot prerelease, not full endurance or RTC qualification.
Full release qualification and generic installation permission remain false.
Publish the exact pinned bf1 binaries and their checksums, updated guides and
reproducible source provenance. No board backup, complete captured flash bank,
EEPROM/SRAM image, serial transcript or host-private data belongs in public assets.

The supported migration evidence covers the exact captured 2604 and 2609
lineages with separately admitted B-first/A-second transactions. The component
binary files are not whole-device programmer images or a generic stock/legacy
installer. No 2.1 payload or native-mode application support is included.

2609 passed original A40/B35 restoration and two owner-controlled interruptions
at verified transfer boundaries, with fallback boots, exact cut/recovery flash,
retained storage, E=1 runtime, BATCH and RAM restoration. These tests do not
qualify mid-erase/program loss, arbitrary byte timing or 2604 electrical behavior.

## Operation

2604 keeps soaking. 2512 is assigned for the two migration qualifications and
otherwise remains RTC-only. Its operation guard blocks incompatible RTC
collection during legacy-monitor or installation stages; skipped attempts are
retained and compatible sampling resumes afterward. 2609 returns to RTC-only after its
four-hour run. 2205 stays powered off. The acceptance supervisor runs every
15 minutes; RTC snapshots remain every three hours. Failed workers are not
automatically restarted. No reset, time/trim/settings change or manual ACK/CLEAR
is authorized by an acceptance check.

After both 2512 route gates passed, the owner requested that 2512 finish with
the complete shared bf1 firmware installed and verified. It remains powered
on for RTC sampling until the owner reports switching it off. Its final-load
installation/checks are separate from the already accepted migration and
restoration receipts; preserve the original RTC baseline across all phases.

The live policy, current assessment and release plan are retained locally under
`output/qualification`; public release notes state the concrete completed and
pending gates without publishing those local device records.

The owner subsequently reported 2512 powered off after its final bf1 checks
and preserving RTC snapshot. 2205 and 2512 remain off; no port access is
permitted until an owner power-return report. Three-hour RTC collection now
covers 2604/2609 only. Policy r4 retains all numerical RTC/soak thresholds and
both accepted migration gates, but suspends collection/freshness requirements
for owner-evidenced powered-off streams. Their old samples remain historical
and are explicitly not marked fresh. Publication still requires the completed
four-hour 2609 soak and RAM restoration, healthy continuing 2604 and fresh
2604/2609 samples. The separate publication automation remains active.
