# Load HIMON And ASM-F2 After STR8-N

The WDCMONv2 migration is complete when physical RESET reaches `STR8-N 1.28`
and the retained stock monitor can be launched with `J0`. It does not install
R-YORS, HIMON, or ASM-F2.

HIMON and ASM-F2 are optional, separate Bank-3 component loads. Obtain or
build only these component S19 files from the adjacent R-YORS repository:

```text
RELEASE/ARTIFACTS/COMPONENT-IMAGES/ryors-v1.2-himon-bank3-c-e.s19
RELEASE/ARTIFACTS/COMPONENT-IMAGES/ryors-v1.2-asm-bank3-8-b.s19
```

The `ryors-` filename prefix identifies their source repository; loading these
two slices does not install a complete R-YORS bank image. Do not use either of
these combined products for this procedure:

```text
ryors-v1.2-himon-asm-bank3-8-e.s19
ryors-v1.2-str8n-himon-asm-bank0-2-8-f.s19
```

Verify the component hashes against the R-YORS release that supplied them.
Keep the 128 KiB programmer backup and the retained WDCMONv2 B0 archive.

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
4. Press physical RESET again and require `STR8-N 1.28`.

This optional component procedure begins after, and is not part of, the
WDCMONv2-to-STR8-N migration transaction.
