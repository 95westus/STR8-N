# STR8-N v1.21 Worked Examples

These examples show what to type and which S19 file to send. Text after `<-`
is explanation, not terminal input. Use normal full-speed text-file transfer
with zero character and line delay.

## Stay in STR8-N after RESET

Wait until the identity and live dots appear, then press `S`:

```text
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.21
0-2 H S: ..S
I L H J
STR8-N>
```

A key typed during `WAIT...` is ignored and flushed. The selector accepts only
`0`, `1`, `2`, `H`, or `S`.

## First Bank-3 install: HIMON only

Use the R-YORS 12K HIMON file:

```text
C:/SRC/R-YORS/SRC/BUILD/s19/ryors-v1.2-himon-bank3-c-e.s19
```

Example session:

```text
STR8-N>I
B0-3: 3
RANGE: C-E
TYPE: 5A
DESC: RYORS
I B3 C-E WRITE? Y: Y
S19
..COMMIT? Y: Y.
OK
STR8-N>H
BOOT WARM

HIMON V 00.0810(1814)
>
```

`TYPE` is two hexadecimal digits. `DESC` is exactly five characters. Use the
project's chosen values consistently; the example values are illustrative.

## Add ASM to an enrolled Bank 3

After HIMON has established Bank 3's identity and entry, install the 16K
ASM-only file:

```text
C:/SRC/R-YORS/SRC/BUILD/s19/ryors-v1.2-asm-bank3-8-b.s19
```

```text
STR8-N>I
B0-3: 3
RANGE: 8-B
I B3 8-B WRITE? Y: Y
S19
...COMMIT? Y: Y.
OK
STR8-N>H
BOOT WARM

HIMON V 00.0810(1814)
>ASM
ASM-F2 00.0810(1814)
ASM>
```

The ASM-only file uses S9 `$FFFF`, meaning keep the existing Bank-3 directory
entry. It is not a valid first Bank-3 enrollment.

## Install ASM and HIMON together in Bank 3

The simplest complete writable Bank-3 payload is:

```text
C:/SRC/R-YORS/SRC/BUILD/s19/ryors-v1.2-asm-himon-bank3-8-e.s19
```

Select Bank 3 and range `8-E`. On a new directory row, supply TYPE and DESC.
The file covers all 28 writable KiB while leaving STR8-N at `F` untouched.

```text
STR8-N>I
B0-3: 3
RANGE: 8-E
TYPE: 5A
DESC: RYORS
I B3 8-E WRITE? Y: Y
S19
......COMMIT? Y: Y.
OK
```

There are six receive-time dots because six non-final sectors can be committed
while the stream arrives. The final dot follows `COMMIT? Y`.

## Build and install the full R-YORS `8-F` image

With sibling `R-YORS` and `STR8-N` folders:

```powershell
make ryors-full-bank
```

This creates:

```text
BUILD/v1.21/s19/ryors-v1.2-asm-himon-str8n-bank0-2-8-f.s19
```

Install it in Bank 0, 1, or 2:

```text
STR8-N>I
B0-3: 2
RANGE: 8-F
TYPE: 5A
DESC: RYORS
I B2 8-F WRITE? Y: Y
S19
.......COMMIT? Y: Y.
OK
STR8-N>J2
J B2
```

The copied top sector starts STR8-N inside Bank 2. Its timeout then enters the
same bank's HIMON. Physical RESET always returns to Bank 3.

## Load and automatically start a RAM program

The S19 must use only S0, S1, and S9. Every S1 record and S9 must be inside
`$2000-$7AFF`.

```text
STR8-N>L
S19
```

Send the file immediately. A valid S9 starts the program automatically; there
is no `G`, no confirmation, and no return address. The program must initialize
the hardware and RAM state it needs.

## Start Bank Maintenance

Build it once if necessary:

```powershell
make bank-maint
```

Then:

```text
STR8-N>L
S19
```

Send:

```text
BUILD/v1.21/s19/str8n-v1.21-bank-maint-2000.s19
```

It starts automatically:

```text
STR8-N 1.21 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q=QUIT>
```

## Copy a full bank and enroll it

`C` performs a raw eight-sector copy, verifies it, and then creates the empty
destination's Bank-3 directory record. The destination must be Bank 0-2.

```text
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q=QUIT> C
SOURCE BANK 0-3> 3
DEST BANK 0-2> 2
!STR8
TYPE COPY 32> COPY 32
........
TYPE 00-FF> 5A
DESC 5 CHARS> RYORS
ENROLL? Y: Y
 OK
```

The required decisions are source, destination, exact `COPY 32` confirmation,
TYPE, five-character DESC, and `ENROLL? Y`.

