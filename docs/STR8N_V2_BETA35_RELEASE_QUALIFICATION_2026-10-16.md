> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# Beta35 release qualification

Started at the owner's request on October 16, 2026 CDT. Target: STR8-N
**2.0b35, generation 47**, CLOCK **1.10**, ASM **0.5**. This is a
qualification record, not a declaration of release acceptance or permission
to distribute a package.

## Scope and protected running campaign

- Keep the 2512 preserving soak and three-hour NIST snapshot campaign running.
  The hourly supervisor follows `soak_run` in the active campaign state.
- Leave 2205, 2604 and 2609 powered off and do not open their ports.
- Do not change clocks, trims, configuration or the four-board RTC baseline.
  Long-term powered and power-off drift collection continues independently;
  no arbitrary end date or acceptance duration has been imposed.
- ACIA receive investigation and optional crypto integration/qualification
  are explicitly deferred. They do not block this scoped release; the guides
  must describe their limits without claiming those paths are qualified.
- Qualify the existing FT245 console and documented 65C02/816-emulation
  profile. Do not infer native 816 application execution qualification.
- Keep v2.1 ABI/storage work outside the release source and artifacts.

## Candidate freeze and evidence

Candidate build metadata SHA256:
`2f5319ab1d7bc751d61bc4b00af225466d83b983bc7e5806a33417940be68365`.

The 2.0 source worktree is `tmp/b34`, separate from the primary v2.1 checkout.
Because its beta35 additions are not all committed, qualification captures
the actual source bytes and hashes, not merely its Git HEAD. The frozen source
copy, artifact hashes, model dependency hashes, test adapters and logs are
indexed under owner-local evidence:

`output/qualification/beta35-release-qualification-2026-10-17-034745Z/`.

`freeze.json` names the short-path source copy used by the legacy WDC tools.
`status.json` records actual fresh checks. `asset-consistency.json` records
reference-image and release-allowlist findings. Earlier attempts remain
separate: missing historical model dependencies and a long-path assembler
crash were harness failures, not passing tests or confirmed firmware faults.
An obsolete F-only test expected the refusal fixed in beta25; it is not a
valid beta35 acceptance assertion. Use current recovery behavior instead.

Frozen candidate artifacts and original installation receipts are preserved.
Fresh test outputs go to the copied build, not the sealed installed candidate.
All reference full-bank images stay owner-local; they may contain opaque/vendor
data and are not a public release kit.

## Acceptance gates

The initial offline pass completed seven selected suites: a **30-file byte-exact
incremental rebuild**, **620 linked duration cases** plus PF/STATS integration,
**12 ASM tests** including all **212 WDC encoding comparisons**, example
Store/Table/Restore and provider integration, BATCH allowlist/error/Esc,
CLOCK summary/query/confirmation preservation, and forced fixed-F recovery
with A/B return and complete persistent-state preservation.

The recovery harness injects S during the current startup recovery window,
after cold RX flushing, and checks the exact compact TIME timestamp. Its old
prequeued-input and `RTCC: UTC` assumptions failed; those original logs are
retained alongside the retargeted passing result. No production firmware was
changed to pass these checks. Results are bound to the frozen build in
`status.json` and `adapters-final.json`. This initial pass does not close the
remaining release gates below.

| Gate | Required evidence / current limit |
| --- | --- |
| Exact identity | Hash all frozen sources, declared artifacts and candidate reference banks; bind results to beta35 generation 47. |
| Incremental reproduction | Rebuild beta35 in a fresh directory from its sealed parent and compare all selected files. This does not establish a clean source-only build of the complete dependency chain. |
| Functional regression | Fresh duration/PF/STATS, ASM encoding/editor/execution, Store/Table/Restore examples, BATCH error/Esc, CLOCK read-only/confirmation and fixed-recovery checks on the copied beta35 build. |
| Complete clean source build | Passed for the frozen FT245/F30D review payload set: 97 source files, 26 fresh links and all 18 artifacts byte-exact; repeated from an extracted archive using isolated Python. No historical BUILD tree or binary input. |
| Preservation / failure paths | Verify retained-data and setting preservation, malformed/corrupt input refusal, interrupted-transfer/commit behavior and recovery in models; distinguish models from electrical power cuts. |
| Migration support matrix | Bind each claimed WDC/published-STR8-N source, CPU/profile and migration/restore route to exact beta35 payloads. Existing beta34-to-beta35 board installs are evidence for that route only. |
| Hardware evidence | Existing four-board beta35 installation receipts remain historical. No new physical migration/reset/power-cycle tests are authorized during the powered-off drift interval. Do not mark this gate complete from model passes alone. |
| Powered soak | Continue 2512 and count actual units/cycles and duration. An initial-cycle result is not long-term acceptance. |
| Manuals and examples | User guide, ASM guide, program/command reference and technical manual; align all examples, addresses, limits and recovery procedures with the frozen version. |
| Package / licensing | Local review-kit cleanup passed: explicit 123-file inventory, 18 payloads, source/toolchain prerequisites and MIT notice; no vendor executable, full bank, private evidence or stale CLOCK/MAINT artifact. Two archives identical; five integrity/refusal checks pass. The final installable kit, migration qualification and version-correct manuals/examples remain required before publication. |

