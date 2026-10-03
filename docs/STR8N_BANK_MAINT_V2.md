# STR8-N bank maintenance 1.0

Utility version: **1.0**, independent of the **2.0a24c1** host firmware.
The RAM layout below is a24c1-compatible; proposed a24c2 addresses require
a future utility update. See the [a24c1 manual](STR8N_V2_A24C1_MANUAL.md).

Build: `make bank-maint-v2`. CPU/flash model checks:
`make bank-maint-v2-check`.

Output: `BUILD/bank-maint-v2/str8n-bank-maint-2000.s19`.
Load through the v2 monitor's RAM S19 loader (`L`), then enter `G 2000`.
The S9 entry is also `$2000`. This is a RAM utility; no `.a` is produced.

Staging is built into the utility. Load only the main S19 and enter
`G 2000`. `S 8` or `S 9` prepares one FF-padded 4 KiB program block in
the editor buffer, replacing its previous contents without writing flash:

| Stage command | Flash destination | Contents |
| --- | --- | --- |
| `S 8` | B1:8, `$8000-$8FFF` | Program originally at `$2000-$2FFF` |
| `S 9` | B1:9, `$9000-$9FFF` | Remaining program from `$3000`, then FF padding |

At `BM>` issue `S 8`, then `W 1 8` and confirm `Y`;
then `S 9`, `W 1 9` and confirm `Y`. Each W verifies the whole sector.
B1:A-F are not needed for this archive. This archive retains the program's
RAM addresses; it must be restored to `$2000` before execution. It has no
B1 reset loader and cannot be started with `J 1`.

Run from an initialized v2 monitor with its fixed RAM console ABI. Bank contents depend on the connected board; identify the board and inspect
its banks before choosing scratch sectors. The tool permits maintenance of
all four banks and does not mark retained firmware banks read-only. It does not run directly under
WDCMON. On 816 use emulation mode, D=0, DBR=0 and PBR=0, as required by v2.
No RTC, SPI SRAM or crypto device is required.

## Commands

All numbers are hexadecimal; ranges include both endpoints. A space is
`R` for RAM or `0`, `1`, `2`, `3` for a flash bank. Flash addresses `8`–`F`
are shorthand for sectors: a source `8-A` means `$8000-$AFFF`, and a
destination `A` means `$A000`. Explicit addresses allow byte ranges.

| Command | Meaning |
| --- | --- |
| `M` | Bank map: E = all FF, U = used, plus reset vectors |
| `E bank first[-last]` | Erase one sector or a range, from 8 through F |
| `C src range dst start` | Copy RAM/RAM, RAM/flash, flash/RAM, or flash/flash |
| `V src range dst start` | Compare; report match or first encountered destination mismatch |
| `R src range` | Read up to 4 KiB into the editor buffer |
| `S 8` / `S 9` | Stage a block of the running program in the editor buffer |
| `W dst start` | Write and verify the entire current buffer |
| `D [offset[-end]]` | Hex dump the buffer, or selected offsets |
| `P offset byte ...` | Patch bytes in the buffer |
| `F offset[-end] byte` | Fill buffer offsets with one byte |
| `N length byte` | Create a buffer of 1–1000 hex bytes with a fill value |
| `K` | Buffer CRC-16/CCITT-FALSE, polynomial 1021, initial FFFF |
| `J bank` | Explicit software boot using the selected bank's reset vector |
| `Q` | Return to the original monitor, unless its F sector was targeted |
| `?` | Help |

For example, `R 2 F` reads B2:F into the editor without writing flash.
`D FD0-FDF` displays those buffer offsets. `P FD0 01 02` changes only the
buffer. `W 1 F` writes that buffer to B1:F after confirmation.
`C 0 8-E 1 8` copies B0 sectors 8–E to B1 sectors 8–E; destination data
is replaced. `E 1 A-C` erases B1 sectors A–C after confirmation.

## Write behavior

**WARNING - power failure during flashing can be dangerous.** Loss of power
during flash erase, copy or buffer write can corrupt the destination. If it
contains firmware or boot vectors, the board may become unbootable and need
an external flash programmer for recovery. Power-loss recovery and automatic
rollback are not guaranteed. Keep power stable and retain a recovery backup.
Do not disconnect USB/power or press RESET/NMI until verified completion.

Every erase, copy, and buffer write displays the operation and normalized
destination range and requires `Y` followed by Enter. Any operation touching
**B3:F** additionally requires `B3F` followed by Enter. Both confirmations
happen before any destination change, including when a range ends in F.
Reading B3:F does not need confirmation.

Flash writes build a complete 4 KiB desired sector in RAM, preserve bytes
outside the destination range, erase only when needed, program, and verify
the complete sector. An already erased erase target needs no physical erase.
Overlapping copies work in the appropriate direction, including within the
same flash bank. RAM writes are read back after each byte.

Ctrl-C cancels input or stops copying between flash sector operations.
Completed sectors stay changed. Flash failure stops the range immediately;
the affected sector may be incomplete. There is no transaction rollback
or power-loss recovery. The editor buffer survives flash write failure so
`W` can be retried after the underlying problem is addressed.

After targeting the resident monitor's F sector, `Q` is blocked even if a
later write repairs it. The utility and console continue in RAM. Use an
explicit `J bank` to boot known firmware. J checks for a ROM-range reset
vector other than FFFF; that is not an image integrity check. A software
boot does not pulse the physical RESET pin. Do not reset/power-cycle after
erasing the boot bank until it contains bootable firmware. NMI safety while
banking or erasing hardware vectors is not established by these CPU tests.

Editor changes remain buffered until `W`; `R`, `N`, and `S` replace the previous
buffer, and `Q`/`J` discard it. Buffer offsets start at zero. The complete
patch/fill command is validated before any buffer change.

## RAM layout and limits

| Area | Use |
| --- | --- |
| `$2000` through manifest `end - 1` | Utility code and constants |
| `$5000-$5FFF` | 4 KiB editor buffer |
| `$6000-$61FF` | Command line and utility state |
| `$6900-$78FF` | Flash sector staging |
| `$7900` upward | Existing v2 worker, state, ABI, vectors and hardware |
| `$C0-$C9`, core scratch | Utility pointers and worker scratch |

RAM copy/read/write ranges must lie within `$0200-$68FF` and avoid the
utility image and `$5000-$61FF`. The same exclusions apply to RAM sources
to prevent streaming from changing scratch memory. Access the editor via
its commands. Lines are limited to 79 characters; overflow is rejected.

## Validation and next features

The executable is tested in the repository's 65C02 CPU, banked flash, and
console model. Bank Maintenance 1.0 also passed scoped physical-board
editor, CRC, four-direction copy, staging, erase and protection checks on
C02 board 2205 and 816 board 2609; see the
[2026-10-03 regression record](STR8N_V2_A24C1_REGRESSION_ACCEPTANCE_2026-10-03.md).
Full before/after bank readbacks verified scratch cleanup and preservation.
Fault recovery and the broader stress matrix remain outside that record.
The build manifest and test results identify the exact S19 hash tested.

Useful next additions, in priority order:

1. S19 export/import of the editor buffer for host backups and sector restore.
2. Per-sector CRC listings and a bank comparison report for backup audits.
3. Byte/text search and ASCII alongside the editor's hex display.
4. Optional bank labels and write locks, so B0 WDCMON/EDU and B2 alpha23
   can be protected until explicitly unlocked.
