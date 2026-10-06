# Beta4 RESTORE / SAVE / TABLE (RST)

RST means **RESTORE / SAVE / TABLE**, implemented at the STR8-N monitor
prompt `B3>`. A saved record retains a RAM program or data range in flash,
then restores that range later. It is separate from a host-side raw bank backup.

## Start the installed BANK MAINT

The release installs unchanged BANK MAINT 1.5 as the label `MAINT` in B3
sectors 8 and 9. At `B3>`:

```text
R MAINT
```

This restores the 7,508-byte program into RAM `$2000-$3D53` and starts it
at `$2000`. At `BM>`, use `?` for help and `Q` to return to `B3>`.
The saved copy survives RESET. The monitor's `M`, `M 1` and `M 3` map
shortcuts restore this same record automatically.

To restore without running:

```text
R MAINT L
G 2000
```

The second command starts the copy already loaded in RAM. A host load is
also available: enter `L`, send `str8n-bank-maint-1.5-2000.s19` as ASCII text
with about 40 ms between lines, wait for completion, then `G 2000`.
BANK MAINT's own `R` reads into its editor and `S` stages bytes. Return to
`B3>` with `Q` before using monitor RESTORE or SAVE.

## TABLE the installed record

```text
T 3
```

The release record appears as:

```text
B3:8000 2000-3D53 1D54 C MAINT
```

Columns give bank/header address, inclusive RAM range, hexadecimal body
length, completion state (`C` means complete), and label. Header plus body
occupies B3 `$8000-$9D6B`. Keep both sectors 8 and 9 intact. Pending records
are listed but cannot be restored. `T` lists all four banks; `T 1-2` lists
an inclusive range. TABLE also works at `BM>` and returns to that prompt.

## SAVE an additional copy

The installed MAINT already occupies B3:8/9. Do not save over it. To practice
SAVE using an erased B1 span, first restore MAINT and return with `Q`, then:

```text
S 1 8000 2000 3D53 MAINTCOPY
T 1
```

The different label avoids a duplicate `MAINT` lookup. Expected TABLE row:

```text
B1:8000 2000-3D53 1D54 C MAINTCOPY
```

General syntax is `S bank flash-address ram-start ram-end [label]`.
SAVE requires completely erased space for the 24-byte header and inclusive
RAM range. It refuses occupied space, writes a pending record, verifies it,
then commits its completion marker. Success reports `Done`. Labels contain
no spaces and have at most 16 characters; program RAM is `$0200-$66FF`.
Leave B0 alone.

To restore this additional copy without executing, or restore and run:

```text
R 1 MAINTCOPY L
R 1 MAINTCOPY
```

RESTORE overwrites the record's RAM range. Use `L` for data or inspection;
without it, the stored RAM start is the execution entry. `R MAINTCOPY`
searches all banks when the label is unique; `R 1 8000 L` addresses the
header explicitly. Missing labels report `SR error 05`; duplicates report
`SR error 06`. A bank/address qualifier resolves duplicates. Invalid or
pending records are refused.

## Remove only the practice copy

While the additional copy is running at `BM>`, after confirming B1 sectors
8/9 contain only this practice record:

```text
E 1 8-9
```

Check the printed destination, enter `Y` plus Enter, wait for `VERIFIED`,
then `Q`. This removes `MAINTCOPY` from B1 while retaining the installed
B3 `MAINT` record. `R MAINT` and monitor maps remain available.
