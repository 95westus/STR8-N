# Migration to STR8-N 2.0b4

The release supplies two entry points to the same beta4 RAM installer:
stock WDC monitor to STR8-N, and an existing STR8-N a24-or-later monitor
to beta4. The stock monitor remains on the user's board until replaced;
no stock firmware or vendor source is distributed.

## Supported sources

The stock route queries the board's serial identity and asks the operator
to confirm W65C02SXB or W65C816SXB. It uses the existing binary memory
protocol to read B3 and load/verify the RAM installer. It refuses a B3 F
sector already bearing the STR8-N signature.

The stock port is opened with RTS/CTS and DTR deasserted before RESET.
The launcher arms read-only sync/identity probing for 60 seconds, then asks
the operator to press and release RESET while the probe is active. It
connects automatically. This also handles retained images that start a
normal program unless the debugger connects during startup. Startup output
and incomplete identity replies are handled before any RAM load or flash
write. If the window expires, leave the backup intact and restart the
launcher; it has not issued a memory-write or execute command.

The STR8-N route accepts the exact a24 F image, a24c1/beta1 outside its
configuration pocket, the known beta2 image, and integrity-checked recovery
format 1 layouts used by the subsequent recovery/beta monitors. A legacy
F image is checked by SHA256. Recovery layouts require a valid monitor-slot
CRC, a matching self-CRC32 core compatibility ID, and valid configuration
journal data. Unknown/corrupt layouts are refused before installation.
This is support for the implemented a24-and-later layouts, rather than
permission to flash arbitrary firmware bearing a version string.

The STR8-N board must be at an idle monitor prompt. It must use its FT245
USB console; close other programs holding the serial port. This launcher
does not operate from a running RAM program or the independent `REC>` menu.
Resolve that state using the current firmware before starting it.

## Launch and validate

Windows: run the appropriate `.ps1` with PowerShell. Linux: invoke the
matching `.sh` using `sh`. Both delegate to the supplied Python tool and
require Python 3 plus pyserial. No assembler/linker is required by users.

Offline file checks open no serial port:

```powershell
.\MIGRATE-WDC-TO-STR8N.ps1 -ValidateOnly
.\MIGRATE-STR8N-TO-B4.ps1 -ValidateOnly
```

```sh
sh ./MIGRATE-WDC-TO-STR8N.sh --validate-only
sh ./MIGRATE-STR8N-TO-B4.sh --validate-only
```

Use `-BackupOnly` on Windows or `--backup-only` on Linux to verify and save
B3 without loading an installer or writing flash. Each run creates a new
`backups/<UTC timestamp>/` directory. Use the Python tool's `--out` option
to select another new directory. Existing evidence is not overwritten.

To prepare and inspect a plan from an already retained B3 readback:

```text
python beta4_migration.py --kind str8n --source prior-b3.bin --out my-plan
```

That command performs no serial I/O. Plans contain owner-specific backups
and expected images; keep them local. The public ZIP never includes them.

## Backup, preserved regions and settings

Before flash writes, the host reads the entire 32 KiB B3 twice and requires
exact agreement. It saves `prior-b3.bin` and a SHA256/verification receipt.
The installer never copies that backup into another flash bank.
B0, B1 and B2 are not written. B3 sectors 8/9 install the saved MAINT
record. B3:8-F is the migration destination; the plan explicitly lists changed
sectors. Back up and relocate any data in that reserved destination before
accepting the installation. Unchanged sectors, including a matching F
core, are not rewritten.

The seven startup fields are retained from `$EFF0` on a24, `$FFD0` on
a24c1/beta1/beta2, or the newest valid recovery journal record. Invalid
settings or a target conflicting with beta4's reserved RAM are refused.
Empty settings become a disabled autostart with target B3 `$F007` and a
one-second delay. An old slot preference/extended locator is cleared:
both newly installed slots have the package generation and reset defaults
to A. If the slots already match and only MAINT needs replacement, an
existing preference is retained. Existing erase counters are retained, and the final journal accounts
for the sectors in this migration. Initial legacy counts start at zero.
Migration-time counts are planned provisioning values; the full migration
is not a power-loss-safe journal transaction.

## Guarded installation

The host validates every packaged artifact hash, prints the plan and asks
for `INSTALL STR8-N 2.0b4`. Cancellation retains the host backup and causes
no flash writes. The RAM installer is loaded, then read back completely
before execution. Its unified entry forces 816 emulation mode; the entry
byte is a defined NOP on W65C02S. It uses its own RAM console/flash worker.
The flash identity must be the supported BF/B5 device.

Before each sector and again after its transfer, the installer checks the
expected full-B3 FNV guard. Each raw 4,096-byte transfer has its own FNV
check before mutation and a full-sector comparison after writing. Sector
order provisions the journals, then monitor slots/E and MAINT; F is last if
it differs. MAINT is written with a pending header and its complete marker
is programmed only after both storage sectors verify. Failure halts in RAM
without jumping into damaged flash.
After all transfers, the launcher waits for physical RESET, then verifies
every byte of the complete B3 against the prepared expected image.

## Failure and recovery

Do not reset, disconnect or remove power during an unverified flash write.
Keep the host backup and serial log if a transfer or verification fails.
A failed run halts in RAM and does not automatically restore the old bank.
The backup is a full bank image for deliberate recovery; monitor RST
records are a different format and cannot restore a raw bank BIN.

When the new fixed F core is intact, its recovery menu can replace a
damaged monitor slot using `U A` or `U B` and the matching slot BIN.
If power was lost while F was erased/programmed and reset no longer works,
recovery may require an external flash programmer using the retained bank
backup. The host backup is not a promise of automatic rollback.

The [hardware acceptance report](STR8N_V2_BETA4_HARDWARE_ACCEPTANCE_2026-10-06.md)
records the physical COM3 stock-migration and COM8 a24c1/beta1 upgrade checks.
See the [release notes](STR8N_V2_BETA4.md) for the qualification limits.

The host interoperates with the documented
[WDCMON protocol](https://www.westerndesigncenter.com/wdc/documentation/WDCMON_User_Manual_v20.pdf).
That reference is not a firmware input to this package.
