# Beta35 migration prerequisites — not an installable kit

`source-catalog.json` contains only exact fingerprints of project-owned code.
It was exported from pinned beta4, beta28 profile, beta34 and beta35 local
builds. The beta4 fingerprints also match the actual local published ZIP.
Legacy beta1/a24c1 code is recognized with only its known 16-byte mutable
startup region normalized. No vendor firmware or board data is included.

`tools/inspect_beta35_source.py` uses this catalog to inspect archived banks.
It requires exact core/monitor code identities, valid slot commits/checksums,
and agreement on the ABI token and private validator profile. It refuses
unknown or altered code even when a familiar token and repaired CRC are present.
It can recognize both active-slot selections, an existing target monitor or a
legacy conversion requirement. Recognition does not validate user settings,
storage destinations or complete target assets. Every result explicitly keeps
`execution_permitted` and `route_qualified` false.

The 34-scenario offline receipt is owner-local at
`output/qualification/beta35-prerelease-2026-10-17/source-inspection.json`.
This directory is separate from the sealed `release/beta35/` source tree and
the existing review ZIP. Nothing here opens a serial port or installs code.

Next steps are a target-owned preserving planner/converter, both-active-slot
qualification, destination/settings validation, interruption and restore tests,
and later physical acceptance. The frozen beta35 review kit contains a beta35
B-slot monitor; the inherited generic A-slot file is still generation 46
(beta34). A fresh A-slot beta35 variant must be built and qualified separately
before claiming inactive-slot upgrades from an active B monitor. Do not change
or silently expand the sealed artifact set to conceal this gap.

A separate source-only experiment now reproduces B35 exactly and builds A35,
but A35 remains unqualified: the frozen native-utility/CLOCK BATCH hooks require
active B0 (QA35-004 / STR8N-007). Do not ship the experimental A image or use it
to authorize an active-B preserving upgrade. Continue qualifying B-target
routes with explicit refusal of routes requiring A35. Any slot-independent
correction needs a separately identified payload set and fresh evidence.

## Offline logical B-target planner

`tools/plan_beta35_offline.py` uses the separately pinned
`destination-catalog.json` as well as the source catalog. It accepts only
registered A/B sources with the unchanged target E/F core and private F30D
profile, active A, exact beta34/beta35 code or erased owned destinations, and
a verified complete four-bank backup. Unknown code, occupied owned ranges,
invalid/stale settings and exhausted counters refuse. Routes requiring A35,
legacy conversion or a different private ABI also refuse.

Run from the repository root, using archived files only:

```
python tools/plan_beta35_offline.py backup --banks-dir <archived-banks> --out <new-private-backup-directory>
python tools/plan_beta35_offline.py plan --banks-dir <archived-banks> --backup-dir <verified-backup-directory> --payload-dir <source-built-payload-directory> --active A --out <new-plan.json>
```

Bank filenames default to `b0.bin` through `b3.bin`; `--prefix` selects another
plain filename prefix. Backup directories contain private full banks and must
never enter a public review kit. The plan writes JSON only and contains no
installer. It preserves A, all unowned bytes (including mutable service tails
and shared-sector holes), and the entire existing configuration/wear journal.

This is a logical payload proposal, **not an executable migration plan**.
It does not account for journal mutation needed to track future erase attempts
or implement staged commit. The archived fleet preference names B34's
generation; preserving those bytes makes that locator disagree with proposed
B35. The report exposes that mismatch and leaves activation policy open.
Do not infer which monitor will boot or silently change the preference.
All execution, installation, route and release permission flags remain false.

The 79-scenario receipt is owner-local under
`output/qualification/beta35-prerelease-2026-10-17/b-target-plan-0624-r2/`.
It covers full logical image comparison, untouched bytes, settings/refusal,
target integrity and backup **file** restoration. It does not qualify physical
restoration, interrupted programming, a generated installer or legacy routes.

