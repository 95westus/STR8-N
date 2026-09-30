# STR8-N

STR8-N is a guarded reset monitor and flash loader for WDC SXB boards. It
occupies Bank 3's `$F000-$FFFF` sector; guest firmware such as R-YORS remains
separate.

## Current code base: v2.0a24

[v2.0a24](https://github.com/95westus/STR8-N/tree/v2.0a24) is the current
**alpha board-test** code base. It uses the FT245 console and provides bank
selection, RAM/S19 loading, verified flash writes, boot handoff, and an
optional E-sector S/R/T extension. W65C816SXB board 2609 passed the core
migration and regression checks. W65C02SXB board 2205 passed the unified
installer and no-EDU migration checks. The EDU daughterboard was absent.

The same alpha24 WDCMONv2 RAM installer runs on both SXB CPU families: its
`$FB` entry byte is XCE on the 816 and a one-byte NOP on the W65C02S. The
65C02 installer runs in an automated CPU/flash model; the 816 qualification
uses recorded manual board tests.

- [W65C816SXB manual migration guide](docs/STR8N_V2_A24_816_MANUAL_MIGRATION.md)
- [Alpha24 package contents and limits](docs/STR8N_V2_A24_PACKAGE_README.md)
- [Alpha24 maps and diagrams](docs/STR8N_V2_A24_MAPS.md)
- [816 qualification checklist](docs/STR8N_V2_A24_816_CHECKLIST.md)
- [02SXB no-EDU migration checklist](docs/STR8N_V2_A24_02_NO_EDU_CHECKLIST.md)
- [02SXB board 2205 result](docs/STR8N_V2_A24_2205_NO_EDU_2026-09-30.md)

Run `make v2-a24-package` to build and verify the local alpha24 ZIP. The
[v2 development guide](docs/STR8N_V2.md) and
[release manual index](docs/RELEASE_MANUALS.md) retain earlier contracts and
release history. STR8-N is independent of WDC and R-YORS; see [LICENSE](LICENSE).
