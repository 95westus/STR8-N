# STR8-N V2

STR8-N is the 4096-byte protected top sector in Bank 3 of a W65C02SXB/EDU.
It owns physical RESET, selects a bank, installs dense S19 images, protects
itself from ordinary installs, and then gets out of the guest program's way.

The complete STR8-N image—resident code, RAM worker, directory, configuration,
and hardware vectors—fits at CPU `$F000-$FFFF` (physical flash
`$1F000-$1FFFF`). HIMON and ASM are separate Bank-3 payloads below `$F000`.

> [!WARNING]
> Flashing can erase software or leave the board needing an external
> programmer. Keep a verified recovery image. Check the bank and range before
> answering `WRITE? Y`. Do not remove power or press NMI while flash is being
> erased or programmed.

## Read first

- [Operator's Guide](docs/OPERATORS_GUIDE.md) — booting, installing, recovery,
  and what the prompts mean.
- [Technical Guide](docs/TECHNICAL_GUIDE.md) — exact S19 rules, memory use,
  flash layout, directory, handoff, and public interfaces.
- [Maps and Diagrams](docs/MAPS.md) — the system, flash, RAM, boot, and install
  flows on one page.
- [R-YORS Integration Boundary](docs/R_YORS_INTEGRATION.md) — how a separate
  R-YORS checkout consumes the pinned STR8-N artifact.

## Operator commands

```text
I       install a payload-only S19 image
L       load an S19 into $2000-$7AFF RAM and execute S9
H       warm-enter compatible HIMON in Bank 3
J0-J3   hand control to the selected bank
```

`I` still writes flash only. STR8-N `L` is the compact recovery loader: it
loads only `$2000-$7AFF` and immediately executes the S9 address. With
R-YORS/HIMON, use HIMON `L` to load without starting or `L G` to load and
start across its broader RAM policy.

Physical RESET always selects Bank 3 first. Banks 0–2 may accept any
contiguous, 4K-aligned range from 4K through 32K. Bank 3 may accept 4K through
28K; sector F is STR8-N and cannot be installed by `I`.

For an image ending at `$FFFF` in Bank 0, 1, or 2, the valid size/range pairs
are `4K F`, `8K E-F`, `12K D-F`, `16K C-F`, `20K B-F`, `24K A-F`, `28K 9-F`,
and `32K 8-F`. Ending at F is useful because it includes the hardware vectors,
but it is not required by the installer.

## Build

The Makefile expects WDC `wdc02as` and `wdcln` on `PATH`.

```text
make                 build and verify everything
make resident        build the resident supervisor
make workers         build the unified RAM worker
make layout-check    enforce fixed addresses and at least 8 spare bytes
make range-matrix-check
                     validate all documented install sizes and ranges
make ram-load-contract-check
                     validate STR8-N L destination and S9 boundaries
make programmer-bin  create the 4096-byte top-sector image
make clean           remove BUILD
```

Primary outputs:

```text
BUILD/bin/str8n-bank3-f000-ffff.bin   external-programmer image
BUILD/s19/str8n-f000.s19              resident component
BUILD/s19/str8n-worker-0200.s19       worker evidence/component
BUILD/str8n-manifest.json             sizes, addresses, ABI, and hashes
```

The BIN file's byte zero belongs at CPU `$F000`, physical flash `$1F000`.
Do not program it at device address zero.

Use `tools/convert_guest_bin_to_s19.ps1` to turn an aligned binary into a
payload-only install stream. Use `tools/compose_str8n_install_s19.ps1` to
validate an existing payload stream. Full rules and examples are in the
[Technical Guide](docs/TECHNICAL_GUIDE.md#s19-install-file-contract).

## Deliberate limits

V2 does not update its own top sector, export S-records, manage backup
allocation, or count flash wear. Its recovery `L` command has no load-only
form and no address fallback: a valid S9 in `$2000-$7AFF` is required.
Refreshing STR8-N or its full directory requires an external programmer.
