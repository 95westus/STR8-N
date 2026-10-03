# STR8-N 2.0 beta 1

Release tag: `v2.0b1`. Package: `str8n-v2-b1.zip`. Date: 2026-10-03.

Beta 1 promotes the exact qualified **2.0a24c1 firmware** on W65C02SXB and
W65C816SXB. Its banner, filenames, launchers and installer confirmation
remain a24c1. Use `INSTALL-A24C1.ps1` on Windows or `INSTALL-A24C1.sh` on
Linux, and type `INSTALL STR8-N 2.0A24C1` when instructed. Maintenance
remains version 1.0. The beta release changes documentation, qualification
status and packaging; it does not change the tested firmware or launchers.

## Flashing disclaimer

**WARNING - power failure during flashing can be dangerous.** Loss of power
during flash erase/programming, installation, maintenance or a configuration
save can corrupt firmware or boot vectors and leave the board unbootable.
Recovery may require an external flash programmer. STR8-N does not guarantee
power-loss recovery or automatic rollback. Keep power stable, retain a
recovery backup, and do not disconnect USB/power or press RESET/NMI until
the operation reports verified completion.

## Qualification and limits

- [Migration/reset acceptance](STR8N_V2_A24C1_TWO_BOARD_ACCEPTANCE_2026-10-03.md):
  stock migration is owner-confirmed; physical RESET, correct CPU banners,
  responsive prompts and exact installed-core readbacks were captured on
  boards 2205 and 2609.
- [Cold/config acceptance](STR8N_V2_A24C1_COLD_CONFIG_ACCEPTANCE_2026-10-03.md):
  cold power cycling, configuration save/persistence, fixed-address autostart
  and S hold passed on both boards.
- [Practical regression](STR8N_V2_A24C1_REGRESSION_ACCEPTANCE_2026-10-03.md):
  commands, S19 load/run, bank handoffs, cross-bank RAM ABI, BRK/IRQ,
  physical NMI and maintenance passed; 2609 also passed native BRK/NMI.
  The first 2205 NMI attempt timed out; the repeat passed.
- [Backup/recovery](STR8N_V2_A24C1_BACKUP_RECOVERY_ACCEPTANCE_2026-10-03.md):
  linked flash-fault model checks passed. Both boards exercised backup/
  guard and R/O routines with RAM fixtures, followed by exact bank restoration.
  Actual physical flash-failure entry/recovery remains unqualified.

This is scoped beta qualification. Native IRQ/COP/ABORT, other guest firmware,
ACIA/EDU, headless/precise timing, the wider stress matrix, and interrupted-
write/power-loss recovery are not established. The a24c2 RAM-layout proposal
is not included. The 816 monitor and normal monitor services run in emulation
mode; native-vector probe results do not establish native console services.

## Package and identity

The 23-file ZIP contains the original 18-file installation kit plus these
release notes and four qualification records. Begin with
[QUICKSTART](STR8N_V2_A24C1_QUICK_START.md). Printable quickstart, operator
manual and maps are regenerated from the current guides. The archive
contains no board dumps, private stock images, recovery backups or test
fixtures. The adjacent `.sha256` file identifies the complete ZIP.

Factory core F SHA-256:
`231fbec1b0e6a1e80f4a956009aa74f6259e4f0dfcf761f09f16755832aece36`.

Installer S19 SHA-256:
`a9f3a156c91483b012265e4de9c52f90ad703241b5b8b06016a4ab5755185726`.

Maintenance S19 SHA-256:
`e435141e41430a96bed362f60d50931168c6377233950605764a73d88a341327`.

Build and verify with `python tools/package_v2_a24c1.py --beta1`.
The package checks image hashes, allowed files, local guide links and ZIP
readback. The extracted Windows and Linux launchers also support
`-ValidateOnly` and `--validate-only`, respectively.
