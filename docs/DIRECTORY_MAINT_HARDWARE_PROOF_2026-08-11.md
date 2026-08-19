# STR8-N v1.2 Directory Maintenance Hardware Proof — 2026-08-11

Status: accepted for Bank Maintenance `D` metadata-only adoption, its erased-row
and RESET/ENTRY guards, its TYPE/DESC validation and precommit cancellation,
the refactored shared directory commit path, and a subsequent `C` copy regression.
The appended 2026-08-18 STR8-N `1.21` continuation additionally accepts the
combined menu's guarded `U`, copy-with-enrollment-cancelled state, positive D2
adoption and `J2` launch, retained B1:F guard, and physical-reset recovery.

Exact tested Bank Maintenance artifact:

```text
BUILD/v1.2/s19/str8n-v1.2-bank-maint-2000.s19
SHA-256 6144C085BCBF8B294897526221B912E54E65BA01785D09DA4868B2919BB3C35B
S1 span $2000-$362A; S9 $2000
private worker store $3400-$362A; run $0200-$042A
private worker SHA-256 FFCDB4201C913FC9B3E3F3D438A98940F76967C5E62F843A2DC32CFF1D1AD1B2
```

The first `D2` attempt proves that `D` refuses a nonempty directory row. The
first `D3` attempt adopts the live Bank-3 payload as
`D3 FF RYORS C000 FCFFFFFF`. A Bank-1 attempt rejects a one-character DESC,
accepts a five-character DESC, and is then cancelled before any journal write.
Erasing Bank-2 payload does not erase D2, and a later adoption still refuses
that nonempty row.

The directory refresher then rejects the misspelled final confirmation before
active erase, repeats safely, backs up live sector sum `$1351`, and completes.
After that refresh, `D3` rejects entries `$FFFF` and `$7FFF`, accepts `$C000`,
and publishes a fresh COMPLETE identity. `D2` with erased sector F fails RESET
validation and leaves its row erased. `D1` rejects a four-character DESC and
adopts the valid-reset Bank-1 top-sector backup as
`D1 FF XXXXX FFFF FCFFFFFF`; this proves the documented RESET-level adoption
contract, not that Bank 1 contains a complete guest payload.

Finally, `C` still copies all eight Bank-3 sectors to Bank 2 through the
refactored shared identity writer, enrolls `D2 FF B2D2X FFFF FCFFFFFF`, and
selector `2` launches the copy. Its explicit `J3` returns through physical Bank
3 and reaches cold HIMON. The locally echoed `3S` is not used as device proof.

Exact retained transcript:

