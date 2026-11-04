# STR8-N UTIL MEMORY — PC memory utility

`python -B tools/str8n-util-memory.py` provides **backup, restore, load, offload,
verify, plan and inspect** through one CLI. Backup images stay on the PC.
The matching temporary RAM agent needs no new resident flash installation.
The [component naming guide](COMPONENT_NAMING.md) defines its canonical display
and payload filenames. `memory_tool.py` remains the compatible implementation
module; existing scripts and recorded qualification commands remain valid.
The new copyright-bearing helper is a separate offline candidate. The 2512
physical acceptance below applies to its recorded original binary hash;
the added notice has CPU-model acceptance, not a new hardware trial.

Status: CPU/bus-model tests passed, and the **2512 physical backup/change/
restore trial passed on November 4, 2026**. A fresh session independently
compared all 288,353 supported bytes to the original, with no differences.
See [2512 acceptance and exact scope](MEMORY_ACCEPTANCE_SUMMARY.md). This remains
a development utility, not a published release or a replacement for the
existing migration/installer workflow. Other physical boards, all-sector
programming and interrupted-write recovery are not qualified by this trial.

## Memory coverage

| Region | Binary size | Coverage |
| --- | ---: | --- |
| `flash` | 131,072 | B0, B1, B2, B3 in that order, each 32 KiB; complete capture and comparison |
| `spi-sram` | 131,072 | Entire 23LCV1024 array, including directory, programs, WORK, reserved and unused bytes |
| `spi-mode` | 1 | SRAM mode register; accepts byte, sequential or page mode (00/40/80) |
| `eeprom` | 128 | MCP79411 user EEPROM at I2C 57, addresses 00–7F |
| `cpu-ram` | 25,856 | CPU addresses 0200–66FF |
| `zero-page` | 224 | CPU addresses 0000–00DF |

Flash restore can replace **124 KiB**. The last 4 KiB, B3:F Foundation, must
already match the backup exactly. A mismatch refuses the plan before any
storage write. Replacing Foundation requires a separate external-programmer
recovery path. `flash.bin` nevertheless contains all 128 KiB for recovery.

CPU backup means the documented **owner RAM ranges**, not a suspended-machine
checkpoint. The active CPU stack, registers, system zero page E0–FF, monitor
workspace, transfer-agent workspace, and I/O are excluded explicitly in each
manifest. The service occupies 6800–77FF and uses 2000–2FFF for staging.
It restores and verifies owner RAM before returning to `REC>`. Starting a
monitor or application afterward may change RAM again.

EEPROM factory/protected addresses 80–FF, RTC calendar/control registers and
RTC battery SRAM are outside this candidate. Memory sizes/wiring are explicit;
this version does not guess other EEPROM models or support 816 native RAM.
`all` requires the matching EDU hardware to be fitted. Remove absent optional
regions from the profile and select the available regions explicitly.

## Build and prerequisites

Use Python 3.10+, pyserial for real serial operation, and WDC02AS/WDCLN on PATH
to build the RAM image. Host-only directory operations use the standard library.
The frozen BASE1 / PR05 Foundation is reused, never rebuilt or changed.

```powershell
python -B tools/build_memory_agent.py --out BUILD/memory-agent-v1
python -B tools/str8n-util-memory.py --help
```

The builder requires a new output directory. To rebuild, use a fresh directory
and pass it using `--agent` to the host tool. The manifest binds the agent to
the exact frozen Foundation SHA-256 and its private recovery entry.

Copy `firmware/memory-agent/profile.example.json` to a private location. Fill
in the actual board ID, COM port, FTDI USB serial and CPU (`65c02` or
`65c816-e`). The listed layout means WDC SXB/EDU Rev D wiring, FT245 USB and
the exact BASE1 / PR05 Foundation in the example. Entry requires a compatible
MON B, either already at `B3>` or launchable from `REC>`.

No port is opened for `inspect` or directory-device operations. Serial operation
checks the USB serial, CPU banner, Foundation bytes and profile before borrowing
RAM. It uses the existing shared serial lease and refuses a recorded pending
board operation. Close other serial terminals first.

## Backup and restore

Every `--out` is a new private run directory; existing files are never replaced.
The following examples use your private profile, not the unfilled example.

```powershell
# Complete PC backup. Result: output/memory/backup-01/backup/
python -B tools/str8n-util-memory.py backup --profile output/my-board.json --out output/memory/backup-01

# Inspect hashes/sizes without connecting to a board.
python -B tools/str8n-util-memory.py inspect output/memory/backup-01/backup

# Compare current board memory to the backup.
python -B tools/str8n-util-memory.py verify output/memory/backup-01/backup --profile output/my-board.json --out output/memory/verify-01

# Prepare a restore plan and fresh preimages; no storage write.
python -B tools/str8n-util-memory.py plan output/memory/backup-01/backup --profile output/my-board.json --out output/memory/plan-01

# Restore, saving fresh preimages and a per-block receipt before each write.
python -B tools/str8n-util-memory.py restore output/memory/backup-01/backup --profile output/my-board.json --out output/memory/restore-01 --write

# Select only SPI SRAM data and its addressing mode.
python -B tools/str8n-util-memory.py restore output/memory/backup-01/backup --regions spi-sram,spi-mode --profile output/my-board.json --out output/memory/spi-restore-01 --write
```

