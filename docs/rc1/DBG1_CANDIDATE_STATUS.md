# DBG1 v1g current candidate status

Status reconciled on October 20, 2026 (America/Chicago). **Promotion is held.**
Scope is RAM debugging on **65C02 and 65C816 E=1**; native applications and
native debugging remain excluded. Published generation-49 rc1 is unchanged.

## Current firmware and qualification

`v1g` is the internal build label for the generation-50 DBG1 candidate,
displayed as `2.0rc1`, ASM 0.5 and BRK ABI 1. It includes the MAINT compatibility
correction and the `$82` invalid-user-ID and `$84` final-RAM-byte fixes.
Its firmware SHA-256 is
`6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b`.

Offline qualification and hardware requalification passed on 2604 and 2609
in both MON A and MON B, including rollback/reinstall, supported apps,
system/user registrations, BRK entry, shared D/M, C/S/N and all eight persistent
breakpoints. The [hardware report](../../output/qualification/rc1-dbg1-v1g-hardware-requalification-2026-10-19-222241Z/report.json)
records 144 registration scenarios, 168 focused `$82/$84` cases, 128 breakpoint
hits and 88 device-verified transfers. Original application RAM and preferences
were restored at that hardware closeout. Those restorations describe the
completed hardware tests. R4, R5 and the ten-pattern R6 continuation have since
closed safely. R6 verified both original full application RAM images restored
and reread after final drift, with all flash/settings unchanged. Its worker has exited.

The frozen install kit's preparation-time qualification flags and older
distribution snapshots retain their original values. Current acceptance is
bound to the later receipts; frozen inputs are not edited to change their flags.

## Ten-pattern LED continuation r6: owner-stopped and verified

The owner-authorized run is
`rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z`.
Its offline admission, fresh backups and expanded hardware preflight passed on
both boards. The owner requested cooperative STOP at **22:12:41 UTC on
October 20**; the workload closed cleanly. The
[current soak pointer](../../output/qualification/rc1-asm-dbg1-soak-current.json)
selects this exact stopped R6 run. Promotion stays held; firmware and installer bytes
are unchanged.

| Identity | Recorded R6 value |
| --- | --- |
| Worker PID, now exited | `15812` |
| Process created | October 20, 13:40:31.666029 CDT / 18:40:31.666029 UTC |
| Launch receipt | `2026-10-20T18:40:31.7521265Z` |
| Workload started | `2026-10-20T18:40:31.997762+00:00` |
| Frozen runner SHA-256 | `32a8d4f381f121660bcb4befebb77b9628879ae6b85e749828a3ac105e63d4f7` |
| LED module SHA-256 | `06314fba6929c051a4f5be8d5741d4364fd2893dd8eca99adcfac771a1fe3d89` |
| Canonical LED cases SHA-256 | `6e00c0f8648cf508bf0915022f270a51d792d10194f583968f6ca1352922b266` |
| Final admission SHA-256 | `344c0d8d71b92b51d646c6986e112acc1b40cd8398209ac641641df8b886f62a` |
| Original campaign drift epoch | October 20, 05:16:03 CDT / 10:16:03 UTC; unchanged from R4 |
| Scheduled first R6 drift boundary | October 20, 17:16:03 CDT / 22:16:03 UTC; workload stopped before it |

The [launch receipt](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/launch.json),
[verified process identity](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/process-identity.json)
and [final status](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/status.json)
retain the identity and recorded final state. Passed per-board unit receipts,
rather than PID presence, establish completed work. The
[dated startup verification](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/startup-check-current.json)
confirmed **two completed full cycles, 1,260 LED frames, 20 completed patterns
and 32 persistent-breakpoint hits on each board** at October 20,
**13:47:54 CDT / 18:47:54 UTC**. Its
[frozen status snapshot](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/startup-status-snapshot.json)
and successful unit receipts show both LED seeds (`$12`, `$25`) advanced,
configuration/preference/wear responses matched, and 2609 remained E=1.
The [supervision receipt](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/supervision.json)
and [runtime integrity audit](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/monitor/heartbeat-2026-10-20-184754Z-runtime.json)
bind that dated result to the exact process, successful units and unchanged
pins. That dated startup result is separate from the verified final closure below.

