# 2609 migration from extracted rc1: B3 scope review

The owner approved this exact scope and the
[2609 extracted-rc1 trial passed](2609_RC1_ZIP_UPGRADE_ACCEPTANCE.md).
The tables below retain the reviewed write budget; actual evidence is separate.
The owner requested 2609, original images/settings/wear history/owner RAM
preserved, no power cuts, frozen F, and 2205 excluded. The immutable operator
ZIP SHA-256 is
`ed9e87ef34323b0504c355bd6b35e0a5095ecd0665d6e67166bd9178c29bddb2`.
No rc1 file is changed and no replacement engine or reader is built.

## Correct route for the installed board

2609 is a 65C816 board, USB COM8 / A10MPQXCA. Its reference and freshly checked
B3 contain known b15 F plus valid SNBT, not a factory WDC boot source.
The preserving route is the ZIP's `migration-host/nf_upgrade.py` existing-
journal upgrade. WDC first provisioning would be the wrong operation here.
This test can qualify that packaged upgrade route; it cannot claim a WDC
first-provisioning pass from this starting state.

"F frozen" means the target is the exact existing 4096-byte BASE1 image,
version 0.3.0 g00000001 / BASE1 / PR05. Installing it requires replacing the
currently different b15 F once. It does not mean keeping the old b15 bytes.

| Item | Current | Reviewed target |
| --- | --- | --- |
| F SHA-256 | 1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8 | 8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1 |
| Latest journal | C800, seq1023 | C900, seq1024 (00000400 hex) |
| Committed records | 10 | 11; all ten old rows retained at original addresses |
| C / D / F counts, decimal | 78 / 47 / 30 | 78 / 47 / 31 |
| Other counters / unknown mask | Original / FFFFFFFF | Unchanged |
| Default / enabled mask / entries | S / 00 / all8000 | Exact original values |
| Application config / pinned MON generation | Original | Exact original bytes |

## Exact persistent footprint

| Region | Permitted trial action |
| --- | --- |
| B3:C900-C9FF | One 256-byte reservation append, commit C9FF last |
| B3:C/D otherwise | No writes; **zero C/D erases**; retain every old row |
| B3:F000-FFFF | **One sector erase**, then program/verify frozen 4K target |
| B0-B2 and B3:8/9/A/B/E | Zero writes; retain original images, including B0 WDC backup |
| Owner RAM 0200-66FF / ZP00-DF | Fresh original escrow before helper upload; restore and independently read back |

Total: one F erase/program, one C900 append, zero owner-image writes and zero
C/D erases. Two prompted physical RESETs keep USB power connected. No power
cuts, whole-chip operation, journal rotation, rollback, automatic retry or
extra erase is included. F becomes the golden runtime anchor after successful
verification. Interrupted-F recovery is outside this test.

## Original backup and kit boundary

The first read-only attempt found REC> and stopped after an empty CR, without
an upload or flash/RAM write. The existing matching b15 MON B was then entered
for resident D/B reads. Its full B3 matched the archived reference; owner
RAM/ZP matched the last verified escrow before either new bank pass.
Fresh independent full-bank and RAM/ZP repeats must finish and agree before
an executable upgrade plan is admitted. Any changed source stops this scope.

The ZIP's upgrade command consumes original capture files; rc1 has no separate
automated b15 pre-helper capture command. This test uses the bundled Python
terminal's Session to drive the resident MON D/B commands. The bench harness
records/parses that manual terminal procedure and coordinates the serial
lease. No unshipped legacy reader is uploaded. Product modules, migration
logic, target BIN and NFU1 engine must all load from the fresh operator-kit
extraction, with their MANIFEST hashes checked. Outside files are private
captures/receipts and test orchestration, not alternate migration components.

This capture precondition remains an operator-workflow limitation of rc1;
the result must not be described as a one-command b15 backup-and-upgrade.
Owner stack/system scratch outside the stated RAM/ZP ranges is not claimed
as restored application memory. No EDU/SPI/RTC commands are part of this trial.

## Trial after exact scope approval

1. Finish fresh independent original capture and prepare/inspect the private
   plan using only packaged `nf_upgrade.py`, CPU declaration `65c816` and the
   packaged prebuilt NFU1 template. Require the exact C900/1024/F31 delta above.
2. Observe physical RESET into old F and choose S without saving a new policy.
   Raw-L loads the packaged rendered upgrade wrapper. Device self/plan/all-bank
   source/chip guards must pass before the one Y; they recheck before append.
3. Program, compare and commit C900, then verify complete B3 with its durable
   F reservation. Only afterward transfer the frozen F payload and perform
   its one reserved erase/program. Verify all device postimages.
4. Observe physical RESET into exact BASE1 identity and REC>. The packaged
   completion path independently reads all four banks, restores original
   RAM/ZP and reads them back. Legacy retained MON/FLASH execution under new
   BASE1 remains unqualified; keep the original S default and finish in REC>.
5. Exercise initial Ctrl-C and a normal read-only RAM-tool load through the
   extracted terminal core, then independently recheck final banks and restore
   original RAM/ZP again. No additional flash write or saved setting is used.
   Native GUI keys were qualified earlier on 2512; this core check is not a
   fresh physical-keyboard pass on 2609.
6. Release COM8 and save a receipt binding this ZIP hash, actual module paths,
   fresh captures, plan, physical resets, retained records/counts and final
   preservation. Any failure stops for inspected handling without blind replay.

Private case: `output/qualification/2609-rc1-zip-migration-20261028-r1`.
Fresh original capture and the packaged prepare/inspect path have now passed.
All four banks were read independently twice; owner RAM/ZP remained exact.
The complete source-bound live plan matched C900/1024/F31. The owner then
authorized execution; the packaged upgrade, terminal core checks and final
image/history/settings/RAM preservation passed without changing the ZIP. Board 2205 and every other board remain excluded.
The ZIP stays immutable; source review/results are recorded separately.
