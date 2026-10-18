> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# Separate native/CLOCK BATCH candidate

Candidate **batchfix-r1**, display **2.0bf1**, generation **48**, CLOCK **1.11**.
This internal candidate identity does not allocate a published beta36 release.
The initial authorization covered offline development. The owner later authorized
2604 installation/checks and its preserving soak, followed by graceful shutdown
of the 2512 workload soak. Beta35 remains generation 47,
B-target scoped, with its payloads/review archives unchanged.

Source and build instructions: [candidate README](../release/candidates/batchfix-r1/README.md).
Owner-local progress: `output/qualification/batchfix-r1-current.json`.
General installation and release qualification remain false. The 2604 test
installation has separate explicit owner authorization and hardware evidence.

## Problem and changes

STR8N-007's native/CLOCK guards bound the BATCH interface to active page B0.
The experimental A monitor therefore fell back to interactive readers and
left queued commands unconsumed. The CLOCK launch path also lacked admission
in the old engine, so its existing BATCH reader hooks could not be exercised
through a normal `BATCH R CLOCK;...` sequence.

This separate candidate introduces a versioned private provider profile
UX/3/42 and a new checked RAM capability marker BA. Both monitor slots accept
only that provider profile and its full seal before publishing BA. The RAM
gate recognizes BA; native/CLOCK predicates validate A0/B0 and gate entry
opcodes. The old B9 capability remains accepted only for legacy B. The storage/
status dispatcher is updated to recognize the new provider profile as well.

Only exact `R CLOCK` / `R 1 CLOCK` launch forms are added to BATCH admission.
Wrong banks, extended names, arguments and arbitrary applications remain
refused; the BT/1/1 registered-application header still gates launch. Native
line, error, cancel and application-admission hooks use the shared predicate.
CLOCK's local predicate follows the same contract.

Deliberate padding preserves the private reader/engine addresses used across
modules. The fixed E/F recovery code and public RAM ABI remain unchanged.
The candidate requires a coherent component set and a future qualified update
plan; do not infer safety of arbitrary partial component installation.

## Evidence and retained failures

Two independent clean source builds perform 27 links each and reproduce all
19 artifacts byte for byte. The five changed source files are identified in
the candidate derivation/provenance records; unchanged outputs match beta35.

Linked admission tests pass 26 cases, covering exact CLOCK forms and malformed
registered-application headers in both slots. The full fake-device model
checks both-slot utility/CLOCK handoff, error/cancel paths, unsupported ASM,
mixed provider/monitor profiles and invalid-monitor fallback. Read the current
receipt for completed case counts; do not treat an in-progress run as a pass.

Initial failed runs are retained. The first guard change exposed the storage/
status dispatcher's old profile check; the next run confirmed native A handoff
and exposed CLOCK launch refusal. A subsequent assembly caught a short branch
that needed explicit long-branch expansion after CLOCK admission was added.
No failure was hidden by changing a comparison fixture or frozen beta35 code.

## Remaining qualification

The initial candidate model checkpoint now passes 25 scenario checks, with
18 explicitly reused completed checks and seven fresh continuation cases.
All 26 linked name/header admission checks pass. Both independent source
builds reproduce the same 19 artifacts. No hardware qualification is inferred.

Initial model success does not qualify broader upgrades, both-slot migration,
electrical interruption, physical restoration/full readback or native CPU
execution. Those need their own candidate-specific evidence and authorization.
That initial offline checkpoint did not access a board.

## October 17 hardware checkpoint and soak handoff

The owner-authorized 2604 installation used the separately modeled B-first then
A route and separate 585-byte A/B reservation helper. The owner confirmed both
physical RESETs. Both slots passed 11 initial hardware check groups each:
native/CLOCK BATCH success/error paths, native Escape cancellation, ASM/RAM
execution, varied LEDs with restoration, exact four-bank readback, EEPROM/
power-event/EUI preservation, full retained SRAM comparison and application
RAM restoration. RTC trim/control match the original baseline. These W65C02
checks do not establish native 816, electrical interruption or full release
acceptance.

2604 now runs the preserving bf1 soak from A, retaining verified bf1 B. The
2512 r5 beta35 workload stopped by request after 2,644 passed units and 77
completed 34-unit cycles; full RAM restoration and process exit were verified.
2512 stays powered on for RTC snapshots. 2205 and 2609 stay powered off. The
three-hour NIST schedule covers 2512 and 2604 against the unchanged original
four-board baseline. Clocks/trims are unchanged; ACIA and crypto remain deferred.

