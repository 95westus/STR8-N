> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# 2512 migration qualification assignment

Owner designated 2512 on October 17, 2026 for two distinct bf1 migration tests:

1. **WDCMONV2 / WDCMON 2.00 to bf1**.
2. **Published STR8-N v2.0b4 to bf1**.

This board assignment does not establish route qualification. No firmware write,
reset, source restoration or target installation was performed to prepare this
plan. 2512 currently remains on its preserved beta35 configuration and RTC-only
collection; its former workload soak remains stopped. 2604 and 2609 continue
their authorized bf1 soaks, and 2205 stays off. Clocks/trims and the original
four-board RTC baseline remain unchanged. Native 816 applications/testing,
ACIA and crypto remain deferred.

## Exact inputs located

- Private 2512 WDCMONV2 bank image: 32768 bytes, SHA-256
  `2f0000c74eceec809a814e31f822702977d7bfed5ee6f3bc4869627864ca59a8`.
  The September 24 before/final readbacks match. The historical source board
  identity is SXB2 / HW 3.00 / WDCMON 2.00, a 65C02 board. This is an owner-local
  fixture, not a public distribution input or a fresh read of the current board.
- Exact published beta4 ZIP: SHA-256
  `4c25bc576cbc32efd04aeea4fe80c68544a50b80685d12bfcf1e44122bacbc14`.
  The local MON A, MON B, E and F components match its manifest. A beta4 profile
  must also account for the published maintenance provider and source settings.
- Target remains the unchanged generation-48 bf1 set. The complete clean
  programmer image is a provisioning artifact; it is not a preserving converter
  for either source route.

The fresh 2512 capture identifies beta35 MON B, generation 47, with A40 retained.
Its current B0 differs from the September whole-bank WDCMON fixture in sectors
8, 9 and A; the retained F sector still matches. The old stock installer's
erased-or-identical B0 copy rule therefore cannot be assumed to apply to a
historically staged source. Preserve current B0 and qualify an explicit
receipt-bound source/restoration policy instead of replaying a whole-bank copy.

## Qualification sequence

Before live changes, take a fresh preserving 2512 RTC snapshot and double-read
flash/EEPROM/full retained SRAM/application RAM backup. Confirm the board's USB
identity, current source, source hashes, settings and current wear history.
Retain the original baseline and every prior measurement.

Develop separate exact-source plans for WDCMONV2 and published beta4. The WDC
route needs the stock-monitor RAM transport, explicit vendor-image identity and
a verified recoverable source backup. Beta4 has a different recovery F image:
its recognition and earlier beta4-to-beta25 tests are not proof of beta4-to-bf1.
Both require target-specific core/layout conversion, owned-range collision
checks, preserved user data/settings and conservative wear accounting.

Prove linked installer execution, stale/unknown source refusal, corrupt/partial
input refusal, explicit activation/commit ordering, interrupted-state recovery
and original-source restoration offline. Bind every plan, helper, source,
target and transfer hash. Do not replay old clean installers after new wear or
configuration changes, or substitute a generic zero-wear image for preservation.

Only after those receipts pass should 2512 stage each historical source and
exercise the corresponding migration under the owner-coordinated physical RESET
procedure. Capture source boot identity before migration, exact final banks,
bf1 A/B identities, BATCH/ASM/CLOCK behavior, retained storage and restored
application RAM. Restore/re-admit source and preimages separately for the second
route; record every mutation and conservative counter increment.

Use a per-board operation guard under the shared serial lease. During a legacy
monitor/reset/installation interval the normal STR8-N RTC collector must skip
2512 explicitly while collecting 2604/2609; resume 2512 acquisition immediately
after a verified compatible idle state. No failed/skipped attempt counts as a
fresh sample. Never stop or restart the two soak workers to obtain this port.

The owner explicitly requires **both routes to pass before publication**.
Each route needs separate offline and hardware acceptance, including retained
storage preservation and verified original application RAM restoration. Neither
route is qualified yet. The four-hour 2609 soak alone cannot authorize publication.

The amended acceptance policy and publication checker enforce both route IDs:
`2512-wdcmonv2-to-bf1` and `2512-v2.0b4-to-bf1`. The publication automation is
paused while this work is prepared. Existing draft assets and sealed evidence
remain preserved; a qualified revision must update the public route scope.

## Separate offline converter candidate

`release/candidates/bf1-2512-legacy-r1` documents the new 24-row RAM installer
candidate. It uses the unchanged bf1 generation-48 payloads. Source staging and
each restoration reserve all planned erase attempts before erasing; current B0,
B1 user programs and unowned B2 ranges remain intact. Historical source staging
uses a verified host escrow for current B3:9C00-9FFF identity/policy/history bytes,
which are restored into the bf1 layout. No vendor image is a public payload.