```text
STR8
RUN STR8: BOOTLOADER @F000 K=03 ? y

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>L
S19

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E U
B2 U U U U U U U U
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF ..... FFFF FFFFFFFF
D1 FF ..... FFFF FFFFFFFF
D2 FF TEST0 FFFF FCFFFFFF
D3 FF ..... FFFF FFFFFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> D
BANK 0-3> 2

DIR NOT EMPTY
ABORT

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> D
BANK 0-3> 3

ENTRY 8000-FFFE> C000

TYPE 00-FF> FF
DESC 5 CHARS> RYORS
TYPE ADOPT B3> ADOPT B3
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E U
B2 U U U U U U U U
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF ..... FFFF FFFFFFFF
D1 FF ..... FFFF FFFFFFFF
D2 FF TEST0 FFFF FCFFFFFF
D3 FF RYORS C000 FCFFFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> D
BANK 0-3> 1

TYPE 00-FF> FF
DESC 5 CHARS> X
DESC 5 CHARS> XXXXX
TYPE ADOPT B1>
ABORT

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> E
BANK 0-3> 2
SECTOR 8-F, ALL, OR X-Y; B3 MAX E> ALL
TYPE ERASE 2ALL> ERASE 2ALL

........ OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E U
B2 E E E E E E E E
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF ..... FFFF FFFFFFFF
D1 FF ..... FFFF FFFFFFFF
D2 FF TEST0 FFFF FCFFFFFF
D3 FF RYORS C000 FCFFFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> D
BANK 0-3> 2

DIR NOT EMPTY
ABORT

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> Q

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>L
S19

STR8-N 1.2 DIRECTORY REFRESH
BACKUP B1:F; TARGET B3:F
TYPE BACKUP B1F> BACKUP B1F
BACKUP VERIFIED
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$1351
TYPE ERASE DIRECTORY> ERASE DIRECTOY
ABORT - NO ACTIVE DIRECTORY REFRESH

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>L
S19

STR8-N 1.2 DIRECTORY REFRESH
BACKUP B1:F; TARGET B3:F
TYPE BACKUP B1F> BACKUP B1F
BACKUP VERIFIED
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$1351
TYPE ERASE DIRECTORY> ERASE DIRECTORY
ERASING B3:F - NO RESET/NMI/POWER
DIRECTORY EMPTY; STR8-N VERIFIED; RESET

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>L
S19

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E U
B2 E E E E E E E E
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF ..... FFFF FFFFFFFF
D1 FF ..... FFFF FFFFFFFF
D2 FF ..... FFFF FFFFFFFF
D3 FF ..... FFFF FFFFFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> D
BANK 0-3> 3

ENTRY 8000-FFFE> FFFF

ENTRY 8000-FFFE> 7FFF

ENTRY 8000-FFFE> C000

TYPE 00-FF> FF
DESC 5 CHARS> RYORS
TYPE ADOPT B3> ADOPT B3
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E U
B2 E E E E E E E E
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF ..... FFFF FFFFFFFF
D1 FF ..... FFFF FFFFFFFF
D2 FF ..... FFFF FFFFFFFF
D3 FF RYORS C000 FCFFFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> D
BANK 0-3> 2
!

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> D
BANK 0-3> 1

TYPE 00-FF> FF
DESC 5 CHARS> XXXX
DESC 5 CHARS> XXXXX
TYPE ADOPT B1> ADOPT B1
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E U
B2 E E E E E E E E
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF ..... FFFF FFFFFFFF
D1 FF XXXXX FFFF FCFFFFFF
D2 FF ..... FFFF FFFFFFFF
D3 FF RYORS C000 FCFFFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> D
BANK 0-3> 2
!

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> C
SOURCE BANK 0-3> 3
DEST BANK 0-2> 2
!STR8
TYPE COPY 32> COPY 32

........
TYPE 00-FF> FF
DESC 5 CHARS> B2D2X
ENROLL? Y: Y
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

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
D3 FF RYORS C000 FCFFFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> Q

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ..2
J B2
3S

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>J3
J B3

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
BOOT COLD
RAM ZERO OK

HIMON V 00.0811(1004)
>
```

Still separate: an explicitly annotated NMI action, independent
external-programmer recovery, explicit command-path `J0`/`J1`/`J2`, Bank
Maintenance AP put, and the remaining complete release-matrix cases.
## 2026-08-13 Erased-Payload/Stale-Directory Continuation

The operator erased `ALL` in Banks 0, 1, and 2. `M` then correctly showed all
24 payload sectors erased while D0-D2 retained their earlier identities:

```text
B0 E E E E E E E E
B1 E E E E E E E E
B2 E E E E E E E E
B3 U U U U U U U P

D0 FF COPY1 FFFF FCFFFFFF
D1 FF XXXXX FFFF FCFFFFFF
D2 FF B2D2X FFFF FCFFFFFF
D3 FF RYORS C000 00FCFFFF
```

Both `C` from Bank 3 to Bank 0 and `D` for Bank 0 then printed `DIR NOT EMPTY`
and aborted. This is expected from the pre-existing safety rule but exposed a
missing narrow recovery operation: payload erase cannot set the separately
stored Bank-3 directory bits back to `$FF`.

Bank Maintenance now has `R=RECLAIM DIR`. It accepts only D0-D2, returns
without mutation for an already-erased row, and otherwise requires all eight
corresponding payload sectors to verify erased before exact `CLEAR Dn`
confirmation. It stages B3F, writes and verifies an original-image backup in
the selected bank's sector F, clears only the selected 16-byte row in RAM,
rewrites and verifies B3F, then erases and verifies the temporary backup.

