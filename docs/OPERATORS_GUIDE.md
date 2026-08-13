# STR8-N v1.2 Operator's Guide

This is the board-facing guide. You do not need to know assembly language to
use it.

For complete sample terminal sessions, see [Worked Examples](EXAMPLES.md).

## Which loader should I use?

No: STR8-N `I` cannot load programs into RAM. It installs a dense S19 image
into flash. STR8-N now has a separate recovery command, `L`, for RAM.

```text
Need                         Use             Destination
install a lasting image      STR8-N I        selected flash bank
recovery load and execute    STR8-N L        RAM $2000-$7AFF, then S9
load without starting        HIMON L         RAM under HIMON policy
load and start under HIMON   HIMON L G       RAM, then the S9 start address
start a flash-bank guest     STR8-N J0-J3    selected bank's RESET vector
```

STR8-N `L` is deliberately smaller than HIMON's loader. It always starts the
program, has one fixed safe range, and provides no load-only or fallback-entry
mode. That makes it useful when the normal Bank-3 payload needs repair.

For normal R-YORS programs loaded by HIMON, `$2000-$4FFF` is the simplest
general-purpose area. More RAM may be available, but check the R-YORS memory
map before using ASM work areas or monitor workspace. HIMON `L` can write
lower RAM too, but loading over active workspace can damage the current
monitor session.

## Before writing flash

1. Keep the 4096-byte STR8-N top-sector BIN and an external programmer or
   another proven recovery method.
2. Know which bank and which 4K sectors the S19 file was made for.
3. Keep power and the FTDI serial connection steady.
4. Do not press NMI or RESET during an erase or write.
5. Remember that `WRITE? Y` allows the transaction to begin. It is not a dry
   S19 validation pass.

> [!WARNING]
> After `WRITE? Y`, STR8-N journals START before printing `S19`. As each
> complete 4K sector arrives, it may be erased, programmed, and verified.
> Only the final selected sector waits for `COMMIT? Y`. A later bad record,
> disconnect, RESET, NMI, power loss, or declined commit leaves the bank
> incomplete and requires the full recovery range.

## What happens at RESET

Physical RESET always returns the hardware to Bank 3 and starts STR8-N. Six
one-second pulses give the FTDI connection and terminal time to attach. Keys
are ignored during these pulses:

```text
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
```

STR8-N then discards any queued input, identifies itself, and opens six
one-second live selector dots:

```text
STR8-N 1.2
0-2 H S: ......
```

- `0`, `1`, or `2` starts a completed guest in that bank.
- `H` warm-starts compatible HIMON at `$C000` in Bank 3 and preserves RAM.
- `S` stays in STR8-N and displays `STR8-N>`.
- If no key is pressed, STR8-N cold-starts compatible HIMON when present.

A key may take up to one second to be noticed. `J3` and physical RESET use the
same sequence, although `J3` normally starts with an already attached terminal.

At `STR8-N>`, the visible commands are:

