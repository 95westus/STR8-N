# a24c1 backup and recovery acceptance

Date: 2026-10-03. Beta checklist item 4 was checked with the linked installer
fault model and controlled RAM fixtures on board 2205 (W65C02SXB, COM3,
FTDI A10MPUPNA) and board 2609 (W65C816SXB, COM8, FTDI A10MPQXCA).
This record distinguishes modeled failures from physical routine execution.

## Physical-board fixture results

| Case | 2205 | 2609 |
| --- | --- | --- |
| Copy B3:F to erased B1:F; exact independent backup readback | PASS | PASS |
| Source B3 remains unchanged after backup/canceled installation | PASS | PASS |
| Reuse identical B1:F without a copy confirmation | PASS | PASS |
| Occupied, different B0:F refused | PASS | PASS |
| Bank 3 rejected as backup destination | PASS | PASS |
| Decline first and second NONE confirmations separately | PASS | PASS |
| Both exact NONE confirmations accepted; installation then declined | PASS | PASS |
| Altered candidate BIN rejected before installation | PASS | PASS |
| Direct recovery R routine installs exact factory F image | PASS | PASS |
| Direct recovery O routine restores exact original configured F from B1:F | PASS | PASS |
| Temporary backup erased; all four complete banks restored exactly | PASS | PASS |

## Fixture boundary

Both boards were already on a24c1 with `C 00 03 F007 40`. The saved source
was this configured B3 image, not stock WDCMON. Stock migration was not
repeated. This is a qualification fixture, not an installed-board update
procedure or an end-to-end test of the packaged stock-board launcher.

Each case first loaded the exact 3,509-byte installer S19 into RAM through
the monitor and independently verified every loaded byte. The harness then
changed two three-byte instructions in RAM only:

- `$258E`: the final abort-message JSR became JMP `$F007`.
- `$251A`: the success wait-loop JMP became JMP `$F007`.

These redirects return to the original monitor between cases. Backup choice,
comparison/copy, image validation, flash programming/verification, and R/O
recovery code were not patched. Each fixture RAM image was read back and
its hash recorded. No firmware source or release artifact was changed.

For recovery, a verified 13-byte RAM wrapper at `$1800` established
emulation mode, IRQ-disabled/decimal-clear state, stack and installer console,
then jumped directly to `W2I_RECOVERY` at `$251D`. It did not induce a flash
failure. R used the already received/validated factory candidate at `$4000`
and programmed/verified B3:F. A complete independent sector readback matched
the factory BIN, including its erased configuration pocket. O then copied
the selected B1:F backup to B3:F, verified it and followed the original
software-reset path. A complete B3 readback matched the original configured
bank. Thus O restored changed flash, rather than merely comparing an
already identical destination.

Occupied-backup, invalid-choice and bad-image cases returned their refusal
messages. NONE acceptance was followed by N at the installation confirmation;
no unbacked installation was performed on physical hardware. Fixture R/O
execution is evidence for those routines, not evidence that a physical
failed write successfully enters or survives the recovery path.

## Linked fault-model results

`python -u tools/test_v2_config_wdcmon.py` passed all seven groups:

- Selected banks/ranges, exact backup copy and neighboring-sector preservation.
- Invalid choices/declined confirmations, occupied refusal and identical reuse.
- Unified entry, selected F backup and exact a24c1 installation.
- Twice-confirmed NONE installation with B3:F-only mutation.
- Altered candidate, backup verification failure and changed-source guards.
- Timeout recovery refuses O when NONE or the backup excludes F, with no new writes.
- Failed installation restores original F from selected B2:F after clearing the modeled fault.

These tests execute the linked 65C02 installer with logical flash/FT245
devices. They do not establish physical fault recovery or native 816 model
execution. The two real boards separately exercised the fixture cases above.

## Identities, preservation and evidence

Unmodified installer S19 SHA-256:
`a9f3a156c91483b012265e4de9c52f90ad703241b5b8b06016a4ab5755185726`.

Factory candidate F SHA-256:
`231fbec1b0e6a1e80f4a956009aa74f6259e4f0dfcf761f09f16755832aece36`.

Each board's before/after complete bank images are byte-identical. Their
hashes match the [practical regression record](STR8N_V2_A24C1_REGRESSION_ACCEPTANCE_2026-10-03.md#scratch-plan-and-preservation).
B0 stock firmware was retained, B1/B2 were restored to all FF, and B3's
firmware/configuration were restored. Both boards ended at B3>, autostart
disabled. RAM scratch used by the fixture is transient.

Owner-local evidence is in
`output/qualification/a24c1-acceptance-2026-10-03/COM3/recovery/` and
`COM8/recovery/`: timestamped TX/RX/IMAGE/FIXTURE logs and complete before/
after bank images. `regression.py` checks backup, candidate and restored
images as each step completes. `verify_recovery.py` verifies recorded
results, fixture identification and exact final bank equality, writing
`recovery-verification.json`. `recovery-model-results.json` retains the
matching model report separately from hardware evidence.

## Release claim and remaining work

Item 4 is complete within this combined model/physical-fixture scope.
Actual flash-failure entry/recovery, physical backup-write failure, recovery
after reset/power interruption, and automatic rollback remain unqualified.
No interruption-recovery claim is added. The historical stable-power
release gate also excluded deliberate active-flash fault injection; this
session did not interrupt power or assert RESET/NMI during writes.

The beta should preserve these limits explicitly. Final versioning,
documentation/PDF/ZIP refresh, host/package checks and publication remain
checklist item 5.