Host status: accepted. `make all`, the Bank Maintenance S19 checker, the R-YORS
external STR8-N contract check, and `git diff --check` pass. The image remains
`$2000-$362A` with S9 `$2000`; private-worker SHA-256 remains
`FFCDB4201C913FC9B3E3F3D438A98940F76967C5E62F843A2DC32CFF1D1AD1B2`.
The new Bank Maintenance S19 SHA-256 is
`B296088666483187E9F7CEA694FB0BE9BCAEE0F3C56592738DC6014B0BFA4940`.

Board status: accepted on 2026-08-13 for the Bank-0 stale-row case. A mistyped
`CREATE D0` confirmation aborted without mutation. Exact `CLEAR D0` reported
`BACKUP VERIFIED` and `OK`; the immediately following Bank-3-to-Bank-0 copy
programmed and verified all eight sectors and enrolled D0 as `BKUP0`. The
final map showed Bank 0 used in all eight sectors and D0 complete. No
standalone `M` was captured between reclaim and copy, so the evidence relies
on `R`'s internal verified cleanup plus the successful copy rather than an
independent post-reclaim map snapshot.

### Retained terminal transcript

```text
STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q/ENTER=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E E
B2 E E E E E E E E
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
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q/ENTER=QUIT> R

RECLAIM BANK 0-2> 0

B3F REWRITE
TYPE CLEAR D0> CREATE D0
ABORT

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q/ENTER=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E E
B2 E E E E E E E E
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
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q/ENTER=QUIT> C
SOURCE BANK 0-3> 3
DEST BANK 0-2> 0

DIR NOT EMPTY
ABORT

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q/ENTER=QUIT> R

RECLAIM BANK 0-2> 0

B3F REWRITE
TYPE CLEAR D0> CLEAR D0
BACKUP VERIFIED
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q/ENTER=QUIT> C
SOURCE BANK 0-3> 3
DEST BANK 0-2> 0
!STR8
TYPE COPY 30> COPY 30

........
TYPE 00-FF> FF
DESC 5 CHARS> BKUP0
ENROLL? Y: Y
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q/ENTER=QUIT> M

BANK 8 9 A B C D E F

B0 U U U U U U U U
B1 E E E E E E E E
B2 E E E E E E E E
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF BKUP0 FFFF FCFFFFFF
D1 FF XXXXX FFFF FCFFFFFF
D2 FF B2D2X FFFF FCFFFFFF
D3 FF RYORS C000 00FCFFFF
 OK
```

## 2026-08-14 D3 Journal-Exhaustion Precondition

The operator captured the live board state that motivated the narrow D3
compaction path. This is precondition evidence, not acceptance of the new
mutation path. D3 retains the expected `RYORS` / `C000` identity, but its
journal is exhausted at `00000000`. Bank 1 sectors 8-E provide erased scratch
space; Bank 1 sector F is used and is not assumed disposable.

```text
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
BOOT COLD
RAM ZERO OK

HIMON V 00.0814(1102)
>L
L S19
L @2000
L OK=162B ENTRY=2000
>G 2000
GO 2000

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q/ENTER=QUIT> M

BANK 8 9 A B C D E F

B0 U U U U U U U U
B1 E E E E E E E U
B2 U U U U U U U U
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 FF BKUP0 FFFF FCFFFFFF
D1 FF XXXXX FFFF FCFFFFFF
D2 FF BACKP FFFF FCFFFFFF
D3 FF RYORS C000 00000000
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR D=ADOPT E=ERASE M=MAP+DIR P=AP B0BF00 R=RECLAIM DIR Q/ENTER=QUIT> Q
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
BOOT COLD
RAM ZERO OK

HIMON V 00.0814(1102)
>
```

The host-built successor makes `R` accept directory 3 only for this exact
full-journal state. It searches B0-B2 sectors 8-F, so this map selects B1:8
without disturbing used B1:F. It preserves D3 bytes +0..+11 and replaces only
+12..+15 with `FCFFFFFF`. `make all`, the strengthened Bank Maintenance
checker, the R-YORS ASM smoke suite, and both repositories' `git diff --check`
pass. The candidate S19 SHA-256 is
`B1088334157A242B4F94AD2228BF4DAEE6328500D6C9533BF9F57E955CF98B73`.
Board execution and the post-operation map remain open evidence.