```text
I       install an S19 into flash
L       load an S19 into $2000-$7AFF and execute its S9 address
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
   be changed without refreshing the protected sector.
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

### Full-speed terminal transfer

Use ordinary text-file sending with zero character delay and zero line delay.
No STR8-N-specific macro, terminal brand, or software flow-control setting is
required.

After `WRITE? Y`, STR8-N copies its RAM worker and opens the persistent
transaction before it prints `S19`. On a new bank row, START, metadata, and the
identity seal are therefore complete before the terminal is invited to send.
Once `S19` appears, send the complete file continuously at full speed.

Because `Y` now opens the transaction before S19 validation, cancelling or
losing power after `Y` leaves an incomplete directory row. Use the documented
full-range recovery procedure on the next boot.

The S19 must contain the exact range selected at the prompts, including every
`$FF` padding byte. Do not send an old stream with `$0200` worker records.

## Load and execute a RAM recovery program with L

STR8-N `L` changes RAM only. It does not erase or program flash and does not
ask for confirmation.

1. At `STR8-N>`, type `L`.
2. When `S19` appears, send an S19 containing S0/S1/S9 records.
3. Every nonempty S1 record must fit completely within `$2000-$7AFF`.
4. At least one S1 record is required.
5. S9 must name an execution address within `$2000-$7AFF`.
6. As soon as the valid S9 is received, STR8-N disables IRQ, clears decimal
   mode, sets X and the stack pointer to `$FF`, and jumps to S9. A/Y and other
   RAM or peripheral state are not initialized for the program.

There is no `L G`, separate `G`, confirmation, or load-only form in STR8-N.
The recovery program must initialize the hardware and RAM state it needs.
It should not execute `RTS` to return because STR8-N deliberately replaces the
stack pointer before entry. Physical RESET returns to Bank 3 and STR8-N.

The RAM stream does not need to be dense, ascending, or 4K-aligned. Each S1
record is checked independently; overlapping records are applied in received
order. S2-S8, bad checksums, empty S1 records, an out-of-range record span, an
out-of-range S9, or a stream with no S1 fail. On failure STR8-N does not
execute, but bytes copied by earlier valid records remain in RAM.

Ctrl-C (`$03`) while `L` is receiving S19 cancels the load. The on-board
STR8-N 1.2 image reports `BAD`, returns to `STR8-N>`, and does not execute the
S9 entry. Complete S1 records accepted before Ctrl-C remain in RAM; cancellation
is not rollback.

`$7B00` is the first protected parser buffer byte. The highest accepted byte
is therefore `$7AFF`, even when one S1 record crosses a page boundary. Stop
sending after S9; queued serial bytes are inherited by the recovery program.

### Load the STR8-N 1.2 bank-maintenance program

Use `BUILD/v1.2/s19/str8n-v1.2-bank-maint-2000.s19`. It is a temporary RAM tool;
loading it does not change flash. It does not require HIMON and uses the
board's FT245R console directly.

1. At `STR8-N>`, type `L`.
2. When `S19` appears, send
   `BUILD/v1.2/s19/str8n-v1.2-bank-maint-2000.s19` at normal full speed.
3. STR8-N validates the file and starts it automatically at `$2000`.

The menu commands are:

```text
M  map every bank and show the Bank-3 directory; does not write flash
C  copy a complete 32K bank and enroll its empty destination directory row
D  adopt an existing payload into an empty directory row; payload is read-only
E  erase selected 4K sectors; Bank 3 sector F is always protected
P  install the narrow, validated AP carrier at Bank 0 $BF00
Q  return to STR8-N through $F000
```

At the Bank Maintenance main menu, an empty line (Enter by itself) is the same
as `Q`: it leaves Bank Maintenance and returns to STR8-N. Ctrl-C and empty
lines at operation subprompts cancel that operation and return to the Bank
Maintenance menu.

The shortest safe rule is: use `M` freely; treat `C`, `D`, `E`, and `P` as flash
operations.

### Upgrade Bank 3 sector F to STR8-N v1.2

The v1.2 release includes the RAM-resident updater
`BUILD/v1.2/s19/str8n-v1.2-top-update-2000.s19`. It is loaded by the existing
STR8-N `L` command and runs entirely from RAM while Bank-3 sector F is erased.
An external programmer remains the preferred first-board and recovery method.
This maintained Top Update artifact replaces the older ASM-generated
TopWriter workflow; those TopWriters are historical, not the current update
path.

The complete onboard sequence through backup verification, Bank-3 sector-F
program/verify, RESET, and live `S` selection was accepted on hardware on
2026-08-11. The recovery commands remain mandatory safeguards; external
restore is still a separate acceptance gate.

Before starting:

1. Keep both the v1.1 rollback BIN and
   `BUILD/v1.2/bin/str8n-v1.2-bank3-f000-ffff.bin` off-board.
2. Confirm Bank 1 CPU `$F000-$FFFF` may be erased. The updater uses it as the
   raw backup sector (`STR8_TOP_SAFE`, physical `$0F000-$0FFFF`).
3. Install `ryors-v1.2-asm-himon-bank3-8-e.s19` into Bank 3 sectors `8-E`
   using the existing STR8-N `I` command.
4. Return to STR8-N; do not use old ASM to write `$7Dxx` during the migration
   window.

Then update the protected top sector:

1. Type `L` and send `str8n-v1.2-top-update-2000.s19` at normal full speed.
2. Check that the tool prints `BACKUP B1:F; TARGET B3:F`.
3. Type the exact first confirmation `BACKUP B1F` only if Bank 1 sector F is
   sacrificial.
4. Require `BACKUP VERIFIED` before continuing.
5. Type the exact final confirmation `STR8-N 1.2`.
6. Do not press NMI or RESET, remove power, or disturb the flash/FTDI hardware
   until the tool reports verification and enters the new RESET vector.

At either typed confirmation, Enter by itself cancels before active erase,
prints `ABORT - NO ACTIVE TOP UPDATE`, and returns to STR8-N. Any other
nonmatching confirmation has the same safe result.

If active programming fails, do not reset. At the RAM recovery prompt use `R`
to retry the embedded v1.2 image or `O` to restore the verified Bank-1 backup.
If the RAM tool cannot recover, externally copy physical `$0F000-$0FFFF` back
to `$1F000-$1FFFF`, or program one of the retained 4096-byte BINs at physical
`$1F000`.

After v1.2 starts, verify `S`, `H`, selector timeout, the `$7DFD-$7DFF` Bank
Jump Record, and the ASM `$7CFF/$7D00` boundary before updating Banks 0-2.

`C`, `D`, `E`, `P`, and `R` write flash and require an exact typed confirmation.
Do not press NMI, reset, remove power, or remove the flash during a write or
erase. `C` prints `!STR8` before confirmation when the source contains the
STR8-N 1.2 `SR 02 03` service signature. `Q` starts the normal STR8-N startup
display again, including its six `WAIT...` pulses.

`C` accepts source Bank 0-3 and destination Bank 0-2. The destination's
Bank-3 directory row must be completely erased; otherwise it prints
`DIR NOT EMPTY` and does not copy. After all eight sectors are copied and
verified, enter a two-digit hexadecimal TYPE and exactly five DESCRIPTION
characters, then answer `ENROLL? Y`. Allowed description characters are
`A-Z`, `0-9`, hyphen, underscore, and period.

Enrollment writes the journal START marker first, the immutable identity
second, and COMPLETE last. `OK` therefore means both the 32K copy and its
directory enrollment were verified, and `J0`-`J2` may use the destination.
If enrollment is cancelled, interrupted, or fails, the copied bytes can
remain in the destination but STR8-N keeps that bank non-bootable. An existing
or incomplete directory row must be handled through `I`, not overwritten by
`C`.

`E` erases payload sectors but cannot restore the corresponding Bank-3
directory row: flash programming only clears bits, while D0-D2 require all
`$FF` before reuse. After `E ALL`, use `R`, select the erased Bank 0-2, and
type the exact `CLEAR Dn` confirmation. `R` first verifies all eight payload
sectors are erased. It stages Bank-3 sector F and first writes a verified raw
backup into the selected bank's sector F. It then changes only the directory
row to `$FF`, rewrites and verifies the complete protected sector, and erases
and verifies the temporary backup. Require `BACKUP VERIFIED` before the B3F
rewrite completes. Do not reset, use NMI, remove power, or disconnect the flash
device during `B3F REWRITE`.

`D` adopts an existing payload into a completely erased directory row without
erasing or rewriting any payload sector. It is the metadata-only recovery path
after a directory refresh. Select Bank 0-3, enter TYPE and exactly five DESC
characters, and type the exact confirmation `ADOPT Bn`. The tool rejects a
nonempty row and a missing, low, or erased RESET vector. Banks 0-2 receive the
normal `$FFFF` directory entry because `J0`-`J2` follow their RESET vectors.

Bank 3 additionally requires the current `SR 02 03` STR8-N signature and an
explicit entry from `$8000-$FFFE`; the first two bytes at that entry may not
both be erased. For the current R-YORS Bank-3 payload, use entry `$C000`, TYPE
`FF`, and DESC `RYORS`. Adoption writes journal START first, immutable identity
second, and COMPLETE last. A successful fresh D3 therefore prints as:

```text
D3 FF RYORS C000 FCFFFFFF
```

`D` never edits or replaces an existing identity. Refresh the protected
directory sector again if the desired row is not completely erased.
The erased-row, RESET/ENTRY, DESC-length, cancellation, D1/D3 commit, and
post-adoption `C` regression paths were accepted on hardware on 2026-08-11.

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

### Full R-YORS 8-F image for Banks 0-2

`make ryors-full-bank` composes the current R-YORS ASM+HIMON 28K payload with
the current STR8-N 1.2 top sector:

```text
BUILD/v1.2/s19/ryors-v1.2-asm-himon-str8n-bank0-2-8-f.s19
$8000-$BFFF  ASM-F2
$C000-$EFFF  HIMON
$F000-$FFFF  STR8-N 1.2 clone
S9/RESET     $F000
```

Install it with `I`, target Bank 0, 1, or 2, and range `8-F`. It is not a
Bank-3 payload because `I` never writes Bank 3 sector F. `J0`-`J2` enter the
copied STR8-N first; its normal timeout can then enter the same bank's HIMON.
Physical RESET always returns to the real Bank-3 STR8-N.

## Bank 3 and the R-YORS v1.2 files

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
ryors-v1.2-asm-himon-bank3-8-e.s19        8-E    ASM + HIMON       $C000
ryors-v1.2-himon-bank3-c-e.s19            C-E    HIMON             $C000
ryors-v1.2-asm-bank3-8-b.s19              8-B    ASM               $FFFF
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

1. Type `L`.
2. Send the RAM-addressed S19.
3. HIMON validates S0/S1/S9 with its private resident parser, then copies
   valid S1 data into RAM. It does not call STR8-N's `$F009` service and it
   rejects any nonempty span touching `$7A00-$FFFF`.
4. After S9, HIMON reports the byte count and start address without executing
   it. Use `G start` separately when execution is wanted; `L G` and `L F` are
   rejected by the bare-`L` grammar.

Like STR8-N recovery `L`, a HIMON `L` file need not describe a 4K-aligned or
dense flash range. HIMON's command is RAM-load-only and enforces its own
destination policy so the running monitor and its workspace remain protected.

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
or if the directory is invalid, use the guarded onboard directory refresh
below or the external-programmer fallback.

## Refresh the directory onboard

`BUILD/v1.2/s19/str8n-v1.2-directory-refresh-2000.s19` is a dedicated
RAM-resident sector-F rewrite. It embeds the exact current 4096-byte top BIN,
whose directory and configuration pocket is erased. Unlike the normal top
updater, it intentionally does not restore the live `$FFB0-$FFF9` bytes into
the candidate before programming.

The refresh otherwise uses the hardware-proven top-updater safety path. It
copies the complete live Bank-3 sector F into Bank 1 sector F, verifies that
backup, runs from RAM while Bank-3 sector F is unavailable, verifies the new
sector, and offers retry or restoration after a write failure.

Before starting, Bank 1 sector F must be sacrificial. Its current contents are
replaced by a fresh exact backup of the live Bank-3 sector F.

1. At STR8-N, type `L`, then `S19`, and send
   `BUILD/v1.2/s19/str8n-v1.2-directory-refresh-2000.s19`.
2. Require the title `STR8-N 1.2 DIRECTORY REFRESH` and
   `BACKUP B1:F; TARGET B3:F`.
3. Type `BACKUP B1F` only if Bank 1 sector F is sacrificial.
4. Require `BACKUP VERIFIED` and record the safe/target physical ranges and
   old-sector checksum.
5. Type the exact final confirmation `ERASE DIRECTORY`.
6. Do not press NMI or RESET, remove power, or disturb the flash/FTDI hardware
   until `DIRECTORY EMPTY; STR8-N VERIFIED; RESET` appears.

At either Directory Refresh confirmation, Enter by itself cancels before
active erase, prints `ABORT - NO ACTIVE DIRECTORY REFRESH`, and returns to
STR8-N. Any other nonmatching confirmation has the same safe result.

If active programming fails, do not reset. Type `R` to retry the erased-pocket
candidate or `O` to restore the verified old sector from Bank 1. After success,
physical RESET returns to STR8-N with D0-D3 and all install journals erased.
Bank payload sectors are unchanged, but `J0`-`J3` remain directory-gated until
the desired rows are enrolled again. Keep Bank 1 sector F intact until the
refresh and subsequent enrollment proof are accepted.

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

For a directory refresh with a T48 or equivalent programmer, preserve the
rest of the device with a checked full-image merge:

1. Power the board off, remove the SST39SF010A, and read the complete 128 KiB
   device twice. Save both reads independently and require identical SHA-256
   hashes before continuing.
2. Keep both raw readbacks. Do not edit either archive.
3. Build a merged programmer image from the matched readbacks:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_directory_refresh_image.ps1 `
  -ReadbackPath "PATH/board-before-directory-refresh-read-1.bin" `
  -ConfirmReadbackPath "PATH/board-before-directory-refresh-read-2.bin" `
  -OutPath "BUILD/v1.2/bin/board-directory-refreshed-20000.bin"