## Findings requiring package preparation

1. **QA35-001:** the builder's owner-local `candidate/b1.bin` still has the
   inherited CLOCK record. The separate beta35 installation plans contain
   the correct CLOCK 1.10 record, as verified by byte comparison. Installed
   2512's qualified plan is correct. Do not use the inherited full-bank
   reference as a canonical public beta35 image.
2. **QA35-002:** inherited artifact metadata includes
   `clock/clock-1.9-2000.s19`, which differs from the current `clock/clock.s19`.
   Build the release allowlist deliberately; do not zip the candidate folder
   or blindly ship every historical artifact named in its metadata.

These findings did not require flashing a board or changing the RTC campaign.
They are closed for the canonical review kit described below. Historical
candidate directories remain sealed, including their stale reference files;
they must not be substituted for the explicit review-kit allowlist.

## Clean source closure and review package â€” October 17 UTC

The independent release source tree is `release/beta35/`. Build it with
`python release/beta35/build.py --out <new-short-directory>` using separately
installed WDC02AS and WDCLN. The included README records prerequisites,
scope, exclusions and verification commands. Its source manifest contains
97 readable assembly/include/JSON files. Executable worker/vector/BATCH/gate
images are regenerated from freshly linked assembly; text, initial journal
data and empty migration tables are generated from declared data/defaults.

One historical packaging inconsistency needed explicit source promotion:
the staged boot source did not retain the F30D selector profile used by its
linked image. The original source-level relocation from the profile builder
is now present in the promoted boot source. Provenance records the original
hash, transformation and resulting hash. No disassembly or embedded compiled
image was substituted for source. The launcher ABI descriptor and reserved
padding are explicit composition rules. All resulting payloads match beta35.

`tmp/c35e` and the isolated-Python rebuild from extracted kit `tmp/k35a` into
`tmp/c35f` each assembled 26 modules and produced the same 18 selected
artifacts. Both build reports are identical. This includes native utilities,
recovery E/F, monitor B, CLOCK 1.10, ASM, RTC/journal, status, battery, local
display, VERSION/PF and the provisioning/migration qualification templates.
The earlier seven offline regression suites remain bound to these exact
firmware bytes; no new hardware qualification is inferred from reproduction.

The canonical sparse layout has 13 non-overlapping logical ranges. Every
mapped byte matches the historical 2512 beta35 installation **plan**; this is
an offline comparison, not a new device readback. It assigns only the immutable
journal prefix, leaving its live record tail and all configuration/wear data
outside the write map. It also leaves fallback A and unowned bytes outside
the map. A layout is not an erase/write plan or a preserving installer.

The two independently packaged archives are byte-identical:

- Owner-local review archive: `output/releases/str8n-2.0b35-review.zip`.
- Size: 287365 bytes; 123 files including manifest, 97 sources, 18 payloads.
- SHA256: `dc7c854f71852a853eac48dbf0070560feb64c8c47df0441d496a5062d7afa1f`.
- Evidence: `output/qualification/beta35-clean-build-2026-10-17-041548Z/report.json`.
- Current evidence pointer: `output/qualification/beta35-release-current.json`.

