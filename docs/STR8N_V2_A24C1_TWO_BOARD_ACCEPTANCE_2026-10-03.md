# a24c1 two-board migration and physical RESET acceptance

Date: 2026-10-03. This closes the stock-migration plus physical RESET
milestone for beta 1. It does not close the broader hardware regression matrix
or publish a beta release.

| Board | Port | FTDI serial | Captured CPU banner |
| --- | --- | --- | --- |
| 2205 | COM3 | A10MPUPNA | `STR8-N 2.0a24c1 B3 65C02` |
| 2609 | COM8 | A10MPQXCA | `STR8-N 2.0a24c1 B3 65C816` |

## Stock migration: owner-confirmed

Both boards already ran a24c1 when this session began. Asked whether both
had been installed from stock WDCMON with the packaged launcher and had
reported `MIGRATION VERIFIED; PRESS PHYSICAL RESET`, the owner answered
"yes". That establishes an owner-confirmed installation result for both
CPU families. The original migration transcripts, installer hashes, backup
choices, and individual preservation results were not captured in this
session. No flash writes or repeat migration were performed today.

## Physical RESET and readback: captured today

Receive-only capture was active on both ports. The owner was asked to press
and release each board's physical RESET and replied "done". Each capture
contains startup dots, the correct a24c1 CPU banner, the ABI banner, and
`B3>`. Subsequent `D F000 FFFF` commands returned all 256 rows and the prompt.

The independent 4,096-byte B3:F readback from each board exactly matches
the packaged factory core, including the erased configuration pocket and
hardware vectors. All three SHA-256 values are:

`231fbec1b0e6a1e80f4a956009aa74f6259e4f0dfcf761f09f16755832aece36`

Owner-local evidence is retained under
`output/qualification/a24c1-acceptance-2026-10-03/`: each port's
`-identify.jsonl`, `-physical-reset.jsonl`, `-f-readback.jsonl`, and `-f.bin`.
The BIN files were extracted with `tools/extract_v2_serial_dump.py`, which
requires complete address coverage and rejects conflicting bytes.

## Remaining scope

The subsequent [cold-start/configuration session](STR8N_V2_A24C1_COLD_CONFIG_ACCEPTANCE_2026-10-03.md)
passed cold power cycling, configuration save/persistence, fixed-address
autostart and S hold on both boards. The subsequent
[practical regression session](STR8N_V2_A24C1_REGRESSION_ACCEPTANCE_2026-10-03.md)
passed the listed command, maintenance, RAM ABI and interrupt cases;
2609 also passed native BRK/NMI. Configuration failure checks and the broader
untested matrix remain open. The subsequent
[backup/recovery record](STR8N_V2_A24C1_BACKUP_RECOVERY_ACCEPTANCE_2026-10-03.md)
passes backup reuse/refusal and R/O routine cases within its stated
model/physical-fixture scope. Actual physical failure/interruption recovery
remains unqualified. See the
[technical guide](STR8N_V2_A24C1_TECHNICAL_GUIDE.md#board-acceptance-and-remaining-qualification).
