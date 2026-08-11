# STR8-N v1.1

STR8-N is the reset supervisor and recovery layer for a W65C02SXB/EDU with
four 32K flash banks. The complete resident system fits in the protected top
4K of Bank 3:

```text
CPU $F000-$FFFF  = 4096 bytes total
resident         = 3412 bytes
unused reserve   =    8 bytes
stored worker    =  596 bytes
directory/config =   74 bytes
vectors          =    6 bytes
```

It owns physical RESET, selects banks, installs dense S19 images, loads and
starts recovery programs in RAM, and protects Bank 3 sector F from ordinary
flash operations. HIMON and ASM are separate Bank-3 payloads below `$F000`.

> [!WARNING]
> Flash operations can erase software or leave a bank incomplete. Keep the
> verified 4096-byte programmer BIN. Check the bank and range before answering
> `WRITE? Y`. Do not press NMI or RESET, remove power, or remove the flash
> device during erase or programming.

## Start here

- [Operator's Guide](docs/OPERATORS_GUIDE.md) - board operation, prompts,
  installs, recovery, and bank maintenance.
- [Worked Examples](docs/EXAMPLES.md) - complete terminal sessions for HIMON,
  ASM, full-bank, RAM, copy, and interrupted-install recovery.
- [Technical Guide](docs/TECHNICAL_GUIDE.md) - exact S19, memory, transaction,
  ABI, directory, and handoff contracts.
- [Maps and Diagrams](docs/MAPS.md) - flash, RAM, boot, install, directory, and
  artifact flows.
- [Bank 0-2 S19 Quick Reference](docs/BANK_0_2_GUEST_S19.md) - guest image
  layout, conversion, validation, and all top-aligned sizes.
- [R-YORS Integration Boundary](docs/R_YORS_INTEGRATION.md) - how the adjacent
  R-YORS checkout consumes and combines STR8-N artifacts.
- [Implementation Record](docs/EMBEDDED_WORKER_REFACTOR_PLAN.md) - settled
  refactor decisions, hardware evidence, and remaining qualification work.

## What appears at RESET

Hardware pull-ups force Bank 3 on power-on and physical RESET. STR8-N first
provides a visible six-second board-alive interval. Keys are ignored during
this interval so USB/terminal startup cannot accidentally select a bank:

```text
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.1
0-2 H S: ......
```

The six dots are the live selector interval. Press `0`, `1`, `2`, `H`, or
`S`; otherwise compatible HIMON cold-starts. STR8-N flushes queued input before
printing its identity, so a key sent during `WAIT...` is deliberately lost.

## Commands

```text
Command  Purpose                                  Destination / entry
I        install a dense payload-only S19         selected flash sectors
L        load a recovery S19 and start it         RAM $2000-$7AFF; S9 entry
H        warm-enter compatible HIMON              Bank 3 $C000
J0-J2    start an enrolled guest                   selected bank RESET vector
J3       hand off to Bank 3                        Bank 3 RESET vector
```

`I` is flash-only. `L` is RAM-only and always executes a valid S9; it has no
load-only form. HIMON `L` and `L G` remain the richer monitor alternatives.

S19 transfer is terminal-program agnostic. Use zero character delay and zero
line delay. After `WRITE? Y`, STR8-N completes worker and directory preparation
before printing `S19`, then accepts the file continuously at normal terminal
speed.

## Flash ranges

Banks 0-2 accept any contiguous 4K-aligned span inside `$8000-$FFFF`, from 4K
through 32K. Bank 3 accepts any such span inside `$8000-$EFFF`, from 4K through
28K; Bank 3 sector F is STR8-N and is protected.

```text
Size   Banks 0-2 ending at F       Bank 3 ending at E
 4K    F      $F000-$FFFF          E      $E000-$EFFF
 8K    E-F    $E000-$FFFF          D-E    $D000-$EFFF
12K    D-F    $D000-$FFFF          C-E    $C000-$EFFF
16K    C-F    $C000-$FFFF          B-E    $B000-$EFFF
20K    B-F    $B000-$FFFF          A-E    $A000-$EFFF
24K    A-F    $A000-$FFFF          9-E    $9000-$EFFF
28K    9-F    $9000-$FFFF          8-E    $8000-$EFFF
32K    8-F    $8000-$FFFF          --     protected
```

These are common top-aligned examples, not the only accepted spans. For
example, `8-B`, `A-D`, and `C-E` are also legal when they fit the selected
bank's writable window.

## Recovery and maintenance images

`make bank-maint` builds a self-contained RAM maintenance program:

```text
BUILD/v1.1/s19/str8n-v1.1-bank-maint-2000.s19
```

Load it with STR8-N `L`. It maps banks, copies and verifies a full 32K bank,
enrolls an empty destination directory row, erases selected sectors with Bank
3 F protection, and installs the narrow AP carrier. It uses its own private
RAM worker and does not depend on HIMON or retired `$F003`/`$F006` gates.

`make ryors-full-bank` combines the adjacent R-YORS 28K ASM+HIMON payload with
the current STR8-N top sector:

```text
BUILD/v1.1/s19/ryors-v1.1-asm-himon-str8n-bank0-2-8-f.s19
$8000-$BFFF  ASM-F2
$C000-$EFFF  HIMON
$F000-$FFFF  STR8-N 1.1 clone
S9 / RESET   $F000
```

That `8-F` file is for Bank 0, 1, or 2. Physical RESET still selects the real
Bank-3 STR8-N.

## Build and verification

The Makefile expects WDC `wdc02as` and `wdcln` on `PATH`.

```text
make                         build and verify the release artifacts
make resident                build the resident supervisor
make workers                 build the unified RAM worker
make bank-maint              build and validate the RAM maintenance S19
make ryors-full-bank         compose the R-YORS plus STR8-N 32K image
make layout-check            enforce fixed addresses and 8-byte reserve
make range-matrix-check      test documented flash install ranges
make ram-load-contract-check test STR8-N L address and S9 boundaries
make programmer-bin          create the exact 4096-byte top-sector BIN
make clean                   remove generated BUILD artifacts
```

Primary outputs:

```text
BUILD/v1.1/bin/str8n-bank3-f000-ffff.bin
BUILD/v1.1/s19/str8n-f000.s19
BUILD/v1.1/s19/str8n-worker-0200.s19
BUILD/v1.1/s19/str8n-v1.1-bank-maint-2000.s19
BUILD/v1.1/s19/ryors-v1.1-asm-himon-str8n-bank0-2-8-f.s19
BUILD/str8n-manifest.json
```

All `.bin`, `.s19`, and generated S19 test outputs are kept below
`BUILD/v1.1/`. The manifest stays at `BUILD/str8n-manifest.json` so the R-YORS
lock check can find it; its artifact paths point into `BUILD/v1.1/`. Object,
listing, and symbol intermediates remain in the unversioned `BUILD/obj`,
`BUILD/lst`, and `BUILD/sym` folders.

The programmer BIN's file offset `$000` belongs at CPU `$F000`, physical flash
`$1F000`. Do not program that byte at flash device address zero.

Use `tools/convert_guest_bin_to_s19.ps1` to convert an aligned binary and
`tools/compose_str8n_install_s19.ps1` to validate and normalize an existing
payload S19. Generated install files contain payload only; never prepend the
`$0200` worker component.

## Deliberate limits

STR8-N v1.1 does not rewrite its protected top sector, export S-records,
allocate backups, count flash wear, or provide a general flash API. Worker
mode 6 is removed. `$F003` and `$F006` are retired fail-closed tombstones.

The `L` command accepts only `$2000-$7AFF` and always starts the S9 address.
Refreshing STR8-N itself, clearing a nonempty directory row, or replacing the
full directory/configuration pocket requires an external programmer.
