# STR8-N 2.0a24c1 maps diagrams and charts

The [detailed technical guide](STR8N_V2_A24C1_TECHNICAL_GUIDE.md) contains
the complete Mermaid diagram set for these maps and the implemented flows.

These maps describe a24c1, not the proposed a24c2 allocation. RAM addresses
are CPU bank zero on the 816. Four 32 KiB flash banks occupy the CPU window
`$8000-$FFFF`; selecting another bank changes that window.

## RAM allocation

| CPU addresses | Allocation |
| --- | --- |
| `$0000-$00DF` | Application zero page |
| `$00E0-$00FF` | Monitor scratch/state |
| `$0100-$01FF` | CPU stack |
| `$0200-$68FF` | Application RAM, 26,368 bytes |
| `$6900-$78FF` | Sector staging, 4,096 bytes |
| `$7900-$7BFF` | Worker reservation, 768 bytes; code uses 759 |
| `$7C00-$7C7F` | Command-line area |
| `$7C80-$7CFF` | Byte workspace |
| `$7D00-$7D3F` | Monitor state area |
| `$7D40-$7D7F` | Receive queue |
| `$7D80-$7D8F` | RAM configuration copy |
| `$7D90-$7DCA` | Private workspace |
| `$7DCB-$7DFF` | Unassigned by current definitions |
| `$7E00-$7E1F` | Interrupt pointer area |
| `$7E20-$7EFF` | Vector code/ABI reservation; code uses 196 bytes |
| `$7F00-$7FFF` | Hardware I/O address area |

## Flash banks and resident F

| Bank | Physical flash offsets |
| --- | --- |
| B0 | `$00000-$07FFF` |
| B1 | `$08000-$0FFFF` |
| B2 | `$10000-$17FFF` |
| B3 | `$18000-$1FFFF` |

Bank contents depend on the board and session. Do not assume B0 or B1 is
free, or that B2 contains a particular guest. Backups use matching sector
addresses in the chosen destination bank.

| Resident-bank CPU addresses | Allocation |
| --- | --- |
| `$8000-$EFFF` | Preserved payload; not supplied by the core installer |
| `$F000-$FFBC` | Core including stored RAM images, 4,029 bytes |
| `$FFBD-$FFCF` | 19 unused bytes |
| `$FFD0-$FFDF` | a24c1 configuration, 16 bytes |
| `$FFE0-$FFFF` | Hardware vectors/reserved words, 32 bytes |

B3:F maps to chip offsets `$1F000-$1FFFF`. The 4 KiB core BIN starts at
offset zero within F. An erased factory pocket does not contain saved settings.

## Installation flow

```text
INSTALL-A24C1.ps1
  -> COM port entry
  -> Physical RESET -> wait 2 seconds -> Enter
  -> WDCMON identification -> uppercase physical board confirmation
  -> RAM installer load -> byte-exact readback -> execute $2000
  -> BANK: 0 / 1 / 2 / NONE
       backup -> sectors -> inspect plan -> BACKUP B3 if erased
       NONE   -> NO BACKUP -> INSTALL WITHOUT BACKUP
  -> Ctrl-U core BIN -> exact image checks
  -> INSTALL STR8-N 2.0A24C1
  -> source guard -> B3:F write -> complete verification
  -> physical RESET -> a24c1 banner and B3>
```

Refused input or an occupied backup destination halts before installation.
An identical backup is reused. On installation failure, R retries from RAM;
O restores old F only when the selected verified backup includes F.

## Configuration data flow

```text
Resident F $F000-$FFFF -> snapshot -> RAM $6900-$78FF
New settings                       -> RAM $78D0-$78DF
Desired sector -> RAM worker $7900 -> resident F program/rewrite
Full-sector comparison             -> prompt or RAM failure/retry
```

## Capacity chart

Each worker bar represents its reserved capacity; figures are exact bytes.

```text
RAM worker   [#############################.] 759 / 768
Vector code  [##########################....] 196 / 224
F before cfg [#############################.] 4029 / 4048
```

## a24c2 comparison

| Area | a24c1 current versus a24c2 proposed |
| --- | --- |
| Application RAM | `$0200-$68FF` versus `$0200-$5FFF` |
| Reserved page | None here versus `$6000-$60FF` |
| Staging buffer | `$6900-$78FF` versus `$6100-$70FF` |
| RST code reservation | None versus `$7100-$78FF` |
| Existing worker | `$7900-$7BFF` in both |

The maintenance utility uses `$6000-$61FF` state in a24c1; it will also
need review for a24c2. Do not apply proposed a24c2 addresses to this release.
See the [a24c2 proposal](STR8N_V2_A24C2_RAM_LAYOUT.md).

Sources: current RAM/public definitions and build report, linked from the
[a24c1 manual](STR8N_V2_A24C1_MANUAL.md).