The independent record-order check caught and corrected beta4 source staging
that published MAINT before its second sector was transferred. A new reservation
helper also needed an explicit branch to preserve the valid MON A preference
path when adding the empty WDC preference. The rejected runs and source copies
remain archived. These corrections affect only the converter candidate.

CPU tests cover exact-source staging/conversion, both bf1 monitor slots,
MAINT/CLOCK BATCH, documented assembler launch, conservative-wear historical
and original-payload restoration, source/transfer refusals and replay-bound cut
recovery. Host transport tests use the actual generated installer bytes with
simulated endpoints and require complete RAM readback before execution.

Core conversion is not guaranteed bootable during every F-sector interruption.
Exact cut-state recovery may require retained RAM execution or an external
programmer. Offline qualification does not establish a working physical WDC
RESET/debugger handshake, electrical power-loss safety, or hardware acceptance.
Before live use, take fresh preserving measurements/backups and re-admit every
current source, counter and mutable-record preimage. The offline plans are not
permission to replay stale bank captures on the device. No live launcher is
provided by this candidate.

## October 17 offline checkpoint

Both **staged source profiles** passed the separate offline candidate checks.
The WDC profile is the exact private diagnostic/monitor fixture with a wear
sidecar; beta4 uses the published generation-13 payloads with MON A explicitly
selected. This does not qualify other vendor images or beta4 source preferences.
The destination bf1 MON A and MON B were both exercised for each route.

| Evidence | Passed checks |
| --- | ---: |
| Conversion, boot/BATCH/ASM, restoration and mutation-cut recovery | 55 |
| Source admission, exhaustion and preservation guards | 24 |
| Independent record publication-order audits | 32 plans |
| Generated-installer RAM transports and corrupt-readback refusals | 12 |
| Full stock-debugger application RAM restoration without execution | 6 |
| Hash-bound recovery admission and unexplained-state refusals | 74 |
| Independent clean source rebuild | Identical templates and manifest |

The authoritative checkpoint is
`output/qualification/bf1-2512-legacy-offline-checkpoint-2026-10-17-r1.json`.
The CPU run is `bf1-2512-legacy-offline-2026-10-17-r6`. Receipts distinguish fresh
execution from reused, byte-equivalent archived execution; the count is not a
claim that every check is a fresh CPU run. The corrected pre-commit cuts verify
bank 3, the complete uncommitted prefix, the old journal sequence, and the exact
next commit mutation. An erase of an already-erased sector can leave identical
byte preimages at two trace prefixes; conservative reservations cover either.

No live board was accessed by this offline work. Neither route has hardware
acceptance. Both remain mandatory publication blockers, and the publication
automation remains paused. The next gate is fresh source/backup admission and
owner-coordinated 2512 hardware checks, including verified application RAM and
retained-storage preservation. Core-erasure recovery capability must be reviewed
before applying these routes. Existing soak and RTC collection remain active.

## Live hardware qualification started October 17

The owner authorized both hardware routes. A fresh 2512 preserving RTC sample
and double-read backup passed in `rtc-campaign-snapshot-2026-10-17-231648Z`
and `bf1-2512-pre-migration-backup-2026-10-17-r2`; original application RAM
restoration was verified before staging. All four source banks matched the
offline-qualified source exactly. The WDC historical-source transaction
completed all 21 transfers and reported device verification. Its receipt is
`bf1-2512-hardware-2026-10-17-r1/wdc-stage/report.json`.

Physical RESET with the stock debugger armed is pending. Neither migration
route has hardware acceptance yet. The 2512 operation guard remains blocked
while its stock monitor/installer is active; 2604/2609 workloads continue and
their RTC collection remains enabled. No controlled power interruption is part
of this authorization.

The owner also shortened the existing 2609 workload to four total monitored
hours. Policy r3 and a separately supervised deadline helper request the
existing worker's safe STOP at 01:52:06 UTC October 18 (8:52 p.m. CDT October 17).
The pinned six-hour runner is unchanged. A matching stop receipt, at least four
hours, complete workload coverage and verified original RAM restoration are
required; the two 2512 hardware route gates still block publication.

The WDC-to-bf1 transaction subsequently completed all 21 transfers. Physical
bf1 boot, both A/B software prompt entries, CLOCK/native BATCH success/error
paths and ASM execution passed on 2512. Double EEPROM, full 131072-byte SRAM,
final four-bank flash and RTC control/trim checks passed; original application
RAM restoration was verified. The hardware receipt is
`bf1-2512-hardware-2026-10-17-r1/wdc-bf1-hardware/report.json`.

