> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Four-board migration qualification plan for beta32 / stable 2.0

**Assignment update, 2026-10-16:** the owner subsequently requested 2205 as a
second complete beta32 prerelease board alongside 2512. Its beta25 -> beta32
installation is recorded in `STR8N_V2_BETA32_2205_2026-10-16.md`. The published
beta4/beta1 fixture assignment below is deferred; installing those fixtures
would require another explicit assignment. The WDC fixtures and opaque backup
bank copies described in later discussion have not been installed by this
update. Keep the 2512 soak stopped.

Recorded 2026-10-16. Planning only: no fixture has been installed by this plan,
no migration or restore has been run, and no flashing is authorized yet. Keep
the 2512 soak stopped. This is a 2.0 release plan, independent of v2.1 ABI work.

Use the completed beta32/support checkpoint `e97d785` as the proposed release
branch base, excluding subsequent v2.1 source and tests. The plan itself may be
carried onto that release branch as a documentation-only change. Freeze the
exact target build and dependency/source manifest before preparing installers;
current deployment tools and historical migration success do not qualify every
source-to-beta32 path. A later changed stable banner/image needs its own hashes
and affected tests; renaming a package does not qualify new firmware bytes.

## Fixture assignments and recorded starting state

| Board / USB identity | CPU | Last verified starting firmware | Proposed migration-source fixture | Test route |
|---|---|---|---|---|
| 2604 / A10MQGVHA (last COM5) | 65C02 | Beta25 B, beta24 A; crypto display was RAM-only | Exact identified WDCMONv2/SPI image for this board | WDC/SPI source -> frozen beta32 target |
| 2609 / A10MPQXCA (last COM8) | 65C816 | Common-code beta32 B, beta28 A, CLOCK 1.9 | Exact identified WDCMONv2 816 image | WDC 816 source -> beta32 in qualified emulation profile |
| 2205 / A10MPUPNA (last COM3) | 65C02 | Beta25 B, beta23 A | Published STR8-N beta4 package; additional published beta1 case sequentially | Published source -> beta32, through required package-owned intermediate stages |
| 2512 / A10MQFLCA (last COM4) | 65C02 | Beta32 B, beta28 A, CLOCK 1.9; stopped soak and restored CPU RAM | Existing verified beta32 prerelease | Same-target/no-op/refusal baseline; later explicit final-2.0 update if its bytes change |

These are recorded states, not a fresh live inventory. Resolve by USB serial,
not remembered COM number. All four most recently had EDU ON, RTC and 128 KiB
SPI SRAM. Record actual component availability before each run. Do not turn
off EDU merely to fabricate missing hardware; test software OFF separately
and qualify real absent-device behavior only in a suitable fixture/model.

2609 is the only 816 board. Beta32 qualification on it remains documented even
while its physical contents temporarily serve as a WDC migration fixture. No
separate 2.1 hardware allocation or alpha installation is part of this plan.

## Three independently recoverable checkpoints per board

**A: original board checkpoint.** Before setting up a source fixture, take two
independent exact reads of all four 32 KiB flash banks and all 131,072 SRAM
bytes. Archive active application RAM using a preserving RAM-only procedure,
saved-program inventory, application/library ownership, CPU/mode, selected and
preferred monitor, full configuration, board name, EDU state and RAM limit.
Capture EEPROM ordinary history and readable identity/status, EUI binding,
RTC UTC/local offset/control/trim and battery policy where present. Record
host/RTC time observations without setting time or trim. Do not read crypto
keys or modify provisioning. Record all source-image and tool hashes.

**B: verified migration-source checkpoint.** After a separately authorized
fixture setup, verify the intended source boots through physical RESET and
its supported transport. Read its complete flash twice and bind an exact B
manifest, expected geometry/layout, stock CPU model and any retained B0 copy.
Archive retained data again. This checkpoint is what the migration actually
starts from; it must not be confused with original checkpoint A.

