# STR8-N v2-alpha2 monitor milestone

Adds B/D/M/G to the bank-independent boot baseline. One binary serves all
flash overlays and both CPUs, with the 816 in emulation mode. No physical
board installation or testing has been performed. F/L/I, configuration, and
autostart remain planned work; unknown commands cannot program flash.

## Commands

All numeric input is hexadecimal without a $ or 0x prefix. Addresses use
one to four digits, byte values one to two. Input is case-insensitive; tabs
are treated as spaces. B/J use compact syntax with exactly one bank digit.

| Command | Behavior |
| --- | --- |
| `?` | Print compact command help. |
| `B0`-`B3` | Change the selected target bank. Print Bn; the prompt continues executing in the resident bank. |
| `D addr [end]` | Display an inclusive range, sixteen bytes per row. With no end, display sixteen bytes. |
| `M addr bytes...` | Preflight the entire RAM edit, then write consecutive bytes. No writes occur if any byte/address is invalid. |
| `G addr` | Select the target bank and jump to the explicit address. Reset the stack, disable IRQs, clear decimal mode, release LEDs; no expected return. |
| `J0`-`J3` | Boot a bank through its RESET vector. On invalid/erased vector, restore the resident bank and report Bad vector. |

Example session:

```text
B1
D 8000 801F
M 0200 A9 41 60
D 0200 0202
```

The sample bytes are for inspection, not a standalone G program: G supplies
no RTS return address. A program launched with G must arrange its own exit.
At the resident bank, `G F003` enters the monitor prompt and preserves user
handler pointers. A different selected bank may contain unrelated code at
$F003, so select the resident bank first. The 816 software-entry contract
remains E=1, direct page $0000, DBR=$00, PBR=$00.

## Bounds and input behavior

- D reads RAM directly and flash through a RAM worker, restoring the resident
  bank before printing. It rejects any range intersecting $7F00-$7FFF before
  reading target data. RAM belonging to the monitor is live state, not a
  frozen snapshot; stack and scratch values can change while displayed.
- `D FFF0` and `D FFFF FFFF` work; `D FFF1` rejects default-length wraparound.
  Reversed ranges and extra arguments fail without a partial dump.
- M accepts application RAM $0000-$00DF and $0200-$68FF, plus documented
  pointer slots $7E00-$7E09 and $7E10-$7E19. Stack, monitor scratch/code,
  other vector-page locations, I/O, and flash are protected.
- M rejects an edit crossing into protected storage before modifying even
  its valid prefix. The selected flash bank does not change low RAM mapping.
- G permits ordinary application RAM and $8000-$FFFF in the selected bank.
  It rejects stack, scratch, vector storage, and I/O. Explicit G does not
  authenticate code or require a RESET-vector/directory record.
- Lines are limited to 32 characters. Backspace/DEL edits input; Ctrl-C
  cancels line entry. Overflow drains the rest of the line and reports
  `Line too long`. Unexpected control/non-ASCII bytes reject the whole line
  with `Bad input`; they are not silently removed to form a different command.
- During M's brief commit loop, an NMI uses RTI rather than the user pointer,
  avoiding a partially published two-byte pointer. That NMI is not replayed.
  IRQs are already disabled at the monitor. Handler routines must preserve
  the registers/workspace they borrow. G does not alter installed pointers.

Long D ranges currently run to completion: Ctrl-C cancels line entry, not an
active dump. Native 816 handler execution, early-reset NMI, and interrupts
while a different bank is visible still require hardware qualification.

## Build and validation

```powershell
make v2-check
```

This builds with WDC02AS/WDCLN and runs both `test_v2_boot.py` and
`test_v2_monitor.py` using py65. The v1.35 roundtrip portion requires the
existing v1.35 top binary/map, as documented in the boot milestone.
Outputs are separate from alpha1 and all v1 artifacts:

- `BUILD/v2-alpha2/str8n-v2-alpha2-e000-ffff.s19`
- `BUILD/v2-alpha2/str8n-v2-alpha2-e000-ffff.bin`
- `BUILD/v2-alpha2/build.json`
- `BUILD/v2-alpha2/test-results.json`
- `BUILD/v2-alpha2/monitor-test-results.json`

The image uses 1414 resident bytes including 105 bytes of worker code and
57 bytes of interrupt entry code. There are 2650 bytes free before the
32-byte hardware-vector region. The RAM map remains provisional.

Before rebuilding, the tool invalidates this milestone's previous named
images/test receipts so a failed build cannot leave them looking current.
An optional full-bank image is regenerated only with `--full-bank`; a normal
build removes any old full-bank output from this milestone.

Host tests cover bank/console handoffs, all 65,536 M address decisions,
whole-command edit rejection, row/page/end-of-memory boundaries, a complete
32 KiB flash dump, RAM display overlapping the scratch buffer, malformed
input, NMI during pointer publication, and software reentry with dirty scratch.
They also retain the actual v1.35 launch/return tests (long delays bypassed).
No simulated result is a claim of board timing or native 816 execution proof.

## Installation through v1.35

Preserve a disposable Bank 0-2. Use v1.35 I with that bank and range E-F,
then send the alpha2 E-F image and complete v1's confirmations. This replaces
both sectors, including any old payload in sector E; autostart configuration
is erased/disabled. Use v1's matching J command to launch v2. J3 returns to
v1.35; send S during its existing selector window to hold there.

Validate the image on the host without board access:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/compose_str8n_install_s19.ps1 -PayloadS19Path BUILD/v2-alpha2/str8n-v2-alpha2-e000-ffff.s19 -PayloadStart 57344 -PayloadEndExclusive 65536 -Bank 0 -S19Path BUILD/v2-alpha2/validated-bank0.s19
```

For v1 incomplete-install recovery only, `python tools/build_v2.py --full-bank`
also emits a dense 8-F image. It pads everything below $E000 with $FF and
replaces the entire bank when installed. Run both host test scripts after
that build to produce matching test receipts.
