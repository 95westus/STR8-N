# STR8-N v1.2 Console ABI Hardware Proof — 2026-08-11

Status: accepted for the guarded onboard update, RESET/live selector,
`$F019` CHAROUT, `$F013` CHARIN, `$F0DB` BRK dispatch, warm HIMON, cold HIMON
timeout, and `J3`. The silent NMI action is not independently visible in the
terminal stream and therefore still needs an operator annotation if it was
performed before `H`.

Exact current artifacts:

```text
BUILD/v1.2/bin/str8n-v1.2-bank3-f000-ffff.bin
SHA-256 DF392E8B018E39E33C54AB4170D656F5F58976420728E44C63C37E8D62B2814F

BUILD/v1.2/s19/str8n-v1.2-top-update-2000.s19
SHA-256 8D5772FFCF250D9D5A128708F497686BE1AAC5B13B91EF91BDACFDE3C67EA08A

BUILD/v1.2/s19/str8n-v1.2-console-abi-test-2000.s19
SHA-256 49AA719A85721F6FBDFE7261E888D694C6348EC1B942E3A1E957B0E3B4E7D16C
```

The guarded updater verified the Bank-1 backup, reported previous live-sector
sum `$21D9`, programmed and internally verified Bank-3 sector F, and entered
the new RESET vector. The RAM probe verified A/X/Y/carry behavior for CHAROUT,
raw lowercase `$71`, raw CR `$0D`, X/Y/carry behavior for CHARIN, and a BRK/RTI
round trip through `$F0DB`.

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
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$21D9
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
CHAROUT $F019 A/X/Y/C: PASS
TYPE q THEN ENTER> q <- $71 RAW: PASS
$0D RAW ENTER: PASS
CHARIN $F013 X/Y/C: PASS
BRK VECTOR $F0DB: PASS
CONSOLE ABI TEST: PASS
PRESS PHYSICAL RESET

WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: .S
I L H J
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
STR8-N>
```

Still separate: independent external-programmer recovery, `J0`-`J2`, and the
remaining destructive maintenance and complete release-matrix cases.
