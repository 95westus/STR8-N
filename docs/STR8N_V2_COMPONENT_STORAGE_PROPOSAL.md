# Fixed-address components and local storage proposal

Recorded 2026-09-25. Design discussion only; no implementation or frozen ABI.

## User direction

- STR8-N v2 remains at `$F000`. HAL, DEBUG, and IRQX (interrupt extension)
  occupy other fixed addresses. No relocations.
- Save an inclusive memory range locally and restore it to its original start
  address, so component code need not be transferred from a host each session.
- Initial syntax discussion included AUTO placement; the later flash-only
  design below supersedes the original argument order and defers AUTO.
- Possible device-oriented syntax: `F0` through `F3` for flash saves and
  `S0` through `S3` for SPI SRAM saves. This remains tentative; SRAM numbering,
  restore syntax, and coexistence with the existing F editor are unresolved.
- HAL is required for SPI SRAM, I2C RTC, and crypto-chip access.
- DEBUG requires IRQX.
- Consider a separate public ABI for each component.

## Agreed flash-only layout and command direction

The user accepted the following reservation layout on 2026-09-25. This is a
design decision, not an implemented firmware layout or measured build fit.

| Address | Size | Purpose |
| --- | --- | --- |
| `$E800-$EEFF` | 1,792 bytes | Flash-only S/R implementation in the resident bank |
| `$EF00-$EFFF` | 256 bytes | Configuration reservation in the resident bank |
| Fixed `$Fxxx` entries | To be assigned | S/R entry stubs in the core's reserved tail |

Reserve the complete configuration page now so later configuration growth
does not displace code. Initially retain the existing 16-byte pocket at
`$EFF0-$EFFF`; unused bytes in the page remain reserved, not code space.
Version the configuration format as fields are added. Do not move the
configuration into the monitor's F sector.

- `S <bank 0-3> <flash address> <RAM start> <RAM end>` uses destination-first
  ordering and an inclusive RAM range. Example: `S 2 8123 2000 316A`.
- `R <bank 0-3> <flash address>` restores to the original recorded RAM address,
  without executing it. Example: `R 2 8123`.
- Named records extend these forms with a save name, restore by name, and
  `DIR <bank>` as described below.
- No sector-alignment requirement for saved-image destinations. Handle sector
  crossings and preserve bytes outside the saved image in affected sectors.
- The discussed flash image storage range is `$8000-$DFFF`; the entire header
  and payload must fit in the permitted range, not only the starting address.
- Keep the initial implementation flash-only and independent of HAL; defer
  AUTO and generalized Storage Areas.
- The core dispatcher enters through fixed F-sector stubs; S/R reuses the RAM
  flash worker. Bank switching and flash mutation must remain RAM-safe.
- Configuration updates must preserve S/R in sector E; extension installation
  must preserve the configuration reservation. Update installation/protection
  rules to account for the extension before implementation is considered ready.

The earlier source-informed estimate for basic S/R was 560-1,000 additional
ROM bytes, budgeting about 800 bytes. This is not an assembled measurement;
arbitrary destination handling, integration, and actual fit remain to be proven.
Named lookup and DIR add parsing, scanning, and validation work beyond that
original minimal estimate; their combined fit must be measured.

## Named saved-image records and DIR

The agreed record direction uses a leading ASCII `SR` signature and a
null-terminated name. There is no trailing `RS` signature and no name-length
byte. Proposed field order:

```text
SR | version | RAM start | payload length | checksum | name | $00 | body
```

Payload length counts only body bytes and determines the record end. The body
begins immediately after the name terminator. The checksum covers the metadata
(including the signature), name, terminator, and body, excluding the checksum
field itself. The checksum algorithm, field widths, and byte order remain to
be specified before implementing or freezing the format.

Proposed name rules are at most 16 characters, normalized to uppercase, with
a required null terminator within 17 bytes. Parsing must enforce this bound.
Duplicate names should produce an ambiguous-name error rather than selecting
one silently. Distinguishing all-hex names from address arguments still needs
a syntax decision; quoting or an explicit name indicator are options.

```text
S 3 8123 2000 316A MICROCHESS
R 3 8123
R 3 MICROCHESS
DIR 3
```

The save example records inclusive RAM range `$2000-$316A` with its header at
Bank 3:`$8123`. Both restore forms use the recorded RAM destination and do not
execute the payload. Whether a name may be omitted when saving remains open.

DIR scans the selected bank's permitted storage range and derives its listing
from saved-image records; it does not maintain a separate directory allocation,
enrollment state, or journal. Example output (hexadecimal values):

