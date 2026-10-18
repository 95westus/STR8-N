> Historical release-work checkpoint. Current v2.0rc1 firmware is installed

> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.

> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.

> Operating instructions below describe their recorded historical stage.



# Issue: beta35 preserving migration needs a durable pre-erase reservation



ID: STR8N-008 (qualification finding QA35-005)



Status: **Implemented for scoped routes; arbitrary electrical interruption coverage remains deferred**



Opened: 2026-10-17



Resume condition: none for offline RAM-helper development and model testing.

Physical qualification waits until the protected RTC campaign permits it.



## Impact



The new preserving B-target route cannot use the frozen sector-transfer

installer alone to qualify durable wear accounting through interruption.

Writing a new journal sector first would erase that sector before its attempt

is durably recorded. The existing 72 exact historical transport/model checks

do not establish electrical power-cut recovery or close this gap.



## Evidence and proposed transaction



`tools/plan_beta35_journal_transaction.py` is a separate semantic planner. It

requires an erased 128-byte record slot in the currently retained journal

sector, exact registered journal records, and an explicit offline activation

policy. It refuses unknown/torn journal data, full retained sectors, insufficient

sequence space and exhausted counters.



1. Append and verify a reservation record, committing byte 127 last. It names

   the retained A monitor and pre-accounts all eight proposed erase attempts.

2. Reclaim the opposite journal sector and stage a newer A-preference record.

3. Install the six declared payload sectors, with CLOCK/monitor commits after

   verification of their pending payloads.

4. Reclaim the original journal sector and write the final B35-preference

   record after the B35 monitor commits. Startup/EDU bytes remain exact.



The reservation, staging and final records use three successive sequences.

Pre-accounted counts are upper bounds after interruption because some planned

erases may not have been attempted. Registered old WC history is reclaimed;

the complete original journal remains in the private full-bank backup.



The corrected semantic test passed **24 scenarios and 118,670 byte states**,

including all four archived fixtures and reversed C/D journal orientation.

Every simulated mutation state retains a valid referenced monitor, unchanged

startup/EDU bytes and counts no lower than modeled attempted erases. The test

also covers refused unsafe journal inputs and exact no-op transactions.



Evidence is owner-local under

`output/qualification/beta35-prerelease-2026-10-17/journal-semantic-0724-r2/`.

The first test failure remains in `journal-semantic-0724/failure.json`: its

supposed torn-record fixture only rewrote a header over an already valid D

record. The corrected fixture explicitly constructs an uncommitted record.

No firmware or archived board source was corrected.



## Next action and close criteria



The separate 530-byte RAM helper is now source-built and has passed 25 linked

model scenarios, including 123 program-boundary cuts. It checks all four bank

preimages and the input page FNV, validates WC CRC/configuration and retained-A

preference, requires an erased aligned journal record, verifies its contents,

then commits byte 127 last. Four archived fixtures match exact expected banks.

Stale/invalid inputs refuse before mutation; timeout and both pre/post-commit

readback failures return without erasing. Serial construction was disabled.



Evidence: `reservation-helper-0826-r2/report.json` beneath the owner-local

prerelease evidence root. The first harness setup used the template's zero-row

plan, which refused before helper execution; its archived harness and abort

record remain in `reservation-helper-0826`. The corrected setup admits one

model-only row and stops before any row is processed. The soak was untouched.



The helper is now integrated through a separately linked wrapper in a new

model-only image. The original template receives an explicit three-byte JMP

detour and plan data; its frozen file and all bank payloads remain unchanged.

The integrated model passed 46 scenarios: four exact fixtures, all-bank stale

refusal before any mutation, corrupt/partial input at all eight sector rows,

and 22 cuts around reservation, erase and commit boundaries. Journal/settings,

fallback A, durable count bounds and selection invariants were checked after

every mutation. Evidence: `transaction-model-0927/report.json` beneath the same

owner-local evidence root; every cut/failure image is retained.



Cold-boot/re-entry now passes on all 46 retained images in the separate

93-check `interrupted-boot-1028-r3/report.json` receipt. Main virtual RTC is

October 17. QA35-006 also verifies the inherited backward-date fixture's exact

2609 BA uncertainty append and stable second boot; both earlier harness

failures remain archived. No real device was involved.



Reversed C/D, activation-only and no-op linked variants now pass 52 checks,

including 32 cuts. The receipt-bound restoration planner passes 48 checks;

42 saved upgrade states have exact original payload/settings restoration

plans with new journal sequences and conservative wear counts. Linked

restoration passes 87 checks including 19 cuts. 20 complete

cases explicitly reuse hash-identical model inputs rather than repeat them.

All fresh mutations check valid selection, settings, A/E/F and durable count

bounds. The planner retains count maxima and reserves added erases first;

it does not copy old backup counters. Unknown/stale states refuse.



Evidence: `variants-restoration-checkpoint.json` under the owner-local evidence

root. New-state boot/re-entry now passes 258 checks, including all saved

variant/restoration cut states. The 35 admitted interrupted-restoration states

recover successfully with both histories replayed against the verified original

backup; seven unsafe-input/preflight cases refuse (42 checks total). Recovered

results pass 34 boot checks and one completed no-op retains its tested parent.

Exact-input reuses are explicit in the receipts. No persistent fake-device

mutation occurs during boot/foreground reads. New sequences/count maxima are

retained, and all new attempts are reserved before erases. Replaying old backup

wear counters remains unqualified restoration.



Evidence: `cut-boot-recovery-checkpoint.json`. This closes the registered

saved-state model recovery gates, not physical/electrical acceptance or an

arbitrary damaged-source recovery route.



The semantic test does **not** execute linked instructions or model electrical

partial-byte failures. The integrated test executes instructions; a separate

test cold-boots the retained cut states. Restoration remains unqualified.

Physical power cuts, hardware acceptance and installation permission remain

open/false. No

board access or persistent-device change occurred during this work.



## Resolution



Open. Semantic, standalone-helper and integrated instruction-model checks

passed, followed by the original cut-state boot/re-entry, linked variants and

receipt-bound wear-aware restoration models. New cut-state boot and recovery

after interrupted restoration now pass for the pinned saved model lineage.

Physical/electrical acceptance and general route permission remain open.

