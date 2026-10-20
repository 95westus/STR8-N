# Separate v1g DBG1 offline-prepared board kit

This separate BRK $82/$84 fix has offline qualification only. It has not been
installed or soaked on either board. The current v1f soak and staged archive
remain unchanged. Promotion is held. Do not run this kit against soaking boards.


This is a preparation and test package, not a hardware acceptance receipt.
No board was accessed while preparing it. Use a 65C02 board first, then repeat
on a 65C816 board booted normally into E=1. Native applications/debugging are
outside scope. The existing reset CPU detector remains as in rc1.

## What gets installed

| Bank/sector | Contents |
| --- | --- |
| B1:A000-AFFF | Debugger, 3975 bytes of code plus CRC; 119 bytes free |
| B1:E000-FFFF | ASM with explicit BRK signature support and matching shared opcode table |
| B3:A000-BFFF | MON A/B headers with automatic BRK entry and HOLD cleanup |
| B3:E000-FFFF | Resident S/R/T guards, bootstrap and copied RAM worker |
| B2:8000-8FFF, D000-DFFF | MAINT compatibility comparisons and matching utility CRC |
| B3:C000-DFFF | Wear-accounted reservation/staging/activation of the existing journal |

Nine firmware sectors change. Eleven 4096-byte transfers accompany one small
reservation-record write. The standalone RAM installer is the existing rc1
transaction engine; it does not call the candidate's protected flash API.
B0, B1:9000, applications, RTC banner, bindings and all other flash bytes
are preserved from the capture. Settings, EDU mode and the preferred monitor
are retained, with the preferred generation changed to 50. Wear counts advance.
The default-filled 96 KiB development `firmware.bin` is not a preserving updater;
do not program it over a working board.

The source must match rc1 generation 49 in all eight replaced existing firmware
sectors, with B1:A erased. The planner refuses an occupied debugger destination,
assumed-erased captures, bad/torn journals, identity mismatches and changed data.
It also needs an erased record in the current journal sector. A refusal requires
inspection and a fresh plan; do not force it or use a beta4/WDC conversion route.

## Preparation

Run from the repository root with Python 3.10+, WDC tools and the test dependencies.
The prepared local package is `BUILD/rc1-debugger-v1g-boardtest-r1`.

```text
python release/candidates/rc1-debugger-brkfix-r1/prepare_board_test.py --build BUILD/rc1-debugger-v1g --out BUILD/new-debugger-boardtest
```

Stop other serial users, close terminal sessions and keep any RTC/soak jobs
stopped. The tools share the repository's serial coordination lock. Use the
board's explicit COM port and USB serial, never a guessed port. Board transport
requires Windows, pyserial and a physical rc1 B3 prompt after reset. It makes
no automatic reset or clock/trim changes. Have an independent flash programmer
available: this update includes F, and an interrupted F erase/program can prevent
normal boot and software recovery. B0 is preserved but is not assumed to contain
a working recovery monitor.

Use fresh private directories for every capture, plan and receipt. In PowerShell:

```powershell
$pkg = 'BUILD/rc1-debugger-v1g-boardtest-r1'
$port = 'COM_REPLACE_ME'
$usb = 'USB_SERIAL_REPLACE_ME'
$board = '2604' # Replace with the selected board's actual identity.
python "$pkg/board_link.py" capture --port $port --usb-serial $usb --board $board --expected-generation 49 --out BUILD/dbg-before
python "$pkg/board_plan.py" install --capture BUILD/dbg-before --out BUILD/dbg-install
python "$pkg/board_plan.py" verify --plan BUILD/dbg-install
```

Capture reads each full flash bank independently twice and archives the current
application RAM range (`0200-64FF`, or `0200-66FF` when released). Store the original
capture and install plan safely. The planner uses the live settings and firmware
bytes from that capture, not historical board images. Review `plan.json`, its
source/expected bank hashes and erase order before execution.

## Install and verify

The following commands are operator-run experimental steps. Preparation does
not execute them. Leave the board powered and do not reset during a transaction.

```powershell
python "$pkg/board_link.py" execute --experimental --plan BUILD/dbg-install --port $port --usb-serial $usb --board $board --out BUILD/dbg-install-receipt
```

Require `MIGRATION VERIFIED; PRESS PHYSICAL RESET`, eleven transfers and a passed
receipt. The device checks all source banks with FNV32 before the first write
(the host binds captures/files with SHA256), validates
each transfer and compares programmed bytes. If it refuses, times out or reports
failure, keep power on, retain logs and inspect; do not repeat a stale plan or
reset automatically. A partial transaction needs a new recovery assessment.

After verified completion, press physical RESET and wait for B3. Then:

```powershell
python "$pkg/board_link.py" verify-flash --plan BUILD/dbg-install --port $port --usb-serial $usb --board $board --expected-generation 50 --out BUILD/dbg-flash-check
python "$pkg/board_link.py" smoke --port $port --usb-serial $usb --board $board --out BUILD/dbg-smoke-a
```

