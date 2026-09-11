# STR8-iN/65 v1.33 RAM Bank Maintenance

This guide applies to the production STR8-iN/65 v1.33 RAM image:

```text
BUILD/v1.33/s19/str8n-v1.33-str8-in65-bank-maint-2000.s19
```

It is part of the v1.33 factory migration ZIP under the consumer-facing name
`ARTIFACTS/STR8-iN65-BANK-MAINT-2000.s19`. The resident cold-start and EDU
quiet-start sequence it supports is canonical v1.33; the tool's WDC-specific
defaults and `F` command remain isolated in RAM. Load it with the running STR8
`L` command. Its S9 record starts the menu at `$2000` automatically.

The v1.33 migration artifacts are host-qualified. The complete factory
migration remains board-proven for v1.32; do not relabel that earlier proof as
v1.33 until the factory path is repeated with these exact artifacts.

## D0 in the current migration image

The current factory loader preserves the original WDCMONv2 image in opaque B0
and installs the exact canonical STR8-N v1.33 top with an erased Bank-3
directory. This RAM maintenance image is therefore a required consumer step:
it explicitly publishes D0 only after the first verified v1.33 boot. `J0`
correctly fails closed while D0 is absent.

## Enroll a retained WDCMONv2 Bank 0 when D0 is absent

At `BM>` enter `D`. For the retained WDCMONv2 consumer identity, enter:

```text
BANK 0-3 [0]>             0
TYPE 00-FF [FF]>          FF
DESC 5 CHARS [AUTO]>      WDCV2
PROPOSED D0 B3:$FFB0: FF FF FF FF 57 44 43 56 32 FE FF FF FC FF FF FF
TYPE ADOPT B0>            ADOPT B0     -> exact commit confirmation
```

The proposed line is emitted before the confirmation. It identifies the
physical Bank-3 directory address and every byte that will be programmed; no
Bank-0 payload byte is part of the write.

The generic RAM tool retains `FF` and `WDCM2` as its empty-input Bank-0
defaults. The v1.33 consumer procedure keeps type `FF` and deliberately
overrides the description with `WDCV2`. Automatic descriptions for the other banks
remain `BANK1`, `BANK2`, and `STR8N`. Descriptions accept uppercase letters,
digits, `-`, `_`, and `.`.

For B0-B2, adoption stores ENTRY=`FFFF`; `Jn` reads the selected bank's real
RESET vector during handoff. D0 is committed in this order:

```text
journal START      FEFFFFFF
TYPE/DESC/seal/ENTRY descriptor
journal COMPLETE   FCFFFFFF
```

After `D` reports `OK`, use `M` and require a row equivalent to:

```text
D0 FF WDCV2 FFFF FCFFFFFF
```

Then return with `Q` and test `J0`. `J0` hands control completely to the
preserved factory system in Bank 0. Press physical RESET to return to STR8-N;
that reset-only return is intentional and by design, not a flaw. Directory
enrollment does not alter any B0 payload byte.

## Update or remove a directory record

- `N` changes only the five-character description of one COMPLETE D0-D3 row.
  It requires an erased scratch sector, takes and verifies a temporary B3:F
  backup, rewrites and verifies B3:F, then erases the scratch backup.
- `R` clears D0-D2 only after all eight payload sectors in that bank verify
  erased. Flash cannot change cleared bits back to one, so this also uses the
  guarded full B3:F rewrite. `R` will not detach a directory row from a bank
  that still contains payload.
- TYPE, seal, and ENTRY remain immutable after adoption. To change those
  fields, erase the payload bank, use `R` to clear the row, restore the payload,
  then adopt it again with the new identity.

## Erase B0 and clear D0

This destroys the retained WDCMONv2 bank. First preserve and verify an external
128 KiB programmer image or another known recovery source.

Use these Bank Maintenance menu transactions in order:

```text
BM> E
BANK 0-3> 0
SECTOR 8-F, ALL, OR X-Y; B3 MAX E> ALL
TYPE ERASE B0ALL> ERASE B0ALL
```

