# STR8-N v1.34 software catalog

The standalone STR8-N release contains reset/recovery firmware, installation
and maintenance tools, and their manuals. HIMON, ASM-F2, and their application
collections have separate release ZIPs. See the [manual index](RELEASE_MANUALS.md).

## Included firmware and tools

| Release file | Use |
| --- | --- |
| `ARTIFACTS/str8n-v1.34-bank3-f000-ffff.bin` | Exact 4 KiB programmer image, Bank 3 CPU `$F000-$FFFF`, device offset `$1F000` |
| `ARTIFACTS/str8n-v1.34-f000.s19` | Resident S19 for integration; resident `I` cannot overwrite protected sector F |
| `ARTIFACTS/str8n-v1.34-worker-0200.s19` | Worker build/evidence component, not a standalone operator application |
| `ARTIFACTS/str8n-v1.34-bank-maint-2000.s19` | RAM map, copy, adoption, reclaim, erase, and AP maintenance |
| `ARTIFACTS/str8n-v1.34-bank-maint-menu-2000.s19` | Expanded maintenance menu, including guarded top update |
| `ARTIFACTS/str8n-v1.34-top-update-2000.s19` | Guarded top-sector update with verified backup |
| `ARTIFACTS/str8n-v1.34-directory-refresh-2000.s19` | Guarded directory refresh; deliberately clears existing directory records |
| `APPLICATIONS/str8n-v1.34-bank-maint-menu-2000.a` | ASM-F2 image carrier matching the expanded maintenance S19 |
| `TOOLS/convert_guest_bin_to_s19.ps1` | Convert an owner-supplied guest BIN into S19 |
| `TOOLS/compose_str8n_install_s19.ps1` | Validate and prepare dense installer S19 |
| `PACKAGES/str8n-v1.34-wdcmonv2-str8n-migration-kit.zip` | Separate factory-migration workflow with project-written tools |

STR8 `L` loads and executes the RAM tools' `$2000` entry. Read the
[operator guide](OPERATORS_GUIDE.md) before any maintenance command; several
operations erase or program flash and require the shown confirmations.
The isolated WDC adoption tool lives inside the migration kit and has its own
[maintenance guide](STR8_IN65_BANK_MAINTENANCE.md).

## Bank Maintenance from ASM-F2

The `.a` file is a generated `DB` image carrier, not symbolic assembly source.
It emits the exact 12,288-byte maintenance menu at `$2000-$4FFF`, including
the canonical top-sector candidate at `$4000`. The release verifier compares
every emitted byte with the supplied S19.

With separately installed HIMON and ASM-F2:

1. Enter `ASM NEW` from HIMON.
2. Send the complete `.a` file; stop on any `ERR=` response.
3. At `SEAL>`, enter `.` to return to HIMON.
4. Enter `G 2000` to start maintenance and follow its prompts.

Edit the project's symbolic `.asm` sources and regenerate the carrier when
developing the tool. The carrier is provided for convenient board loading.

## Separate HIMON and ASM-F2 releases

The [R-YORS releases](https://github.com/95westus/R-YORS/releases) provide
HIMON, ASM-F2, their relevant manuals, and maintained applications. Those
collections include bank audit/dump/CRC tools, AP flash read/dump tools, an
ASM session report, LED and terminal examples, and appropriately licensed
games selected by their release manifests. Consult those manifests and
license notices for exact contents and prerequisites.

These files are not duplicated into the STR8-N distribution. Use the
[component installation guide](HIMON_ASMF2_AFTER_STR8N.md) after factory
migration or when updating an existing board.

## Qualification programs and distribution boundary

`TESTS/` contains optional console ABI, IRQ, and LED/worker test programs.
The worker test can program and erase flash. Use the documented procedure
in the [follow-up report](STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md);
these are qualification fixtures, not ordinary applications.

All supplied STR8-N code carries the project MIT license. The release does
not include WDC tool executables, WDCMON firmware, stock bank images,
owner captures, or games. Migration tools communicate with firmware already
on the owner's board and keep any archive bytes local. See the
[provenance policy](WDCMONV2_MIGRATION_PROVENANCE.md).