The [launch verification history](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/launch-verification-history.json)
records correction of the host helper's typed-timestamp comparison and a
preflight-to-running operation-marker reconciliation. These metadata corrections
did not restart the worker, change pinned inputs or represent a hardware failure.

### Verified final workload and drift

The [final closeout](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/monitor/final-closeout.json)
has SHA-256 `b19ab0895b3b6c1b1de1487d61a90a21a51d8b24c2efe1142a3a16e1a8695883`.
It binds the [final worker report](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/report.json),
[actual process-exit verification](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/worker-exit.json)
and every successful cycle receipt. No actual workload failure, RAM-restoration
failure or final-snapshot retry occurred. No workload or periodic sampler was restarted.

| Board | CPU / selected slot | Passed cycles | LED frames | Completed patterns | Persistent breakpoint hits |
| --- | --- | ---: | ---: | ---: | ---: |
| 2604 | 65C02 / MON B | 61 | 38,430 | 610 | 976 |
| 2609 | 65C816 E=1 / MON A | 60 | 37,800 | 600 | 960 |

Both boards covered all 40 rotating ASM sources. Monitored and active workload
were both **12,803.703 seconds (3 h 33 min 23.703 s)**. The final safe closure
was a separate **216.041609 seconds**; total worker wall span from start to
finished was **13,019.862814 seconds**. The worker finished at
**22:17:31.860576 UTC** and actual exit was verified at **22:17:58 UTC**.
R6 completed **zero periodic checkpoints and one final checkpoint**. Its owner
stop preceded the next original-phase boundary; final drift occurred during
safe closure. This records its actual scope, not a fixed four/eight-hour pass.

Both original full **25,344-byte** application RAM images were restored,
host-verified and reread after final drift. All four flash banks, configuration,
monitor preferences/wear observations and RTC controls/trims matched. 2609
remained E=1 before and after every unit and during final restoration.

| Board | Reference UTC, October 20 | Offset seconds | Offset interval seconds | Rate interval ppm |
| --- | --- | ---: | --- | --- |
| 2604 | 22:16:28.739642 | +1.221858 | +0.797302 to +1.646414 | -0.362950 to +4.743935 |
| 2609 | 22:17:06.292456 | +0.660544 | +0.281434 to +1.039653 | -1.523459 to +3.540781 |

The [final drift summary](../../output/qualification/rtc-campaign-snapshot-2026-10-20-221601Z/summary.json)
has SHA-256 `50a87a5aeaa358dd37edcb7ae9057a21250caa7222e742055f06951b572fdc15`.
The [immutable RTC baseline index](../../output/qualification/rtc-four-board-snapshot-2026-10-17-031840Z/baseline-index.json)
retains SHA-256 `5db3f89e0bcdd1ec1bd9d1958c6abbc8530977783a2f1bb195bc80220af4913e`.
2604 compares with its original baseline; 2609 compares with the preserved
[recovery anchor](../../output/qualification/2609-RTC-owner-recovery-2026-10-18-r1/report.json)
in `2609-post-RTC-recovery-2026-10-18-r1`, without replacing the original baseline.
The passing preserving collection does not establish the separate full RTC
endurance/rate qualification gate.

### Qualification and exact scope

The [R6 admission](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/admission.json)
records **93 new offline checks**: 22 LED protocol/oracle tests, 26 worker
policy tests and 45 CPU trace/write-allowlist guards. Final admission binds
72 source files, 41 external evidence receipts and 95 workload pins. Actual CPU
qualification performed **16 onboard-ASM assemblies and four full 630-frame LED executions**
across both CPUs and both monitor slots. Each of the four seeded images was
assembled in all four CPU/slot combinations; the images are byte-identical
across those combinations, and each seed executed once in the four-scenario
matrix. All ten timed segments ran with real delay instructions, without
acceleration. See the [CPU model join](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/LED-model-join.json).
The 48 earlier broader-workload checks, four full-utility CPU-model units,
16 built-in RAM-program executions and 160 isolated ASM model executions are
**inherited**, not newly executed R6 tests. The earlier three-pattern LED
qualification is also [separate inherited evidence](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/inherited-LED3-qualification.json);
it does not qualify the new ten-pattern images. The
[qualification history](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/offline-LED-qualification-history.json)
retains the offline policy-test fixture correction and earlier harness history.

