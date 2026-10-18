> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# Beta35 migration support matrix

Target: 2.0b35 generation 47. This is a prerelease evidence inventory; the
general migration matrix and installable release remain unqualified.

## Fresh exact-fixture checks

| Historical fixture | Source/target | Fresh offline cases | Hardware evidence |
| --- | --- | --- | --- |
| 2205 | b34 gen 46 -> b35 gen 47 | 18 passed | Earlier internal install verification; no fresh test/readback |
| 2512 | b34 gen 46 -> b35 gen 47 | 18 passed | Earlier internal install verification; no fresh test/readback |
| 2604 | b34 gen 46 -> b35 gen 47 | 18 passed | Earlier internal install verification; no fresh test/readback |
| 2609 | b34 gen 46 -> b35 gen 47 | 18 passed | Earlier internal install verification; no fresh test/readback |

All 72 model cases passed: exact final banks and erase order, FNV opcode
equivalence, retained A, verified final monitor commit, stale preimages for
each changed bank, and corrupt/incomplete payloads at every transfer row.
An incomplete transfer waits without mutating that row or committing the
new monitor. Earlier completed rows may already have changed. This does
not prove atomic migration or electrical power-cut recovery.

These exact plans preserve B28 in A and replace B34 in B from RAM. They
do not preserve the previously active B34 monitor as an inactive-slot-only
upgrade would. Recovery E/F, unlisted sectors and mutable service records
remain unchanged. Wear increments match the seven declared sector erases.
All 13 canonical payload ranges match the freshly source-built review kit.
The emulator uses the W65C02 model and the historical initial-XCE handling;
no native 816 or new physical acceptance is claimed.

## Routes still requiring beta35 qualification

| Source | Status |
| --- | --- |
| Stock WDC monitor | pending target-owned route and qualification |
| Published beta1/a24c1 | fingerprint recognized; legacy conversion explicitly refused; converter and route proofs pending |
| Published beta4 | fingerprint recognized; different F core requires conversion, explicitly refused; beta25 proof is not transitive |
| Registered AB/F30D with exact target E/F and accepted owned destinations | conditional logical planning; integrated execution limited to archived/derived fixtures below |
| Active B requiring A35 | explicitly refused; QA35-004 / STR8N-007 remains open |
| Beta28 F31B private ABI | recognized; ABI conversion explicitly refused |
| Unknown/corrupt/occupied destinations | bounded source/planner refusal cases passed; arbitrary-source recovery remains unqualified |

The existing generic launcher catalog/default selection still describes
beta25-era routes. Do not treat recognition of an older source or a b4-to-b25
test as a qualified b4-to-b35 upgrade. A release-owned beta35 planner must
select the exact source/ABI/layout automatically, preserve user data and
settings, reject unknown/occupied ranges, and qualify backup restoration
and interrupted commits before the published forward-upgrade promise can
be made for beta35. Physical qualification remains after the protected drift
interval; no powered-off board was contacted.

Owner-local evidence: `output\qualification\beta35-prerelease-2026-10-17\migration-matrix.json`.
ACIA and crypto remain deferred. RTC clocks, trims and baseline are unchanged.

## Offline source-inspection prerequisite

The new serial-free inspector and fingerprint catalog passed 34 scenarios:
both active slots for the four captured beta34/beta35 fixtures, the local
published beta4 images, both beta28 private-ABI profiles, legacy exact/mutable
startup forms, erased inactive slots, unknown/corrupt code and ABI mismatch.
An altered monitor with a valid repaired CRC still refuses. Legacy recognition
does not claim inactive-slot semantics. Source recognition never authorizes
execution or validates destination/user-data migration by itself.

Code: `tools/inspect_beta35_source.py`; catalog:
`release/beta35-prerelease/source-catalog.json`. Evidence:
`output/qualification/beta35-prerelease-2026-10-17/source-inspection.json`.

**QA35-003:** the canonical review kit currently has a beta35 B-slot artifact;
the inherited generic `str8n-v2-recovery-slot-a0.bin` remains generation 46
(beta34). The actual fleet A slots retain B28. Neither is a beta35 A-slot target.
Build and independently qualify an A-slot beta35 extension in a separate
workspace before claiming preserving inactive-slot updates from an active B
monitor. The existing frozen artifact set and prior ZIP remain unchanged.

