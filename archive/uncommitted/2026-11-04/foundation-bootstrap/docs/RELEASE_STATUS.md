# STR8N-F 0.2.0 release scope

An early Boot & Recovery Toolkit release: b15 F, matching CONFIG, OPAQUE,
DEMO and READBACK RAM tools, optional BASE MON A/B, packet preparation,
operator instructions and component destinations. The separate source ZIP
retains the unified source closure and optional system components.
Package 0.2.0 and F generation 8000000F are different identities.

## Supported scope

- WDC banked 65C02 and 65C816 emulation runtime, USB/FT245.
- Reset chooser, saved/default/manual bank entry and B3:F recovery.
- F-only recovery/raw RAM loading without MONs or a journal.
- Compatible existing SNBT C/D; blank-only initialization with prior wear unknown.
- Immediate CONFIG entry/default saves; manual paced OIP1 reads/replacements,
  preimage checks, durable erase reservation and full sector readback.
- Explicit external-programmer F-sector provisioning under the installation
  boundaries. An automatic factory converter is not implied.

B0/B1/B2 are user-owned. Ordinary opaque writes exclude B3:A/B/C/D/F.
An address admitted by OIP1 does not authorize replacing owner backups or
optional services. Those remain subject to the actual inventory.

## Evidence for the exact bytes

The [public hardware summary](../validation/hardware-summary.json) identifies
its artifact hashes and scope. Private original receipts stay with the owner.

- Exact F was installed on 2512 (65C02) and 2609 (65C816 emulation) over USB.
  2512 includes initial Ctrl-C and normal BIN reception evidence.
- CONFIG enable/entry/default/restore was demonstrated on 2512. The b15 CONFIG
  predecessor saved A, booted it, restored S and booted REC on 2609. The shipped
  generic CONFIG changes only its same-length banner. The shipped common CONFIG
  ran on 2512 for inspection and independent executed-RAM checking.
- OIP1/FLASH writes, no-op/readback and restoration were demonstrated on 2512.
  No new opaque install on the current 2609 ES1/VX1 profile is claimed.
  READBACK and owner-RAM restoration ran on the 2512 preservation path.
- Both CPU models previously exercised core boot/config/OIP. The unified source
  was independently reproduced before this release. These are inherited results,
  not newly executed release tests.

Release checks cover archive membership, SHA-256, source/provenance, component
addresses, documentation and extracted-package integrity. No board flashing,
firmware build or CPU/NOR rerun is part of this release. 2205 remains read-only.

## Limits and deferred work

Raw L executes after an idle interval without declared length or transfer CRC.
A local file checksum does not verify device reception. Independent RAM readback
occurs after execution, not before it. Incomplete transfers must not be treated
as valid tools.

Physical ACIA acceptance, native 816 applications, physical interrupted-power
acceptance, a general preserving factory-WDC migrator, owner-history import or
repair and an automatic live opaque installer remain outside the supplied
workflow. Healthy F can load repair tools; destroyed F/reset vectors need an
external recovery mechanism. Stable 1.0 factory acceptance is not claimed.

The SPI WORK message journal, WTOR, login/session features, new maps, personality
ports and BASIC/Forth selector remain future work. Full-system images do not
become relocatable opaque applications merely by being stored in a BIN.