The separate `tools/plan_beta35_journal_transaction.py` now describes an
explicit `select-B35` transaction with a reservation record before any erase,
a staged A preference, six payload sectors and final B35 activation. Its
24 semantic tests cover 118,670 byte states, including both journal-sector
orientations. It emits no machine code and grants no execution permission.
The frozen installer cannot perform the reservation append: QA35-005 /
STR8N-008 requires a new separately identified and qualified RAM helper.
Full retained journals and unknown/torn records refuse. Counts reserve all
planned attempts and can overcount after interruption. Restoring old backup
wear counters does not qualify physical restoration.

`source/reservation.asm` and `tools/build_beta35_reservation_helper.py` now
build the separate 530-byte helper. The caller must have initialized the
frozen migrator's RAM worker/hash routines; this is not a standalone monitor
program or an installer. The helper uses code at $3000, four expected FNVs at
$3500, a journal destination at $3510, an input-page FNV at $3512 and the WC
record/padding page at $3600. It programs only a verified erased, aligned
128-byte journal record in B3:C/D, verifies the first 127 bytes, then commits
the marker last. It performs no erase or ROM calls.

The serial-disabled standalone model passed 25 checks, including 123
program-boundary cuts, in `reservation-helper-0826-r2/report.json` under the
owner-local evidence root. The module and all generated images retain
installation/release permission false; do not load them on campaign boards or
describe the helper result as an accepted migration route.

`source/reservation-entry.asm` and `tools/build_beta35_transaction_image.py`
compose separate model-only eight-sector images. A wrapper at $3300 replaces
the original template's first `MIG_NEXT` instruction with an explicit JMP,
calls the unchanged helper before row zero, replays the displaced LDX and
returns to the original loop. Rows stage the alternate journal, install six
payload sectors, then activate B35 through the final journal. The original
template and sealed payload files remain untouched; generated images halt in
RAM and have no serial launcher or automatic reset.

The integrated model passed 46 cases including 22 mutation-boundary cuts;
receipts and private full-bank snapshots are under `transaction-model-0927/`
in the owner-local evidence root. The model checks final banks and durable
selection/settings/count invariants. A separate cold-boot/re-entry model now
passes all 46 retained states, with 92 state checks and one explicit battery
policy diagnostic (`interrupted-boot-1028-r3/report.json`). Main virtual RTC is
October 17; the earlier October 8 fixture's expected archived-2609 uncertainty
append is retained and verified separately. Boot/BATTERY can append policy
stage changes and must not be called universally read-only.

The separate variant model now passes 52 checks, including 32 cuts, for
derived reversed C/D, activation-only and no-op fixtures. The receipt-bound
restoration planner passes 48 checks and the linked restoration model passes
87 checks (19 cuts; 20 complete cases reuse identical inputs).
Receipts are under `transaction-variants-1120/`, `wear-restore-plan-1118/` and
`wear-restoration-1118/` in the owner-local evidence root.

`tools/plan_beta35_attested_restoration.py` is the restoration admission entry:
it requires a case from the pinned upgrade-model receipt and its exact upgrade
plan and original backup. Its lower-level experimental composer is not a
general recovery interface. New reservation records retain maximum durable
counts plus restoration attempts before erases. Original payload/settings
bytes are restored; C/D retain new sequences/counts. Old backup counters are
never replayed. Unknown/stale states refuse. No serial launcher is provided.

New-state boot/re-entry passes 258 checks (74 fresh boots,
55 exact-input boot reuses). `tools/plan_beta35_restore_recovery.py`
admits 35 pinned interrupted-restoration states by replaying both the original
upgrade and restoration against the verified original backup. These recoveries
and seven refusals pass 42 linked/admission checks; resulting images pass
34 boot checks (9 fresh; 25 reuses), with the completed no-op
retaining its already-tested parent. Evidence: `cut-boot-recovery-checkpoint.json`.

This is registered saved-model lineage coverage, not general damaged-source
recovery or electrical/physical acceptance. Those physical gates remain
pending. No route, release or installation permission is granted. Private
images never belong in a review archive.


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
