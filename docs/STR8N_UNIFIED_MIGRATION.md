> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Source-aware monitor migration

## Intended published upgrade contract

Every published v2.0bX release should be able to upgrade to any later published
v2.0bY through one upgrade command. The published b1 and b4 packages establish
the two starting layouts. Later releases must retain this forward-upgrade
contract for their descendants.

The target package owns source recognition, layout conversion, settings/data
migration, compatible fallback selection, required intermediate stages, and
verification. Users should not choose ABI profiles, rebuild an installer, or
manually install intermediate releases. Exact source identity and layout checks
must precede mutation; an unknown or corrupt image still requires diagnosis.

Forward-upgrade availability and rollback are distinct guarantees. A b1 layout
conversion preserves a complete backup for restoration. A/B upgrades retain an
old monitor when the target shared firmware supports that monitor's ABI. A
future ABI break needs an explicit rollback strategy and qualification without
removing that source release's ability to upgrade.

Release qualification must cover the supported published source/target matrix,
including b1 conversion, b4 and descendant layout revisions, settings and user
data, active A/B selection, interrupted transfers/commits, recovery, exact
readbacks, and representative hardware. A release cannot advertise family-wide
support from source recognition tests alone.

This is the intended contract, not the current qualification claim. The current
implementation qualifies beta23 generation 32 and beta24 generations 34/35
planning to beta25. Physical upgrade/retest on 2205, 2512, 2604 and 2609 passed;
all four boards now run beta25 in B with the prior A monitor retained. Legacy b1 is
recognized and refused pending conversion qualification. Other historical
sources and arbitrary later targets are not yet qualified.

## Current implementation

`tools/migrate_v2.py` uses a complete, repeated four-bank backup and the active
monitor read from the board. It identifies the installed core and active monitor
by exact registered images. A compatibility token alone is insufficient.

For supported A/B sources, the planner retains the active monitor byte for byte,
selects the other slot, installs the required shared components, and makes the
new monitor the default. Both monitors subsequently use the updated shared
components: for example, TIME becomes local date/time and offset on both.
R CLOCK retains its detailed information.

The beta23 profile retains the beta23 fixed-F private validator at F30D. The
beta24 generation-34 profile retains F318 and generation 35 retains F31B.
These profiles are all beta25; their
source ABI differs so the old monitor can remain usable. The profile builder
checks old monitor references, journal entries, worker/vector identity, and the
actual linked validator address in both new monitor images. The profile token
is distinct from the whole-core identity CRC.

The board number does not select firmware or slot A/B. It selects the expected
FTDI serial number for the one hardware connection. The verified installed
images select the ABI profile, and the active slot selects which slot to retain.
The planner preserves configuration, EDU mode, identity/offset/name records,
unrelated flash, EEPROM and SRAM. A source with EDU OFF remains OFF.

## Workflow

The fleet entry point `tools/upgrade_v2_fleet.py` inventories all requested boards
with repeated flash backups, captures retained references for boards needing an
upgrade, verifies already-current boards without writes, and arms receive-only
physical boot capture. Plans and mixed-image qualification receipts are kept
per board. `tools/retest_v2_migration.py` uses the plan's board identity, source
version/generation, stored offset and name for hardware qualification.

1. Resolve one requested board by FTDI identity. Record the active slot. Capture
   all four flash banks twice and verify their hashes. Capture retained devices
   and, when present, both copies of the complete SRAM array.
2. Run `migrate_v2.py inspect --root <backup-root> --board <board>`.
3. Run `migrate_v2.py prepare --root <backup-root> --board <board>`. The default
   target selection uses an available beta25 profile with the matching ABI.
   An explicitly qualified package can be supplied using `--build`.
4. Rehearse the exact installer with `test_v2_unified_migration.py --root
   <backup-root>`. Run firmware and mixed-monitor suites for that exact package.
   Audit checks bind results to firmware hashes and the prepared bank results.
5. Run `migrate_v2.py install --root <backup-root> --board <board>`. The installer
   rechecks every complete preimage before loading, checks each transfer before
   erasing, executes from RAM, verifies sectors, and commits MAINT and the new
   monitor only after their contents are complete. It requires physical RESET.
6. Capture the physical boot; exercise both monitors, startup keys/menu/recovery,
   TIME, CLOCK, APPS, MAINT, ABI/interrupt probes and wear counts. Compare all
   flash banks and retained devices with the bound expected results.

The initial replacement of shared F is not power-failure atomic. Keep board
power stable until the RAM installer reports verification. The fallback promise
applies after the complete migration, not to an interrupted F erase/program.

An active monitor already at the target version/generation refuses a further
update, preserving the fallback. Unknown firmware, altered cores, incompatible
ABIs, exhausted journal/count fields, stale backups and corrupt transfers refuse.
Later release packages require their own compatibility checks and qualification;
recognizing an image does not qualify an arbitrary future target.

## Legacy v2.0b1

The same source inspection recognizes the historical beta1/a24c1 core, including
its mutable startup configuration. That layout has no A/B slots. It cannot be
updated under an inactive-slot-only promise or preserve a directly bootable b1
monitor in the new layout. Preserve its complete original backup for rollback.

The planner currently stops with `legacy-conversion-required`; it does not
silently select a slot or perform a conversion. The historical conversion tool
is `tools/beta4_migration.py`. A complete b1-to-current conversion route still
needs qualification before execution through this workflow. No legacy hardware
conversion was performed as part of the 2205 beta23 update.

## Published b4 conversion qualification (October 14)

The unified launcher recognizes the published b4 kit, verifies every kit member,
and selects beta25's compatible F30D profile automatically. It retains the active
b4 monitor byte-for-byte and writes only the inactive monitor. Before replacing
b4's B3:8000-9FFF MAINT record with the RTC provider/journal, it stages verified
MAINT in B1 and installs CLOCK, SRAM, WORK, EDU and display assets in their
current locations. Unknown occupied destinations and crossing/duplicate user
records refuse without writes. Existing user records outside those ranges are
preserved; the launcher does not automatically move or discard them.

A complete b4 layout conversion uses 17 sector rows. Its RAM installer has a
24-row table; beta25 ROM artifacts remain byte-identical to the qualified b23
ABI profile. Every SR header is published after its full record is present;
the new monitor's commit is the final flash mutation. Configuration and wear
counts carry forward. b4 has no identity/name/offset journal, so new services
start unbound, unnamed and at UTC+00:00. No EEPROM/SRAM initialization, clock set
or trim change is performed.

The retained b4 monitor keeps its original capabilities. It has no TIME command
and does not initialize the new RTC/SRAM services. CLOCK reports services
unavailable safely there; boot beta25 for the new services and local-only TIME.
Old/new P selection, RAM edit, saved-record listing, MAINT, HOLD and recovery
are covered separately from beta25 service tests.

Both A-active and B-active pure-b4 layouts have passed exact installer execution,
source/payload refusal tests, commit ordering and mixed-monitor linked tests.
Physical b4-to-b25 qualification on 2604 passed, retaining b4 A and installing
beta25 B. The physical source retained existing system programs in B1/B2; the
full installation into empty B1/B2 is covered by both 17-sector model cases.
The original beta24 A / beta25 B was restored afterward, with all 19 additional
erases accounted and full SRAM, repaired EEPROM history and RTC settings
preserved. See [the qualification report](STR8N_V2_B4_TO_BETA25_2026-10-14.md).
Evidence: `output/qualification/beta25-b4-unified-2026-10-14/`.

Selecting a retained fallback when the target monitor and shared image are already
installed refuses a redundant rewrite; boot/promote the target instead.
