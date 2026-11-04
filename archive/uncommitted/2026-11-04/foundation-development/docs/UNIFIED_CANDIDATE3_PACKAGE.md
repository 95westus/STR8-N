# Local unified candidate3

November1,2026. This is a new local acceptance archive; historical candidate1/2,
published Foundation/preview downloads, tags and branches remain unchanged.

- Archive: `STR8N-MON-g00000010-candidate3.zip`
- Local directory: `C:/SRC/STR8-N/BUILD/unified-g10-candidate3-20261101-r3/`
- Size:1,312,527 bytes
- SHA-256:`6b1b3220cf5c05be0b49bf98c055f1df82e3870531512e2d3f94f3363b4bc789`

It contains the current2512 g10 Traditional MON A/B profile, WB2 gE,
SRAM/WORK g4, PROGRAM g3, CLOCK, FLASH/CONFIG, BANK MAINT2.4 and their
shared services. It includes exact frozen F.bin, the published Foundation
operator kit/RAM migrator, current terminal0.1.2 with Shift+F2/F3 RAM S19,
the reconciled native manual, supporting docs and small commented examples.
The local Foundation extraction overlays only the current console/core,
requirements and console manual; original published archives are unchanged.
No vendor WDC firmware, board captures, settings/journal records, EEPROM/SPI
data or qualification RAM fixtures are packaged. Source/provenance is a
working-tree snapshot identified by file hashes and its base commit.

The profile reserves88KiB, including F and C/D: B1:8-D, B2:8-F and B3.
There are19 utility image targets; F and C/D are excluded. B3:9 distributes
only its3072-byte code prefix. The preparer retains the target's entire1024-byte
RTC metadata tail. B1 targets require a current B1 capture for occupied-image
review; owner B0 and B1:E/F are outside these image targets.

## Accepted host-only extraction

A fresh extraction passed its exact file-set/hash verifier. Its extracted
preparer emitted19 complete target sectors identical to the archived current
2512 profile. RTC metadata and C/D history were retained byte-for-byte.
Missing B1 was refused before creating output. The extracted console reports
version0.1.2 and opens no port for that version query.

No firmware was rebuilt, no CPU simulation ran, and no board was accessed.
The corrected FLASH full-source help collapses to the same installed compact
menu, so no help-only build/erase is necessary; see `FLASH_HELP_PROVENANCE.md`.

Receipt:
`BUILD/unified-g10-candidate3-20261101-r3/EXTRACTION-PREPARATION-RECEIPT.json`.
The earlier r2 archive was an intermediate host-preparation checkpoint; r3
adds the corrected current allocation/storage/install manual. Use r3 for the
next live trial. Historical files have not been overwritten.

## Later live acceptance and remaining limits

The subsequent [2512 live trial](CANDIDATE3_2512_LIVE_ACCEPTANCE.md) passed on
November2:19 live components, physical Shift+F2/F3 and native dialogs, initial
S19/BIN cancellation and normal BIN execution/return. Fresh owner RAM/ZP was
restored/read back; B3/F/settings/history remained exact; final REC>, COM4 free
and RTC eligible. No flashing was needed. The earlier
[plan](CANDIDATE3_2512_ACCEPTANCE_PLAN.md) remains the reviewed procedure.
The archive's pre-trial manifest flags remain historical; the dated external
completion receipt binds acceptance to this unchanged archive hash.

The same system components are now installed on2609/65C816 emulation. Its
[reviewed upgrade and targeted live acceptance](CANDIDATE3_2609_LIVE_ACCEPTANCE.md)
passed, including saved-B physical startup and RTC readmission. The26 old
journal rows were archived and all counts/settings carried forward; F stayed
golden. The latest profile now has2512 and targeted2609 evidence, with no
claim that every2512 positive-write fixture was repeated on2609.
No new migration, factory flash, source-only rebuild from this snapshot,
publication or all-board rollout is claimed. The kit's preparers open no port
and grant no erase allowance. ASM/DBG remain follow-on work.
