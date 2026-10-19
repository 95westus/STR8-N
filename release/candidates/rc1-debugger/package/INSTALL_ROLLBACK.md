# DBG1 preserving installation, smoke test and rollback

Use this procedure for the generation-50 candidate in this extracted archive.
Only RAM debugging on 65C02 and 65C816 **E=1** is supported. Native applications
and debugging are excluded. The existing reset CPU detector is unchanged.
The procedures below are operator-run; unpacking/verifying this package does
not access a board. Keep other serial users, soaks and RTC jobs stopped.

## 1. Verify the package and select the exact board

From the extracted package root in PowerShell:

```powershell
python verify_package.py
python -m pip install -r requirements.txt
$pkg = (Resolve-Path './install').Path
$portName = 'COM_REPLACE_ME'
$usbSerial = 'USB_SERIAL_REPLACE_ME'
$boardId = 'BOARD_ID_REPLACE_ME'
$trialRoot = 'C:/REPLACE_ME/dbg1-private-new-run'
$coordRoot = 'C:/REPLACE_ME/shared-serial-coordination'
```

Replace every placeholder and use a new private trial directory outside the
package. Use the same coordination directory as any other board tools. In
the STR8-N source checkout, that is its `output/qualification/serial-coordination`
directory. The transport checks COM port, USB serial and the board's own ID;
do not guess a port. Keep all capture/plan/receipt subdirectories new.

Have an independent flash programmer available. This update replaces B3:F;
an interrupted F erase/program can prevent boot and software recovery. B0 is
preserved but is not assumed to contain a working recovery monitor.

The admitted source is coherent **rc1 generation 49**, with exact matching
existing firmware sectors and an erased B1:A sector, plus a clean C/D journal
with space for a reservation record. Unknown sources or occupied B1:A refuse.
Both monitors must be valid. 2604/2609 already run generation 50 and should not
be installed again with this route. No time, trim or offset setter is needed.

## 2. Take fresh backups and derive the install plan

At an already-idle B3 prompt:

```powershell
python "$pkg/board_link.py" capture --port $portName --usb-serial $usbSerial --board $boardId --expected-generation 49 --coordination-root $coordRoot --out "$trialRoot/before"
python "$pkg/board_plan.py" install --capture "$trialRoot/before" --out "$trialRoot/install"
python "$pkg/board_plan.py" verify --plan "$trialRoot/install"
```

Capture reads all four complete flash banks independently twice, compares
the reads and archives application RAM twice-checked at `$0200-$64FF` or
`$0200-$66FF` as discovered. Keep `before` and the original `install` directory
for rollback. Inspect `plan.json`, source/expected hashes, preference and erase
order. A plan is for these exact captured bytes and identity, not another board.

Seven firmware sectors change: B1:A/E/F and B3:A/B/E/F. The transaction also
stages/activates the existing journal, for nine 4 KiB transfers/erases and one
reservation-record append. It preserves B0/B2, B1:9, other data, settings and
the original monitor preference, advancing generation to 50 and wear history.

## 3. Execute once, then physical RESET

```powershell
python "$pkg/board_link.py" execute --experimental --plan "$trialRoot/install" --port $portName --usb-serial $usbSerial --board $boardId --coordination-root $coordRoot --out "$trialRoot/install-receipt"
```

Keep power on and do not reset during the transaction. Require a passed receipt,
nine completed transfers and **MIGRATION VERIFIED; PRESS PHYSICAL RESET**.
The device checks all source bank fingerprints before mutation, checks each
transfer and compares programmed bytes. If refused/failed or timed out, preserve
power and logs and inspect durable state; do not repeat a stale plan or reset
automatically. Interrupted-write recovery for DBG1 is not qualified here.

After verified completion, press physical RESET on this board only. The RAM
installer is halted and needs that reset. Wait for B3; `VERSION` must report
both MON A/B valid at `00000032` (50 decimal). The version/ASM titles remain
`2.0rc1` / `ASM 0.5`. Record the active slot and original preference.

## 4. Verify all flash before changing preference

```powershell
python "$pkg/board_link.py" verify-flash --plan "$trialRoot/install" --port $portName --usb-serial $usbSerial --board $boardId --expected-generation 50 --coordination-root $coordRoot --out "$trialRoot/flash-check"
```

This compares all four banks against the transaction targets. Do it before
any preference change, since P appends a journal record. Inspect any mismatch;
boot-time persistent housekeeping must not be silently accepted as a match.

## 5. Check 816 E=1 and smoke-test both slots

