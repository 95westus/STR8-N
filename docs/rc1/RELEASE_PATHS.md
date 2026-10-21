# rc1 v1g image choices and programmer offsets

The current package is **DBG1 generation50 v1g**. The default preserving
installation is the [uniform upgrade command](UNIFORM_UPGRADE.md), qualified
directly from registered WDCMONV2 and beta4 on 2604 and 2609. Exact current
v1g takes a verified no-write path. Firmware is unchanged from r8.
Native applications/debugging are excluded; the 816 target runs E=1. The RTC
issue is deferred and drift is outside release qualification.

## Choose the artifact

| Purpose | Package path | Scope |
|---|---|---|
| Preserving upgrade | `upgrade/upgrade.py` | Source-aware capture, admission, verified transaction, RESET when required and full borrowed-RAM restoration. |
| Fresh full system | `firmware/str8n-2.0rc1-dbg1-gen50-full-system.bin` | 96 KiB B1/B2/B3, including MON A/B, ASM, DBG1, CLOCK, utilities, providers and UCHESS. Exact alias of the reference BIN. |
| Fixed F recovery component | `firmware/str8n-2.0rc1-dbg1-gen50-b3-f000-ffff.bin` | Exact 4 KiB B3 F slice. Recovery component, not a normal monitor or standalone Jn bank launcher. |
| B3 bank reference | `firmware/str8n-2.0rc1-dbg1-gen50-b3-bank-reference.bin` | Exact 32 KiB B3 slice, including generic settings/journal defaults. V1g still has cross-bank dependencies. |
| Monitor recovery components | `firmware/str8n-2.0rc1-dbg1-gen50-monitor-a.bin` / `-monitor-b.bin` | Exact 4 KiB A/B slices; require the matching system and DBG1 hooks. |
| ASM component references | `firmware/str8n-2.0rc1-dbg1-gen50-asm-e000-efff.bin` / `-asm-f000-ffff.bin` | Two exact 4 KiB slices. F also supplies DBG1 tables and vectors. |
| DBG1 component | `firmware/debugger-a000.bin` | Exact B1 A sector, coupled to the v1g monitor/core/ASM build. |

`firmware/components.json` binds the added slices to offsets, sizes and hashes.
The complete image remains
`firmware/str8n-2.0rc1-dbg1-gen50-reference.bin`, SHA-256
`6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b`.
No component is rebuilt or independently modified.

## Programmer address map

| Artifact | Bytes | CPU destination | Full 128 KiB device offset |
|---|---:|---|---|
| Full system / reference | 98304 | B1/B2/B3 `$8000–$FFFF` | `$08000` |
| B3 bank reference | 32768 | B3 `$8000–$FFFF` | `$18000` |
| MON A | 4096 | B3 `$A000–$AFFF` | `$1A000` |
| MON B | 4096 | B3 `$B000–$BFFF` | `$1B000` |
| Fixed F | 4096 | B3 `$F000–$FFFF` | `$1F000` |
| DBG1 | 4096 | B1 `$A000–$AFFF` | `$0A000` |
| ASM E | 4096 | B1 `$E000–$EFFF` | `$0E000` |
| ASM F | 4096 | B1 `$F000–$FFFF` | `$0F000` |

File offset zero maps to the destination shown, not automatically to device
offset zero. The full system concatenates three 32 KiB banks:

`file offset = (bank - 1) * $8000 + CPU address - $8000`

Raw BINs are **fresh provisioning/reference components**, not preserving
updaters. They replace all covered bytes, including owner data/settings or
journals. Generic provisioning counts are not lifetime wear. They contain no
B0, WDCMONV2 image, private board capture, EEPROM, RTC or external SRAM image.
Use the uniform workflow for preserving upgrades.

## Opaque banks and J0/J1/J2/J3

From the normal monitor, `Jn` selects bank n and follows `$FFFC/$FFFD`;
invalid/erased vectors refuse. It does not require a STR8-N app record or
relocate the target. The target owns its startup, interrupt vectors and runtime
assumptions. `J3` restarts this complete rc1 layout.

The F-only recovery menu has no `Jn` command parser. Neither that component nor
the B3 bank slice is a qualified compact monitor with all B0/B1/B2 opaque.
The full system occupies B1/B2 and DBG1 depends on B1. A minimal bank launcher
requires a different build and separate qualification. Do not copy the B3 F
component into another bank as a substitute.

Use the [flash reclaim guide](FLASH_RECLAIM.md) for optional applications,
sector sharing, already-free space and the limits of deleting ASM or DBG1.
Image-slice checks are host-only; component deletion checks are CPU models,
not physical uninstall qualification. Both boards retain complete v1g.