**C: verified target checkpoint.** After a separately authorized migration,
capture exact target flash, startup, version/ABI/slot and preserved-data
receipts. Keep A and B immutable. Store backups under ignored owner-local
qualification paths with SHA-256 manifests and a second independent backup
location; exclude vendor images and raw board data from Git/public packages.

Before any fixture write, prepare and rehearse both B -> A and C -> B/A restore
plans with their exact preimages, sector allowlists and verification. Retain a
known working external flash-programmer rescue path and the correct original
board image before replacing recovery/reset code. If that rescue path has not
been established, fixture installation remains blocked; a software return
through recovery is not a substitute when recovery itself may be overwritten.

## Per-board migration and return paths

### 2604: WDCMONv2/SPI source

1. Identify the intended WDCMONv2/SPI version and exact full image; do not assume
   that a four-byte signature or historical stock banner establishes identity.
2. Preserve A (current beta25 environment and retained storage), then prepare a
   qualified A -> WDC fixture installer. Historical v1/alpha WDC migrations are
   reference evidence, not a qualified direct beta32 route.
3. After authorization, install/verify B. Test WDC RAM loader/transport and
   device access without destructive SRAM initialization or EEPROM writes.
4. Qualify the package's WDC/SPI -> beta32 route, including retained-vendor-copy
   handling and safe rejection of occupied/conflicting destinations.
5. From beta32 C, exercise the exact CPU-correct WDC restore to B; verify stock
   RESET/transport and full-bank hashes. Then restore original A unless the
   owner explicitly chooses to keep B or C.

### 2609: WDCMONv2 816 source

1. Locate and hash-verify the original CPU-correct 816 stock archive. **Current
   B0 is erased** in the latest complete readbacks; do not use an old instruction
   saying to copy B0 to B3 without independently checking the source bytes.
2. Prepare A -> B fixture setup and rescue, including correct native/emulation
   entry/exit and reset vectors. Never substitute a 65C02 vendor image.
3. Test B -> beta32 C from the real WDC 816 loader state; verify the resulting
   monitor is in its supported emulation profile, with RAM ABI calls and the
   advertised native interrupt-vector contract tested separately.
4. Exercise C -> B using the validated 816 restore tool; verify actual physical
   RESET and WDC identity/transport, not just a successful software jump.
5. Restore original A by default, with the board's own settings and accounted
   wear; retain both source and target evidence.

### 2205: published STR8-N sources

1. Verify the published beta4 package and hashes, prepare A -> beta4 fixture B,
   and verify the complete fixture rather than only its banner. State whether
   it is a clean published layout or a populated-user-data layout.
2. Qualify beta4 -> beta32 using the target package's source recognition and
   complete planned intermediate stages. Existing beta4 -> beta25 qualification
   is useful evidence but does not finish this later route.
3. Test supported A/B source choices, erased versus occupied destinations,
   saved startup/EDU settings, and mixed old/new-monitor semantics. Do not
   advertise newer services through an older fallback that cannot initialize them.
4. Restore B and verify an actual repeatable starting fixture. Separately run
   the published beta1/a24c1 F-only layout -> beta32 conversion on this board,
   with its own B manifest and rehearsed restore. Beta1 lacks the normal A/B
   fallback; model-only recognition must not be called hardware qualification.
5. Return to original A by default. Repeating published-source cases on the
   816 is a later matrix extension if required by the final support claim;
   one 65C02 run does not establish every source/CPU combination.

### 2512: beta32 prerelease baseline

1. Confirm stopped-soak RAM restoration and capture fresh A/B (identical unless
   explicit setup is needed). Preserve beta32 B, beta28 A and CLK 1.9.
2. Verify an identical-target request performs no erases or persistent writes.
   If the supported tool refuses instead of treating it as a no-op, document
   that deliberate behavior. Selecting the fallback must not overwrite the
   already installed target when the appropriate action is to boot/promote it.
