# STR8-N 1.35 board qualification - 2026-09-16

Status: ordinary guarded update, policy restoration, physical/software reset,
and post-reset AM03 handoff checks pass on COM4. Factory migration is not
board-qualified for this version. Earlier v1.34 reports remain historical
evidence only; interrupt, worker and factory results are not carried forward.

Canonical 4096-byte top BIN SHA-256:
`96416190B7E1A37E2C01A407AB9C8EA4ADE06855BBFD0DDCC306FF68418A359A`.
The public ABI/layout are retained, with 134 resident bytes free.

Evidence is preserved in the companion R-YORS repository:

- `DOC/GUIDES/LOGS/STR8N_V135_BOARD_2026-09-16/`: guarded update verified
  B2:F backup and B3:F installation. Complete four-bank readback limited
  changes to those sectors. Policy A6 restoration and scratch restoration
  were subsequently verified by another complete readback.
- `DOC/GUIDES/LOGS/AM03_BOARD_2026-09-16/physical-reset-20260916-203949/`:
  physical RESET reported `RST H`, STR8-N 1.35 and HIMON `00.0916(1949)`.
  The ASM resume flag cleared. Bank APTEST, a RAM child execution marker
  with provider preservation/state retirement, and BANKDUMP menu/map/return
  passed. All 32 flash sectors exactly matched the expected installed image.

The final configured live top differs from the canonical programmer image
because of board directory, policy and installer-journal data. Its SHA-256 is
`F354D2276C6D0BB374E6C838447AA5BCE75D9B92353AFC21D7074844B2AD2A33`.
The final full-flash SHA-256 is
`3f550b36ab774e9ab190743af68b8266feec7916685756a3fe8a2873d6b760ae`.
Installed ASM-F2 remains `00.0915(2324)`; this is not proof of a new ASM image.

No v1.35 factory-migration, Linux hardware, or complete interrupt/worker
release-matrix qualification is claimed by these tests.
