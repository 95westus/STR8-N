> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# 2604 bf1 install and recovery preparation

The owner initially reported 2604 powered on October 17, 2026 and authorized a return
snapshot, preserving backups, offline bf1 route verification and drift analysis
combined with 2512. No firmware installation, reset or electrical interruption
was authorized by that initial instruction. The owner subsequently authorized
bf1 installation, initial checks, 2604's soak and graceful shutdown of the 2512
workload after successful handoff. ACIA and crypto remain deferred.

## Preserved return evidence

The immutable October 16 local-date four-board baseline remains registered.
The return snapshot reference is October 17 at 12:23:09.726 CDT, NIST
132.163.96.6. The baseline-to-return span is 14.046368 hours. RTC minus NIST
is +0.578373 seconds with acquisition bounds [+0.239505, +0.917242].
The change from baseline is +0.073608 seconds, bounded by
[-0.676615, +0.823830], or an endpoint mean +1.455651 ppm bounded by
[-13.380579, +16.291882]. These are uncertainty bounds, not confidence
intervals. Zero drift remains consistent. The span includes powered-on time
around the powered-off interval; it is not a pure powered-off rate.

The return acquisition restored its temporary RAM byte for byte. Trim -12
and control register 0 match the original baseline. User reports establish
approximate switch times; no precise outage duration is inferred.

Return measurement:
`output/qualification/rtc-campaign-snapshot-2026-10-17-172053Z/summary.json`.
Backup directory:
`output/qualification/2604-return-backup-2026-10-17-1724Z`.
The backup report must say `passed: true`, all three repeat checks true,
application RAM restored, and `restore-needed.json` must say `needed: false`
before any subsequent device work. An in-progress capture is not a completed
backup. Offline CPU modeling may use independently verified double-read
bytes while the separate backup worker finishes restoring application RAM;
its intake receipt explicitly records that distinction.

## Exact source and staged route

The captured source runs beta35 generation 47 in B. A is a valid beta28
generation 40 fallback. F is the registered F30D core and matches bf1 exactly;
E also matches. The private candidate is batchfix-r1 / 2.0bf1 generation 48,
CLOCK 1.11, UX/3/42. This is a separate candidate, not a change to beta35.

1. Admit the exact double-read source and every registered occupied range;
   reject altered preimages, unknown assets or incompatible E/F. Preserve B0,
   user payloads, all unowned sector bytes, EEPROM, SRAM and RTC settings.
2. Reserve all planned erase attempts durably before the first erase. Select
   original A40 as the transaction fallback. Stage the opposite C/D journal,
   install the complete bf1 shared component set and B48, commit CLOCK and
   monitor headers last, and select B48 only after the coherent set is complete.
3. After full verification of coherent B48, a distinct transaction can install
   A48 while retaining B48. Select A48 at final journal activation. This phase
   is necessary to exercise the original A-slot BATCH defect on hardware.
4. For original-payload recovery after both phases, first restore original A40
   while retaining coherent B48. Then retain A40 while restoring original
   B35/shared assets and original startup/EDU settings and boot preference.
   Preserve new journal sequence numbers and conservatively accumulated wear
   counts. Never flash the old C/D backup over newer erase history.

Legacy A40 and a partially updated shared provider are a monitor-console
fallback, not a claim that every native utility remains usable during an
interruption. bf1 private-provider capability is enabled only for a coherent
matching profile. Do not use arbitrary partial firmware installation.

## Offline proof and physical gates

`tools/plan_bf1_2604_route.py` and `tools/verify_bf1_2604_route.py` implement
the separate offline route. Serial constructors are forbidden in the model.
The distinct `release/candidates/batchfix-route-r1` RAM helper validates either
A or B fallback generation. The original beta35 helper accepts A only and
refused the first A-phase attempt before any mutation; that failure and its
diagnostic are retained. This helper extension does not modify bf1 firmware
or the frozen beta35 helper. The new validator has separate linked checks.
The retained 2604 bytes, candidate build, generated RAM image, transfers,
expected complete banks and mutation traces bind each case. Representative
cuts and replay-attested restoration are distinct from exhaustive interruption
coverage and physical power interruption.

Read the final route checkpoint for actual completed checks. A failed or
in-progress report does not qualify a route. Final backup completion must be
bound separately if modeling began during application RAM restoration.

The new-helper instruction-model run completed 28 checks in
`output/qualification/bf1-2604-route-2026-10-17-r2/report.json`. They cover
fresh-byte admission, five linked validator cases grouped in one check,
complete B then A installations, both-slot native/CLOCK BATCH, two-phase
original-payload restoration and restored B35 boot, four stale-bank refusals,
two corrupt-transfer refusals, four B-install mutation cuts with boot and
recovery for each, and altered recovery-preimage refusal. All 28 checks in
this run are fresh. The 585-byte helper independently reproduces in two
source builds. This does not repeat or relabel the earlier 25 generic bf1
scenarios or the failed original-helper run.

The four representative B cut positions are events 123, 23144, 27165 and
27289 of this exact transaction trace. Their meaning depends on this pinned
source, installer and transfer set; they are not universal electrical timing
boundaries. A-phase and interrupted-restoration cuts are not exhaustively
covered by this route run.

## Subsequent authorized hardware execution

Both B and A installations verified on 2604; the owner confirmed both physical
RESETs. Each slot passed 11 initial hardware check groups, including exact
full-bank flash readback, native/CLOCK BATCH success/error behavior and native
Escape cancellation, ASM/RAM execution, LED restoration, unchanged EEPROM and
all retained SRAM, and verified restoration of original application RAM.

The preserving bf1 soak now runs from A with verified bf1 B retained. The 2512
workload stopped gracefully after 2,644 passed units / 77 full 34-unit cycles;
RAM restoration and process exit were verified. 2512 remains powered on for
RTC snapshots. Current proof is
`output/qualification/bf1-2604-hardware-2026-10-17/soak-handoff.json`.

The subsequent offline continuation passed 49 selected cut states: 12 for the
A install, 12 for A restoration retaining bf1 B, and 25 for original B/shared
payload restoration retaining original A. Every cut passed selected-monitor
boot and replay-attested recovery followed by boot. Recovery preserves newer
sequence numbers and conservative erase counts; already complete clean states
are write-free no-ops. These are reservation/erase/header-commit boundaries and
their immediate predecessors in the pinned traces, not every programming byte.

The continuation freshly executed 93 cut/recovery CPU transactions and 64
boots, explicitly reusing 34 boots only for identical full bank/device inputs.
Another 42 fresh CPU transport tests passed stale-bank, corrupt-row and
partial-row cases across all three phases. All 27 planner/replay refusal tests
passed, including altered backups/traces, fallback overwrite, configuration
change and synthetic sequence/counter exhaustion. The three existing complete
phase proofs are explicitly reused rather than relabeled as fresh execution.
Bound reports and archived harnesses are linked from
`output/qualification/bf1-offline-current.json`.

Electrical interruption, physical recovery, broader candidate regression/manual
review and full release acceptance remain open. Native 816 is owner-deferred
outside this candidate's current W65C02 acceptance scope; ACIA and crypto remain
deferred.
2205/2609 remain off. Clocks/trims and the original baseline are unchanged.
The three-hour NIST schedule covers both powered boards and regenerates fresh
combined reports. No new baseline was created. ACIA and crypto remain deferred.