3. Use offline fixtures for stale preimages, corrupted transfers and invalid
   metadata. A genuinely changed final-2.0 image requires a fresh planned
   beta32 -> final route and its own later write authorization; do not simulate
   a version upgrade by gratuitously reflashing beta32.
4. Check A/B/J3, utilities, BATCH success/error/Esc, retained CLK and write-free
   queries. Return to A if any persistent target changes were authorized.

## Common qualification and restore rules

- Model exact fixture setup, migration and return sector plans before hardware.
  Refuse unknown source images, wrong CPU/bank, stale backups, short/corrupt
  payloads, ambiguous records and insufficient relocation space before mutation.
  Validate actual geometry and permitted units; a 256-byte allocation page,
  64-byte API transfer and 4096-byte flash erase are different constraints.
- Exercise migration transport interruption/cancellation and commits in models,
  including reset/recovery behavior. Do not perform an electrical mid-program
  power cut as part of ordinary migration testing. Any such test needs an
  explicit destructive-test plan and verified external rescue.
- Keep opaque B0/user images independent from system code. Never erase or
  overwrite an occupied bank simply because a reference candidate uses it.
  Preserve, relocate under a verified plan, or refuse. Cover erased B0, an
  already-preserved matching stock copy and conflicting B0 as separate cases.
- Verify full flash after every setup, target install and restoration, not only
  updated sectors. Preserve fixed recovery and fallback byte-for-byte when ABI
  compatibility allows. Where the recovery ABI changes, explicitly qualify
  the replacement/rollback path; do not claim an old fallback still works.
- Pre-account known STR8-N erase attempts and keep an external ledger during
  WDC operation, when no STR8-N journal may exist. An operational return to A
  must not roll wear counts backward: preserve its settings and original
  records while publishing a verified journal update accounting for all known
  fixture/migration/restore erases. Reconcile expected hashes to that permitted
  journal difference. A forensic byte-exact old image is a separate archive,
  not permission to pretend subsequent erase attempts never happened.
- By default, retained SRAM and EEPROM are not test scratch. Any authorized
  mutation uses separately backed-up records/ranges and verified restoration.
  Preserve RTC progression, trim, offset, EUI/binding, battery policy and saved
  application records. Do not blindly restore old RTC/calendar bytes.
- Physical RESET/power-retention checks may create legitimate outage-history
  events. Archive before/after and verify the expected ring update separately
  from unchanged slots/identity/settings; do not erase real evidence to force
  a false byte-identical history claim. Distinguish J3 from physical RESET.
- A failed run stops with logs and a durable pending-restoration record. Finish
  or recover that restoration before another fixture. Do not restart a soak,
  apply trim, initialize storage or provision crypto as a side effect.

## Exit criteria and current limits

Each accepted source/target/profile needs setup, migration, boot, complete
readback, retained-data and exercised restore receipts bound to the same hashes.
Source fixtures must be repeatable; a successful target boot alone is not enough.
Record the final board state A/B/C explicitly. Default final state is A.

This four-board allocation is a starting matrix, not proof of all published
versions or all source/CPU/EDU combinations. Close gaps with sequential fixtures
and representative hardware, or explicitly narrow the release support claim.
Current unknowns include the exact WDCMONv2/SPI fixture identity, availability
and verification of owner-local original images/programmer rescue, final beta32
source-only build closure and direct package support for every intended source.
This document resolves none of those by assuming historical tools still match.

References: [upgrade contract](STR8N_UNIFIED_MIGRATION.md),
[published beta4 qualification route](STR8N_V2_B4_TO_BETA25_2026-10-14.md),
[historical 816 stock restore](STR8N_V2_2609_B0_TO_B3_RESTORE_2026-09-30.md),
[common-code beta32 on 2609](STR8N_V2_BETA32_COMMON_CODE_2609_2026-10-16.md),
and [soak stop/restoration](STR8N_V2_BETA32_SOAK_STOP_2026-10-16.md).
