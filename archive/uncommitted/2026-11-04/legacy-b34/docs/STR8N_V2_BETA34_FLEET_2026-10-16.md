# Beta34 / ASM 0.5 on all four boards

All four boards now have beta34 monitor B, generation 46 (`0000002E`),
ASM 0.5, the common MAINT 2.4 and SRAM/WORK/EDU 1.4 native utilities,
and CLOCK 1.9. Beta28 monitor A remains a valid fallback on every board.
The 65C816 board runs the monitor in emulation mode.

| Board | CPU | Port | Previous running version | Result | Sector erases this request |
|---|---|---|---|---|---:|
| 2512 | 65C02 | COM4 | beta34 | Full backup/readback confirmed; no rewrite | 0 |
| 2205 | 65C02 | COM3 | beta32 | Flashed and verified | 6 |
| 2609 | 65C816 | COM8 | beta32 | Flashed and verified | 6 |
| 2604 | 65C02 | COM5 | beta25 | CLOCK, system and ASM updated; verified | 19 |

## Verification and preservation

Before any writes, all four boards were backed up in parallel. Each capture
read all four flash banks and all 128 KiB SPI SRAM twice, compared EEPROM
normal/protected/status and RTC SRAM/settings/history, and restored and
verified application RAM. The backup archive passed ZIP CRC and all 147
archived file hashes.

Each new installer was bound to those exact bank preimages. The CPU model
verified final bank contents, allowed sector order, descriptor/monitor
publication, and rejection of stale preimages and damaged payloads. Model
and hardware checks covered installer return, J3 boot, native utility BATCH,
CLOCK 1.9, and ASM PASTE/assembly of a RAM program calling public PUTC/HOLD.
ASM printed the correct inclusive range and Store command:

```text
RAM $0200-$0207
S 1 AUTO 0200 0207 PROGRAM
```

The newly updated boards also booted their beta28 A fallback, returned to
beta34 through J3, and passed another complete four-bank readback. All SPI
SRAM, EEPROM, RTC settings/history and application RAM matched the saved
bytes afterward; calendar time was allowed to advance. All B0 images were
preserved. 2205 retains its unnamed board setting. 2604's uninitialized SPI
SRAM was preserved without formatting. Its known legacy flash CLOCK record
was updated to 1.9; the legacy MAINT record was preserved.

2604 used a four-sector CLOCK step followed by a fifteen-sector firmware
step. The source A monitor stayed intact until new B was verified and the
common fixed recovery image was installed; beta28 A was installed last.
Each erase, including both journal-sector erases, was included in the
tracked counts.

The CLOCK step exposed an installer return-stub defect: its last transfer
selected B1, but the stub jumped to F004 without selecting B3. The flash
step completed and verified before the wrong-bank jump. One physical RESET
was required because the halted console could not accept J3. After reset,
all four banks matched the CLOCK target and the saved application RAM was
restored. The main update resumed without rewriting the CLOCK record.

The deployment helper now explicitly selects B3 before entering ROM RESET.
A regression reproduced the original B1 return, verified the corrected
actual installer end state, and booted from that actual final bank instead
of assuming B3 in the functional fixture. The corrected main installer
passed these checks and the normal source/payload guards. Original failed
attempt/source evidence is retained in `2604/clock-attempt-hardware/` and
`deploy-tool-before-return-fix.py`; reset recovery and passing regressions
are recorded separately.

2512 was already current: its fresh full flash readback matched the earlier
successful beta34/ASM/Microchess hardware receipt. Its saved SRAM CLOCK
matches the sealed CLOCK 1.9 body. Its existing UCHESS record remains intact;
the other boards received no additional saved demonstration records. Their
ASM smoke tests made no persistent test writes.

## Backup and evidence

All paths below are relative to `C:\SRC\STR8-N`:

- `output/qualification/beta34-fleet-2026-10-16/report.json`: fleet receipt,
  build/source hashes and per-board final flash hashes.
- `output/qualification/beta34-fleet-2026-10-16/before-beta34-all-boards.zip`:
  complete fresh pre-update archive and its adjacent `.sha256` checksum.
- `output/qualification/beta34-fleet-2026-10-16/fresh/<board>/`: raw flash,
  SPI SRAM, EEPROM, RTC and application RAM images, repeat reads, file hashes
  and load-only application RAM restore S-record.
- `output/qualification/beta34-fleet-2026-10-16/<board>/hardware/`: complete
  final flash/SRAM readbacks, RTC/EEPROM comparisons, console transcripts,
  original/restored RAM and completed restoration marker.
- `output/qualification/beta34-fleet-2026-10-16/<board>/<stage>/upgrade/`:
  exact installer, sector payloads, target images, model receipts and plan.
- `output/qualification/beta34-2512-2026-10-16/`: earlier live ASM 0.5,
  Microchess assembly and Store/Table/Restore proof on 2512.

Raw archives remain ignored and contain board-specific data. Application
RAM restore S-records are loaded with `L` without executing `G`; these are
data backups, not resumable CPU execution checkpoints. Historical migration
source archives were retained for later fixture restoration.

All serial ports are released. The soak remains completely stopped. No
migration matrix was run, and no v2.1 alpha code was flashed.
