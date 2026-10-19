# rc1 firmware contents and programmer mapping

One STR8-N-only firmware set serves 65C02 and 65C816 emulation-mode runtime.
It excludes B0 and WDCMONV2 binaries. Native applications, ACIA and crypto
remain deferred; startup CPU detection retains its accepted exception.
Published generation 49 has no DBG1 debugger. The matching local generation-50
extension adds the row marked below; see [DBG1](DEBUGGER_GUIDE.md) and its
[board results](DEBUGGER_BOARD_RESULTS.md).

| Application or facility | Image location / access |
| --- | --- |
| UCHESS / Microchess | B1:`$8000`, stored record; `T 1`, `R 1 UCHESS` |
| DBG1 RAM debugger (generation 50 only) | B1:`$A000-$AFFF`; automatic RAM BRK entry, both MON A/B |
| CLOCK 1.11 | B1:`$B000–$DFFF`; `R CLOCK` |
| ASM 0.5 | B1:`$E000` plus matching vectors; `ASM` |
| MAINT, SRAM, WORK, EDU | B2 utilities/provider area; named utility commands |
| Boot status, battery, local display, version | B2 provider regions |
| RTC and journal services | B3:`$8000–$9FFF`, with protected mutable holes |
| MON A / MON B | B3:`$A000` / `$B000` |
| S/R/T implementation | B3:`$E800`, within E core |
| Fixed recovery/reset core | B3:`$F000` |

This is the new application-image candidate's inventory. `APPS` and `T` show
different application-directory/stored-record views. UCHESS contains 1,439
executable bytes plus its 24-byte stored-record header; RAM origin/entry is
`$0200`, final executable address `$079E`. Its source and complete license
must accompany the executable.

DBG1 changes seven firmware sectors: B1:A/E/F and B3:A/B/E/F, with two
wear-accounted C/D journal erases in its nine-transfer preserving install.
It includes matching ASM/vector/monitor/core changes; adding only B1:A is
insufficient. B1:9, B0/B2 and other data were preserved in both board trials.
No application RAM is reserved for the debugger. The published raw images
listed here remain generation 49; use the separate experimental candidate
procedure for DBG1, not a default-filled raw BIN over existing board data.

## File offsets

The 96 KiB image concatenates banks B1/B2/B3:

`file offset = (bank - 1) * $8000 + CPU address - $8000`

| Region | File offset | Full-device offset |
| --- | --- | --- |
| B1 | `$00000` | `$08000` |
| B2 | `$08000` | `$10000` |
| B3 | `$10000` | `$18000` |
| MON A | `$12000` | `$1A000` |
| MON B | `$13000` | `$1B000` |

Follow the actual programmer's chip/bank mapping. Do not program this file at
full-device offset zero. It is a fresh-provisioning image with deterministic
defaults and a provisioning wear baseline, not lifetime counters for an
existing chip. Writing it replaces covered flash data. Use the preserving
migration workflow when existing settings/programs must survive. It contains
no RTC, EEPROM or external SRAM image.

## Candidate checks and remaining gates

The application image passed actual rc1 ASM 0.5 source assembly, byte comparison
against the previously independent WDC game build, MON A table/load/gameplay/
HOLD checks, and MON B fallback/table/run/HOLD/CLOCK BATCH checks in the W65C02
model. Pinned firmware code remains unchanged. The full-system RAM migrations also installed providers and UCHESS on physical
2609 from original WDC and 2604 from beta4 with empty B0/B1/B2. Both completed
22 transfers, bf1 boot and UCHESS/BATCH checks. rc1 targets are tested offline. General occupied-bank upgrades,
Linux physical serial migration and broad RTC preservation remain outside the
current candidate qualification.

See [migration](QUICK_START_MIGRATION.md), [ABI](ABI_REFERENCE.md) and
[attribution](THIRD_PARTY_NOTICES.md).

## Separate F component and J commands

`str8n-2.0rc1-b3-f000-ffff.bin` is the exact 4,096-byte fixed F component
already present in the complete image. Its destination is **B3 CPU
`$F000–$FFFF`**, full-device programmer offset **`$1F000`**. It is source-built
STR8-N code with no WDCMONV2 bytes. It is not a complete rc1 installation or a
bank-independent standalone monitor. Use a reviewed programmer/recovery plan;
do not treat the raw component as a preserving update script.

`J0`, `J1`, `J2` and `J3` select that flash bank and follow its reset vector at
`$FFFC/$FFFD`. They do not relocate firmware. Erased/invalid vectors are
refused. The rc1 F bootstrap explicitly selects B3 and uses the B3 A/B slots,
E code and matching B1/B2 providers. Therefore this F file must not be copied
over B0/B1/B2 merely to make `J0/J1/J2` launch rc1; B1/B2 F pages already hold
application/provider content. With the complete rc1 layout, `J3` is the rc1
software restart. Historical early-v2 bank-resident images were different
layouts; their J0/J1/J2 tests do not qualify the current two-slot rc1 bootstrap
as a standalone image for another bank. No board programming is implied by
including this component.
