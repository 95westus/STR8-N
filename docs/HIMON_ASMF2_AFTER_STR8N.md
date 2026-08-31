# Load HIMON And ASM-F2 After STR8-N

The WDCMONv2 migration is complete when physical RESET reaches `STR8-N 1.29`
and the retained stock monitor can be launched with `J0`. It does not install
R-YORS, HIMON, or ASM-F2.

`J0` hands the computer completely to the retained factory system. Physical
RESET is the designed way back to STR8-N; the absence of a software-return
command in that guest is intentional and is not a flaw in STR8-N or the
migration.

HIMON and ASM-F2 are optional Bank-3 component loads. The STR8-N v1.29 release
places the ready-to-send files together under `OPTIONAL/HIMON-ASM/`:

```text
OPTIONAL/HIMON-ASM/ryors-v1.2-himon-bank3-c-e.s19
OPTIONAL/HIMON-ASM/ryors-v1.2-asm-bank3-8-b.s19
OPTIONAL/HIMON-ASM/ryors-v1.2-himon-asm-bank3-8-e.s19
```

The same files can be obtained or rebuilt from the adjacent R-YORS repository.

The `ryors-` filename prefix identifies their source repository. Loading the
two slices does not install a complete R-YORS bank image. For the separate
component procedure below, do not substitute either combined product:

```text
ryors-v1.2-himon-asm-bank3-8-e.s19
ryors-v1.2-str8n-himon-asm-bank0-2-8-f.s19
```

Verify the component hashes against the R-YORS release that supplied them.
Keep the 128 KiB programmer backup and the retained WDCMONv2 B0 archive.

## Simplest combined install

For a new Bank-3 installation, install the packaged combined image in one
transaction:

```text
I
B0-3: 3
RANGE: 8-E
TYPE: FF
DESC: RYORS
I B3 8-E WRITE? Y: Y
S19
```

Send `ryors-v1.2-himon-asm-bank3-8-e.s19`. Require seven sector dots, the
commit prompt, and `OK`. Its S9 entry is `$C000`, so completion starts HIMON.
The separate procedure below is useful when only one component is wanted or
is being updated.

## Load HIMON first

At `STR8-N>` enter:

```text
I
B0-3: 3
RANGE: C-E
TYPE: 48
DESC: HIMON
I B3 C-E WRITE? Y: Y
S19
```

Send only `ryors-v1.2-himon-bank3-c-e.s19`. Require three sector dots, the
commit prompt, and `OK`. Its S9 entry is `$C000`, so a successful transaction
starts HIMON. Record the exact `HIMON V` banner.

At the HIMON prompt enter `STR8` to return to `STR8-N>`. If that command is
not available in the supplied HIMON build, press physical RESET and select
`S` at the STR8-N selector.

## Load ASM-F2 second

At `STR8-N>` enter:

```text
I
B0-3: 3
RANGE: 8-B
TYPE: 41
DESC: ASMF2
I B3 8-B WRITE? Y: Y
S19
```

Send only `ryors-v1.2-asm-bank3-8-b.s19`. Require four sector dots, the
commit prompt, and `OK`. Record the exact `ASM-F2` identity after its S9 entry.

These are `I` flash-install payloads, not STR8 `L` RAM programs: their target
ranges are `$8000-$BFFF` and `$C000-$EFFF`, outside STR8's `$2000-$7AFF` RAM
load window. Neither component touches protected Bank-3 sector F.

## Prove the resulting board

1. Press physical RESET and select `C`; require the installed HIMON identity.
2. Enter ASM-F2 from HIMON and require the installed ASM identity.
3. Return to STR8-N, run `J0`, and require the retained WDCMONv2 board identity.
4. Press physical RESET again and require `STR8-N 1.29`.

This optional component procedure begins after, and is not part of, the
WDCMONv2-to-STR8-N migration transaction.
