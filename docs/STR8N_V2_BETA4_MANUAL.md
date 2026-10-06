# STR8-N 2.0b4 operator manual

STR8-N runs from Bank 3 and provides an FT245 USB monitor console on
W65C02SXB or W65C816SXB in emulation mode. RESET initializes RAM services,
checks both monitor images and offers a bounded A/B/S selection. `S` at
that boot selection enters independent recovery; at `B3>` it means SAVE.
Autostart follows the saved startup settings after the selection window.

## Monitor commands

Numbers are hexadecimal. Commands are entered at the current `B0>` through
`B3>` prompt; flash reads use the selected bank while the resident monitor
remains in B3.

| Command | Behavior |
| --- | --- |
| `?` | Grouped help |
| `B0` through `B3` | Select a logical flash bank |
| `D start [end]` | Display an inclusive memory range |
| `M addr byte ...` | Edit permitted RAM |
| `F addr byte ...` | Guarded flash edit |
| `L` | Load ASCII S19 into permitted RAM; does not execute |
| `G address` | Execute at a preflighted address |
| `I start end` | Receive/install aligned whole-sector S19 flash images |
| `S bank flash start end [label]` | SAVE an inclusive RAM range as a stored record |
| `R [bank] label [L]` | RESTORE a unique label; default runs, L loads only |
| `R bank flash [L]` | RESTORE the record at an explicit header address |
| `T [bank or first-last]` | TABLE; bare T lists all banks |
| `M` / `M 2` | Range map through a saved MAINT utility |
| `M 1` / `M 3` | Sector grid / wear and ownership through MAINT |
| `W` | Persistent sector erase-attempt counters |
| `U A` / `U B` | Update the inactive, unpreferred monitor slot |
| `P` / `P A` / `P B` | Display / change the exact preferred slot and generation |
| `C` | Display startup settings |
| `C enable bank address delay` | Store startup settings, address target |
| `C enable bank V delay` | Store startup settings, selected bank's RESET vector |
| `J0` through `J3` | Boot a bank through its RESET vector |
| `APPS` | List installed program descriptors; fresh release has none |

## RAM and flash map

| RAM range | Use |
| --- | --- |
| `$0000-$00DF` | Program zero page |
| `$00E0-$00FF` | Monitor/worker scratch |
| `$0100-$01FF` | CPU stack |
| `$0200-$66FF` | Program RAM |
| `$6700-$67FF` | Journal workspace |
| `$6800-$77FF` | Flash-sector staging buffer |
| `$7800-$7BFF` | RAM flash/console worker |
| `$7C00-$7DFF` | Monitor input, settings, receive queue and storage scratch |
| `$7E00-$7EFF` | Interrupt pointers/vector code and public RAM entries |
| `$7F00-$7FFF` | Hardware I/O |

| Bank 3 range | Use |
| --- | --- |
| `$8000-$9FFF` | Saved MAINT record and erased padding |
| `$A000-$AFFF` | Monitor slot A |
| `$B000-$BFFF` | Monitor slot B |
| `$C000-$DFFF` | Configuration and erase-count journals |
| `$E000-$E7FF` | Program launcher support and descriptor table |
| `$E800-$EEFF` | RESTORE/SAVE/TABLE |
| `$EF00-$EFFF` | Reserved tail, erased in the migration image |
| `$F000-$FFFF` | Fixed reset/recovery core and hardware vectors |

Public ROM console entries begin at `$F004`; compatible RAM console/vector
entry addresses are retained. Ordinary maintenance cannot write B3:A-F.
The migration uses an independent RAM worker because initial F replacement
cannot depend on the firmware being replaced.

## Startup and image preference

`C 0 3 F007 0A` disables autostart, retains the B3 hold target and sets a
one-second delay. Enable is 0/1, bank is 0-3, and delay is measured in
tenths of a second with a minimum of hexadecimal 0A. `V` selects a RESET
vector target. Changed settings require confirmation and append a checked
journal snapshot. Unchanged settings do not write flash.

Reset validates complete A/B slot images. A valid stored preference chooses
that exact slot/generation; otherwise the highest unsigned generation wins,
with A winning a tie. Invalid or uncommitted images are ignored. A one-time
A/B selection does not save a preference. `P A` / `P B` validates and saves
the selected exact image; it does not reset immediately. `U` refuses an
active or preferred destination and a stale/equal generation.

The independent `REC>` menu offers `A`, `B`, `W`, `U A` and `U B`. For an
update, confirm and send the exact matching 4,096-byte slot BIN as binary.
This receiver remains available when both monitor slots are damaged.
Use a generation newer than the active monitor, or recovery when no active
monitor is valid. Do not send BIN data using the monitor's S19 loader.

## Maintenance and storage

Enter `R MAINT` to restore and start the installed BANK MAINT 1.5 record.
It is unchanged and uses `$2000-$3D53` in RAM. `Q` returns to the monitor.
The release installs its record in B3 `$8000-$9D6B`, spanning sectors 8/9;
both sectors belong to that record. Monitor map shortcuts restore this copy
automatically. `R MAINT L` loads without running, followed by `G 2000`.
The separate S19 can also be loaded through `L` when needed.

The [RST guide](STR8N_V2_BETA4_RST.md) gives a complete SAVE/TABLE/RESTORE
example. RESTORE runs by default: use `L` for data or inspection. Duplicate
labels require a bank/address qualifier. SAVE requires erased space and
does not erase/replace an occupied record. A complete record includes its
24-byte header and every sector occupied by its body.

See the [maintenance guide](STR8N_BANK_MAINT_RECOVERY.md) for utility commands,
and the [migration guide](STR8N_V2_BETA4_MIGRATION.md) for installation,
backup and failure handling. Keep power stable during flash operations.
