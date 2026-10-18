> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# Beta35 automated prerelease work

Authorized continuation of the frozen 2.0b35 generation-47 prerelease, separate
from v2.1. Current machine-readable progress is owner-local:
`output/qualification/beta35-prerelease-state.json`. The existing clean-build
report and review ZIP remain sealed; new results are appended under new paths.

## Operating constraints

Keep the current 2512 soak, varied LEDs, hourly supervisor and three-hour NIST
snapshots running. Resolve the worker through the active RTC campaign's
`campaign_state` and `soak_run`; never assume a historical run is current.
Do not stop/restart it for offline work. Do not open serial ports in prerelease
jobs, reset boards, install firmware, alter persistent devices, SET/TRIM,
acknowledge power events or replace the baseline. 2205, 2604 and 2609 stay off.
ACIA and crypto remain deferred. Do not publish a release or mark electrical
power-cut/hardware gates passed from an emulator result.

Use Python 3.13 with pyserial installed. Model dependency/source hashes are
retained in the owner-local qualification freeze. Fresh installer rehearsals explicitly disable serial construction. Frozen
model workspace: `tmp/q35-034745`; its dependency/source hashes are retained in
the earlier qualification freeze. Use new short workspaces for WDC assembly.

## Ordered work queue

1. **Exact historical migration fixtures.** Run
   `tools/qualify_beta35_installer_model.py --board <id> --out <new-directory>`
   for all four boards. Each case needs exact final banks/sector order, retained
   A fallback, final monitor commit ordering, real linked FNV equivalence,
   stale-bank refusal, corruption refusal on every transfer, and incomplete
   transfer preservation. Bind all source/installer/payload hashes. Incomplete
   transfer tests are model receive interruptions, not electrical power cuts.
2. **Target-specific migration support matrix.** Inspect the current launcher,
   published b1/b4 routes and intermediate layouts against the exact beta35
   payloads. Preserve the distinction between source recognition, planning,
   model execution, historical board installation and fresh full readback.
   The existing four-board beta34 update replaces B34 in B and retains B28 A;
   do not describe it as preserving the previously active B34 monitor. Never
   infer b4 -> b35 from b4 -> b25. Record unsupported routes and concrete
   missing tests. Develop/test package-owned offline planning/conversion in
   a separate workspace if needed; target payload hashes stay frozen. Unknown
   sources and occupied destinations must refuse. Qualify both active slots,
   data/settings preservation, commit interruption and backup restoration.
   Passed prerequisites are 34 source-inspection cases, 79 logical B-target
   planning/refusal/backup-file cases, 24 semantic journal scenarios / 118,670
   byte states, and 25 standalone linked-helper checks including 123 program
   cuts. Reuse their receipts while inputs stay unchanged. The original logical
   proposal deliberately retains the old locator; the separate journal model
   explicitly reserves counts and stages A before selecting B35.

   The integrated separate model-only installer now passes 46 scenarios,
   including four exact archived fixtures, all-bank stale refusal, corrupt and
   partial transfers at all eight rows, and 22 mutation-boundary cuts. Evidence:
   `transaction-model-0927/report.json`. Its only original-template instruction
   patch is an explicit JMP through a separately linked reservation wrapper;
   bank payloads and the old ZIP remain sealed. Startup/EDU settings, fallback A,
   durable count bounds and activation ordering were checked after mutations.
   Counts reserve planned attempts and can overcount after interruption.

   Cold-boot and original-installer re-entry now pass on all 46 retained
   states: 92 state checks plus one explicit backward-date battery-policy
   diagnostic. Main virtual RTC is October 17; all persistent model devices
   stay exact. QA35-006 records the prior October 8 fixture's expected single
   uncertainty append on archived 2609 and a stable second boot. Boot/BATTERY
   must not be described as universally read-only. Evidence:
   `interrupted-boot-1028-r3/report.json`; earlier failures remain retained.

   Reversed C/D, activation-only and exact no-op instruction models now pass
   52 cases, including 32 mutation cuts. These are derived archived fixtures,
   not new board tests. Receipt-bound restoration planning passes 48 checks;
   42 saved upgrade states restore original bytes outside C/D while retaining
   count maxima and reserving additional erases. Linked restoration passes
   87 checks including 19 cuts; 20 complete cases reuse proven
   byte-identical model inputs. Evidence: `variants-restoration-checkpoint.json`.

   New variant/restoration state boot and stale-installer re-entry now pass
   258 checks (74 fresh boots; 55 exact-input boot reuses).
   Interrupted-restoration recovery passes 42 checks: 35 registered 2512
   interruption states plus seven refusals; 16 complete cases reuse identical
   CPU inputs. Recovered results pass
   34 boot checks (9 fresh; 25 identical-input reuses); the
   exact final no-op retains its already-tested parent. Original backup bytes
   and settings return while new sequences/count maxima remain durable.
   Evidence: `cut-boot-recovery-checkpoint.json`. This is registered-lineage
   model coverage, not arbitrary damaged-source recovery or electrical proof.

   Integrated flash-fault models now pass 68 bounded timeout/readback cases
   and all 68 retained-state boots (44 fresh; 24 exact-input reuses).
   Four late errors follow a valid final commit; failure does not imply rollback.
   `flash-fault-support-checkpoint.json` binds receipts and support boundaries.
   Unsupported converters remain unfinished/unqualified release gates.

   **Next:** audit the four new drafts under `docs/beta35/`, verify their examples
   and assemble a new allowlisted review kit. Physical interruption/restoration
   and full route qualification remain pending. QA35-005 / STR8N-008 remains
   open for physical acceptance; its saved-state model recovery gates pass.
   QA35-003/004 / STR8N-007 keep A35 unqualified because frozen native BATCH
   hooks require active B0. Refuse routes needing A35, legacy conversion or an
   incompatible E/F/private-ABI profile until separately qualified; any firmware
   correction must use a separately identified candidate.