Require `OK`, then clear the now-stale directory row:

```text
BM> R
RECLAIM DIR 0-3> 0
TYPE CLEAR D0> CLEAR D0
```

Require `BACKUP VERIFIED` and `OK`. Finally use `M`: every B0 sector must show
`E`, and D0 must be all `FF`. Between the two transactions B0 is erased but D0
is intentionally stale, so `J0` fails closed.

Configured WORK or top-backup sectors are protected from `E`. B3:F is always
protected; Bank 3 erase operations cover only sectors 8-E and return directly
to STR8.

## Search-policy flag

`F` edits only the accepted scoped AP/FNV search-policy byte at B3:`$FFF2`.
Enter accepts the STR8-iN/65 default `$A6`, which enables B1 and B2 while
excluding the retained WDCMONv2 B0:

```text
BM> F
SEARCH FLAG FF/A0-A7 [A6]> Enter
TYPE FLAGS A6> FLAGS A6
```

`FF` disables automatic external search; `A0`-`A7` encode the B0-B2 mask.
The change uses a verified temporary B3:F backup and a full rewrite. It does
not affect explicit `J0`, read-only B0 inspection, or recovery operations.
The current STR8-iN/65 resident does not consume this AP/FNV policy; `F`
provisions the accepted byte contract for the later HIMON scoped-search slice.

## Deliberately not written by this image

- B3:`$FFF0` WORK and `$FFF1` top-backup role bytes are preserved exactly by
  D0 adoption; the canonical v1.33 image initializes them to B1:E and B1:F.
- No VTOC byte layout is implemented or frozen in STR8-N or R-YORS. Current
  planning treats a future VTOC as a projection/locator over a managed catalog,
  not bytes that this migration tool may invent. Therefore this RAM image has
  no `V` write command.

## Hardware evidence

The first 2026-08-29 v1.29 consumer run exercised explicit D0 enrollment as
`65 WDCV2 FFFF FCFFFFFF`, read it back through `M`, launched retained
WDCMONv2 through reset selector `0` and shell `J0`, and captured physical
RESET returning to STR8-N 1.29 after each launch. That proves the transaction
mechanics, external 4096-byte BIN, and final RESET path, but the intended
`FF WDCV2` identity still required a rerun. The immediately following complete
factory-baseline run exercised erased-B0 preservation and accepted the exact
`FF WDCV2 FFFF FCFFFFFF` row, selector `0`, `J0`, and both RESET returns.

The 2026-08-30 board #3 run repeated the v1.29 erased-B0 factory path on COM3
with a W65C02SXB/EDU board that had no visible date stamp; operator boards #1
and #2 are recorded as date-stamped `202205` and `202512`. Board #3 accepted
the factory WDCMONv2-to-STR8-N 1.29 migration, copied and verified B3 into B0,
installed the external 4096-byte v1.29 top, launched retained WDCMONv2 through
reset selector `0` and shell `J0`, and returned to STR8-N 1.29 by physical
RESET after each launch. Its D0 row was recorded as the consumer-target
`FF WDCV2 FFFF FCFFFFFF`, providing cross-board success evidence.

The first 2026-08-28 v1.28 board run accepted prompted default D0 enrollment as
`FF WDCM2 FFFF FCFFFFFF`, read it back through `M`, launched B0 twice through
`J0`, and recovered STR8-N 1.28 through physical RESET. The later v1.28
factory-path run accepted the embedded-D0 migrator directly, including exact B3-to-
B0 preservation, `J0`, the visually observed CS0-CS3 chase, complete retained
EDU application startup, and final physical RESET. The complete retained
transcripts, including a rejected pre-write menu-overlap build, are in
[WDCMONV2_MIGRATION_BOARD_TEST.md](WDCMONV2_MIGRATION_BOARD_TEST.md). These
runs are historical evidence for the earlier embedded-D0 design.
