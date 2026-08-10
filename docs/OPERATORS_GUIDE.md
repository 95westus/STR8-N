# STR8-N V2 Operator's Guide

This is the board-facing guide. You do not need to know assembly language to
use it.

## Which loader should I use?

No: STR8-N `I` cannot load programs into RAM. It installs a dense S19 image
into flash.

```text
Need                         Use             Destination
install a lasting image      STR8-N I        selected flash bank
load a temporary program     HIMON L         RAM $0000-$7EFF
load and start a program     HIMON L G       RAM, then the S9 start address
start a flash-bank guest     STR8-N J0-J3    selected bank's RESET vector
```

This is deliberate. Reusing HIMON's loader is the simplest, most
code-efficient choice and leaves more room in STR8-N's protected 4K sector.
If HIMON is not installed, a user program needs its own RAM loader.

For normal R-YORS programs loaded by HIMON, `$2000-$4FFF` is the simplest
general-purpose area. More RAM may be available, but check the R-YORS memory
map before using ASM work areas or monitor workspace. `L` can write lower RAM
too, but loading over active workspace can damage the current monitor session.

## Before writing flash

1. Keep the 4096-byte STR8-N top-sector BIN and an external programmer or
   another proven recovery method.
2. Know which bank and which 4K sectors the S19 file was made for.
3. Keep power and the FTDI serial connection steady.
4. Do not press NMI or RESET during an erase or write.
5. Remember that `WRITE? Y` allows the transaction to begin. It is not a dry
   S19 validation pass.

> [!WARNING]
> After the first valid S1 data record, STR8-N journals START. As each complete
> 4K sector arrives, it may be erased, programmed, and verified immediately.
> Only the final selected sector waits for `COMMIT? Y`. A later bad record,
> disconnect, RESET, NMI, power loss, or declined commit leaves the bank
> incomplete and requires the full recovery range.

## What happens at RESET

Physical RESET always returns the hardware to Bank 3 and starts STR8-N. The
short selector displays:

```text
0-2 H S:
```

- `0`, `1`, or `2` starts a completed guest in that bank.
- `H` warm-starts compatible HIMON at `$C000` in Bank 3 and preserves RAM.
- `S` stays in STR8-N and displays `STR8-N>`.
- If no key is pressed, STR8-N cold-starts compatible HIMON when present.

At `STR8-N>`, the visible commands are:

```text
I       install an S19 into flash
H       warm-enter compatible HIMON in Bank 3
J0-J3   select a bank and jump through its RESET vector
```

An improper command is discarded. Enter a valid command; the command text is
not printed again merely because a bad key was pressed.

## Install an image with I

The same procedure applies to every bank.

1. At `STR8-N>`, type `I`.
2. At `B0-3:`, enter the bank number.
3. At `RANGE:`, enter one sector digit or the first and last 4K sector digits.
   Examples: `8-F` means `$8000-$FFFF`; `C-E` means `$C000-$EFFF`; `A` means
   `$A000-$AFFF`.
4. For a new bank-directory row, enter the requested two-digit hexadecimal
   `TYPE:` and exactly five characters at `DESC:`. A description may use
   `A-Z`, `0-9`, hyphen, underscore, or period. These identity fields cannot
   be changed without externally refreshing the protected sector.
5. Read the `I Bn x-y` summary. At `WRITE? Y:`, type `Y` only if the bank and
   range are correct.
6. When `S19` appears, send the payload-only S19 through the FTDI console.
   There is no separate worker file to send.
7. A dot means one 4K sector has already been programmed and read back. For a
   multi-sector file, dots can appear while the S19 is still being received.
8. After STR8-N accepts S9, it prints `COMMIT? Y:`. Type `Y` to program the
   held final sector and finish the directory transaction.
9. `OK` means COMPLETE was journaled and the transaction is usable. `FAIL`
   means do not try to boot that bank; use the recovery procedure below.

The S19 must contain the exact range selected at the prompts, including every
`$FF` padding byte. Do not send an old stream with `$0200` worker records.

## Banks 0-2

Banks 0-2 allow any contiguous, 4K-aligned size from 4K through 32K.

Yes, every top-aligned size in this table can be installed:

```text
SIZE   RANGE  ADDRESS RANGE
 4K    F      $F000-$FFFF
 8K    E-F    $E000-$FFFF
12K    D-F    $D000-$FFFF
16K    C-F    $C000-$FFFF
20K    B-F    $B000-$FFFF
24K    A-F    $A000-$FFFF
28K    9-F    $9000-$FFFF
32K    8-F    $8000-$FFFF
```

These are not the only legal ranges. For example, `8-B`, `A-D`, and `C-E`
are also accepted. The rule is simply: one contiguous range, starting and
ending on 4K sector boundaries, wholly inside sectors 8 through F.