Evidence: `output/qualification/bf1-2604-hardware-current.json` and
`output/qualification/bf1-2604-hardware-2026-10-17/soak-handoff.json`.
The new runner is `tools/run_bf1_2604_soak.py`; resolve its current run from
campaign state. Do not restart the intentionally stopped 2512 workload.

## Extended offline recovery checkpoint

The separate continuation passed 49 selected A-install and two-stage
restoration interruption states, with boot/recovery/boot checks for each.
It freshly executed 93 CPU transactions and 64 boots; 34 identical-input boot
checks explicitly reuse completed results. All 42 additional CPU transport
tests and 27 planner/replay refusal tests passed. Prior full phase proofs
remain labeled as reuse. Clean completed recovery performs no flash writes.

The checkpoint binds report and source hashes, archived harnesses, the initial
candidate/route/hardware receipts, unchanged 19 bf1 and 23 beta35 artifacts,
both prior review archives and the immutable RTC baseline. See
`output/qualification/bf1-offline-current.json` and
`output/qualification/bf1-offline-qualification-2026-10-17-r1/checkpoint.json`.

This is selected instruction-model interruption coverage, not electrical
power-loss qualification. Physical restoration, long-term accumulation,
broader candidate regression/manual review and release acceptance remain open.
General installation and release flags remain false.

The owner has explicitly deferred native 816 beyond bf1. It is outside the
current acceptance scope, together with ACIA and crypto, rather than an open
gate for this candidate. The processor execution claim is W65C02 only.
Historical checkpoints retain the scope that existed when they were recorded.

## bf1 manual/ABI gate

The separate [bf1 draft manuals](bf1/README.md) target generation 48, CLOCK
1.11 and ASM 0.5. The fresh W65C02 audit passed 26 checks: source/documented
addresses and buffer boundaries, public RAM calls with each bank selected,
paste and BATCH cancellation, command-error stopping, both-slot exact CLOCK
BATCH forms and unsupported ASM refusal, CLOCK query sessions, and fresh
manual-example assembly, S-record export and RAM execution in A and B.
All modeled persistent devices remained unchanged. These runtime results are
fresh bf1 checks, not relabeled beta35 example evidence.

The final editorial review resolves 30 local links and preserves the exact
example source. Exact CPU-audit drafts and final corrected prose are archived
separately. The acceptance policy is
`release/bf1-prerelease/acceptance-scope.json`; native 816, ACIA and crypto are
deferred. The receipt is
`output/qualification/bf1-manual-gate-2026-10-17-r1/checkpoint.json`.

The candidate-specific local review package gate subsequently passed. Physical
electrical interruption/restoration, long-term measurement accumulation and
explicit release acceptance remain open.

## Local review package and integrity gate

The final owner-local kit is
`output/releases/str8n-2.0bf1-local-review-2026-10-17-r2.zip`:
145 files, 97 source files, 19 artifacts, four guides and 36 resolved local
links. The 10-byte ASM example has checked A/B S-record exports. Only explicit
source/payload/document/helper inputs and stdlib review tools are included;
board captures, hardware launchers, vendor firmware and v2.1 sources are absent.

A fresh build from the first extraction performed 27 links and reproduced all
19 pinned artifacts. A fresh helper build reproduced its 585 bytes. The final
extraction has byte-identical firmware/helper build inputs; those fresh build
results are explicitly reused after a verifier-only correction, rather than
claiming another build. All 19 final integrity/refusal checks passed.

The first verifier accepted a broadened route description when its digest was
updated. The second requires the exact owner-approved 2604 migration scope and
preserving campaign policy. The original ZIP and failed test remain retained;
neither firmware nor helper source changed. ZIP hashes must be checked against
the separate receipt; the manifest is not a digital signature.

Evidence: `output/qualification/bf1-review-current.json` and
`output/qualification/bf1-review-gate-2026-10-17-r2/checkpoint.json`.
The latest checkpoint supersedes the earlier workflow queue's package task.
No further offline gate is pending in this scoped queue. Physical electrical
interruption/original-payload restoration, longer soak/RTC accumulation with
owner-selected acceptance criteria, and explicit release acceptance remain.
All general installation/publication/release flags stay false; native 816,
ACIA and crypto remain deferred. The prerelease automation stays paused;
independent soak and RTC schedules stay active.