The historical WDC source restoration then completed all 21 transfers with
conservative newer wear counts. Its physical RESET/source verification and
original beta35-payload restoration remain pending. The WDC route has not yet
received full acceptance, and the beta4 hardware route remains pending. Failed
initial debugger probes are retained; a paced RTS=1/no-CTS-gating identity probe
and actual wire audit established the successful stock connection and exact
RAM-only restoration. The firmware payloads were not modified to correct the
host probe.

The WDC route subsequently passed physical historical-source readback, exact
RAM restoration, original beta35-payload restoration and its post-RESET full
flash/wear, EEPROM/SRAM, RTC control/trim and RAM checks. Its accepted checkpoint
is `2512-wdcmonv2-to-bf1-acceptance-2026-10-17-r1.json`; the evaluator continues
to require the separate beta4 route. A preserving NIST sample at 23:55:45 UTC
passed, retained the original baseline, and overlapped the pre-migration offset
interval. Beta4 source staging is now in progress; its hardware gate is pending.

The staged published beta4 generation-13 MON A subsequently passed physical
boot and exact four-bank source checks, with original application RAM restored.
The qualified beta4-to-bf1 conversion is in progress; its hardware and
restoration acceptance remain pending.

The owner subsequently requested that, after migration and restoration
qualification succeeds, 2512 be left with the complete shared bf1 firmware.
This final installation is additional to the restoration qualification; its
verification must have a separate receipt. Keep 2512 powered on and eligible
for RTC sampling until the owner explicitly reports switching it off. Preserve
the original four-board baseline, clocks, trims and retained storage throughout.

The beta4-to-bf1 hardware checks subsequently passed: physical MON B boot,
both A/B monitor command paths, CLOCK, BATCH success/error cases and ASM,
double EEPROM reads, all 131072 retained SRAM bytes, final four-bank flash,
RTC control/trim preservation and exact original application RAM restoration.
Evidence is `bf1-2512-hardware-2026-10-17-r1/beta4-bf1-hardware/report.json`.
Historical beta4 and original-payload restoration checks remain required for
route acceptance; the historical-source restoration transaction is in progress.

Historical beta4 restoration subsequently passed physical MON A boot, exact
four-bank/source admission and original RAM restoration. The original beta35
payload restoration then completed all 21 transfers with device verification
and conservative newer wear history. Its final physical RESET, original-boot,
retained-storage, wear-history and RAM checks remain pending before the beta4
route can be accepted. The requested final bf1 installation follows that gate.

Both routes subsequently received acceptance. The beta4 original restoration
passed physical boot, exact initial/final flash, double EEPROM, full retained
SRAM, unchanged RTC control/trim, exact conservative reserved wear counts and
original application RAM restoration. Its checkpoint is
`2512-v2.0b4-to-bf1-acceptance-2026-10-17-r1.json`. These receipts cover the exact
qualified source profiles; they do not authorize arbitrary legacy images.
The additional owner-requested final complete bf1 load is being qualified
separately and remains pending hardware installation and verification.

The final-load offline CPU qualification passed ten checks, including both
bf1 monitor boots and four stale-bank, corrupt-row and partial-row cases.
Its sealed evidence is `bf1-2512-final-offline-2026-10-18-r1/seal.json`.
The final complete bf1 installation subsequently verified all ten transfers
on 2512. Physical RESET and final hardware/storage/RAM verification remain
pending; the board must stay powered on until the owner reports otherwise.

The final bf1 load subsequently passed physical boot, both monitor-slot
checks, double EEPROM and full SRAM comparisons, final four-bank flash and
RTC control/trim checks, and original application RAM restoration. A preserving
NIST snapshot at 00:37:22 UTC October 18 (7:37 p.m. CDT October 17) passed with
offset interval [-0.543344, +0.065598] seconds and verified RAM restoration.
The original four-board baseline is unchanged. The final checkpoint is
`bf1-2512-final-checkpoint-2026-10-18-r1.json`; 2512 is powered on, bf1, RTC-only
until an owner power-off report.

The new sealed local review kit is revision r5, SHA256
`2ac8219fdde8206f72133ddfd0be65634003240d8c0c114643791fe5fad8a723`.
It verified 180 files, 97 sources, 19 artifacts and 43 document links, plus
seven migration-extension acceptance/refusal checks. Prior review archives
and firmware payloads remain unchanged. The separate publication automation
is active again, subject to the four-hour 2609 stop/restoration and all existing
readiness gates; no publication has occurred at this checkpoint.

The owner then reported 2512 powered off. The report was recorded at
00:47:25 UTC October 18 (7:47 p.m. CDT October 17); the exact physical switch
time is unknown. Its final verified bf1 load, last powered-on snapshot and
original baseline are retained. RTC collection continues on 2604/2609 only;
2512 and 2205 ports must remain unopened until an owner power-return report.
The new powered-off interval cannot be measured until a future return snapshot.
