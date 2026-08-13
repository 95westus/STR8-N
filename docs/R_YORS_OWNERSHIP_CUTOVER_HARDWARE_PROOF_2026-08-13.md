# STR8-N / R-YORS Ownership-Cutover Hardware Proof — 2026-08-13

Status: accepted for the separated repository boundary, R-YORS Bank-3 payload
installation, HIMON and STR8-N RAM-loader interoperability, guarded Bank-3 to
Bank-0 copy and directory enrollment, and post-operation cold boot.

Host artifacts associated with this session:

```text
R-YORS/SRC/BUILD/s19/ryors-v1.2-asm-himon-bank3-8-e.s19
SHA-256 21F66CC54C23E4DB5763C3D31D162E23BF10030611DB03B192F2977FD31CE7BC
range $8000-$EFFF; S9 $C000

STR8-N/BUILD/v1.2/s19/str8n-v1.2-bank-maint-2000.s19
SHA-256 B1A9413355CF369FBEE0975CDDB8D4E05151EBCA65DC19261C6AD5374B9F0065
S1 span $2000-$362A; S9 $2000; payload $162B bytes
```

The transcript identifies the Bank Maintenance image by its `$162B` accepted
byte count, `$2000` entry, v1.2 banner, and exercised behavior. It is not an
independent cryptographic readback of the transmitted RAM image; the hash
above records the matching host artifact.

The first Bank-3 `8-E` transfer failed before any progress dot. Its cause was
not captured. Retrying the same guarded transaction produced all seven sector
dots, committed, and returned `OK`. Sector F was not part of that transaction.

After cold boot, HIMON `L` accepted the Bank Maintenance image without
executing it and `G 2000` started it. The initial map showed Bank 0 erased and
the pre-existing D1, D2, and D3 identities. The guarded `C` operation copied
all eight sectors of Bank 3 to Bank 0 only after the exact `COPY 30`
confirmation, then enrolled `D0` as type `$FF`, description `COPY1`, entry
`$FFFF`, journal `FCFFFFFF`. A second map showed Bank 0 used and the new row.

After returning to STR8-N, resident `L` loaded and directly executed the same
kind of RAM maintenance image. Its map preserved the Bank-0 payload and D0
identity. A final reset still timed out through STR8-N into cold HIMON. The
test therefore covers both distinct loader contracts: HIMON bare `L` reports
S9 and requires explicit `G`, while STR8-N `L` executes the accepted S9 entry.

The entered HIMON token `V` is not a registered command in this build.
`#D30C0E69# HSH_NF!` is the expected hash-not-found diagnostic and is not a
firmware failure.

Exact operator transcript:

```text
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>I
B0-3: 3
RANGE: 8-E
I B3 8-E WRITE? Y: Y
S19

FAIL
STR8-N>I
B0-3: 3
RANGE: 8-E
I B3 8-E WRITE? Y: Y
S19
......COMMIT? Y: Y.
OK
STR8-N>
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
BOOT COLD
RAM ZERO OK

HIMON V 00.0813(0552)
>V
#D30C0E69# HSH_NF!
>ASM
ASM-F2 00.0813(0552)
ASM>$2000: .
ASM BYE
>
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>H
BOOT WARM

HIMON V 00.0813(0552)
>L
L S19
L @2000
L OK=162B ENTRY=2000
>G 2000
GO 2000

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q/ENTER=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E U
B2 U U U U U U U U
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF ..... FFFF FFFFFFFF
D1 FF XXXXX FFFF FCFFFFFF
D2 FF B2D2X FFFF FCFFFFFF
D3 FF RYORS C000 00FCFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q/ENTER=QUIT> C
SOURCE BANK 0-3> 3
DEST BANK 0-2> 0
!STR8
TYPE COPY 30> COPY 30

........
TYPE 00-FF> FF
DESC 5 CHARS> COPY1
ENROLL? Y: Y
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q/ENTER=QUIT> M

BANK 8 9 A B C D E F

B0 U U U U U U U U
B1 E E E E E E E U
B2 U U U U U U U U
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF COPY1 FFFF FCFFFFFF
D1 FF XXXXX FFFF FCFFFFFF
D2 FF B2D2X FFFF FCFFFFFF
D3 FF RYORS C000 00FCFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q/ENTER=QUIT> Q

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>L
S19

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q/ENTER=QUIT> M

BANK 8 9 A B C D E F

B0 U U U U U U U U
B1 E E E E E E E U
B2 U U U U U U U U
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF COPY1 FFFF FCFFFFFF
D1 FF XXXXX FFFF FCFFFFFF
D2 FF B2D2X FFFF FCFFFFFF
D3 FF RYORS C000 00FCFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q/ENTER=QUIT> Q

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
BOOT COLD
RAM ZERO OK

HIMON V 00.0813(0552)
>
```

This session does not claim an independent flash readback, explain the first
failed transfer, test a sector-F update, or verify execution from the new
Bank-0 copy. It does prove the copy's eight-sector completion, verification
result as reported by Bank Maintenance, durable directory enrollment, and
survival of the normal Bank-3 cold-boot path.
