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