Restore requires the same board identity as the backup. `restore` without
`--write` plans only. Flash planning compares all 32 sectors, rejects a changed
Foundation and lists changed sectors. The agent skips identical sectors and
erases/programs/verifies one changed 4 KiB sector at a time. SPI SRAM transfers
use separately addressed bytes so the existing mode does not alter the result.
EEPROM writes never cross an 8-byte page boundary and have bounded ACK polling.

**Exact flash restore includes old C/D journal bytes.** It therefore restores
old boot settings and can roll back native erase-count history. The host
`receipt.json` durably records every attempted changed sector before its erase,
including an unresolved attempt after a lost reply. Keep that receipt with the
backup as additional wear/recovery evidence. This raw image operation does not
merge old journals with newer wear history; use the existing installer when
you need its managed journal/accounting semantics. After a flash write, existing
board-operation metadata retains `firmware_verification_pending` so old qualified
firmware identities are not silently reused.

## Import/export individual binary images

`load` accepts a full-region image or a smaller binary at `--offset` (default
zero). The offset is relative to the region image; CPU RAM offset zero means
CPU address 0200. Bytes outside the supplied image are preserved by merging
with independently captured preimages. This supports importing up to 124 KiB
of flash without requiring a Foundation sector in the input file. A full
128 KiB flash import must contain the identical Foundation bytes.
`offload` produces the same complete raw binary layout as a backup region.

```powershell
python -B tools/str8n-util-memory.py offload spi-sram output/my-sram.bin --profile output/my-board.json --out output/memory/export-01
python -B tools/str8n-util-memory.py load spi-sram output/my-sram.bin --profile output/my-board.json --out output/memory/import-01 --write
python -B tools/str8n-util-memory.py load flash output/my-124KiB.bin --profile output/my-board.json --out output/memory/flash-import-01 --write
python -B tools/str8n-util-memory.py load spi-sram output/payload.bin --offset 0x10000 --profile output/my-board.json --out output/memory/partial-import-01 --write
```

Both operations preserve unrelated owner RAM. To load CPU owner RAM, use
`cpu-ram` and/or restore the separate `zero-page` image. Firmware, directory
format and payload compatibility remain the responsibility of the supplied
image; the raw utility does not relocate or convert image contents.

## Integrity, interruptions and recovery data

Each backup folder has independent binary files and `manifest.json` containing
board identity, exact byte counts, SHA-256 hashes, declared CPU RAM scope and
exclusions. `complete` is published only after all requested captures match and
local file readback verifies. Initial owner RAM is independently captured twice
before the RAM helper is loaded. It is exported from that escrow, not from
RAM already overwritten by the helper. Other memory is captured twice directly.

The binary wire protocol uses CRC16-CCITT (FFFF initialization), bounded blocks
and paced USB transmission. The complete write payload and its CRC are checked
in staging RAM before any target storage mutation. Every write has independent
readback and the entire requested postimage is compared at completion. There are
no automatic retries after a failed or ambiguous write.

On successful cleanup the service restores the intended owner RAM/ZP, verifies
both ranges and returns to `REC>` without resetting. CPU restore is ordered
so the whole 2000–2FFF staging buffer is written last. Non-RAM final verification
happens before final CPU restoration. The `ram-state.json` receipt records
cleanup separately from storage-write success.

If a response is lost/corrupted or the bootstrap phase is ambiguous, the host
closes the port without sending blind cleanup bytes into an unfinished binary
request. `ram-state.json` remains pending, and `entry-cpu-ram.bin` plus
`entry-zero-page.bin` retain the fresh original RAM. A write receipt's `pending`
block may have changed even when no completion was received. Do not rerun a
flash restore blindly. Preserve the run directory and resolve the actual board
state through the established recovery workflow. This candidate does not yet
automatically resume interrupted sessions.

A CRC-valid status 2/3 reply confirms that the full request and any payload
were consumed. The failed storage operation is not retried; owner RAM cleanup
can proceed at that known command boundary. Malformed/CRC-damaged replies
retain the conservative no-cleanup behavior.

## Offline exercise and tests

The explicit directory device exercises archives and restore policy without
opening serial ports or needing a board:

```powershell
python -B tools/str8n-util-memory.py init-test-device output/memory/offline-device
python -B tools/str8n-util-memory.py backup --device-dir output/memory/offline-device --out output/memory/offline-backup
python -B tools/str8n-util-memory.py restore output/memory/offline-backup/backup --device-dir output/memory/offline-device --out output/memory/offline-restore --write
```

CPU tests require an already installed local py65 dependency; 816 tests also
require the local py65816 model. No dependencies are downloaded:

```powershell
python -B tools/test_memory_tool.py --build BUILD/memory-agent-v1 --deps tmp/migration-python
python -B tools/test_memory_tool.py --build BUILD/memory-agent-v1 --cpu 65c816-e --deps tmp/migration-python --deps-816 tmp/p1-clean/BUILD/test-deps-816
```

Tests execute the assembled loader and RAM agent. Flash command sequences and
SPI GPIO are bus models. EEPROM high-level page/address/read/write paths use
hooked I2C byte primitives. The separate 2512 live trial additionally exercised
real USB transfer, physical RAM preservation and representative flash/SPI/
EEPROM writes. Device absence, brownouts, power-loss recovery and other boards
still need qualification. Model tests alone do not qualify a live restore.
