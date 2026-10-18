# Linux full-system migration quick start — rc1 candidate

One firmware set supports 65C02 and 65C816 emulation runtime. This package's
live routes require **erased B0/B1/B2** and the exact SXB6 65C816 WDCMONV2 or
published STR8-N v2.0b4 source in B3. The RAM tool verifies all four complete
bank preimages before any erase and refuses occupied/unknown banks. It installs
MON A/B, recovery/core, all providers/apps, CLOCK, ASM, UCHESS and S/R/T code.
It does not erase B0 or prepare your source firmware: those are separate,
explicitly authorized provisioning operations. Do not use the raw programmer
image as an upgrade.

## Setup

Extract the entire package into a new directory. Keep `migration`, `firmware`,
`docs` and `uchess-source` together. Use Python 3.10+ and pyserial 3.5:

```sh
chmod +x ./*.sh
python3 -m pip install pyserial==3.5
./rc1.sh verify
./rc1.sh status
python3 -m serial.tools.list_ports -v
```

The optional `STR8N_PYTHON` environment variable selects your interpreter.
Close terminal/debugger sessions owning the board port. Use the exact USB
serial reported for that selected port; do not use another board to work around
an identity/access error. Linux additionally requires normal access to its
serial device. No board is opened during `verify`, `status` or plan preparation.

## Original WDCMONV2 to complete rc1

Replace the example port, USB identity, label and private output directory:

```sh
./wdcmonv2-to-rc1.sh --port /dev/ttyUSB0 --usb-serial YOUR-USB-SERIAL --board my-board --out wdc-rc1-backup --empty-banks --accept-unknown-wear-history --no-host-readback
```

The tool opens only that port, arms the debugger and asks for physical RESET.
It independently captures B3 twice, archives application RAM, and plans the
complete system. B0/B1/B2 are explicitly **assumed erased**, not falsely labeled
as read: the RAM installer proves those preimages before writing. No WDCMONV2
binary is included in the package; its original source stays only in your
private backup. Unknown historical wear is acknowledged as a **new tracked
baseline**, not zero lifetime erases. Only the exact SXB6 65C816 stock profile is admitted live; SXB2 recognition
is offline-only. The resulting firmware supports both CPUs.

Type `INSTALL RC1` at the explicit installation confirmation. Keep power stable.
Press physical RESET again **only when the installer reports device verification
complete**, then press Enter in the host tool. The tool checks rc1 boot and
UCHESS discovery and loads the saved application RAM archive without executing
it. Do not run WDC's EDU menu or RAM tests during this workflow.

## Published beta4 to complete rc1

Use the same explicit identity selection on the idle beta4 monitor:

```sh
./beta4-to-rc1.sh --port /dev/ttyUSB0 --usb-serial YOUR-USB-SERIAL --board my-board --out beta4-rc1-backup --empty-banks --no-host-readback
```

This is the published generation-13 beta4 B3 source, with erased B0/B1/B2.
The tool preserves its configuration and conservative wear history, fills the
provider/application banks, installs both rc1 monitors and UCHESS, and follows
the same verified-halt/physical-RESET/boot/RAM-restoration sequence.

`--no-host-readback` skips additional installer/RAM-restoration readbacks; source
acquisition and on-device full-bank guards/verification remain mandatory.
Omit it to request extra host RAM readbacks and RAM-restoration verification.
A loader acknowledgement alone is never reported as host-verified restoration.
The tools issue no clock/time/trim/offset setters and do not write EEPROM/SRAM.
A prior native-WDC test lost RTC continuity; source startup and a corrected
host-stack fault remain possible causes. Full RTC-preservation qualification
is not claimed. Save your existing clock/trim information before migration.

## Recovery and local file review

Keep the complete private output, especially capture, plan, original images,
RAM archive, transfers and receipts. Never include it in a public release.
Verify a saved plan without opening a port:

```sh
./rc1.sh verify-plan --plan beta4-rc1-backup/plan
```

For interrupted work with an accessible STR8-N/rc1 monitor, acquire a fresh
repeated full-bank capture, then prepare or execute matching recovery:

```sh
./rc1.sh capture --port /dev/ttyUSB0 --usb-serial YOUR-USB-SERIAL --board my-board --out current-backup
./rc1-recovery.sh forward --plan beta4-rc1-backup/plan --capture current-backup --out recovery-plan
```

Add `--port`, `--usb-serial`, `--board` and optionally `--no-host-readback` to the
recovery command to execute it, after its `RECOVER RC1` confirmation. An exact
completed target yields a no-write receipt. Use your WDC-origin saved plan for
WDC forward recovery. Early vendor-source cuts without a valid rc1 monitor and
tracked journal refuse serial recovery; retain private backups and use an
external programmer. Never force an arbitrary partially programmed state.
`restore-beta4` is for a fully completed beta4-origin target only; it preserves
newer conservative wear counts. It is not vendor restoration.

Native 816 applications/testing, ACIA and crypto remain deferred. The accepted
existing startup detector exception remains. This candidate is not a fully
release-qualified firmware; long soak/RTC and broader recovery gates remain
separate. See [migration/recovery](MIGRATION_RECOVERY.md), [all manuals](README.md)
and [firmware mapping](FIRMWARE_CONTENTS.md).
