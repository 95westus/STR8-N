# DBG1 board and offline test results

## Current v1g status

The current `v1g` image includes MAINT compatibility and BRK `$82/$84` fixes.
Its firmware SHA-256 is
`6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b`.
Offline qualification and hardware requalification passed on 2604 and 2609
in both MON A/B before and after rollback/reinstall. The
[v1g hardware report](../../output/qualification/rc1-dbg1-v1g-hardware-requalification-2026-10-19-222241Z/report.json)
records 144 registration scenarios, 168 focused `$82/$84` cases, 128 breakpoint
hits and 88 device-verified transfers. Both full original application RAM images,
flash contents and settings were verified at that completed hardware closeout.

R3 closed cleanly after 3,387.5 seconds, with 42/41 cycles and 672/656
breakpoint hits on 2604/2609; original RAM, flash/settings and final drift passed.
R4 also closed cleanly: 156/154 cycles and 2,496/2,464 hits on 2604/2609,
with one periodic checkpoint and final restoration/drift passed. The current
ten-pattern LED R6 continuation passed 93 new offline checks, 16 CPU-model
onboard assemblies, four full 630-frame LED executions and both-board hardware
preflight. Hardware preflight covered all four LED seeds plus a complete cycle
per board: five LED executions, 3,150 frames and 50 completed patterns per board,
entry-LED restoration and unchanged CRA/DDRA. Both original full RAM images,
all flash/settings, preserving drift and post-drift RAM rereads passed before
launch. R5 closed separately with 7/6 cycles, 3,640/3,120 LED frames and 112/96
hits on 2604/2609; its original-phase checkpoint and final restoration/drift
passed. R6 then closed cleanly at owner STOP after **12,803.703 seconds of
monitored/active workload**, plus 216.041609 seconds of final safe closure
(13,019.862814 seconds total worker wall time). 2604 passed **61 cycles,
38,430 LED frames, 610 patterns and 976 breakpoint hits**; 2609 passed
**60 cycles, 37,800 frames, 600 patterns and 960 hits**. There were zero R6
periodic checkpoints, no actual workload failures and no snapshot retry.
Both original full 25,344-byte RAM images were restored and reread after final
drift, with all flash/settings unchanged. Actual worker exit was verified.
Final offsets were **+1.221858 s** (2604, interval +0.797302 to +1.646414 s)
and **+0.660544 s** (2609, +0.281434 to +1.039653 s). Baseline/recovery anchors,
rate intervals and source hashes remain in [current status and exact evidence](DBG1_CANDIDATE_STATUS.md).
Immutable distribution r7 packages the reviewed closeout and checksums.
The owner has approved scoped RC1 promotion; the passing snapshot is preserving drift collection,
not full RTC-endurance acceptance.

## Saved-register edit qualification

A separate later qualification passed PC/A/X/Y/P/SP in MON A and MON B on both
boards, using unchanged v1g firmware. The
[aggregate report](../../output/qualification/rc1-v1g-register-edits-qualification-r1-2026-10-20-225008Z/report.json)
binds the per-board receipts and independent preservation audit.

| Board | CPU | Parser checks | Actual resumes, including S/N then C | Unsafe-PC refusals |
| --- | --- | ---: | ---: | ---: |
| 2604 | 65C02 | 2,876 | 110 | 66 |
| 2609 | 65C816 E=1 | 2,876 | 110 | 66 |
| Total | | 5,752 | 220 | 132 |

