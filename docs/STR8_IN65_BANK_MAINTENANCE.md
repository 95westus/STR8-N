# STR8-iN/65 v1.28 RAM Bank Maintenance

This guide applies only to the isolated STR8-iN/65 v1.28 RAM image:

```text
BUILD/v1.28/s19/str8n-v1.28-str8-in65-bank-maint-2000.s19
```

It remains a migration-specific RAM tool outside the canonical STR8-N v1.28
manifest and migration ZIP. The resident cold-start sequence it was built to
support is now canonical v1.28; the tool's WDC-specific defaults and `F`
command remain isolated. Load it with the running STR8 `L` command. Its S9
record starts the menu at `$2000` automatically.

## D0 in the current migration image

The current one-command migration installer preserves the original WDCMONv2
image in B0 and installs a migration-configured STR8-N top that already
contains COMPLETE `D0 FF WDCM2 FFFF FCFFFFFF`. Selector `0` and `J0` therefore
work immediately after migration; this RAM maintenance image is not a required
consumer step.

Use the adoption path below only when working with an older test image, a
deliberately refreshed/erased directory, or another retained B0 whose D0 row
is genuinely all `$FF`. `J0` correctly fails closed while D0 is absent.

## Enroll a retained WDCMONv2 Bank 0 when D0 is absent

At `BM>` enter `D`. The STR8-iN/65 defaults are:

```text
BANK 0-3 [0]>             Enter        -> Bank 0
TYPE 00-FF [FF]>          Enter        -> opaque/foreign type $FF
DESC 5 CHARS [AUTO]>      Enter        -> WDCM2 for Bank 0
TYPE ADOPT B0>            ADOPT B0     -> exact commit confirmation
```

The automatic descriptions are `WDCM2`, `BANK1`, `BANK2`, and `STR8N` for
Banks 0 through 3. A typed two-digit TYPE or typed five-character description
overrides its default. Descriptions accept uppercase letters, digits, `-`,
`_`, and `.`.

For B0-B2, adoption stores ENTRY=`FFFF`; `Jn` reads the selected bank's real
RESET vector during handoff. D0 is committed in this order:

```text
journal START      FEFFFFFF
TYPE/DESC/seal/ENTRY descriptor
journal COMPLETE   FCFFFFFF
```

After `D` reports `OK`, use `M` and require a row equivalent to:

```text
D0 FF WDCM2 FFFF FCFFFFFF
```

Then return with `Q`, reset if desired, and test `J0`. Directory enrollment
does not alter any B0 payload byte.

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

- B3:`$FFF0` WORK and `$FFF1` top-backup role assignment remain a separate
  first-role transaction because that operation must create and retain its
  recovery copy before publishing the locators.
- No VTOC byte layout is implemented or frozen in STR8-N or R-YORS. Current
  planning treats a future VTOC as a projection/locator over a managed catalog,
  not bytes that this migration tool may invent. Therefore this RAM image has
  no `V` write command.

## Hardware evidence

The first 2026-08-28 board run accepted prompted default D0 enrollment as
`FF WDCM2 FFFF FCFFFFFF`, read it back through `M`, launched B0 twice through
`J0`, and recovered STR8-N 1.28 through physical RESET. The later factory-path
run accepted the current embedded-D0 migrator directly, including exact B3-to-
B0 preservation, `J0`, the visually observed CS0-CS3 chase, complete retained
EDU application startup, and final physical RESET. The complete retained
transcripts, including a rejected pre-write menu-overlap build, are in
[WDCMONV2_MIGRATION_BOARD_TEST.md](WDCMONV2_MIGRATION_BOARD_TEST.md).
