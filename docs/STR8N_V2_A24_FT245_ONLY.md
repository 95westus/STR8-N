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

Build: `make v2-a24-check`. The targeted host model checks normal FT245 commands,
public console selection after USB removal, absent-USB startup, and zero ACIA
register accesses. The linked monitor suite also passed. Existing legacy ACIA
suite cases require revision before they can serve as an a24 full regression.

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
and cancel tests. The legacy full suite has ACIA-specific expectations and
is not an a24 qualification result.