```

4. Require the tool to report a 131072-byte output, the current top-BIN hash,
   `CHANGED PHYSICAL = $1F000-$1FFFF only`, and `DIRECTORY REFRESH IMAGE = PASS`.
5. Load the merged 128 KiB image at programmer address zero, program the whole
   SST39SF010A, and verify all 131072 bytes against that same merged file.
6. Save the programmer's post-write readback and require its SHA-256 to equal
   the merged programmer image SHA-256.
7. Reinstall the flash with board power off, then use physical RESET. STR8-N
   remains at Bank 3 `$F000`, but D0-D3 and the Bank-3 install identity are
   erased until the desired banks are enrolled again.

The merge tool requires two distinct readback paths and refuses them unless
both files are exactly 128 KiB with identical SHA-256 hashes. It also refuses
a top BIN that is not exactly 4096 bytes, a mismatched STR8-N signature/RESET
vector, or a top BIN whose directory/configuration pocket is not all `$FF`.
It never modifies either archived readback and changes only output offsets
`$1F000-$1FFFF`.

## A bank handoff is not a power-on reset

`J0`-`J3` disable IRQ, clear decimal mode, set X and the stack pointer to
`$FF`, select the bank, validate its RESET vector, and jump through that
vector. RAM and peripheral registers are otherwise preserved. A guest must
initialize the hardware state it needs and must not overwrite the VIA PCR
bank-selection bits by accident.

Physical RESET is the universal return to Bank 3.

For the picture version of these rules, see [Maps and Diagrams](MAPS.md).
For copyable sessions, see [Worked Examples](EXAMPLES.md).