Verify VERSION reports both monitors valid at `00000032` (50 decimal). The firmware
version text still reads `2.0rc1`; generation and hashes identify this experiment.
The automated smoke checks the actual saved registers, not just the prompt.
It overwrites a small RAM test program and `$0600`, so restore the archived RAM
after testing. Installation also stages its RAM image in application RAM.

To repeat on the other monitor, use monitor `P B` (or `P A`) and physical RESET,
then run `smoke` into a new receipt directory. Record the active monitor with
`D 7D30 7D30`: A=`A0`, B=`B0`. Changing preference appends journal state, so run
the exact whole-flash comparison before changing preference. This comparison is
strict: if boot-time housekeeping changed persistent metadata, retain and inspect
that difference rather than accepting it automatically. Rollback uses a
fresh capture and accepts that later valid journal state.

## Manual smoke procedure

`smoke/scenarios.json` is the authoritative ordered command/expected-result list.
Its linked addresses come from `smoke/symbols.json`. Each test starts at an idle
B3 monitor: `L`, send the indicated `.s19` as text, wait for `Entry 0200`, then
`G 0200`. Load each test separately. These images contain common instructions
only and never switch CPU mode.

1. Load `smoke/steps.s19`. Its `BRK 01` must enter `DBG>` automatically. Check
   A=`11`, X=`22`, Y=`33`, SP=`FF`, and PC=`STEP_POINT`. Run the listed D/M/U
   probes; M writes `$A5` to `$0600`. `S` executes INX, enters JSR, steps two
   INX instructions and RTS, restoring SP from `FD` to `FF`. `N` executes INY,
   then steps over a second JSR. X becomes `27`, Y=`34`; `C` stops after
   `BRK 02`, and another `C` returns through HOLD to B3.
2. Load `smoke/breakpoints.s19`. At its first stop, set B at BP0 through BP7,
   and list all eight with `B`. `B 0600` must fail with `?` and retain the eight
   existing entries. Continue 16 times: BP0..BP7 appear in order twice, with
   X=`00..0F` before the respective INX; Y=`00` on pass one and `01` on pass two.
   Each continue rearms the previous breakpoint. D must show all eight original
   `E8` bytes while paused. Another C reaches the final BRK with X=`10`, Y=`02`.
   Clear BP3, verify seven remain, `BC *`, verify none remain, and C to HOLD.
3. Reload the breakpoint image, set all eight again and use `X` to abort. B3 must
   return and lifecycle bytes `$7BFC-$7BFD` must both be zero. Read back the loaded
   program and compare with its S19 bytes: no patches may remain. The automated
   runner performs this program readback after every HOLD/X.
4. Load `smoke/query.s19`. `BRK 80` must return without stopping; `BRK 03` then
   stops with A=`01`, X=`10`, Y=`04`. C returns to B3.

Keep serial logs and `report.json` for both monitor slots on both CPUs. These
software breakpoints persist through continue/step, not HOLD, X or reset.

## Restore application RAM

After each board's test (or after rollback), load the original archive and verify
it on the host without executing the archived program:

```powershell
python "$pkg/board_link.py" restore-ram --archive BUILD/dbg-before --port $port --usb-serial $usb --board $board --expected-generation 50 --out BUILD/dbg-ram-restored
```

Use generation 49 after rollback. If the original archive includes through 66FF,
the monitor must still expose that range; restoration refuses a now-owned service
area rather than overwriting it. RAM bytes are restored; an interrupted running
program's CPU/device state is not resumed.

## Roll back to the original rc1 firmware

At B3 with the candidate still working, capture it afresh. Do not restore the old
C/D bytes or program the original whole-device image over new wear records.

```powershell
python "$pkg/board_link.py" capture --port $port --usb-serial $usb --board $board --expected-generation 50 --out BUILD/dbg-after
python "$pkg/board_plan.py" rollback --capture BUILD/dbg-after --original-plan BUILD/dbg-install --out BUILD/dbg-rollback
python "$pkg/board_plan.py" verify --plan BUILD/dbg-rollback
python "$pkg/board_link.py" execute --experimental --plan BUILD/dbg-rollback --port $port --usb-serial $usb --board $board --out BUILD/dbg-rollback-receipt
```

After the verified message, physical RESET, then:

```powershell
python "$pkg/board_link.py" verify-flash --plan BUILD/dbg-rollback --port $port --usb-serial $usb --board $board --expected-generation 49 --out BUILD/dbg-rollback-check
python "$pkg/board_link.py" restore-ram --archive BUILD/dbg-before --port $port --usb-serial $usb --board $board --expected-generation 49 --out BUILD/dbg-rollback-ram
```

Rollback restores the nine original firmware sectors, including the originally
erased B1:A sector. Current settings and current data outside those sectors are
preserved; the original monitor preference is restored at generation 49. The
journal sequence and erase counts advance again. Both monitors must report
`00000031 VALID`. Do not execute a BRK test after rolling back.

For a board that cannot reach B3, this normal rollback command is unavailable.
Preserve the original four `source-bN.bin` files, current readable flash and all
receipts for programmer recovery. The original C/D files are forensic backups,
not an instruction to reset wear history. Interrupted-write and programmer
recovery for this new candidate are not claimed as qualified by this package.

