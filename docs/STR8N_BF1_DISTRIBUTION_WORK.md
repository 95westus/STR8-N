> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# bf1 distributable migration/recovery and documentation closure

The owner explicitly held publication until the documentation is complete and
the release kit includes tested WDCMONV2/beta4-to-bf1 migration and recovery
scripts. This is additional to the two accepted board-specific 2512 routes.
The existing public draft must stay unpublished. Policy r5 and the publisher
require a separate distributable-kit qualification receipt.

**Superseding owner clarification:** deliver a user-facing scripted
**WDCMONV2 -> bf1** route, a separate **beta4 -> bf1** user upgrade, and a
STR8-N-only bf1 `.bin` with no WDCMONV2 binaries. Follow the beta4 release's
usable launcher pattern. The earlier two-hop bridge experiment is not the
requested final route. Do not include vendor images or intermediate beta4
firmware in the final kit; source recognition uses hashes. Implement and
qualify direct factory-WDC handling rather than relabeling the staged-WC route.

The STR8-N-only image has been composed at
`output/qualification/bf1-str8n-only-image-2026-10-18-r1/`: 98304 bytes in B1,
B2, B3 order, excluding B0; SHA256
`dd7b9633ea17b04e7e0759ec68d513da64943ad4193b7c35154a0a2c33fadaca`.
All 22 layout/content checks passed. Its code bytes equal the corresponding
portions of the earlier source-built image. Programmer file offset zero maps
to full-device offset 32768, not B0; document this clearly. This raw image is
fresh provisioning, while the scripts must preserve each user's data/settings.

## Additional owner distribution requirements

Deliver installed-board and migration quick starts, user/operator guides, ASM
manual, command/program usage, and a technical manual with full public ABI
tables and Mermaid architecture/recovery diagrams. Working additions are in
`docs/bf1/QUICK_START.md`, `QUICK_START_MIGRATION.md`, `OPERATOR_GUIDE.md`,
`ABI_REFERENCE.md` and `THIRD_PARTY_NOTICES.md`. Their launcher commands must
match qualified package interfaces; documentation review is still pending.

Build separate Windows and Linux migration/recovery packages. Normal user kits
contain only STR8-N bf1 bins with all supported apps and S/R/T code, required
S19 payloads, required scripts/dependencies, self-contained documentation,
checksums/licenses, and uChess source with full upstream attribution. Exclude
the developer source tree, private captures/logs, vendor firmware and
intermediate beta4 images. Preserve sealed historical developer archives.

The current image includes S/R/T at B3:$E800 but not UCHESS. Do not call that
image app-complete. Create a new named composition and app inventory with T/R
discovery/boot/execution checks, without modifying campaign firmware. Verify
the supplied uChess source with bf1 ASM 0.5; retain Peter Jennings's complete
license, Daryl Rictor and Bill Forster credits. Preserve occupied user program
space in upgrades; refuse conflicts. Both platform packages need extracted-kit
route/recovery tests; Windows success alone does not establish Linux support.

New offline application-image checkpoint:
`output/qualification/bf1-app-image-2026-10-18-r1/report.json`. The 98304-byte
`str8n-2.0bf1-apps-str8n-only.bin` has SHA256
`f20b53793563acd5685cca1ed987f67118f7340fa8f1551955b135830f5e672a`.
Actual bf1 ASM0.5 PASTE/ASM produced the independently qualified uChess bytes.
The builder adds its stored record at B1:$8000 and leaves pinned firmware
unchanged. MON A boot, T/R discovery, load, game moves and HOLD passed with
persistent fake devices unchanged. Source/license files are copied together.
This new provisioning candidate is not yet integrated into preserving user
upgrades or a qualified Windows/Linux package. See active offline checks in
work state before starting duplicate MON B/manual audit jobs. Preserve the
earlier image and reports; never silently repin the campaign payloads.

Policy r6 adds mandatory distribution flags for complete quick-start/operator/
ABI/Mermaid docs, separately tested Windows and Linux packages, verified full
app image, minimal public contents and attributed uChess source. Numeric soak
and RTC requirements are unchanged. Publication stays held.

## Campaign and preservation constraints

All new qualification work is offline. The owner subsequently stopped both
2604 and 2609 workloads; both stopped at safe boundaries with their soak RAM
restoration verified. Do not restart either worker or its superseded STOP helper,
or edit their pinned dependencies. 2604 recorded 1047 passed units/30 cycles
over 8.290 monitored hours; 2609 recorded 389/11 over 3.880 hours. Neither is
a duration-gate pass or waiver.
2604/2609 RTC collection continues. 2205/2512 are powered off: never open their
ports. Clocks, trims, configuration, original baseline and retained/power
evidence stay preserved. A separately authorized 2609 NIST sync restored trim
-14 and control $80 after RTC loss during Windows testing. Its post-recovery
measurement segment is separate; do not calculate rates across SET or infer
that recovery proves migration RTC preservation. Native 816 applications/tests, ACIA and crypto remain
deferred. No firmware installation or physical test is authorized by this work.