The extracted verifier accepts the exact kit and refuses a changed/stale
CLOCK, an extra full-bank payload, a missing assembly source and an unsafe
manifest path (five tests passed). ZIP inventory/checksums and payload hashes
are checked independently. The kit carries the project MIT notice and no WDC
tools, Python runtime, py65 or vendor monitor. The S19 encodings retain the
historical S0 serializer label for exact reproduction; payload identity and
current version are established by the manifest and decoded image.

This is a local review kit, with `installation_permitted: false` throughout.
No serial launcher or board-specific installation plan is packaged. Migration
matrix, physical acceptance, continuing soak/drift collection and final
manuals/examples remain open. No publication occurred. Both sealed candidates,
all owner-local reference banks and the RTC baseline were verified unchanged.
At closure the 2512 worker was running, with 58 passed units and two full
cycles observed; its hourly supervisor and three-hour NIST schedule remain
active. Boards 2205, 2604 and 2609 remain off; ACIA and crypto remain deferred.

## Soak fixture correction

The first powered-soak run stopped safely at its EEPROM comparison and restored
all borrowed application RAM. Its comparison fixture predated two already
recorded power events: sequences 13 and 14 captured at 03:07:19 and 03:15:14 UTC
on October 17, both before the new four-board RTC baseline. Two fresh EEPROM
reads matched, all four record checksums were valid, the other slots were
unchanged, and factory/status bytes matched. No EEPROM repair/write occurred.

The diagnosis and hashed read-only comparison image are retained under
`output/qualification/beta35-soak-eeprom-baseline-2026-10-16/`. After verifying
application RAM restoration, the corrected runner resumed in
`output/qualification/beta35-powered-soak-2512-2026-10-16-r2/`. This correction
does not replace the RTC drift baseline or erase the original failure record.

The first full flash pass in r2 then found 36 differing bytes, all in two BA
battery-policy records at $9CE0 and $9D00. Both records have valid checksums,
sequence 1/2 and stage zero. The first soak's CLOCK opening already showed a
known within-age policy; the older installation plan had blank bytes there.
A fresh full Bank 3 read matched the observation exactly. Every other Bank 3
byte and all other flash banks matched their planned images. No battery
record was erased, restored or rewritten by this investigation.

The read-only diagnosis and full comparison image are retained under
`output/qualification/beta35-soak-flash-baseline-2026-10-16/`. After r2's
application RAM restoration was verified, the runner resumed in
`output/qualification/beta35-powered-soak-2512-2026-10-16-r3/`, checking EEPROM
and Bank 3 first. The supervisor resolves this path from campaign state.
Earlier failures remain archived and are not counted as completed cycles.

## User-requested LED variety â€” October 17 UTC

`tools/soak_led_patterns.py` generates replayable playlists with two selected
named sequences plus random sparkle. The named catalog includes wig-wag,
forward/reverse scanner, bounce, mirrored pairs, zipper, ripple, double chase
and Gray code. Each sequence has eight masks and a bounded 120â€“240 ms frame
hold. Each interlude records its random seed, exact masks and timing in
`led-plan.json`; `led-state.json` verifies original LED restoration. The
existing hashed, RAM-only probe restores the LEDs after every eight frames.
Pending drift acquisition or STOP ends the playlist between restored sequences.

The new cycle has 27 unchanged non-LED workloads and seven LED interludes,
34 units total. The earlier r3 cycle had 28 units; retain each run's counts
with its own workload definition. Seven offline tests passed, including seeded
playlist replay/bounds, 48 linked-probe executions checking restoration and
the narrow RAM/LED write set, a RAM-only LED readback helper, and yielding to
drift after restoration.

R3 stopped normally after 65 passed units and two completed cycles. Its full
application-RAM restoration was verified before starting r4 at 04:20:04 UTC.
R4 passed EEPROM/Bank-3 verification, then its LED readback failed because
monitor D protects the I/O range. The failure occurred before pattern execution;
all application RAM was restored and the failed run remains archived. The
corrected harness reads the LED latch/CRA with a 17-byte RAM helper at $5000,
then dumps only its RAM result bytes. It writes no I/O registers. Verification
compares LED state and CRA setting bits, excluding volatile IRQ flags.
The campaign state now points to
`output/qualification/beta35-powered-soak-2512-2026-10-16-r5/`, with the prior
run and totals retained in `handoff.json` and campaign history. Each new run
archives its runner/pattern source and hashes. No reset, firmware installation,
persistent-device write, clock/trim change or baseline replacement occurred.
The existing supervisor and NIST snapshot schedules continue to resolve the
current run from campaign state. Other boards remain off; ACIA/crypto remain
deferred.