```text
RANGE  ADDRESS RANGE   SIZE
8-F    $8000-$FFFF     32K
8-B    $8000-$BFFF     16K
C-E    $C000-$EFFF     12K
E      $E000-$EFFF      4K
```

A normal bootable full-bank image owns:

```text
$8000-$FFF9  guest code, data, and padding
$FFFA-$FFFB  NMI vector, low byte first
$FFFC-$FFFD  RESET vector, low byte first
$FFFE-$FFFF  IRQ/BRK vector, low byte first
```

For a full 32K install, S9 must equal the non-erased RESET vector. `J0`, `J1`,
and `J2` always read the selected bank's RESET vector; they do not jump to S9
or to a directory entry.

A partial image may use S9 `$FFFF` or an address inside its selected range,
but that value is only install metadata. A partial install does not create or
repair the RESET vector unless sector F is included. A first partial install
into an erased bank can complete successfully yet still be unable to boot.

Even when sector F is included, check the RESET vector at `$FFFC-$FFFD`. It
must point to real code in that bank. `J0`-`J2` ignore S9 and follow RESET.

## Bank 3 and the R-YORS v1.1 files

Bank 3 permits 4K through 28K in sectors 8 through E. Sector F contains
STR8-N and is never writable through `I`.

```text
SIZE   TOP-ALIGNED RANGE  ADDRESS RANGE
 4K    E                  $E000-$EFFF
 8K    D-E                $D000-$EFFF
12K    C-E                $C000-$EFFF
16K    B-E                $B000-$EFFF
20K    A-E                $A000-$EFFF
24K    9-E                $9000-$EFFF
28K    8-E                $8000-$EFFF
```

```text
FILE                                      RANGE  CONTENT           S9
ryors-v1.1-asm-himon-bank3-8-e.s19        8-E    ASM + HIMON       $C000
ryors-v1.1-himon-bank3-c-e.s19            C-E    HIMON             $C000
ryors-v1.1-asm-bank3-8-b.s19              8-B    ASM               $FFFF
```

The combined `8-E` file is the simplest first install. To install the pieces
separately, install HIMON `C-E` first, then ASM `8-B`. The ASM-only S9 `$FFFF`
means "keep Bank 3's existing entry" and is not accepted as the first image in
an empty Bank-3 directory.

Bank 3 records one immutable S9 entry as install identity, but the operator
commands remain explicit: `H` checks the HIMON marker and enters `$C000`, while
`J3` follows Bank 3's hardware RESET vector and normally re-enters STR8-N.

## Load a temporary RAM program with HIMON

From the HIMON `>` prompt:

1. Type `L` to load without starting, or `L G` to load and start.
2. When HIMON reports that it is ready, send the RAM-addressed S19.
3. HIMON uses STR8-N's `$F009` service to validate each record, then copies
   valid S1 data into RAM. It rejects I/O and flash destinations.
4. After S9, HIMON reports the byte count and start address. `L G` starts the
   S9 address when usable; otherwise it may use the first loaded address.

Unlike STR8-N `I`, a HIMON `L` file need not describe a 4K-aligned or dense
flash range. It should still use valid S0/S1/S9 records and must avoid RAM
needed by the running monitor and loader.

## If an install is interrupted

The directory records START before flash changes and COMPLETE only after the
final sector and verification succeed. A started but incomplete bank fails
closed.

- For Bank 0, 1, or 2, retry with a full `8-F` 32K install.
- For Bank 3, retry the writable payload with a full `8-E` 28K install.
- A smaller retry is refused because it could leave unknown old bytes behind.
- An interrupted first install may ask for the same `TYPE` and `DESC` again.
  They must exactly match any bytes already programmed.

Each bank has 16 START/COMPLETE transaction pairs. A failed transaction and
its full-range recovery finish the same open pair. After 16 completed pairs,
or if the directory is invalid, refresh STR8-N with an external programmer.

## External-programmer recovery

The programmer BIN is exactly 4096 bytes:

```text
file offset $000-$FFF  -> CPU $F000-$FFFF
                       -> physical flash $1F000-$1FFFF
```

Do not program byte zero of this file at physical device address zero. A new
top-sector BIN contains an erased directory and configuration pocket. Writing
it therefore clears all STR8-N install journals and Bank-3 identity; existing
Bank 0-2 contents are not erased, but `J0`-`J2` remain directory-gated until
those banks are installed again through `I`.

## A bank handoff is not a power-on reset

`J0`-`J3` disable IRQ, clear decimal mode, set X and the stack pointer to
`$FF`, select the bank, validate its RESET vector, and jump through that
vector. RAM and peripheral registers are otherwise preserved. A guest must
initialize the hardware state it needs and must not overwrite the VIA PCR
bank-selection bits by accident.

Physical RESET is the universal return to Bank 3.

For the picture version of these rules, see [Maps and Diagrams](MAPS.md).
