# STR8-N 2.0b4 quick start

Extract the entire release ZIP into a writable folder. Install Python 3
and pyserial (`python -m pip install pyserial`, or `python3 -m pip install
pyserial` on Linux). Close any other terminal using the board's USB port.

## Choose the entry point

| Board currently running | Windows launcher | Linux launcher |
| --- | --- | --- |
| Stock WDC monitor | `MIGRATE-WDC-TO-STR8N.ps1` | `MIGRATE-WDC-TO-STR8N.sh` |
| STR8-N 2.0a24 or later supported layout | `MIGRATE-STR8N-TO-B4.ps1` | `MIGRATE-STR8N-TO-B4.sh` |

On Windows, for example:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\MIGRATE-WDC-TO-STR8N.ps1
```

For an existing STR8-N monitor, use `MIGRATE-STR8N-TO-B4.ps1` instead.
On Linux:

```sh
sh ./MIGRATE-WDC-TO-STR8N.sh
```

Use `sh ./MIGRATE-STR8N-TO-B4.sh` for the STR8-N upgrade. Supply `--port
/dev/ttyUSB0` if desired; Windows accepts `-Port COM3`.

## Installation

1. Choose the serial port. For a stock board, confirm its physical board
   type. The launcher opens the port and arms a read-only debugger probe
   for 60 seconds. Press and release physical RESET while it is armed;
   it detects the debugger automatically, without a subsequent Enter delay.
   For an existing STR8-N board, first leave it at its idle monitor prompt.
2. The launcher reads B3 twice, compares the reads, and writes a host backup
   to the kit's `backups/<UTC timestamp>/` folder. It validates the source
   layout/settings and prints the sectors it will replace.
3. Review that plan. Type `INSTALL STR8-N 2.0b4` exactly to start. B0-B2
   are preserved. B3 sectors 8 and 9 store MAINT; A-F belongs to beta4 after migration;
   any prior data in that region survives only in the host backup.
4. Keep power stable. The launcher loads and verifies the RAM installer,
   sends the sector transfers, and waits for `MIGRATION VERIFIED; PRESS
   PHYSICAL RESET`. A needed reset-sector rewrite is always last.
5. Press physical RESET only when asked. After startup, press Enter in the
   launcher. It compares the complete B3 readback with the expected image.
   Keep the backup and `verification.json`.

The two new monitor slots have the same generation; without a stored
preference, reset chooses A. Both identify themselves as `STR8-N 2.0b4`.
At `B3>`, use `?`, `C`, `P`, `W`, and `T` to inspect the monitor, startup
settings, preference, wear counters and stored records.

## Load BANK MAINT

At `B3>`, enter `R MAINT`. The release installs a saved MAINT record in B3
sectors 8 and 9; RESTORE copies the unchanged utility into RAM and starts it.
At `BM>`, `?` lists commands and `Q` returns to the monitor. The saved record
remains available after RESET. `M`, `M 1` and `M 3` work at the monitor.

The S19 remains included for a host load: enter `L`, send
`str8n-bank-maint-1.5-2000.s19` with about 40 ms between lines, wait for
completion, then `G 2000`. `R MAINT L` restores without running.

For a saved copy, follow the
[RESTORE/SAVE/TABLE walkthrough](STR8N_V2_BETA4_RST.md).
See the [migration guide](STR8N_V2_BETA4_MIGRATION.md) for offline validation,
source limits and failure handling, and the
[operator manual](STR8N_V2_BETA4_MANUAL.md) for commands and memory maps.