```text
B3  NAME              START END   FLASH BYTES
    MICROCHESS        2000 316A  8123  116B
    BANKMAINT         2000 27FF  9300  0800
```

FLASH identifies the record's leading SR address. START and END describe the
original inclusive RAM range; BYTES is the payload length, excluding metadata.

DIR and named restore share a scanner. Search for a candidate SR signature,
then validate the supported version, bounded name, lengths, address ranges,
and checksum before accepting the record. Reject arithmetic wraparound and
records extending beyond permitted storage. A signature alone is insufficient:
ordinary program data may contain the same bytes. After accepting a record,
skip its entire extent, including payload, before continuing the scan. A failed
candidate must not use unvalidated length data to skip possible later records.

Qualification should cover embedded SR bytes in payloads, missing name
terminators, invalid lengths/checksums, duplicate names, and agreement between
DIR listings and named/address-based restoration. This remains a proposed
extension to v2, not a change to the frozen release's command contract.

## Candidate saved payloads

A v2 bank-maintenance utility is a strong first practical S/R payload: keep
the tool in flash, restore it to its fixed RAM address when needed, and run
it explicitly. Candidate operations include bank inspection, blank checks,
checksums, comparisons, and controlled erase/copy operations.

The existing v1 utility is not automatically compatible. A v2 adaptation must
remove dependencies on v1 directory/journal policy and use the v2 memory and
service contracts. Its execution range must avoid STR8-N workspace, and its
flash operations must protect STR8-N, the S/R extension, configuration, and
saved images designated for retention. Flash mutation and bank switching must
execute safely from RAM.

Other candidates, not commitments to implement:

| Payload | Purpose and constraints |
| --- | --- |
| Memory test | On-demand RAM diagnostics; exclude its own code, live data, and monitor workspace. |
| Board diagnostics | Console, VIA, LED, and interrupt checks without a fresh host transfer. |
| Disassembler | On-demand code inspection without enlarging the resident core. |
| HAL modules | Restore SPI/I2C and device support from flash before accessing devices that require HAL. |
| IRQX and DEBUG | Restore into separate fixed ranges; initialize IRQX before DEBUG installs its hooks. |
| Small applications | Locally available games, display demos, and control programs. |
| Data and settings | Preserve tables, display patterns, or application configuration as ordinary byte ranges. |

Restore does not activate a component or recreate hardware state. Each program
needs a defined entry or initialization procedure, and simultaneously loaded
components need nonoverlapping memory allocations and compatible interfaces.

Suggested qualification order:

1. Save a small program with known byte patterns, alter its source RAM, restore
   it, and verify the complete original range before executing it. Include an
   unaligned flash destination and a saved image crossing a sector boundary;
   verify neighboring flash bytes remain unchanged.
2. Exercise invalid headers, checksums, ranges, and protected destinations,
   confirming the intended rejection behavior before using a flash-writing tool.
3. Save and restore the v2 bank-maintenance utility. Verify its restored bytes
   and read-only operations first, then qualify its guarded flash operations.
4. Extend qualification to multiple components and their initialization order.

## Recommendations under consideration

- Keep command meanings stable regardless of HAL presence. Missing HAL makes
  its device operations unavailable rather than changing their meanings.
- Store original address, length, format identity, and payload checksum with
  each saved image. Restore and initialization/execution are separate actions.
- AUTO must include header space and distinguish allocated image contents from
  free space; an FF run inside an image is not evidence of a free allocation.
  Designated storage regions and explicit image extents are a possible policy.
- Respect monitor/configuration reservations and live RAM workspace. Flash
  erase granularity and preservation of neighboring data need an explicit rule.
- Flash storage addresses differ from execution addresses. Components from
  different flash overlays can coexist when restored to disjoint RAM ranges;
  execution across flash overlays needs RAM-based bank switching.
- SPI SRAM is volatile unless the hardware provides retention.
- Give each component a small versioned public jump table with a shared calling
  convention. Define registers, flags, errors, CPU mode, memory ownership,
  initialization, and interrupt/reentrancy rules. Concrete addresses and layouts
  are not assigned yet.
- DEBUG should check for a compatible IRQX before activation. HAL device
  availability should be queryable. No HAL-to-IRQX dependency has been decided.
- IRQX would own handler registration/dispatch policy above the existing
  STR8-N vector facilities; DEBUG would obtain its interrupt hooks through IRQX.

Resident ROM fit, allocation details, ABI discovery, device capacities, and
startup ordering require further design. This proposal does not change the
current v2 command or ABI contract.