Frozen generation-48 bf1 payloads, earlier review ZIPs, eight existing draft
assets and historical receipts remain unchanged. Build new named revisions.
Do not package private captures, vendor images, EEPROM/SRAM, transcripts or
host-specific paths. Source recognition hashes may be distributed.

## Concrete checkpoint

- Public runtime source: `release/bf1-migration-r1/`.
- Current isolated prototype: `tmp/bf1-distribution-r12/migration` (27 files,
  no beta4-bridge binaries). The older r4/bridge experiments remain retained.
- Builder: `tools/build_bf1_distribution_candidate.py --out <new-directory>`.
- Runtime equivalence: `bf1-portable-runtime-tests-2026-10-18-r2.json`, 19 checks.
  Eight historical transaction plans, RAM installers and transfer sequences
  match their CPU-qualified counterparts exactly. This reuses earlier CPU
  execution evidence; it is not a fresh CPU/hardware run.
- Preparation/admission: `bf1-portable-preparation-tests-2026-10-18-r1.json`,
  11 checks. Includes exact beta4 preparation, alternative beta4 preferences,
  occupied-provider/unknown-core/path refusals, a CPU-attested erase-state
  admission, and a synthetic factory-WDC bridge chain.
- The r3 prototype failed offline with a leftover checksum dependency. Its
  source and failure receipt remain retained. r4 corrects the dependency.
- Every prototype has `live_installation_enabled=false` and
  `distribution_qualified=false`. `migrate.py` and `recover.py` currently
  prepare plans only; there is no qualified public live capture/execute flow.
- r5 recognizes beta4 by component digests without packaging beta4 firmware.
  It offers read-only WDC source inspection; the direct WDC planner/launcher
  is still pending and must not be advertised as working. Runtime equivalence
  on r5 passed `bf1-portable-runtime-tests-2026-10-18-r3.json`, 19 checks.
- `bf1-distribution-work-state.json` records the active work and publication hold.

Latest input/recovery checkpoint: r7 archives the original capture identity,
binds board/source/kit/template/installer/transfer/optional-escrow inputs, and
re-derives the admitted beta4 target and full transaction before recovery.
Cross-board, changed target/escrow/installer/transfer, unknown partial states
and absent valid fallback refuse. A fully completed exact target emits only a
no-write receipt, avoiding additional journal erases. Fresh binding/recovery
preparation checks passed 27 cases in
`bf1-portable-bindings-tests-2026-10-18-r3.json`. The 19 runtime equivalence
checks pass on r6 and are reused for r7 by hash proof: only `recover.py`
changed; runtime/template/payload inputs did not. Retain the earlier failed
Python `-I` CLI harness receipt; `-O` clean-directory refusal passed after the
test invocation was corrected. No live execution or fresh recovery CPU claim.

The existing manual/ABI model job has completed: 26 checks passed in
`bf1-manual-abi-audit-2026-10-18-r1/report.json`. The later content/link audit
of all 11 current documents is a separate receipt; final editorial review,
Mermaid rendering and actual user launcher usage remain pending.

New direct-factory input-binding checkpoint: r12 adds a deterministic factory
plan validator and the file-only `verify-plan` CLI. It binds source board/CPU,
kit/capture, optional tracked history/metadata, application and template, then
re-derives the transaction, complete target, installer and every transfer. All
35 admission/tamper checks passed in
`bf1-factory-plan-bindings-2026-10-18-r1.json`; the existing 65C816 fixture's
installer and transfers exactly match prior CPU-executed bytes. This is reuse,
not a fresh CPU run or a passed RTC-preservation test. New unknown-wear
acknowledgement preparation is validated offline without a lifetime-wear claim.

Both new host archives are under `output/releases/bf1-user-review-2026-10-18-r3`.
Actual Windows cmd and Ubuntu 24.04 WSL launchers passed 17 extracted-package
checks, including direct-WDC preparation/validation, CPU-profile tamper refusal,
beta4/no-write recovery, checksums, links, licenses and live-operation refusals.
Each has 58 allowlisted files and identical app-complete 96KiB provisioning
firmware. No vendor images were added. They remain offline review packages:
portable capture/live transport, direct-WDC recovery and RTC preservation,
beta4 app-placement/conflicts, final editorial/Mermaid review and the remaining
release gates are still open. The current `recover` command accepts beta4-origin
plans only; `verify-plan` must not be described as recovery execution.

Commands use bundled Python from the chat; prototype operations are stdlib-only
until a future explicitly selected serial transport needs pyserial. Tests may
read private local fixtures; their data must never enter a distributable kit.

## Earliest incomplete tasks, in order

1. Audit portable planner/recovery inputs and outputs. Remove remaining board
   assumptions and bind saved plans to kit hashes, captures and exact supported
   profiles. Validate guards under Python optimization, changed files, escaping
   paths, corrupt transfers, altered target/escrow and stale recovery states.
   Current recovery admission recognizes bounded complete/erased/precommit
   states; it must not guess arbitrary partially programmed flash.