The first r5 live playlist completed mirrored pairs, bounce and random sparkle,
then the normal RTC-settings workload passed and the soak continued. Activation
evidence is `led-activation-verified.json` in r5. The monitor's G entry clears
the LED latch before executing RAM; the helper samples that launch state and
CRA setting bits. The linked-probe model checks the probe's own restoration
before return, and the monitor restores its normal running indication.

## Automated prerelease continuation â€” October 17 UTC

An hourly local heartbeat, **Beta35 prerelease qualification**, now follows
`docs/STR8N_V2_BETA35_PRERELEASE_WORK.md` and
`output/qualification/beta35-prerelease-state.json`. It continues incomplete
offline tasks, retaining concrete checkpoints and notifying only for meaningful
milestones, failures or required owner action. Passed tests are reused while
inputs are unchanged. It does not open board ports, interrupt the soak,
install/publish firmware or convert emulator results into hardware acceptance.
The independent soak supervisor and NIST snapshot schedules remain active.

The first continuation completed fresh serial-disabled installer rehearsals
for all four exact historical beta34-to-beta35 fixtures: **72 cases passed**.
Each board covers the exact final banks/erase order, linked FNV hash equivalence,
retained A fallback, verified final monitor commit, stale preimages for all
three changed banks, corrupted payloads at all seven rows, and partial payloads
at all seven rows. Partial input waits without mutating that row or committing
the new monitor; earlier completed rows may already have changed. This is not
atomic migration or electrical power-cut qualification.

The evidence inventory also verifies unchanged recovery E/F, unlisted flash
sectors and mutable service records, exact tracked erase increments, and all
13 canonical source-built payload ranges against every historical target plan.
See [the migration matrix](STR8N_V2_BETA35_MIGRATION_MATRIX.md) and owner-local
`output/qualification/beta35-prerelease-2026-10-17/migration-matrix.json`.

These specific plans retain B28 in A and replace B34 in B from RAM. They do
not preserve the previously active B34 monitor under an inactive-slot-only
contract. The old generic launcher's beta25 routes do not establish a general
stock-WDC/b1/b4/intermediate-layout-to-beta35 path. Package-owned target planning,
source/ABI/layout conversion, refusal/restore coverage and later physical
acceptance remain open. Documentation drafts/examples and the final local
review-kit audit are queued; full release qualification remains false.

## Separate A-slot experiment — October 17 UTC

A separate five-link source build reproduced the frozen B35 monitor byte
for byte and produced an experimental A35 image. Twelve serial-disabled
model diagnostic scenarios passed: mixed slot/default selection, corrupt
CRC/uncommitted/ABI fallback, fixed-F return to both monitors, standalone
CLOCK queries, ASM/RAM execution and persistent-state preservation.

**The A35 extension is not qualified.** QA35-004 /
[STR8N-007](issues/BETA35_A_SLOT_BATCH.md) reproduces native BATCH
handoff stopping at MAINT under A, while the exact B-slot control completes
all four utilities. Frozen utility and CLOCK hooks explicitly require
active B0. The diagnostic pass includes reproducing that known failure;
it is not a full A-slot feature pass. The original failed qualification
assertion is retained alongside the follow-up report.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/a-slot-checkpoint.json`.
Continue B-target planning, preservation/refusal/interruption/restore
qualification, manuals and examples. Refuse routes requiring qualified
A35; a slot-independent correction requires separately identified
payloads. The original candidate, sealed ZIP and RTC baseline hashes
were verified unchanged. No board, clock, trim or persistent-device
changes were made. Release/installation permission remains false.

## Logical B-target planner checkpoint — October 17 UTC

The new serial-free logical payload planner passed 79 scenarios against
the four archived fixtures, exact owned range fingerprints, full-bank
backup/file restoration, seeded unowned data, settings/refusal, stale
preimages and altered target payloads. The CLI also ran with serial
imports forbidden. The initial erased-slot test setup failure is retained;
only that synthetic fixture construction was corrected.

The proposal changes six payload sectors, retains fallback A and every
unowned byte, and preserves the complete original configuration/wear
journal. It is deliberately non-executable: journal wear accounting and
staged activation/commit are not implemented. Preserved settings still
name the old B34 generation; the report exposes the mismatch with proposed
B35 and leaves activation policy open. Generated installer execution,
interrupted programming, physical backup restoration and hardware
acceptance remain unqualified. Routes requiring A35, legacy conversion
or different E/F/private-ABI profiles refuse.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/b-target-plan-checkpoint.json`.
All frozen artifact, sealed ZIP and RTC baseline hashes were checked.
The running 2512 campaign was only observed; no serial connection,
firmware/settings change or hardware acceptance occurred.