The [fresh-backup receipt](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/fresh-backups.json)
and [hardware preflight](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/hardware-preflight.json)
record passing checks on both boards: all four LED seeds plus one complete new
workload cycle, totaling **five LED executions, 3,150 frames and 50 completed
patterns per board**, with 16 debugger breakpoint hits per board from the
complete cycle. LED execution took about **12.625-12.641 seconds** per program
on hardware, within the admitted 10-25 second bounds. Both full original
application RAM images were restored and verified, all four flash banks/settings
matched, and preserving drift plus post-drift full RAM rereads passed before launch.
The [preflight drift summary](../../output/qualification/rtc-campaign-snapshot-2026-10-20-183835Z/summary.json)
has SHA-256 `78b3909f7d81031a29cfe28468e1f866d2c0f332f2aecbef2471461d6f5f63b5`.
These preflight results remain separate from the final restoration/drift evidence above.

Each R6 cycle included preserving rc1 base commands and all installed utilities,
one rotating source from the original **40-source ASM suite**, every built-in
BRK **`$80-$84` in each unit**, system/user registration and `$82/$84` edge
cases, and full debugger smoke with **16 persistent-breakpoint hits**. It also
assembled and executed one of **four seeded LED sources**, each displaying all
**ten patterns / 630 frames**: wigwag (8), Gray code (256), binary counter (256),
walking one (16), walking zero (16), bouncing dot (14), checkerboard (8),
fill/drain (16), expanding/contracting pairs (8) and seeded LFSR sparkle (32).
Source, exact emitted image, every write/readback frame, entry-latch restoration
before BRK and HOLD cleanup were checked. Only LED data `$7FA0` is additionally
writable; the application does not write CRA or DDRA. MON B remains selected
on 2604 and MON A on 2609, with 2609 E=1 before and after each unit.

The debugger's implemented command names are covered by C/S/N, shared D/M/U,
B/BC/X smoke and added help, bare R register queries and F function inspection.
This does not claim arbitrary register-edit parser forms. See the
[exact workload contract](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/workload-scope.json).
Utility operations exclude persistent command forms, CLOCK BATTERY and its
policy-record path, SRAM reclaim/format, WORK resize/upgrade/repair, EDU mode
changes and resets. Documented uninitialized SRAM/WORK query refusals are
classified without initialization or repair. The inherited resident SRAM
query path can perform exact XOR-`$FF` probe/restore pairs only at reserved
external SRAM `$1FFFF`; CPU qualification verifies the full array and mode
unchanged. This grants no general storage-write permission and forbids SRAM
mode writes, EEPROM/RTC/flash writes and unrelated SRAM writes.

R6 was authorized until owner STOP with preserving drift **every four hours
on R4's original campaign phase**. It reached no periodic checkpoint before
owner stop; its final checkpoint restored both full RAM images, checked
flash/settings, collected drift and reread both original images. The immutable
RTC baseline and separate `2609-post-RTC-recovery-2026-10-18-r1` segment were
preserved. The worker has exited; no workload or RTC sampler was restarted.

HOLD must clear ACTIVE, BUSY, RUNMODE and REG_VALID (`$7BFC-$7BFF`);
invalidated physical registry slots may retain stale bytes and are not required
to be erased. Native applications/debugging remain excluded.

## Separate historical results

- The original `v1e` eight-hour soak passed 431 cycles per board. Later MAINT
  regression required the `v1f` correction; those eight-hour results do not
  qualify `v1g`.
- The owner stopped the `v1f` six-hour run after 2 h 33 min 11.859 s and the
  earlier fixed three-hour `v1g` run after 6,006.453 s. Their restoration and
  final drift checks passed, but neither completed its planned duration.
- Continuing `v1g` R1 stopped after two cycles per board on the harness's
  incorrect physical-registry-ID-zero assertion. R2 passed its hardware
  regression, then rejected newline-normalized fixtures before its first
  cycle. Both attempts restored original RAM and passed closing drift checks.
  R3 corrected the lifecycle assertion, copied fixtures byte-exact and verified
  every workload pin before board access and before launch. Firmware is unchanged.
- The owner stopped R3 cleanly after **3,387.5 seconds (56 min 27.5 s)**.
  2604 completed **42 cycles / 672 breakpoint hits** and 2609 completed
  **41 cycles / 656 hits**. Both full original application RAM images were
  restored and reread after the passing final drift snapshot; all flash/settings
  matched. No four-hour periodic checkpoint was reached. This closed R3 scope
  does not qualify later broader or LED-expanded workloads.

