# STR8-N v2.0a24 FT245-only console

The a24 console always selects FT245. Startup, monitor commands, and the public
RAM/ROM console entries do not initialize, poll, read, or transmit through ACIA.
The ACIA implementation remains in the RAM worker source for later re-enabling.
`BOARD_QUERY` reports FT245 and its present status; ACIA flags are clear.
With USB absent, console output waits for FT245 readiness.

The guarded F updater accepts the exact a23 F image and backs it up to B2:F.
The E extension was relinked because it calls RAM worker addresses that moved
in a24. A separate E updater accepts the exact previously verified E sector,
preserves its configuration and saved records, and changes four extension bytes.
Each updater verifies its programmed sector. No sector readbacks were performed.

Build and host regression: `make v2-a24-check`. The a24 runner covers boot,
handoff, vectors, capabilities, the RAM ABI across all resident/caller banks,
monitor commands, S19 loading, flash operations, configuration, interrupt
probes, S/R/T, and absent-extension behavior. FT245-only checks replace the
legacy backup-console expectations and include delayed USB arrival and zero
ACIA register accesses. The native 816 probe is checked structurally; its
execution still requires the physical 816 board. A successful run writes
`BUILD/v2-alpha24/a24-regression.json` with the tested image hash.

## Remaining current-alpha prerequisites

- Complete physical regression with exact E/F readback, physical reset, and
  cold power-cycle evidence. Retain the artifact hashes and transcripts.
- The [a24 WDCMONv2 installer and bank maintenance kit](STR8N_V2_A24_WDCMON_MIGRATION_KIT.md)
  passes offline build and host checks. Board 2609 returned WDCMONv2 `SXB6`
  through the binary interface; the physical migration path remains untested.
- Record the 816's stock identity and bank inventory, preserve its stock image,
  and qualify migration and native execution on that board.

The next alpha is the EDU presence/RTC test described in
[the agreed requirements](../TASKS.md#current-alpha-and-next-edu-alpha-agreed-2026-09-30).
Future upgrades must preserve static-bank maintenance `.a`/`.s19` compatibility
with S/R optional. A complete ABI freeze awaits the explicit interface inventory.
The a24 rebuild reports 31 bytes free before the vectors; EDU resident hooks
and the optional E-sector HAL still require a measured fit.

## Host prerequisite evidence, 2026-09-30

`make v2-a24-check` passed all 15 reported checks/suite groups. The result
receipt explicitly leaves physical hardware and native 816 execution untested.

The rebuilt E/F image SHA-256 is
`988795dc7c211302f9295d6e1afd1fc7d3d7eafd29541c6d4963353ce26bf457`.
The exact-F updater and board-specific E updater host tests passed, including
backup/recovery and mismatch/cancel refusal. The existing a22 maintenance S19
also passed its copy, occupied-destination refusal, erase, and B3-protection
cases against the a24 model, both with S/R present and with its code erased.
This is scoped S19 compatibility evidence; the `.a` carrier and physical 816
maintenance paths still need qualification. Local logs are
`tmp/a24-maint-compatibility.log`, `tmp/a24-maint-without-sr.log`, and
`tmp/a24-prerequisites.log`.

## Board 2205 installation, 2026-09-27

Installed over COM3 in two steps: guarded F update, then guarded E relink.
Both reported `VERIFIED` and returned to `B3>`. The a24 banner appeared after
a software J3 restart. Board commands passed: `C` returned `C 00 00 V 0A`;
`T 3` retained the `8FF0 ... TEST` record; `R 3 8FF0` returned `Done` and
`D 2000 2003` showed `12 34 56 78`; `?` listed the expected commands.
The board was left at `B3>`. Physical reset and cold power-cycle behavior were
not exercised in this session.

Evidence: `output/qualification/board-2205-a24-2026-09-27/` contains the F and
E installation transcripts and command checks. `test_v2_a24_top_update.py`
passed exact-old-F rejection, backup, install, restore, and mismatch tests;
`test_v2_a24_e_update.py` passed exact-old-E rejection, update, preservation,
and cancel tests. This installation record does not establish full physical
a24 regression or W65C816 qualification.