## Semantic journal/activation checkpoint — October 17 UTC

A separate semantic transaction passed 24 scenarios covering 118,670 byte
states. It appends a reservation before any erase, stages a retained-A
preference in the opposite journal sector, installs the six payload sectors,
then writes the final B35 preference. Startup/EDU settings remain exact.
Both journal-sector orientations retain a valid monitor preference and
durable counts no lower than modeled attempted erases at every tested state.
Counts reserve planned attempts and may overcount unattempted rows after
interruption. Original journal history stays in the private full backup.

**This does not execute linked instructions or qualify electrical cuts.**
[STR8N-008](issues/BETA35_JOURNAL_RESERVATION.md) / QA35-005 requires a
separate RAM reservation helper and all-bank preflight before the pinned
transfer installer can implement this transaction. Linked execution,
interruption tests and wear-aware restoration remain open. An earlier
synthetic torn-record test error is retained with the passing follow-up.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/journal-semantic-checkpoint.json`.
All 23 frozen artifact hashes, the sealed review ZIP and immutable RTC
baseline were verified unchanged. The 2512 soak was only observed; no
serial connection, firmware/settings change or publication occurred.

## Standalone linked reservation helper — October 17 UTC

The separate 530-byte RAM helper source-built and passed 25 serial-disabled
linked-model checks, including four exact archived fixtures and 123 cuts
after actual byte-program events. All-bank FNV preflight, input integrity,
WC CRC/configuration/retained-A locator, erased aligned journal destinations,
readback and commit-last were exercised. Stale/invalid inputs refuse before
mutation. Timeout and pre/post-commit readback failures return without erase.
Actual linked FNV equivalence was checked before accelerating range loops.

This qualifies the standalone helper model only. It does not execute the
complete staged transaction or establish electrical partial-byte behavior.
Full installer integration, staged journal/payload/activation interruption,
wear-aware restoration and physical acceptance remain open. The first
count-zero template harness refusal was retained; only the offline model
was stopped and its admission setup corrected. No board was contacted.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/reservation-helper-checkpoint.json`.
All 23 frozen artifact hashes, the sealed review ZIP and immutable RTC
baseline remain exact. The running 2512 soak and its schedules were untouched.

## Integrated transaction instruction model — October 17 UTC

A separate model-only installer now integrates the tested reservation helper
through a linked RAM wrapper and an explicit three-byte JMP detour. The
frozen template file and bank payloads remain exact. The eight-sector
transaction reserves counts first, stages the alternate journal, installs
six payload sectors, then selects B35 through the final journal record.

The instruction model passed 46 scenarios: four complete exact fixtures,
four all-bank stale preflights, eight corrupt transfers, eight partial
transfers and 22 mutation-boundary cuts. Valid journal/monitor preference,
startup/EDU bytes, durable count bounds and unchanged A/E/F were checked
after every mutation. Complete final banks and erase order match exactly.
Counts reserve planned attempts and may overcount unattempted rows after
interruption. All interrupted/partial images are retained privately.

