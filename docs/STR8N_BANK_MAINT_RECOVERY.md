# BANK MAINT 1.5 for beta4

BANK MAINT remains the existing 1.5 program. It loads into RAM
`$2000-$3D53` and runs at `$2000`, with `BM>` as its prompt. Its 7,508 program
bytes are unchanged from the installed October 5 COM3 utility. The release
installs a saved MAINT record in B3 sectors 8 and 9. Enter `R MAINT` to
restore/run it, or `R MAINT L` to load only. `Q` returns to `B3>`.

Migration replaces B3 sectors 8/9 with this record. The generated storage
image contains a 24-byte SR header plus the 7,508 unchanged program bytes;
its occupied range is `$8000-$9D6B`. Both sectors must remain intact.
The matching release S19 is also included for host loading through `L`.
Choose another erased span and a different label for an additional SAVE;
do not overwrite or duplicate the installed MAINT record.

The monitor supplies **RESTORE / SAVE / TABLE (RST)**. See the
[RST walkthrough](STR8N_V2_BETA4_RST.md) for the full workflow. BANK MAINT's
existing `S` stages bytes and `R` reads into its editor buffer; neither is
changed to implement monitor SAVE/RESTORE.

## Existing utility commands

All numbers are hexadecimal. Flash sectors 8-F may be used as aligned range
shorthand. Source/destination `R` denotes RAM; 0-3 denotes a flash bank.

| Command at BM> | Meaning |
| --- | --- |
| `M` / `M 2` | Address ranges, record extents, erased tails and access reservations |
| `M 1` | Compact sector grid, with ownership legend |
| `M 3` | Per-sector erased/used state, erase attempts, ownership and monitor status |
| `T [bank or first-last]` | Stored-program table; bare T lists all banks |
| `E bank first[-last]` | Erase an allowed sector range |
| `C src range dst start` | Copy between RAM and flash in either direction |
| `V src range dst start` | Compare ranges |
| `R src range` | Read up to 4 KiB into the editor buffer |
| `D [offset[-end]]` | Display editor-buffer bytes |
| `P offset byte ...` | Patch editor bytes |
| `F offset[-end] byte` | Fill an editor range |
| `N length byte` | Create a filled editor buffer |
| `K` | Editor CRC16-CCITT-FALSE |
| `W dst start` | Write and verify the editor buffer |
| `S 8` / `S 9` | Stage part of the utility in the editor buffer |
| `J bank` | Boot a selected bank through its reset vector |
| `Q` | Return to the resident monitor |
| `?` | Show utility help |

`T` returns to `BM>` in maintenance. At the monitor, `W` reports wear;
in maintenance, `W` writes the editor buffer. Maps refresh ownership on every
request. The clean profile has no installed application descriptors.
Erased sectors are not automatically available: the access column also accounts
for recovery reservations.

## Write guards and RAM

Writes print the operation and destination, then require `Y` plus Enter.
Every B3:A-F destination is protected, including a range starting in storage
and ending in the reserved region. Reads and comparisons may inspect those
sectors. A refused write reports `CANCELED (completed sectors retained)` and
does not ask for confirmation. Successful writes report `VERIFIED`.
Failures stop the operation; completed sectors are not rolled back.
Each actual sector erase is recorded in the persistent erase-attempt journal.

| RAM range | Use |
| --- | --- |
| `$2000-$3D53` | BANK MAINT code and constants |
| `$5000-$5FFF` | 4 KiB editor buffer |
| `$6000-$61FF` | Command/state and application-label cache |
| `$6700-$67FF` | Recovery journal workspace |
| `$6800-$77FF` | Recovery flash staging |
| `$7800-$7EFF` | Recovery worker, state, console and vector services |

RAM transfers stay within application RAM `$0200-$66FF` and must avoid the
running utility, editor and state. Use editor commands to access its buffer.
On 65C816 the utility requires emulation mode with D/DBR/PBR zero.
Use the beta4 build's matching utility: startup checks the recovery-core
compatibility ID and refuses a mismatched core.

Run `make -f Makefile.beta4` to build the standalone utility alongside beta4.
The ZIP contains `str8n-bank-maint-1.5-2000.s19`; the manifest records its entry,
inclusive end, length and hash. No bank backup is part of that kit.
