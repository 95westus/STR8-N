# STR8-N v1.2 Expanded Resident ABI Hardware Proof — 2026-08-11

Status: accepted for the guarded onboard update, verified Bank-1 backup,
RESET/live selector, `$F006` ABI_QUERY, `$F003` CONSOLE_INIT, `$F019` CHAROUT,
`$F03E` non-consuming CHAR_READY empty/ready paths, `$F013` CHARIN, `$F0E6`
BRK dispatch, warm HIMON, cold HIMON timeout, guarded onboard directory
refresh, Bank-3-to-Bank-2 copy+enrollment, selector `2` launch, and `J3` return
to physical Bank 3.

NMI remains unclaimed. The terminal stream does not independently identify a
physical NMI action, and no operator annotation accompanied this run. The two
`BAD` responses before warm `H` are consistent with empty command lines; an
empty Enter prints `BAD`, while the default NMI handler returns silently.

Exact tested artifacts:

```text
BUILD/v1.2/bin/str8n-v1.2-bank3-f000-ffff.bin
SHA-256 799E563E538AF706CF00655E81EAC4ED7A16FCA570123D85CCB1FF41B4DCB334

BUILD/v1.2/s19/str8n-v1.2-top-update-2000.s19
SHA-256 1E22E6FCEDDE2826C04CB56D4F963D2C723DB840CAF80F810206C37BC1DCD9B4

BUILD/v1.2/s19/str8n-v1.2-console-abi-test-2000.s19
SHA-256 1713743021933330FFB12932B56C6F7F7622E8367A3D311BC07361F06CAB64AE

BUILD/v1.2/s19/str8n-v1.2-directory-refresh-2000.s19
SHA-256 1643F8A465CCD857B79661742D2F3FE506634B7BA98909B137604B720E8535FE

BUILD/v1.2/s19/str8n-v1.2-bank-maint-2000.s19
SHA-256 0EB33A64D36EAC4EFF7BA9C64A6DBE24BA81EC38A8BB91540898C6AE7445FB3F
```

The updater reported old live-sector sum `$144F`. This is a receipt for the
immediately preceding installed sector, including preserved live
directory/configuration bytes. The earlier `$21D9` receipt belonged to the
sector replaced by the preceding accepted update; it was not the expected
receipt for this run. The updater copied the `$144F` sector to Bank 1 and
verified the copy before erasing Bank 3 sector F, then programmed and verified
the new image and entered its RESET vector.

The RAM probe verified resident ABI version `$01`, capability byte `$3F`,
ABI_QUERY Y/carry behavior, CONSOLE_INIT A/X/Y and both incoming carry states,
CHAROUT A/X/Y/carry behavior, both CHAR_READY states and non-consumption, raw
lowercase `$71`, raw CR `$0D`, CHARIN X/Y/carry behavior, and a BRK/RTI round
trip through `$F0E6`.

After `J3`, bare `0`, `1`, `2`, `3`, and `S` at the release command prompt
silently re-prompted as unsupported commands. A later empty command produced
`BAD`. Those extra inputs were outside the prescribed ABI proof and match the
current command-loop behavior.

Exact retained terminal transcript:

```text
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>L
S19

STR8-N 1.2 TOP UPDATE
BACKUP B1:F; TARGET B3:F
TYPE BACKUP B1F> BACKUP B1F
BACKUP VERIFIED
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$144F
TYPE STR8-N 1.2> STR8-N 1.2
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 1.2 VERIFIED; RESET

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>L
S19

STR8-N 1.2 CONSOLE ABI TEST
ABI_QUERY $F006 V1 CAPS $3F/Y/C: PASS
CONSOLE_INIT $F003 A/X/Y/C: PASS
CHAROUT $F019 A/X/Y/C: PASS
TYPE q THEN ENTER> q <- $71 RAW: PASS
$0D RAW ENTER: PASS
CHAR_READY $F03E EMPTY/READY/X/Y/C: PASS
CHARIN $F013 X/Y/C: PASS
BRK VECTOR $F0E6: PASS
CONSOLE ABI TEST: PASS
PRESS PHYSICAL RESET

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>
BAD
STR8-N>
BAD
STR8-N>H
BOOT WARM

HIMON V 00.0811(1004)
>
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
BOOT COLD
RAM ZERO OK

HIMON V 00.0811(1004)
>
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>J3
J B3

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>0STR8-N>1STR8-N>2STR8-N>3STR8-N>
BAD
STR8-N>0STR8-N>
BAD
STR8-N>SSTR8-N>
BAD
STR8-N>
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
BOOT COLD
RAM ZERO OK

HIMON V 00.0811(1004)
>
```

