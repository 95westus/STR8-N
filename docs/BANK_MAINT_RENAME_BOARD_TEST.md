# Bank Maintenance Directory Rename Board Test

> [!NOTE]
> Superseded pre-v1.29 proof card. The current v1.29 Bank Maintenance image
> includes `N`; use the current Operator's Guide and versioned artifact. The
> source path and prompts below are retained only to reproduce this pending
> historical test.

Status: host-built; board proof pending.

`N` changes only the five-byte description in one COMPLETE D0-D3 directory
record. It must preserve type, reserved bytes, seal, entry, journal, the other
three rows, configuration bytes, and vectors.

## Exact onboard source

```text
C:\SRC\R-YORS\RELEASE\ARTIFACTS\SOURCES\str8n-v1.23-bank-maint-menu-2000.a
```

At HIMON:

```text
ASM NEW
```

Send the complete `.a`. At `SEAL>` enter:

```text
.
G 2000
```

Run `M` and save all four directory rows. Require at least one fully erased
non-role sector in B0-B2. Then choose a COMPLETE row and a legal five-character
replacement. For example, to rename D1 to `BASIC`:

```text
N
1
BASIC
RENAME D1 BASIC
```

Require:

```text
B3F REWRITE
SCRATCH Bn:s
TYPE RENAME D1 BASIC> RENAME D1 BASIC
BACKUP VERIFIED
 OK
```

Do not reset, use NMI, remove power, or interrupt the terminal after the exact
confirmation. Run `M` again. Require only D1's description to change and the
scratch sector to return to erased. Stop on `DIR NOT COMPLETE`, `NO ERASED
SCRATCH`, any `ERR=`, or any unexpected map difference.