The separate source-only experiment now builds with five fresh links and
reproduces the frozen B35 image exactly. Its A35 image is **not qualified**:
QA35-004 / [STR8N-007](issues/BETA35_A_SLOT_BATCH.md) reproduces native-utility
BATCH handoff waiting at the MAINT prompt under A. Frozen utility/CLOCK batch
hooks explicitly require active page B0. Model boot, standalone commands and
fallback diagnostics do not establish full A-slot feature compatibility.
Keep any route needing a qualified A35 target refused. A correction requires
separately identified payloads; the sealed review kit remains unchanged.

## Offline logical B-target planning prerequisite

The serial-free `tools/plan_beta35_offline.py` and its pinned destination
catalog passed 79 scenarios. For each archived beta34 fixture with active A,
the six proposed payload sectors reproduce the historical beta35 target,
except that the complete source configuration/wear journal remains unchanged.
Active B, legacy/private-ABI conversion, unknown or occupied owned code,
invalid/stale settings, exhausted counters, stale preimages, altered target
payloads and corrupt backups refuse. Seeded unowned bytes, mutable service
tails and shared erase-sector holes remain byte exact. Existing beta35 assets
produce a logical no-op. The CLI passes with serial imports forbidden.

This is **not executable route qualification**. Journal mutation/wear
accounting and staged commit are not planned. Preserved fleet settings still
name B34's preferred generation; reports expose its disagreement with proposed
B35 and leave activation policy open. Generated installer execution,
interrupted programming, physical backup restoration and hardware acceptance
remain unqualified. The backup check proves archived file restoration only.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/b-target-plan-0624-r2/report.json`.
The earlier `b-target-plan-0624/failure.json` retains a test-fixture setup error:
it attempted to validate settings after erasing the monitor named by those
settings. The corrected test clears that preference before constructing the
erased-slot fixture. No firmware or source board bytes were corrected.

## Semantic journal/activation transaction

The separate `tools/plan_beta35_journal_transaction.py` passed 24 semantic
scenarios covering 118,670 byte-mutation states. Before any sector erase, an
append-only reservation record names retained A and reserves all planned erase
attempts. A newer A record is then staged in the opposite journal sector; the
six payload sectors follow; the final B35 preference is written in the original
journal sector after the monitor commits. Startup/EDU settings remain exact.
Both C/D orientations and unsafe journal/sequence/counter refusals are covered.
Interrupted transactions may overcount unattempted erases; full original
journal history remains in the private backup.

This is an abstract state-transition test, not linked instruction execution or
an electrical power-cut result. The frozen transfer installer lacks the
required append-only reservation prelude. [STR8N-008](issues/BETA35_JOURNAL_RESERVATION.md)
tracks the separate RAM helper, all-bank preflight, generated-installer
interruption tests and wear-aware restoration work. No installation or route
permission is granted. Evidence: `journal-semantic-0724-r2/report.json` beneath
the owner-local prerelease evidence root. The original failed synthetic
torn-record test is retained in the earlier `journal-semantic-0724` directory.

The separate reservation helper is now a 530-byte source-built RAM module.
Its standalone linked model passed 25 checks, including four exact archived
fixtures, all-bank stale preflight, unsafe/occupied journal destinations,
record/input corruption, configuration/locator checks, readback/timeout faults
and 123 mutation-boundary cuts. Only the declared erased 128-byte journal slot
is programmed; its marker is last and no sector erase occurs. The existing
journal remains valid before that commit. The successful report is
`reservation-helper-0826-r2/report.json` beneath the owner-local evidence root.
The first count-zero harness refusal is retained separately.

That receipt closes standalone helper model coverage only. The subsequent
integrated and cold-boot checkpoints below cover linked staged transactions
and retained interruption states. Additional variants and wear-aware
restoration remain pending. Physical cuts and installation permission remain
unqualified. No firmware payload or board was changed.

## Integrated instruction-model checkpoint

The separately composed eight-sector image passed 46 cases, including four
exact archived fixtures, stale preflight for all banks, corrupt/partial input
at all eight rows and 22 cuts around erase and commit boundaries. The helper
runs through an explicit three-byte JMP detour and a separate RAM wrapper;
the original template and bank payloads remain sealed. Every mutation checks
the valid journal/monitor preference, startup/EDU bytes, fallback A and durable
erase-count bounds. B35 selection occurs after its payload/monitor commits.
Complete final banks and erase order match each proposal exactly.

Evidence: `transaction-model-0927/report.json` under the owner-local evidence
root, with retained full-bank cut/failure images. This is instruction-model
coverage for the four active-A fixtures, not electrical cuts or full route
qualification. Cold-boot/re-entry from all 46 retained states now passes the
separate 93-check receipt in `interrupted-boot-1028-r3/report.json` (92 state
checks plus one battery-policy diagnostic). Each image boots its valid selected
monitor; stale original-installer re-entry refuses without further mutation.
The main virtual RTC is explicitly October 17, after archived battery dates.
The original October 8 fixture's expected 2609 uncertainty append is preserved
and verified byte exactly, including a stable second boot and unchanged other
persistent devices. No firmware change was needed (QA35-006).

Reversed journal orientation, activation-only and exact no-op models now
pass 52 checks across derived four-board fixtures, including 32 mutation cuts.
Receipt-bound restoration planning passes 48 checks. The linked restoration
receipt passes 87 checks including 19 cuts; 20 complete cases
reuse identical bank/RAM/transfer/expected/count inputs explicitly.

Restoration accepts only pinned successful upgrade-model receipts, replays
their events against a verified original backup and refuses unknown or stale
images. It restores original payload/settings bytes while writing new C/D
records that preserve the maximum durable counts and reserve all additional
erases before the first erase. It does not replay old backup counters. The
private full backup retains original journal history. On the 2512 completed
fixture, C counts progress 33 -> 34 -> 35 and D 13 -> 14 -> 15 through original,
upgrade and restoration states. This is model evidence, not new board wear.

Evidence: `variants-restoration-checkpoint.json` under the owner-local evidence
root. New-state boot and original-installer re-entry pass 258 checks,
with 74 fresh boot executions and 55 hash-identical boot reuses. All
new saved cut states are covered. Recovery after 19 restoration cuts and 16
corrupt/partial-transfer states passes, with four stale-bank preflights and
three admission refusals (42 checks total). Original upgrade and first-restore
events are replayed as one history against the verified original backup.
Every additional erase is reserved before mutation; prior durable counts never
decrease. Recovered results pass 34 boot checks, including 9 fresh executions
and 25 exact-input reuses; the completed no-op preserves its tested parent.

Evidence: `cut-boot-recovery-checkpoint.json`. Scope is the pinned saved model
lineage, not an arbitrary damaged-source recovery interface or native/electrical
proof. Electrical/physical acceptance remains pending. A35/stock/legacy/core/
private-ABI converters and general installation permission remain unqualified.

## Route support boundaries

A validator address alone does not identify an interchangeable recovery core.
Published beta4 and the target both use F30D, but their F-sector bytes differ;
the logical planner refuses the required conversion. The legacy beta1/a24c1
fingerprint and the F31B profile are recognized separately and refused for
unqualified conversion. A stock WDC route has no allowlisted converter or exact
beta35 execution proof. An unknown-source refusal must not be presented as a
stock-image route test.

The derived reverse-journal, activation-only and no-op cases extend bounded
model coverage. They do not establish every admitted logical source as an
executable route. Unsupported converters remain unfinished work; their absence
does not become a waived gate when manuals or packaging are completed.


## Integrated flash-fault and support-boundary checkpoint (October 17 UTC)

The linked forward/restoration images pass 68 bounded fault cases: erase,
program and explicit-commit polling timeouts, plus transient/persistent sector
verification faults at each applicable row. Each failure halts in RAM, clears
flash busy/NMI hold and performs no subsequent flash mutation. Settings, valid
selected monitor, fallback/core bytes and durable count bounds remain safe.
Full case banks, events and transcripts are retained.

All 68 saved states pass cold boot and a foreground RAM read with flash,
EEPROM, RTC and SRAM unchanged: 44 fresh CPU executions and 24 hash-identical
boot reuses. Four late final-journal errors retain an already-valid target
preference. Failure does not imply rollback: inspect actual durable state and
retain the original backup before retrying. This bounded polling/readback
model is not an electrical timing or arbitrary damaged-source proof.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/flash-fault-support-checkpoint.json`.
It binds prior/new receipts and explicit route support boundaries. Stock,
legacy, incompatible-core/private-ABI converters remain unfinished and
unqualified; active-B/A35 routes remain refused. Their absence is not a waived
release gate. The inherited RAM installer banner names beta27; exact pinned
plans/payload hashes identify the composed beta35 image. No frozen firmware
was changed. All 23 payloads, the old review ZIP and RTC baseline still match.

Four draft manuals now exist under `docs/beta35/`. Example/manual audit and a
new allowlisted local review kit are next. Physical/native acceptance, general
route qualification and installation permission remain open. The 2512 soak
and RTC campaign continue; other boards stay off and clocks/trims unchanged.


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
