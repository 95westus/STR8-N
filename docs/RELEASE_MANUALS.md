# STR8-N v1.34 release manuals

This standalone release supplies the exact 4 KiB STR8-N top-sector BIN,
resident S19, RAM maintenance tools, Bank Maintenance `.a`, and the separate
WDC-to-STR8 migration kit. HIMON and ASM-F2 come in their own release ZIPs.

## Choose the relevant guide

| Task | Manual |
| --- | --- |
| Operate the board, install or recover a payload | [Operator's guide](OPERATORS_GUIDE.md) |
| Follow complete terminal sessions | [Worked examples](EXAMPLES.md) |
| Understand addresses, ABI, S19 contracts, and builds | [Technical guide](TECHNICAL_GUIDE.md) |
| Inspect memory maps and boot/install flows | [Maps and diagrams](MAPS.md) |
| Choose an included image or application | [Software catalog](SOFTWARE_CATALOG.md) |
| Migrate a factory WDC board | [Migration guide](WDCMONV2_MIGRATION.md), then the nested kit's QUICKSTART.txt |
| Adopt the retained stock guest | [Migration Bank Maintenance](STR8_IN65_BANK_MAINTENANCE.md) |
| Install the separate monitor/assembler releases | [HIMON/ASM-F2 installation](HIMON_ASMF2_AFTER_STR8N.md) |
| Prepare a Bank 0-2 guest | [Guest S19 quick reference](BANK_0_2_GUEST_S19.md) |
| Integrate an external STR8 checkout | [R-YORS integration](R_YORS_INTEGRATION.md) |
| Understand physical versus software reset | [Reset-source contract](RESET_SOURCE_CONTRACT.md) |
| Review redistribution boundaries | [Migration provenance](WDCMONV2_MIGRATION_PROVENANCE.md) |

The ready-to-use files are under ARTIFACTS, APPLICATIONS, TOOLS, and PACKAGES.
Paths beginning with BUILD, src, tools, or C:/SRC in the developer manuals
refer to source-checkout examples. They do not mean those directories must
exist on an operator's computer. The catalog gives the archive locations.

## Identity and verification

The canonical 4096-byte top BIN has SHA-256
`9538D97854BA9D5D76143CBA0FEDB3B2E7CE18F977CE89557406E63404026CB7`.
The release retains STR8-N version 1.34; packaging refreshes documentation
and its manifest timestamp without changing that accepted firmware.

Run VERIFY-PACKAGE.ps1 after extraction. SHA256SUMS.txt and
PACKAGE-MANIFEST.json enumerate the files and hashes. CHECK-LINKS.ps1 checks
packaged Markdown destinations without network or serial access. References
to historical evidence or source files not bundled here use the source
repository at the recorded commit. Those external links require internet.

## Exact hardware coverage

The accepted firmware is covered by the
[update/reset/console report](STR8N_V1_34_BOARD_TEST_2026-09-15.md),
[interrupt/worker report](STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md), and
[Windows factory-migration report](STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md).
The [size report](STR8N_V1_34_SIZE_OPTIMIZATION.md) records the host checks.

Bank 1/2 guest boots, transient LED timing, injected failure/recovery paths,
and Linux migration remain outside those reports' accepted coverage.
Historical board reports retain their tested versions and observations;
packaging is not a new hardware run.