## 2026-08-14 D3 Journal Compaction Acceptance

The subsequent `1157` board continuation closes the mutation and post-map
evidence left open above. The guarded path selected the expected erased B1:8
scratch sector, accepted only exact `RESET J3`, verified its backup, rewrote
B3F, erased the temporary backup, and returned `OK`:

```text
RECLAIM DIR 0-3> 3

B3F REWRITE
SCRATCH B1:8
TYPE RESET J3> RESET J3
BACKUP VERIFIED
 OK
```

The immediate map proved that B1:8 was erased again, D3's type, description,
and entry were unchanged, and only its journal was compacted:

```text
B1 E E E E E E E U

DIR B T DESC ENTRY JOURNAL
D0 FF BKUP0 FFFF FCFFFFFF
D1 FF XXXXX FFFF FCFFFFFF
D2 FF BACKP FFFF FCFFFFFF
D3 FF RYORS C000 FCFFFFFF
 OK
```

This accepts the D3 compactor's protected mutation, identity preservation,
verified backup/B3F rewrite, and scratch cleanup on hardware. The integrated
R-YORS closure card still requests an explicit STR8-N `J3` command to prove
the compacted row through the selector's directory gate; that is a launch
integration check, not an open Bank Maintenance mutation check.

## 2026-08-14 Compacted-D3 `J3` Launch Acceptance

The next operator continuation closes that launch integration check. From the
live STR8-N shell, explicit `J3` selected Bank 3 and followed its RESET vector.
The normal timeout then cold-booted matching HIMON `00.0814(1157)`, and `Q`
reached its NMI monitor:

```text
STR8-N>J3
J B3
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
BOOT COLD
RAM ZERO OK

HIMON V 00.0814(1157)
>Q

NMI PC=C54B
A=C5 X=FF Y=07 P=A5 S=FB Nv-bdIzC
>
```

Result: the compacted D3 row passes the actual `J3` directory gate. D3
mutation, post-map, cleanup, and launch integration are all board-accepted.

### Operator correction: launch evidence is inconclusive

The operator subsequently reported possible physical RESET intervention after
`J B3`. The transcript therefore proves command recognition but cannot
causally attribute the following RESET/cold path to `J3`. Superseding the
launch-acceptance statement above, the Bank Maintenance mutation, post-map,
identity preservation, and scratch cleanup remain accepted; the integrated
`J3` launch must be repeated without touching RESET or sending input between
the command and the matching HIMON identity.

### Uninterrupted `J3` rerun acceptance

The operator supplied the required continuous rerun and confirmed that no
physical RESET or other input intervened after `J3`:

```text
>STR8
RUN STR8: BOOTLOADER @F000 K=03 ? y

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ..S
I L H J
STR8-N>J3
J B3
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
BOOT COLD
RAM ZERO OK

HIMON V 00.0814(1157)
>
```

This supersedes the causal qualification above while preserving it as part of
the evidence history. The installed STR8-N `1.2` / R-YORS `1157` image now has
accepted compacted-D3 mutation, post-map, scratch cleanup, directory-gated
`J3` selection, RESET-vector handoff, and matching cold HIMON identity. It is
historical evidence only; the rebuilt STR8-N `1.21` / R-YORS `1303` image still
requires its own installation and identity smoke.

### Operator correction: rerun RESET was physical

The operator subsequently clarified that every RESET indicated in the logs,
including the RESET after `J B3` in the rerun above, was physical and
intentional. This supersedes the rerun-acceptance interpretation while leaving
the transcript intact. The rerun proves explicit `J3` recognition and `J B3`
output, but the following physical RESET prevents causal attribution of the
Bank-3 RESET-vector handoff to `J3`. The D3 compaction, post-map, identity
preservation, and scratch cleanup remain accepted. Launch integration remains
open until `J3` is followed by the matching cold HIMON identity without any
physical RESET or intervening input.

### Synthetic-RESET `J3` acceptance

The operator then supplied a new continuous capture and explicitly identified
the RESET immediately following `J B3` as synthetic. It ran from a live HIMON
`STR8` launch through STR8-N `J3`, the synthetic Bank-3 RESET-vector transition,
the normal cold timeout, and matching HIMON `00.0814(1157)` without a physical
reset after `J3`.

