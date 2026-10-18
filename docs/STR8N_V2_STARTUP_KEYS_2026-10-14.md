> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta24 startup keys — October 14, 2026

The `BUILD/v2-startup-keys` beta24 generation 34 image was flashed to 2604 and
2609. Physical RESET capture and the final hardware retest passed. 2609 later
received the [generation 35 FIFO drain](STR8N_V2_STARTUP_FIFO_2026-10-14.md);
2604 retains this generation 34 image.
During the startup dots, A/a or B/b selects that monitor and launches its cold
entry after validating the slot's commit, header, length, compatibility and
payload CRC. A rejected slot returns to the chooser. Every other input byte,
including ESC, space, Enter, S and Ctrl-C, skips the remaining dots and displays
the ordinary timed chooser:

```text
A/B/S,Enter default [3s]:
```

At that chooser, A/B select a validated monitor, S or Ctrl-C enter the fixed
recovery menu, and Enter uses the valid default. No input retains all 160 dots
and the timed default. Disconnected USB remains bounded.

Startup resets the software RX queue but does not drain the FTDI hardware
FIFO. A byte already queued in that FIFO can select A/B or skip the dots.
A bounded hardware FIFO drain was subsequently added and tested on 2609 in
the generation 35 update linked above.

The recovery core occupies 4061 of 4064 bytes before the hardware vectors.
The journal CRC entry points and shared application route retain their old
addresses. Both monitor slots carry the new core identity and generation.
The twentieth private slot service retains the RAM-edit entry used by the E
dispatcher; explicit model and hardware M-write checks cover both slots.
MAINT's four identity-guard operands are rebuilt for that identity; its other
instructions stay byte-identical. Worker, vector, RTC/SPI services and sealed
display helpers, including the STR8N-006 fix, are unchanged. The relinked E
launcher is byte-identical and is retained without an erase.

The deployment planner uses independently repeated full flash backups and
stages B3:C/F, B1:8 and B3:B/A. B1:8 is committed after complete MAINT record
verification. Each sector attempt is accounted in wear metadata. The RAM
installer guards the complete target bank before every write and checks the
payload before mutation. Identity, timezone and name records, EDU preference,
saved programs and retained devices are preserved.

The first hardware retest exposed an omitted twentieth private service word
in the rebuilt slot headers: `M addr bytes` could not dispatch to RAM edit.
The builder now supplies that word and seals the slot checksum afterward.
Both corrected slots pass explicit instruction-model M writes. Fresh complete
backups and rehearsed corrective installers updated only B3:C/B/A on each
board. The recovery core, E launcher and MAINT were retained in this repair.
Both corrective installers verified their device writes; physical RESET
capture and the complete corrected hardware retest pass on both boards.
Original evidence is preserved alongside the
`slot-header-repair/{2604,2609}` plans and `corrected-retest` results.
Owner-local evidence lives under
`output/qualification/startup-keys-2026-10-14/{2604,2609}`. Model receipts live
in the candidate directory. Hardware tests exercise early upper/lowercase
A/B, six other key classes, menu A/B and independent recovery, no-key timing,
RAM ABI, actual BRK/VIA1 IRQ and command smoke. Invalid/uncommitted/incompatible
slots are tested in the instruction model. Complete flash, 128 KiB SRAM,
EEPROM, identity, history, trim and control are compared against references.
This scope does not repeat physical NMI/native entry, power cycling or a soak.

| Final check | 2604 | 2609 |
| --- | --- | --- |
| Physical RESET, both generation 34 slots valid | PASS | PASS |
| A/a/B/b launch and RAM M-write/readback/restore | PASS | PASS |
| ESC, x, space, Enter, S and Ctrl-C skip dots; menu A/B retained | PASS | PASS |
| Menu S reaches independent F recovery; A returns | PASS | PASS |
| No-key 160 dots and timed default | PASS | PASS |
| RAM ABI, actual BRK/VIA1 IRQ and command regression | PASS | PASS |
| All four flash banks exactly match the final plan | PASS | PASS |
| Full 128 KiB SRAM matches the fresh reference | PASS | PASS |
| EEPROM, history, identity, trim and control preserved | PASS | PASS |

The final labels remain `2604` and `2609`, as found in the fresh pre-update
backups. Both retain EDU ON and their original offsets; trim steps remain
−12 and −14 respectively. There were five planned sector erases in the first
installer and three in the corrective header installer per board, all
accounted in wear metadata. No test appended NAME/configuration records,
set UTC, changed trim/offset, formatted SRAM or administered EEPROM history.
The STR8N-006 helper fix is retained; unrelated STR8N-004/005 remain open.

Tools: `build_v2_startup_keys.py`, `test_v2_startup_keys.py`,
`deploy_v2_startup_keys.py`, and `retest_v2_startup_keys.py` under `tools/`.