This does not cold-boot the cut states, qualify additional transaction
classes, restore wear accounting or establish electrical interruption
behavior. Those recovery/restoration and physical gates remain open;
route, release and installation permission remain false. The historical
MAINT-relocation harness guard was replaced with current exact-bank and
CLOCK/monitor/journal invariants because this route retains MAINT in B2.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/transaction-model-checkpoint.json`.
All 23 frozen artifact hashes, the old review ZIP and the immutable RTC
baseline were verified. No board access or soak interruption occurred.

## Interrupted-image boot and re-entry model — October 17 UTC

All 46 retained completed, refused, partial-transfer and mutation-cut states
cold-boot into the journal-selected valid monitor and execute a RAM read.
Re-running each original installer refuses changed preimages before any
mutation. The 92 state checks plus one explicit battery-policy diagnostic
pass with serial construction disabled. Main virtual RTC is explicitly
2026-10-17; flash, EEPROM, RTC and SRAM remain byte exact during these boots.

QA35-006 preserves the earlier failed backward-date fixture: the inherited
October 8 virtual RTC predates archived 2609 battery high-water October 16.
Firmware correctly appends one exact sequence-6 stage-3 uncertainty record
at B3:9E80. All other flash and device bytes remain exact, and a second boot
does not append again. Boot/BATTERY is therefore conditionally persistent;
this expected policy behavior was tested explicitly, not suppressed. Both
earlier harness failures and the changed-bank evidence remain archived.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/interrupted-boot-checkpoint.json`.
Reversed journals, activation-only/no-op linked variants, wear-aware
restoration, electrical cuts and hardware acceptance remain pending.
Release and installation permissions remain false. All 23 frozen payload
hashes, the sealed ZIP and immutable RTC baseline were verified unchanged.
No board access, clock/trim change or soak interruption occurred.

## Transaction variants and wear-aware restoration models — October 17 UTC

Derived reversed-journal, activation-only and no-op fixtures passed 52
linked model checks, including 32 cuts. All four board-derived complete
cases pass each class; exact no-ops emit no installer or device mutations.
Restoration planning passed 48 checks, including 42 admitted saved states
and six refusals. Linked restoration passed 87 checks with 19 cuts;
20 complete cases reuse explicitly hash-identical CPU inputs.

Restoration admission binds the pinned prior report, exact bank hashes,
upgrade plan, event replay and verified original backup. It restores all
original bytes outside C/D and the exact original startup/EDU settings.
C/D use new sequences and maximum durable counts plus all newly reserved
erase attempts; original journal history stays in the private backup.
For 2512, modeled C counts are 33 -> 34 -> 35 and D 13 -> 14 -> 15.
These are offline model counts, not additional board erases.

Cold boot of the new variant/restoration states and recovery after an
interrupted restoration remain pending. Electrical and physical tests,
general routes, release and installation permission remain unqualified.
All 23 frozen payload hashes, prior ZIP and immutable RTC baseline match.
The 2512 campaign continues without serial access or settings changes.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/variants-restoration-checkpoint.json`.
Detailed five-snapshot RTC report and graphs:
`output/qualification/rtc-detailed-analysis-2026-10-17-1113Z/report.html`.

## New cut-state boot and interrupted-restoration recovery — October 17 UTC

New variant/restoration state boot and original-installer refusal pass
258 checks: 74 fresh CPU boots, 55 identical-input boot reuses
and 129 stale-installer refusals before mutation. All 51 new
saved variant/restoration cut states are covered, plus completed, partial
and refused-transfer images. No-image no-ops/admission refusals are listed
separately. Boot uses the explicit October 17 virtual RTC, frozen sources
and deterministic fake EEPROM/SRAM. Full flash, EEPROM, RTC and SRAM stay
exact through boot and a foreground RAM read.

Recovery from 19 restoration cuts and 16 corrupt/partial-transfer states
passes 35 cases, plus four stale-bank preflights and three admission
refusals. The complete upgrade and first-restoration events are replayed
against a verified original backup. Additional attempts are reserved before
erases and prior durable count maxima never decrease. All original bytes
outside C/D and original startup/EDU settings return; journal sequences and
conservative counters remain new. Recovery after the final committed
restoration state is a no-op, retaining its already-tested parent image.

Recovered results pass 34 boot/foreground checks (9 fresh executions;
25 identical-input reuses), confirming B34 selection and persistent
device preservation. Evidence is bounded to this pinned saved model
lineage; this is not an electrical cut or arbitrary damaged-source proof.
Physical/native acceptance, general routes and installation permission
remain unqualified. A35/legacy/private-ABI routes stay refused.

Evidence: `output/qualification/beta35-prerelease-2026-10-17/cut-boot-recovery-checkpoint.json`.
All 23 frozen payloads, sealed review ZIP and immutable RTC baseline match.
No serial access, real reset or campaign settings change occurred.


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