This is the explicit exception to the preceding physical-reset clarification.
For the installed STR8-N `1.2` / R-YORS `1157` image, compacted-D3 mutation,
post-map, scratch cleanup, directory-gated `J3` selection, and RESET-vector
handoff are now board-accepted. STR8-N `1.21` / R-YORS `1303` remains a
separate installation and current-identity smoke.

## 2026-08-18 STR8-N `1.21` Combined-Menu Adoption And Launch

This append-only continuation accepts the current combined Bank Maintenance
menu's positive metadata-only adoption edge separately from `C` enrollment.
Terminology in this section calls the observed non-R-YORS payload the
**factory onboard firmware**. Literal operator directory descriptions `WDCV2`,
`WDCBK`, and `WDCDG` are evidence labels, not proof that the payload is
WDCMONv2.

The combined menu first completed its guarded top update, verified the B1:F
backup, preserved the live directory, and reset through the new B3:F image:

```text
BM> U

STR8-N 1.21 TOP UPDATE
BACKUP B1:F; TARGET B3:F
TYPE BACKUP B1F> BACKUP B1F
BACKUP VERIFIED
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$0715
TYPE STR8-N 1.21> STR8-N 1.21
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 1.21 VERIFIED; RESET
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.21
```

With D2 erased, `C` then copied and verified all eight Bank-0 sectors to Bank
2. The operator cancelled at the identity prompt, leaving the payload present
and its directory row erased:

```text
BM> C
SOURCE BANK 0-3> 0
DEST BANK 0-2> 2
TYPE COPY 02> COPY 02

........
TYPE 00-FF> ABORT

BM> M

B2 U U U U U U U U

DIR B T DESC ENTRY JOURNAL
D0 02 WDCV2 FFFF FCFFFFFF
D1 F2 WDCBK FFFF FCFFFFFF
D2 FF ..... FFFF FFFFFFFF
D3 FF RYORS C000 000000FF
 OK
```

`D` adopted those existing bytes without a second copy, committed D2, and the
following map retained its COMPLETE journal:

```text
BM> D
BANK 0-3> 2

TYPE 00-FF> F2
DESC 5 CHARS> WDCDG
TYPE ADOPT B2> ADOPT B2
 OK

BM> M

D0 02 WDCV2 FFFF FCFFFFFF
D1 F2 WDCBK FFFF FCFFFFFF
D2 F2 WDCDG FFFF FCFFFFFF
D3 FF RYORS C000 000000FF
 OK
```

The operator intentionally erased only B1 sectors `8-E`, retaining B1:F as
the verified B3:F recovery backup. The map and reclaim refusal prove the guard
recognized that retained sector and made no directory mutation:

```text
B1 E E E E E E E U

BM> R

RECLAIM DIR 0-3> 1

BANK NOT ERASED
ABORT
```

D1 still describes the former Bank-1 guest, so `J1` is prohibited in this
intentional recovery state. B1:F must not be erased while that backup is
required.

Finally, returning to STR8-N and selecting Bank 2 passed the new D2 record's
directory gate and entered the adopted payload through its RESET vector:

```text
BM> Q
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.21
0-2 H S: .2
J B2
3S

================================
  W65C02SXB + EDU Kit  Rev 1.0
  W65C02S @ 8 MHz  |  5V System
  I2C/SPI bit-banged via W65C22
================================
Initializing...
Scanning devices...
  OLED (SSD1306)     $3C  OK
  RTC  (MCP79411)    $6F  OK
  SPI SRAM           OK
Init complete.
```

An intentional physical RESET returned to STR8-N `1.21`; `H` warm-entered
HIMON `00.0818(1108)`, and a final Bank Maintenance map preserved B1 as
`E E E E E E E U` and D2 as `F2 WDCDG FFFF FCFFFFFF`. This accepts the
combined-menu `U`, separate copy-without-enrollment state, positive `D2`
adoption, COMPLETE persistence, directory-gated `J2`, factory-firmware guest
initialization, retained-backup reclaim refusal, and physical-reset recovery.
No exact full-bank SHA-256 or CRC identity is claimed for the factory firmware.