2. Implement portable preserving capture and live workflow source with explicit
   port/board identity selection, double readbacks, original RAM archiving and
   restoration, readback-before-execution, local durable evidence and owner
   physical RESET prompts. Do not execute it on campaign boards. Test actual
   transport methods using simulated endpoints, including timeout, bad RAM
   readback, stale flash, partial transfer and restoration failures. Never enable
   a live path merely because preparation tests passed.
3. Qualify forward recovery and beta4-source restoration with fresh CPU tests
   where bytes/behavior differ; reuse exact prior evidence only after proving
   equivalence. Replay actual interrupted states and verify conservative wear
   history, clock/trim/configuration and user storage preservation. Unexplained
   states require retained evidence and a documented external-programmer route.
4. Implement the requested **direct factory WDCMONV2 -> bf1** route, distinct
   from the staged WDC-with-WC/host-escrow profile previously tested on 2512.
   Factory WDC has no compatible WC sidecar: qualify explicit metadata/wear
   initialization and recovery, never require private 2512 escrow as a public
   prerequisite or silently invent prior wear history. The earlier beta4 bridge
   experiment remains research evidence only. The original vendor image is
   recognized by a digest and never shipped. Qualify the direct source and
   restoration/recovery behavior and failure paths. Do not claim hardware
   acceptance from the earlier staged route. The admitted WDC sources are the exact
   SXB2 65C02 and original SXB6 65C816 HW3.00 MON2.00 digest profiles recorded in
   the kit. Other vendor images/CPU source profiles are refused; this is not generic WDC support.
   The target bf1 code remains one identical set for 65C02 and 65C816 E=1.
5. Finish the four version-correct manuals and add migration/recovery usage:
   supported profiles, dependencies, Windows/Linux command examples, backups,
   verification, RESET sequencing, preservation limits, interrupted recovery,
   programmer fallback and deferrals. Audit commands/ABI/examples against the
   unchanged candidate. Do not mark documentation complete by removing “draft”
   alone. Keep historical beta35 manuals separate.
6. Build a new allowlisted kit containing both tested user launchers and recovery,
   the STR8-N-only B1/B2/B3 bf1 image/components, current manuals, checksums and
   provenance. Exclude WDCMONV2 and intermediate beta4 binaries. Extract it to
   a clean directory without repository/build/capture paths. Test its real CLI,
   dependencies, fixtures, all supported routes, recovery and refusal behavior.
   Add fake/stale/missing qualification receipt refusal tests to publication.
7. Only after all required evidence passes, create
   `bf1-distribution-qualification-current.json` pointing to an immutable receipt
   with `passed`, `documentation_complete`, `portable_migration_scripts_tested`,
   `portable_recovery_scripts_tested`, `clean_extracted_kit_verified` all true,
   candidate `batchfix-r1`, version `2.0bf1` and hash-bound passed evidence.
   Do not synthesize or overstate physical acceptance. If an additional physical
   gate is necessary, prepare a concrete reviewed procedure and record the exact
   blocker; current owner instructions keep the available test boards off/busy.
8. Revise public draft preparation/assets/source provenance as a separate named
   revision once the new kit passes, preserving prior receipts/assets. Update
   publisher pins/tests and scope with actual completed results. Do not upload
   private fixtures or silently replace sealed firmware. Publication automation
   stays paused until new gates pass and publication authorization is valid.
   The existing tonight window expires 05:00 UTC October 18; do not bypass an
   expired window. Longer 2604/RTC gates remain disclosed pending.

Continue from existing outputs; never duplicate running jobs or rerun unchanged
whole suites merely because a heartbeat fired. Use fresh output names and save
concrete checkpoints. Notify only meaningful milestones, failures or required
owner action. RTC/acceptance automations remain active; workload soaks stay
stopped and beta35 prerelease remains paused.


## October 18 empty-bank hardware and local candidate closure

Both owner-requested physical full-system RAM migrations passed: original SXB6 WDC on 2609 and published beta4 on 2604, each with erased B0/B1/B2, 22 device-verified transfers, full bf1/UCHESS/BATCH checks and saved RAM loader acknowledgment (no extra host readback). Windows cmd and native Ubuntu WSL clean extracted candidate workflows passed. Candidate packages and a STR8-N-only all-apps image are in `output/releases/str8n-2.0bf1-migration-candidate-2026-10-18-r1`. Fourteen manuals include platform/installed-board quick starts, name/clock setup, ABI tables, Mermaid source diagrams and credited uChess source. Evidence is in `output/qualification/bf1-empty-bank-candidate-closure-2026-10-18-r1`. Publication remains held; Linux physical serial, prior RTC preservation failure and broader gates are not passed. Both workloads and RTC sampling are owner-stopped; do not restart them.
