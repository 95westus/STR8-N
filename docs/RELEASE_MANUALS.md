# STR8-N release manuals

## Current beta 1 release (2.0a24c1 firmware)

Release `v2.0b1` retains the exact tested firmware and launcher names.
The [beta notes](STR8N_V2_BETA1_RELEASE_NOTES.md) describe its qualification,
power-failure disclaimer and untested limits. The beta ZIP includes the
current printable guides and all four acceptance records.

Use the [quick start](STR8N_V2_A24C1_QUICK_START.md),
[detailed technical guide with Mermaid diagrams](STR8N_V2_A24C1_TECHNICAL_GUIDE.md),
[operator and technical manual](STR8N_V2_A24C1_MANUAL.md),
[maps diagrams and charts](STR8N_V2_A24C1_MAPS.md),
[stock installer guide](STR8N_V2_CONFIG_WDCMON_INSTALL.md),
[configuration guide](STR8N_V2_FLASH_CONFIG.md), and
[bank maintenance 1.0 guide](STR8N_BANK_MAINT_V2.md).

Printable current copies are in `output/pdf/STR8N-A24C1-*`.
The [release ZIP contents](STR8N_V2_A24C1_RELEASE_ZIP_PROPOSAL.md) lists the
packaged files. a24c2 remains a proposed layout. The
[two-board acceptance record](STR8N_V2_A24C1_TWO_BOARD_ACCEPTANCE_2026-10-03.md)
closes the beta 1 migration/reset milestone. Qualification remains scoped
to the linked records; beta packaging refreshes the printable guides.

The [cold-start/configuration record](STR8N_V2_A24C1_COLD_CONFIG_ACCEPTANCE_2026-10-03.md)
passes beta checklist item 2 on both boards: cold power, configuration
save/persistence, fixed-address autostart and S hold.

The [practical regression record](STR8N_V2_A24C1_REGRESSION_ACCEPTANCE_2026-10-03.md)
passes beta checklist item 3 on both boards, including RAM ABI, BRK/IRQ,
physical NMI, maintenance and restored-bank verification; 2609 also passed
native BRK/NMI. The record lists untested cases and retained attempts.

The [backup/recovery record](STR8N_V2_A24C1_BACKUP_RECOVERY_ACCEPTANCE_2026-10-03.md)
completes item 4 within its stated model/physical-fixture scope. Actual flash
failures were modeled; both boards exercised backup/guard and R/O routines
without induced hardware failure. All banks were exactly restored.
The beta package retains the tested bytes and includes these evidence records.

## Native Linux test

The [owner-reported Linux test](STR8N_V2_A24C1_LINUX_TEST_2026-10-02.md)
passed on 2026-10-02.

## Historical records

Older quickstarts, operator manuals, maps, migration instructions and
checklists have been removed. Use the a24c1 guides above for installation
and operation. Dated board test reports, source history and qualification
evidence remain available; their results apply to the versions tested.