Each slot passed 1,438 parser checks, 55 resumes and 33 unsafe-PC refusals;
the resume count includes 48 edited-register S/N-then-C executions combined.
All byte values were parsed; hardware resumes kept IRQ masked and used
stack-safe SP values, with exhaustive P/SP resumes modeled separately.
Fresh repeated backups, both full 25,344-byte RAM restorations and two complete
RAM rereads per board passed. All four flash banks, settings, C/P/W and RTC
controls/trims matched; original MON B/2604 and MON A/2609 were restored.
2609 remained E=1 with DBR/PBR/direct page zero. Both workers exited with zero
actual test failures. RTC drift is outside release qualification; native mode
is excluded and the owner has approved scoped RC1 promotion. R6 retains query-only R coverage and immutable
r7 predates these tests. See [syntax and limits](DEBUGGER_GUIDE.md#editing-saved-registers).

## Historical v1e and v1f scope

The original installation and eight-hour soak evidence below belongs to
`v1e` firmware (`e3c7ae6247f23e579a2ffc31ea72986eb62611d22fc862da321371139ae6727a`).
Subsequent app regression found that MAINT rejected its DBG1 boot marker.
The corrected `v1f` firmware is
`923c8fee01310b873e89cc5e8982778e25fd425ccb9050735fb07604ef6228ba`.
Its offline suites and fresh hardware requalification passed in
`output/qualification/rc1-dbg1-maint-requalification-2026-10-19-1718Z`.
Both boards passed the corrected-image checks and rollback/reinstall.
The owner stopped that v1f six-hour run after 2 h 33 min 11.859 s; restoration
and final drift passed, but the planned six hours were not completed.
The original eight-hour receipts belong to `v1e` and do not qualify v1f or v1g.

The local **rc1 DBG1 generation-50 candidate** passed the bounded tests below
on October 18-19, 2026 (America/Chicago; receipt timestamps are UTC).
The published generation-49 rc1 tag, ZIP and source tree remain unchanged.
This is debugger installation/smoke and bounded soak evidence for **65C02 and 65C816 E=1**;
native applications and native debugging are outside scope.

## MAINT correction and requalification

The candidate builder now generates MAINT's four compatibility comparisons from
the same constant as the boot image. Strict rejection of mismatched markers is
retained. Only four comparison bytes in B2:8000 and the utility CRC in B2:D000
change from `v1e`; debugger size and application RAM capacity are unchanged.

Full offline suites passed on 65C02 (22 groups) and 65C816 E=1 (25 groups),
including both monitor boots, matching MAINT markers, refusal of each mismatched
marker byte and the legacy marker, and exact packaged debugger smoke. Actual
standalone install/rollback instructions were rehearsed on both CPU models;
stale source and corrupted transfers were refused before mutation. Registration
cases and documented ASM examples also passed on both models.

| Board | Runtime | MON A / MON B | Registration cases | Breakpoint hits | Final preference |
| --- | --- | --- | --- | --- | --- |
| 2604 | 65C02 | Pass / Pass | 36 | 64 | B |
| 2609 | 65C816 E=1 | Pass / Pass | 36 | 64 | A |

Each slot passed MAINT, ASM, UCHESS, SRAM, WORK, EDU and CLOCK checks both before
and after corrected-package rollback/reinstall. All 72 system/user registration
cases passed. BRK entry, shared D/M/U, C/S/N, all eight persistent breakpoints,
ninth refusal, clear and X/HOLD cleanup passed, with **128 breakpoint hits**
across initial and final checks. E=1 was observed before and after each 2609
slot's workload and during final cleanup.

Each board completed an old-candidate rollback (nine transfers), followed by
corrected-candidate install, rollback and reinstall (eleven transfers each).
All **84 transfers** were device-verified. Fresh repeated flash/RAM backups
preceded the transactions; all four flash banks matched each transaction target
after reset. Final cleanup verified all 25,344 original application RAM bytes,
original preferences/configuration, and preserved RTC control, trim, oscillator
and backup settings. Wear accounting advanced for the flash transactions;
preferences used journal appends during slot switching.

The final 2609 reset watch initially expired while physical action was pending;
it wrote neither firmware nor RAM. After the owner reported pressing RESET,
fresh B3 and identity checks were observed and final verification completed.
This operator-action wait is separate from the passing firmware/app results.

The run's `report.json`, per-board receipts and `evidence-checksums.json` contain
the detailed evidence. The prior candidate's failure and soak/drift records are
retained. The published rc1 release and prior candidate ZIP were not rewritten.

## Offline release review

This section records the historical v1f review. Both findings below were
subsequently corrected and requalified in v1g; see [current status](DBG1_CANDIDATE_STATUS.md).

The MAINT correction retains all four marker comparisons; the expected bytes
come from the same constant as the boot image. It changes exactly the four
comparison operands and utility CRC. It does not bypass the guard or change
debugger code, private entry addresses or application RAM capacity.

The existing registration evidence covers callback arguments/results, user
removal and missing valid IDs, sixteen user slots and seventeenth refusal,
four system slots and fifth refusal, independent capacity, duplicate and
protected IDs, invalid request/handler ranges, flags, nested BRK refusal and
HOLD cleanup. Hardware ran 18 scenarios in each slot on each board: 72
scenario executions. Each CPU model ran the same 36 slot/scenario combinations.

An additional boundary review ran 44 checks per CPU, across both slots. It
reproduced two issues: invalid `$00` removal can report success against an empty
user slot, and valid `$84` text ending at the application RAM limit prints but
returns an error and changes A/P. Twenty check executions reproduce these two
issues; the other 68 of the 88 checks pass. This includes valid/missing user
IDs, system ID/request boundaries, refusal during an active session and text
ranges that cross the RAM limit. The original passing suites did not cover
these exact edges. See the [debugger guide](DEBUGGER_GUIDE.md#candidate-review-status)
for the current correction and qualification status.

The v1f staging snapshot recorded these findings and then-pending six-hour
soak/drift qualification. It was not approved for promotion. Review and staging
use local file copies only; neither board nor the running soak's pinned inputs
are changed. Native applications/debugging remain excluded.

## Original candidate hardware results

| Board | CPU/runtime | MON A | MON B | Verified breakpoint hits | Restored preference |
| --- | --- | --- | --- | --- | --- |
| 2604 | 65C02 | Pass | Pass | 16 per slot, 32 total | B |
| 2609 | 65C816 E=1 | Pass | Pass | 16 per slot, 32 total | A |

Each slot ran the same four packaged scenarios:

1. Automatic `BRK 01` entry, shared D/M/U, S into/through JSR/RTS, N over
   ordinary instructions and JSR, C through another explicit BRK, then HOLD.
2. All eight persistent breakpoints in order twice, with saved-register
   checks; automatic rearming, original bytes visible while paused, ninth-slot
   refusal, individual/all clear, and final HOLD.
3. All eight set again, followed by X abort and cleanup verification.
4. `BRK 80` query returning without a stop until `BRK 03`, with A=`01`,
   X=`10`, Y=`04`, then C to HOLD.

All four combinations passed: **64 breakpoint hits across both boards**.
Loaded program bytes were checked after each HOLD/X for leftover patches.
2609 also passed six E=1 observations, including before/after each slot's
smoke: DBR, PBR and direct page zero, IRQ disabled and decimal clear. The RAM
observer records prior E with SEC/XCE while forcing E=1; it cannot enter
native mode. The unchanged startup CPU detector retains its existing behavior.

Each installation used fresh repeated reads of all four 32 KiB flash banks
and an application-RAM archive. All nine transfers were device-verified;
the owner then confirmed physical RESET. All four flash banks matched the
installation targets before preference changes. Slot changes used the
existing P/J3 software restart path.

After testing, all **25,344 original application RAM bytes per board** were
restored and checked byte for byte, and original preferences were restored.
Final repeated captures reverified all seven firmware sectors, preserved
other flash data/settings, and accounted for exactly nine erases per board.
Application RAM capacity and ASM buffers were unchanged. RTC controls, trim,
oscillator-start and backup-enable state were preserved; no clock/trim setter
was issued. At that initial checkpoint, soaks and periodic RTC sampling were stopped.

At this initial checkpoint, rollback plans were derived from each final fresh
capture and verified offline; they had not yet been executed on hardware.
Later hardware closeout and MAINT-fix requalification exercise rollback and
reinstall separately. If the board changes, capture
again and rederive a plan; old C/D journal images must not reset wear history.

## Eight-hour rc1/ASM/DBG1 soak and final RTC snapshot

The owner-authorized soak ran October 18, 22:52:18 through October 19,
06:52:42 CDT (03:52:18-11:52:42 UTC), **8h 00m 23.703s**, with no failures.
The common eight-hour deadline allowed the current safe unit to finish.
One worker alternated the boards; the soak used the preferred slot shown
below. The earlier smoke separately established both-slot coverage.

| Board | Runtime / soak slot | Passed cycles | Persistent breakpoint hits |
| --- | --- | --- | --- |
| 2604 | 65C02 / MON B | 431 | 6,896 |
| 2609 | 65C816 E=1 / MON A | 431 | 6,896 |

Every cycle exercised read-only rc1 commands and BATCH, real onboard ASM
with output checked against the tested RAM image before execution, BRK entry,
shared D/M/U, C/S/N, all eight persistent breakpoints twice, ninth refusal,
individual/all clear, X/HOLD cleanup, and BRK 80 query. E=1 and the supported
ABI state were observed before and after each 2609 cycle. Native applications
and native debugging were excluded; the startup CPU detector was unchanged.
At this historical v1e checkpoint, callback registrations were offline-tested,
not hardware-qualified. The later v1g hardware qualification is recorded above.

Fresh repeated full-flash and application-RAM backups preceded the soak.
Seven hourly four-bank flash comparisons per board and final four-bank
hash comparisons passed: firmware, settings and wear history were unchanged.
All **25,344 original application RAM bytes per board** were restored and
verified, then verified again after the drift snapshot. Application RAM
capacity and monitor preferences were unchanged. No flash, RTC clock, trim,
offset or persistent-setting write was issued.

The final NIST-referenced snapshot passed at 06:55 CDT October 19. Positive
offset means the board RTC was ahead of the reference; these are current
offsets, not eight-hour drift increments. Boards were sampled sequentially.

| Board | Reference UTC | Offset (seconds) | Offset bounds (seconds) | Trim |
| --- | --- | --- | --- | --- |
| 2604 | 2026-10-19 11:55:14.620468 | +0.950532 | +0.612121 to +1.288943 | -12 |
| 2609 | 2026-10-19 11:55:52.415133 | +0.545367 | +0.087614 to +1.003120 | -14 |

The original baseline index is unchanged. Against its original anchor, 2604's
accumulated drift interval is -0.303999 to +1.195532 seconds over 203,691.820s.
2609 uses its separate `2609-post-RTC-recovery-2026-10-18-r1` segment:
-0.564323 to +0.824579 seconds over 119,524.377s. This comparison does not
bridge the recovery clock setting or replace the original baseline. Both
intervals include zero; these measurements do not establish full RTC accuracy
or endurance qualification. Controls remained 0 on 2604 and 128 on 2609.

The workload ended and its follow-up monitor was paused after verification;
older soaks and periodic RTC sampling were not restarted. Local evidence:

- `output/qualification/rc1-asm-dbg1-soak-2026-10-19-034545Z/report.json`
- `output/qualification/rc1-asm-dbg1-soak-2026-10-19-034545Z/completion-audit.json`
- `output/qualification/rtc-campaign-snapshot-2026-10-19-115447Z/summary.json`

Distribution revision 2 includes portable public soak and drift summaries
with source-receipt hashes. Private RAM/flash captures and serial logs stay local.

## Offline scope and limits

The matching build passed 21 65C02 groups and 24 independent 65C816 E=1 groups,
including full boots and packaged smoke in both slots, 512 decoder cases per
CPU, and 177 direct instruction comparisons on the 816. Dynamic user/system
registrations, capacity/bounds, unregister and nested-BRK refusal were tested
offline. The board smoke exercised query `$80`; it did not qualify callback
registration or all BRK services on hardware.

The documentation audit additionally assembled and executed the four marked
examples (C/S/N, eight breakpoints, user register/unregister, system registration)
in both slots on both models: **16 example executions**. Those runs passed
22 65C02 groups and 25 816 E=1 groups, including the existing complete suites.
They produced separate `debugger-test-manuals.json` and
`debugger-test-65c816-e-manuals.json` reports; historical board/model receipts
were retained. The firmware bytes were unchanged. Reproduce after building
the candidate and its board package as described in the candidate README:

```text
python tools/test_rc1_debugger.py --build BUILD/rc1-debugger-v1e --smoke-package BUILD/rc1-debugger-boardtest-r1 --manuals docs/rc1
python tools/test_rc1_debugger.py --build BUILD/rc1-debugger-v1e --cpu 65c816-e --smoke-package BUILD/rc1-debugger-boardtest-r1 --manuals docs/rc1
```

A separate 21-check package model exercised actual RAM installer/rollback
instructions on both CPUs, stale-source and corrupt-transfer refusal, and
host smoke/restoration guards. Model hash ranges were accelerated. This does
not establish electrical timing, interrupted-write recovery, general occupied-
bank upgrades, native-mode behavior, or full endurance/RTC qualification.

## Reproducible identity and local evidence

| Artifact | SHA-256 |
| --- | --- |
| `BUILD/rc1-debugger-v1e/firmware.bin` | `e3c7ae6247f23e579a2ffc31ea72986eb62611d22fc862da321371139ae6727a` |
| `BUILD/rc1-debugger-boardtest-r1/board-test-manifest.json` | `3287d719b703b1ae87300c05ffba9fe803594995e4a9156781c03c86d4fb0e9c` |
| `BUILD/rc1-debugger-boardtest-r1.zip` | `8543c8718479df6e6db4a90bfdc6b30f5cf931e3739c42d446654ac6bbc212e2` |

Local receipt roots, relative to the repository:

- `output/qualification/rc1-debugger-2604-boardtest-2026-10-19-024408Z`
- `output/qualification/rc1-debugger-2609-boardtest-2026-10-19-030225Z`

Each contains the combined `report.json`, `before`/`after` captures,
`install-receipt`, `flash-check`, `smoke-A`, `smoke-B`, `RAM-restored`, and
an unexecuted `rollback` plan. Private board captures/logs remain local and
are not part of the public manuals or published rc1 ZIP.

Candidate source/build and exact experimental install/rollback procedure:
[DBG1 candidate](../../release/candidates/rc1-debugger/README.md) and
[board-test procedure](../../release/candidates/rc1-debugger/BOARD_TEST.md).

## Owner-approved distribution r8

The owner authorized staging, archive/checksum verification, the related Git
commit and scoped RC1 promotion. The new package includes the separate R-register
qualification: 5,752 physical parser checks, 220 resume cases and 132 expected
unsafe-PC refusals across both boards and both monitor slots, with original RAM
restored and flash/settings unchanged. Supported runtimes are 65C02 and 65C816
E=1; native applications/debugging are excluded. **RTC drift is not part of
release qualification and is not a promotion gate.** Historical RTC records and
prior held archives retain their original scope and bytes. See the
[release policy](../../release/candidates/rc1-debugger-brkfix-r1/release-policy.json) for the owner decision.
