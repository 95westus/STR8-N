# STR8-N 2.0a24c2 RAM layout proposal

Status: agreed layout, pending implementation. Recorded October 2, 2026.

This document defines the proposed RAM layout for **2.0a24c2**, continuing
the a24c1 candidate. It reserves space for an RST (Restore Save Table)
worker copied from flash into RAM. The RST design remains preliminary.
This document does not change firmware or establish a tested release.

## Agreed RAM allocation

All addresses below are CPU bank zero on the W65C816.

| Address range | Use | Size |
| --- | --- | ---: |
| `$0000-$00DF` | Application zero page | 224 bytes |
| `$00E0-$00FF` | Monitor scratch and state | 32 bytes |
| `$0100-$01FF` | CPU stack | 256 bytes |
| `$0200-$5FFF` | Application RAM | 24,064 bytes |
| `$6000-$60FF` | Reserved; purpose unassigned | 256 bytes |
| `$6100-$70FF` | Flash-sector staging buffer | 4,096 bytes |
| `$7100-$78FF` | RST worker reservation | 2,048 bytes |
| `$7900-$7BFF` | Existing RAM worker reservation | 768 bytes |
| `$7C00-$7C7F` | Command-line area | 128 bytes |
| `$7C80-$7CFF` | Byte workspace | 128 bytes |
| `$7D00-$7D3F` | Monitor state area | 64 bytes |
| `$7D40-$7D7F` | Receive queue | 64 bytes |
| `$7D80-$7D8F` | RAM configuration copy | 16 bytes |
| `$7D90-$7DCA` | Current S/R/T private state | 59 bytes |
| `$7DCB-$7DFF` | Unassigned by the current definitions | 53 bytes |
| `$7E00-$7E1F` | Interrupt pointer area | 32 bytes |
| `$7E20-$7EFF` | RAM vector code and public RAM entries | 224 bytes |
| `$7F00-$7FFF` | Hardware I/O address area | 256 addresses |

The combined worker reservation is `$7100-$7BFF`, or 2,816 bytes.
The existing worker retains its `$7900` start and current entry addresses.
The buffers, state and vector allocations at `$7C00` and above retain
their current addresses.

## Changes from a24c1

| Allocation | a24c1 | Proposed a24c2 |
| --- | --- | --- |
| Application RAM | `$0200-$68FF` | `$0200-$5FFF` |
| Reserved page | None here | `$6000-$60FF` |
| Sector staging buffer | `$6900-$78FF` | `$6100-$70FF` |
| RST RAM code area | None | `$7100-$78FF` |
| Existing RAM worker | `$7900-$7BFF` | `$7900-$7BFF` |

Application RAM loses 2,304 bytes: 2,048 bytes for the RST reservation
and 256 bytes for the reserved page. Its lower start remains `$0200`;
its upper limit becomes `$5FFF`.

The a24c1 build reports 759 bytes for the existing worker and 1,208 bytes
for the S/R/T extension. The existing worker has 9 bytes spare in its
768-byte reservation. A 2,048-byte RST reservation would leave 840 bytes
if the copied RST code were the same size as the current S/R/T extension.
That is a planning estimate; relocating or redesigning RST may change its size.

The allocation provides room for RST development while preserving the
existing RAM worker entry addresses. The reserved page gives application
RAM a `$5FFF` upper boundary without assigning a new use to `$6000` yet.

## Proposed RST location byte

The proposed configuration field is one byte containing:

- High nibble: flash bank containing the RST code.
- Low nibble: flash sector containing the RST code.

The monitor would read this location and copy the RST code to the
`$7100-$78FF` reservation before executing it. This is a proposed mechanism,
not an existing a24c1 configuration field or startup behavior.

The byte's offset in the 16-byte configuration record, valid bank and
sector values, disabled or erased encoding, and configuration format
compatibility remain to be defined. A nibble provides an encoding range;
it does not establish that the hardware supports sixteen banks.

## RST decisions still open

- Copy length: fixed image size or a length supplied by a descriptor.
- RAM entry points and how flash code is linked to execute at `$7100`.
- Validation of the selected image and handling of missing or invalid RST.
- Copy timing and whether RST remains resident throughout operation.
- Relationship between the RST code, its table, and the current S/R/T extension.
- Calls between RST, the existing RAM worker, and resident flash code,
  including behavior while another flash bank is selected or F is rewritten.

## Implementation and validation requirements

Update every sector-buffer reference from `$6900` to `$6100`, including
derived pointers. For example, the staged configuration pocket changes
from `$78D0-$78DF` to `$70D0-$70DF` because the persistent flash record
remains at `$FFD0-$FFDF`.

Apply the `$5FFF` application RAM limit consistently to loading, saving,
restoring, request validation, and other existing operations that enforce
the application RAM boundary. Keep `$6000-$60FF` reserved.

Add build bounds for RST and retain the existing worker and vector bounds.
Review code-copy and bank-switch paths so copying RST cannot overwrite
the sector buffer, existing worker, monitor state, or vector code.

Validate loading at the new RAM boundary, full-sector staging and writes,
configuration save and retry, S/R/T operations, and the public RAM entries.
Once the RST format is defined, validate its location decoding, image checks,
copy bounds, and RAM execution. Board qualification is required before
promoting the candidate to a release baseline.

## References

- [a24c1 configuration and flash layout](STR8N_V2_FLASH_CONFIG.md)
- [Current RAM definitions](../src/v2-config/str8n-v2-eq.inc)
- [Current S/R/T implementation](../src/v2-config/str8n-v2-sr.asm)
- [a24c1 builder](../tools/build_v2_config.py)