3. **Recovery/failure-path closure.** Extend only the remaining meaningful
   exact-image model coverage for recovery/bootstrap, malformed inputs and
   interrupted erase/program/commit. Keep historical failures and distinguish
   fixture/harness problems from product defects. A firmware defect requires a
   separate candidate and explicit evidence; do not silently edit the freeze.
4. **Version-correct documentation drafts.** Prepare a beta35 user guide, ASM
   guide, program/command reference and technical manual under `docs/beta35/`.
   Use current readable source, maps, linked command output and existing guides
   as evidence. Cover FT245, 65C02/816 emulation, ASM 0.5, CLOCK 1.10, PF/STATS
   year-inference/minute-resolution limits, memory/ABI, storage and recovery.
   Label drafts and unqualified installation routes honestly. Do not rewrite
   the published beta4 manuals or present deferred features as available.
5. **Examples and manual audit.** Assemble/run the documented examples against
   the frozen version, check public calls, RAM ranges, expected output, error
   and cancellation behavior, and all local links. Retain build/model evidence;
   no live-board example execution during the protected campaign. Correct
   unsupported documentation claims and stale version/address references.
6. **Final local review-kit audit.** Prepare a new explicitly allowlisted review
   archive containing verified manuals/examples and qualified offline tooling;
   keep the earlier ZIP unchanged. Repeat extracted-source reproduction and
   integrity checks only for new content or unresolved concerns. Never include
   board dumps, vendor firmware, private evidence or unrelated v2.1 sources.
   Record the remaining physical and long-term acceptance gates separately.

Advance incomplete work without repeating passed checks unless inputs change.
Save precise checkpoints, commands, logs, hashes and pending actions. When all
remaining work needs hardware access, accumulated soak/drift duration or an
owner decision, record that state and report it rather than manufacturing a
pass. Recurring prerelease work can then stop; the independent soak and drift
automations continue.


## Expanded review completion checkpoint

The broader manual/ABI audit passed 23 checks; the unchanged ten-byte ASM
example reuses its pinned assembly/export/execution receipt. Four guides were
corrected and audited; F is a flash patch, not a RAM fill. The final local kit
is `output/releases/str8n-2.0b35-expanded-review-2026-10-17-r2.zip`: 147 files,
40 local links, three stdlib offline tools and nine package integrity/refusal
checks passed. The original 97 sources and 18 payloads are unchanged; their
prior 26-link clean reproduction is reused explicitly. Prior ZIPs stay sealed.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/expanded-review-checkpoint.json`.
The owner route-scope decision is now resolved: beta35 is limited to bounded
B-target routes, with broader upgrades deferred to a separate candidate.
Stock/legacy/core/private-ABI and A35-dependent routes remain unqualified.
Physical/native/electrical acceptance and long-term campaign observations
also remain pending. No release or installation permission is granted.

The prerelease heartbeat is paused at this owner/hardware/measurement boundary.
The independent 2512 soak supervisor and three-hour NIST schedules stay active;
other boards remain powered off and clocks/trims/settings stay unchanged.


## Owner-approved B-target scope

The owner selected bounded proven B-target maintenance routes for beta35 and
deferred broader upgrades to a separately identified candidate. This resolves
the route-scope decision; it does not qualify hardware or permit installation.
FT245/F30D, exact target E/F, registered source/profile, protected destinations,
verified full backups/current preimages, validated A fallback and all journal/
sequence/count refusals remain required. The archived path retains B28 A while
replacing B34 B, not the previously active B34 as an inactive-slot-only upgrade.

Stock/legacy/core/private-ABI converters and A35-dependent routes are outside
beta35 scope. STR8N-007 remains an excluded A35 defect, deferred for a separate
candidate; it is not fixed by this decision. Native and CLOCK BATCH hooks need
validated slot-independent capability checks, with signature/version/fallback
guards and success/error/cancel paths qualified together. The frozen B-target
payloads stay unchanged; no A35 repair is introduced into beta35.

The scoped acceptance plan is `docs/STR8N_V2_BETA35_SCOPED_ACCEPTANCE.md` and
the machine-readable policy is `release/beta35-prerelease/beta35-route-scope.json`.
The reservation-enabled composed installer remains model-only, pending physical
acceptance; the old template is not promoted. Physical/native/electrical gates
and long-term observations remain open, with no release/installation permission.
The 2512 soak/drift campaign continues; the other boards remain off and all
real clocks/trims/settings unchanged. ACIA and crypto remain deferred.