If the destination directory row is not all `$FF`, the tool prints
`DIR NOT EMPTY` and refuses the copy. After `OK`, quit to STR8-N and use the
matching `J0`, `J1`, or `J2`.

If the payload bank was deliberately erased but its old directory row remains,
reclaim that one row before retrying the copy:

```text
STR8-N 1.21 BANK MAINT
... R=RECLAIM DIR ...> R
RECLAIM DIR 0-3> 0

B3F REWRITE
TYPE CLEAR D0> CLEAR D0
BACKUP VERIFIED
 OK
```

The operation refuses with `BANK NOT ERASED` unless every byte in all eight
Bank-0 payload sectors is `$FF`. It temporarily uses Bank 0 sector F for the
verified B3F backup, then erases that backup only after the protected rewrite
verifies. Do not interrupt it. After `OK`, `M` must show D0 completely erased
and all Bank-0 sectors erased; `C` can then copy and enroll Bank 3 normally.

If D3's journal is exhausted, compact only that journal without replacing the
installed STR8-N or R-YORS payload. At least one Bank-0/1/2 sector must be
completely erased for the verified temporary B3F backup:

```text
STR8-N 1.21 BANK MAINT
... R=RECLAIM DIR ...> R
RECLAIM DIR 0-3> 3

B3F REWRITE
SCRATCH B1:8
TYPE RESET J3> RESET J3
BACKUP VERIFIED
 OK
```

After `OK`, use `M` and require the D3 identity and entry to be unchanged and
its journal to read `FCFFFFFF`. The chosen scratch sector must again show `E`.
The compaction leaves 15 additional `I3` transactions.

## Refresh all directory rows onboard

Use the dedicated refresh image when the protected directory pocket is full,
invalid, or must be rebuilt. This operation erases every directory identity
and journal while preserving the current STR8-N code and vectors. Bank 1
sector F is overwritten with a verified recovery copy first.

```text
STR8-N>L
S19
```

Send:

```text
BUILD/v1.21/s19/str8n-v1.21-directory-refresh-2000.s19
```

The guarded confirmations and successful result are:

```text
STR8-N 1.21 DIRECTORY REFRESH
BACKUP B1:F; TARGET B3:F
TYPE BACKUP B1F> BACKUP B1F
BACKUP VERIFIED
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$hhhh
TYPE ERASE DIRECTORY> ERASE DIRECTORY
ERASING B3:F - NO RESET/NMI/POWER
DIRECTORY EMPTY; STR8-N VERIFIED; RESET
```

`$hhhh` is the checksum of the live top sector and can vary with the installed
image. Do not continue unless Bank 1 sector F is sacrificial and `BACKUP
VERIFIED` appears. Do not press RESET/NMI or remove power during the erase and
rewrite.

## Adopt an existing bank after a directory refresh

`D` creates only the missing directory record; it does not erase, program, or
fully validate the payload. The row must be completely erased and the selected
bank must have a usable RESET vector. This example restores the current R-YORS
Bank-3 identity after a directory refresh:

```text
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q=QUIT> D
BANK 0-3> 3
TYPE 00-FF> FF
DESC 5 CHARS> RYORS
ENTRY 8000-FFFE> C000
TYPE ADOPT B3> ADOPT B3
 OK
```

Bank 3 additionally requires the current `SR 02 03` STR8-N signature and
non-erased bytes at the explicit entry. A following `M` must show:

```text
D3 FF RYORS C000 FCFFFFFF
```

For Banks 0-2, `D` derives launch from RESET and stores directory entry
`$FFFF`; there is no ENTRY prompt. Adoption proves only the guards checked by
the tool, not that the entire guest payload is complete. Prefer a full `I`
install or `C` copy whenever complete-payload verification is required.

## Map banks and directory rows

`M` is read-only:

```text
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E E
B2 U U U U U U U U
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED
```

The directory table below the map decides whether `J0`-`J2` may launch. Used
flash bytes alone do not enroll a bank.

## Recover an interrupted install

If power, RESET, NMI, a bad S-record, or a cancelled commit interrupts `I`,
the bank remains incomplete.

```text
Bank 0-2 recovery: repeat I with the full 8-F range and a complete 32K S19
Bank 3 recovery:   repeat I with the full 8-E range and a complete 28K S19
```

Use exactly the original TYPE and DESC if prompted. Do not try to repair an
incomplete bank with a smaller range. If the directory row is exhausted,
corrupt, or must change identity, use the guarded onboard directory refresh.
Keep the checked full-device external-programmer merge as the recovery
fallback.