For a 65C816 board, boot normally and verify E=1 before and after each slot's
smoke. The included `diagnostics/emulation/mode.s19` is the exact RAM observer
used on 2609. At the idle monitor, enter L, send the S19 as text, wait for
`Entry 2000`, then enter `G 2000` and `D 2440 244D`. The first six bytes must be
`16 01 00 00 00 00`: CPU 816, prior E=1, DBR/PBR/direct page zero. Byte at
`2446` masked with `0C` must equal `04` (IRQ disabled, decimal clear).
The observer uses SEC/XCE, forcing E=1 while recording prior E; it cannot
enter native mode. A different result needs inspection before smoke testing.
It and the smoke programs borrow RAM; restore the archive after all tests.

Run the smoke in the current slot, using a distinct output name for each:

```powershell
python "$pkg/board_link.py" smoke --port $portName --usb-serial $usbSerial --board $boardId --coordination-root $coordRoot --out "$trialRoot/smoke-first-slot"
```

The runner checks saved registers and four scenarios: automatic BRK/shared
D/M/U/C/S/N; all eight persistent breakpoints twice, ninth refusal and clears;
X cleanup with eight entries; BRK 80 query. It checks lifecycle bytes and
original program bytes after every HOLD/X. Expect 16 breakpoint hits per slot.
For manual command-by-command checks use `install/smoke/scenarios.json` and
[the original procedure](install/BOARD_TEST.md#manual-smoke-procedure).

At the monitor, use `P B` if the first slot was A, or `P A` if it was B, then
`J3` for the tested software restart path (or physical RESET). Check VERSION
and `D 7D30 7D30`: A=`A0`, B=`B0`. Repeat the E=1 observations on the 816 and
the smoke with `--out "$trialRoot/smoke-second-slot"`. Require both reports
passed. Native-mode instruction experiments are outside this procedure.

Restore the original preference with P and J3, and confirm VERSION again.
Record RTC control/trim status before final RAM restoration if comparing it
with a pre-install observation. CLOCK itself borrows application RAM.

## 6. Restore and verify original application RAM

```powershell
python "$pkg/board_link.py" restore-ram --archive "$trialRoot/before" --port $portName --usb-serial $usbSerial --board $boardId --expected-generation 50 --coordination-root $coordRoot --out "$trialRoot/RAM-restored"
```

Require `RAM_restoration_host_verified: true`. This restores bytes without
executing the archived program; it does not resume interrupted CPU/device
state. Do not run CLOCK, ASM or another RAM program afterward if preserving
those restored bytes. A restoration failure needs inspection before reuse.

## 7. Capture the final state and prepare rollback offline

```powershell
python "$pkg/board_link.py" capture --port $portName --usb-serial $usbSerial --board $boardId --expected-generation 50 --coordination-root $coordRoot --out "$trialRoot/after"
python "$pkg/board_plan.py" rollback --capture "$trialRoot/after" --original-plan "$trialRoot/install" --out "$trialRoot/rollback"
python "$pkg/board_plan.py" verify --plan "$trialRoot/rollback"
```

Compare the before/after application RAM archives byte for byte. Retain all
receipts. Preparing rollback makes no board changes. If the board changes
afterward, take another fresh capture and derive a new rollback plan/output;
do not execute an old plan against a changed board.

## 8. Execute rollback only when you intend to remove DBG1

For a still-working B3 monitor and a current verified rollback plan:

```powershell
python "$pkg/board_link.py" execute --experimental --plan "$trialRoot/rollback" --port $portName --usb-serial $usbSerial --board $boardId --coordination-root $coordRoot --out "$trialRoot/rollback-receipt"
```

After the verified nine-transfer message, physical RESET, then:

```powershell
python "$pkg/board_link.py" verify-flash --plan "$trialRoot/rollback" --port $portName --usb-serial $usbSerial --board $boardId --expected-generation 49 --coordination-root $coordRoot --out "$trialRoot/rollback-check"
python "$pkg/board_link.py" restore-ram --archive "$trialRoot/before" --port $portName --usb-serial $usbSerial --board $boardId --expected-generation 49 --coordination-root $coordRoot --out "$trialRoot/rollback-RAM-restored"
```

Both monitors must report `00000031 VALID`. Rollback restores the seven original
firmware sectors, including the erased B1:A sector, and original preference.
It preserves current settings/data outside those sectors and advances current
wear history. Never replay the old whole-bank C/D images to reset counters.
Do not run a BRK smoke after removing DBG1. Rollback was model-tested and
planned/verified on both boards, but not executed on hardware in these trials.

If the board cannot reach B3, this software rollback route is unavailable.
Preserve all original backups, current readable flash and receipts for an
independent-programmer recovery assessment. Do not treat the development BIN
or a single F byte edit as a preserving DBG1 installer or rollback.