- R4 closed cleanly for the LED scope transition after **26,678.906 seconds**
  monitored: **26,462.828 seconds active workload** and **216.078 seconds in
  its periodic checkpoint**. 2604 completed **156 cycles / 2,496 hits**;
  2609 completed **154 cycles / 2,464 hits**. Its one periodic checkpoint and
  final restoration/drift both passed, including original full RAM rereads and
  unchanged flash/settings. These are R4 results, not ten-pattern R6 LED-soak results.

- R5 closed cleanly for the ten-pattern scope transition after **1,516.938
  seconds** monitored: **1,292.703 seconds active workload** and **224.235
  seconds in its periodic checkpoint**. 2604 completed **7 cycles / 3,640 LED
  frames / 112 hits**; 2609 completed **6 cycles / 3,120 frames / 96 hits**.
  Its periodic checkpoint followed the original R4 campaign phase; this is
  not a claim of four hours of R5 workload. That checkpoint and final drift
  passed, with both original full RAM images restored/reread and unchanged
  flash/settings. These results describe the earlier three-pattern scope.

The [r3 prior-attempt record](../../output/qualification/rc1-asm-dbg1-v1g-continuing-soak-r3-2026-10-20-083000Z/previous-failed-continuation.json)
and [prior fixed-run safe stop](../../output/qualification/rc1-asm-dbg1-v1g-continuing-soak-r3-2026-10-20-083000Z/prior-safe-stop.json)
preserve the earlier separate outcomes. The [R3 closure receipt](../../output/qualification/rc1-v2-base-utils-asm-dbg1-v1g-continuing-soak-r4-2026-10-20-093805Z/previous-continuation-closure.json)
and [R3 final drift](../../output/qualification/rtc-campaign-snapshot-2026-10-20-094045Z/summary.json)
record its actual completed scope. The [R4 safe-stop report](../../output/qualification/rc1-v2-base-utils-led-asm-dbg1-v1g-continuing-soak-r5-2026-10-20-172528Z/prior-safe-stop.json)
and [verified R4 closure](../../output/qualification/rc1-v2-base-utils-led-asm-dbg1-v1g-continuing-soak-r5-2026-10-20-172528Z/previous-continuation-closure.json)
preserve that transition. The [R5 safe-stop report](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/prior-safe-stop.json),
[verified R5 closure](../../output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z/previous-continuation-closure.json)
and [R5 final drift](../../output/qualification/rtc-campaign-snapshot-2026-10-20-182504Z/summary.json)
record its separate outcome. No prior run is substituted for R6 qualification.

## Package closeout and promotion hold

The immutable [distribution r7 archive](../../output/release/staging/str8n-v2.0rc1-dbg1-v1g-candidate-r7-staged.zip)
and adjacent [archive checksum](../../output/release/staging/str8n-v2.0rc1-dbg1-v1g-candidate-r7-staged.zip.sha256)
package the verified closeout. Archive SHA-256 is
`8e3d1f901fe9bcbb4ae15a83214be0999e746bdf4f088e8c9b308f345a47b528`.
The [package report](../../output/qualification/rc1-dbg1-v1g-r7-staging-2026-10-20-223000Z/package-report.json)
records full/extracted verification of 215 files and 164 Markdown links/anchors.
Manifest SHA-256 is `a55b4da98b6c43d4b1a6b141c68ad98ef8f92d9adea629f572347e8619927dcf`.
The [staging pointer](../../output/qualification/rc1-dbg1-v1g-staging-current.json)
identifies the latest packaged snapshot.

Distribution r7 corrects one operator-summary timing sentence in the prior
immutable r6 archive: final drift followed owner STOP during safe closure.
Counts, detailed timeline, firmware/installer bytes and source receipts were
already correct. This was a documentation wording issue, not a hardware failure;
the prior r6 archive and both reviewed overlays remain unchanged.

This package is prepared for the authorized selective Git commit. Firmware,
installer bytes, tested manuals, immutable RTC anchors and frozen evidence are
preserved. Private board RAM/flash captures, serial logs, secrets and transient
output are excluded from the release and commit. Prior r5 and earlier archives
retain their historical scope. Promotion requires a separate owner decision
and remains held; no publication or firmware change is implied by packaging.
