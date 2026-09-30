# Board 2609: stock restore, unified remigration, and guarded B3:E installation

Board 2609 is the W65C816SXB on COM8 with SST39SF010A flash (`BF/B5`). The
operator asked to copy the retained stock B0 to B3, run the unified alpha24
WDCMONv2 migrator, and optionally install the B3:E binary S/R extension. The
board began at `STR8-N 2.0a24 B3 65C816`, `B3>`. All serial logs and byte
readbacks for this run are owner-local under
`output/qualification/board-2609-remigrate-2026-09-30/`.

## Preflight and stock restore

Complete 32 KiB readbacks were captured before writes. B0 SHA-256 was
`1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`,
identical to the previously recorded original stock image. B3:F SHA-256 was
`43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a`,
the alpha24 monitor, and B3:E was all zero. B1 and B2 were also captured for
whole-bank preservation checks.

The previously qualified board-2609 restore S19 had SHA-256
`cdb4499fed6e2fccea8fa7c30fb23dad283abbb48e58a776c3223d9f254f2ad8`.
Monitor `L` loaded it at `$2000-$2BC7`; a 3,016-byte RAM readback matched
every S19 byte. Its live preflight reported `BF/B5`, B0 FNV-1a `280928EC`,
RESET `$F818`, and B0 retention. After the exact `RESTORE B0 TO B3` token,
the tool copied sectors 8-E and F last and reported `B0 == B3 WHOLE BANK
VERIFIED` and `B0 PRESERVED`. A receive-only physical-reset capture booted the
stock W65C816SXB native-mode menu from B3. Its peripheral scan is stock
firmware output, not EDU daughterboard qualification.

## Unified WDCMONv2 remigration

The extracted, verified 32-file alpha24 package supplied the unified script,
its pinned 2,460-byte RAM installer S19, and canonical F BIN. During the
physical-reset identity gate, WDCMONv2 reported `SXB6`, hardware 3.00, and
WDCMON 2.00. The operator confirmed the physical W65C816SXB model. RAM
readback was byte-exact. The installer matched stock B3 FNV-1a `280928EC`,
accepted the already-preserved B0, received the 4,096-byte top BIN, and
reported `MIGRATION VERIFIED`. A physical RESET then booted
`STR8-N 2.0a24 B3 65C816` at `B3>`.

An independent complete B3:E/F readback after F installation was SHA-256
`2519c05ff558969b19401a702382a2986219b5e2d5f805d402deaa0552998d15`:
E was the exact stock all-zero sector; F matched the canonical alpha24 BIN.

## Guarded B3:E installation and preservation

The packaged `BUILD-B3-E-UPDATER.py` consumed that exact 8 KiB readback. It
generated an E installer S19 and staged E BIN, preserving `$E000-$E7FF` and
`$EF00-$EFFF` and inserting the alpha24 S/R code at `$E800-$EEFF`. The
generated 8,640-byte RAM image was byte-for-byte identical to the previously
hardware-installed board-2609 updater image. Its CPU/flash-model test passed.
Monitor `L` loaded it at `$2000-$41BF`; every RAM byte read back exactly.
`G 2000` reported `B3:E exact; TYPE Y to repair>`, and `Y` produced
`B3:E VERIFIED; RESET`. The monitor returned to the alpha24 `B3>` prompt.

An independent complete B3:E/F readback exactly matched the staged E BIN and
canonical F BIN, SHA-256
`5864227879b4298ace8d9c5a6d637cda1347a6c6b4c6ebbdf0505555b58f535c`.
`T 3` returned to `B3>` without `SR unavailable`. Complete before/after
readbacks proved B0, B1, and B2 unchanged byte-for-byte:

| Bank | 32 KiB SHA-256, before and after |
| --- | --- |
| B0 | `1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94` |
| B1 | `64f94bdd2ba08ed01da20092ec4cce18e0d7e29688b2704a4772960f107fc9c8` |
| B2 | `2f0000c74eceec809a814e31f822702977d7bfed5ee6f3bc4869627864ca59a8` |

A separate physical RESET after E installation was requested but had not been
captured when this record was written. A new S/R save/restore operation was not
performed in this run. EDU hardware was absent and was not qualified.
