# STR8-N 2.0a22 COM3 regression sweep

Date: 2026-09-26 (America/Chicago). Target: W65C02SXB with EDU Kit,
8 MHz, FT245 on COM3. This checks the dot-enabled 2.0a22 E/F pair installed
in Bank 3. The board was left at the Bank 3 monitor prompt.

## Image and configuration

The a22 build completed with 4,064 resident bytes ending immediately before
vectors, 1,208 E-extension bytes, and a 759-byte RAM worker. Rebuilt F matched
the board exactly, SHA-256
`1bae74704dd5c66ca34fa8d3b1bdfa9f2cf65ffab72a724a8eba87888420a439`.
Rebuilt `$E800-$EEFF` also matched the board. The final full B3:E/F readback
has SHA-256 `a3da9523dfb2e3778efa91f89fa738a7cbfd85ac6eb27527fcaee27340ce6b12`.
Compared with the post-install readback, every E/F byte outside the 16-byte
configuration pocket was unchanged. The current configuration is disabled,
Bank 0, vector mode, delay `$0A`, bytes
`01 00 00 00 00 0A 01 00 00 00 00 00 00 00 0C 70`. This configuration
was present at the start of this sweep; the sweep did not change it.

## Host suites

| Gate | Result |
| --- | --- |
| `make v2-check`: rebuild plus boot, ACIA model, B3 migration, monitor, load, flash, config, interrupt suites | PASS, exit 0 |
| `python tools/build_v2_a22.py` | PASS; exact board F and E-code match |
| `python tools/test_v2_a22_sr.py` | PASS: S/R/T, direct ABI, boot dots/headless and late FT245, error paths |
| `python tools/test_v2_a22_e_install.py` | PASS: staged E with neighboring/configuration preservation |
| `python tools/test_v2_a22_e_repair.py --dot` | PASS: exact E preflight, rollback, mismatch/cancel |
| `python tools/test_v2_a22_e_repair.py` | PASS: historical E repair against its archived images |
| `python tools/test_v2_a22_top_update.py --dot` | PASS: exact F preflight, B2:F backup, recovery, mismatch |
| `python tools/test_v2_a22_top_update.py` | PASS: initial top update path |
| `python tools/test_v2_a22_top_update.py --repair` | PASS: historical cold-start F repair against its archived images |

The baseline interrupt suite prints `FAIL` and `TIMEOUT` for its deliberately
injected negative probe cases; its final assertion and process exit passed.
The historical F-repair test initially compared its archived updater with the
new dot image and failed that test assertion. The harness was corrected to
compare with the archived repaired F image; rerun passed. No firmware or board
state changed in this correction.
The `v2-check.log` SHA-256 is
`c56434d23063737f0a91b3aedad9480fe5f90aa89cf3a6a999a4b283ee8657d6`.

## COM3 board checks

| Gate | Result |
| --- | --- |
| Resident/extension identity | B3:F `SN 02 00`; E descriptor `SR 01 01 18`; CPU `$02`, FT245 console `$00` |
| Bank selection/display | B0-B3 selections, selected-bank F headers, and B0/B1 vectors read without changing B3 residency; B2:F shows previous a22 top |
| Configuration/help | `C` reported `C 00 00 V 0A`; `?` listed S/R/T and existing monitor commands |
| Record listing and rejection | `T 3` listed `8FF0 2000-2003 0004 C TEST`; invalid `R 3 8000` returned `SR error 04`; occupied `S 3 8FF0 ...` returned `SR error 02`; record bytes were unchanged |
| Extension protection | `S 3 E800 2000 2003` returned `SR error 01` without a write |
| RAM edit/restore | `M 2000 00 00 00 00` read back zero; `R 3 8FF0` reported `Done` and restored `12 34 56 78` |
| RAM ABI | RAM-loaded `G 2000` probe printed `B0 B1 B2 B3 RAM ABI: PASS` and returned to B3 |
| BRK/VIA1 IRQ | RAM-loaded probe printed `V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS` and returned to B3 |
| Physical NMI | Operator pressed NMI while the RAM probe printed `PRESS NMI`; probe reported `V2 NMI / A-X-Y / STACK / RTI: PASS` and returned to B3 |
| Software monitor restart | `J3` printed 160 dots, banner, and `B3>` under disabled autostart |
| Physical RESET | Operator pressed RESET once; receive-only capture recorded 160 dots, banner, and `B3>`; post-reset `T 3` and `C` still returned the test record and `C 00 00 V 0A` |

The physical RESET raw capture is 219 bytes, SHA-256
`45f5e45f58ef8b4dacf047026a7f934390a9a83c1af18d73f7f3bd1305765377`.
The previous [dot update installation report](STR8N_V2_A22_COM3_INSTALL_2026-09-26.md)
records the same installed pair's separate USB power off/on test with enabled
autostart: 148 dots, Bank 0 EDU Kit startup, and operator confirmation that
RESET was not pressed.

All new COM3 commands in this sweep were read-only or RAM-only. The save
program path and guarded E/F flash updates have the earlier physical evidence
in the installation report and current linked-code model coverage; no new
flash record or deliberate flash fault was created in this sweep. Direct S/R
application ABI calls were model-tested, not called from a new board probe.
ACIA receive remains unqualified, W65C816 hardware was unavailable, and
interrupted-write/power-loss recovery was not tested.

Logs, raw capture, and final readback are under
`output/qualification/board-com3-a22-regression-2026-09-26/`.