## Follow-on HIMON and Bank Maintenance evidence

The same board session then used HIMON `STR8` to locate and enter the Bank-3
resident at `$F000` with `K=03`. Bank Maintenance loaded through `L`.

`C` correctly refused Bank 0 because directory row D0 was not empty. `E`
then erased and verified all eight Bank-0 payload sectors. A second `C`
correctly refused the still-nonempty D0 row: payload erase intentionally does
not rewrite the protected directory in Bank 3 sector F. `M` confirmed Bank 0
sectors `8-F` erased, Bank 1 sector F used by the verified top backup, Bank 2
sectors `8-F` erased, and Bank 3 sector F protected. It also showed all four
directory rows nonempty. A Bank-3-to-Bank-2 `C` therefore correctly refused D2.

This accepts Bank Maintenance destructive erase/verify for Bank 0 and the
nonempty-directory guard for B0 and B2. It does not accept copy+enrollment:
there is no empty destination directory row on this board. That proof requires
the guarded onboard directory refresh or the external-programmer fallback.
The onboard refresh first replaces Bank 1 sector F with a newly verified exact
backup of the current live top sector; keep it intact afterward until the
refresh and copy+enrollment proof are accepted.

Exact retained continuation:

```text
>STR8
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
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> C
SOURCE BANK 0-3> 3
DEST BANK 0-2> 0

DIR NOT EMPTY
ABORT

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> E
BANK 0-3> 0
SECTOR 8-F, ALL, OR X-Y; B3 MAX E> ALL
TYPE ERASE 0ALL> ERASE 0ALL

........ OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> C
SOURCE BANK 0-3> 3
DEST BANK 0-2> 0

DIR NOT EMPTY
ABORT

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

BANK 8 9 A B C D E F

B0 E E E E E E E E
B1 E E E E E E E U
B2 E E E E E E E E
B3 U U U U U U U P
E=ERASED U=USED A=AP VALID P=B3F PROTECTED

DIR B T DESC ENTRY JOURNAL
D0 F0 TEST0 FFFF FCFFFFFF
D1 FE TEST1 FFFF FEFFFFFF
D2 F8 TEST2 FFFF FCFFFFFF
D3 FF RYORS C000 C0FFFFFF
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> C
SOURCE BANK 0-3> 3
DEST BANK 0-2> 2

DIR NOT EMPTY
ABORT

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT>
```

## Onboard directory refresh and copy+enrollment acceptance

The retained continuation below accepts the dedicated onboard directory
refresh, including a newly verified Bank-1 sector-F backup, live-sector sum
`$0BE5`, active Bank-3 sector-F rewrite, internal verification, and RESET. The
first Bank Maintenance `M` after RESET proves all four directory rows and
journals erased while every non-target bank sector retained its prior state.

Bank Maintenance then copied all eight sectors from Bank 3 to the erased Bank
2, recognized the STR8-N source signature, verified all eight writes, and
enrolled D2 as `FF TEST0 FFFF FCFFFFFF`. A second `M` proves both the complete
Bank-2 payload and COMPLETE directory journal. Selector `2` launched the copied
Bank-2 STR8-N, and its explicit `J3` returned through the physical Bank-3 RESET
path before cold HIMON entry.

Exact retained continuation:

```text
ABORT

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> Q

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
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$0BE5
TYPE ERASE DIRECTORY> ERASE DIRECTORY
ERASING B3:F - NO RESET/NMI/POWER
DIRECTORY EMPTY; STR8-N VERIFIED; RESET

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
STR8-N>L
S19

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

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
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> C
SOURCE BANK 0-3> 3
DEST BANK 0-2> 2
!STR8
TYPE COPY 32> COPY 32

........
TYPE 00-FF> FF
DESC 5 CHARS> TEST0
ENROLL? Y: Y
 OK

STR8-N 1.2 BANK MAINT
B3 ERASE RETURNS TO STR8; SELECT S
!STR8=SOURCE HAS STR8
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> M

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
C=COPY+DIR E=ERASE M=MAP+DIR P=AP B0BF00 Q=QUIT> Q

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .2
J B2
3S

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ...S
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

The subsequent
[directory-maintenance hardware proof](DIRECTORY_MAINT_HARDWARE_PROOF_2026-08-11.md)
accepts the new `D` adoption path and the refactored `C` path using the current
Bank Maintenance artifact.

Still separate: an explicitly annotated NMI action, independent
external-programmer recovery, explicit command-path `J0`/`J1`/`J2`, Bank
Maintenance AP put, and the remaining complete release-matrix cases.
