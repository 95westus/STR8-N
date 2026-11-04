# Installed R SRAM / R WORK scope

November 1, 2026. **Owner approved both reviewed installs; both passed and
remain installed.** See [installed acceptance](STORAGE_NATIVE_ACCEPTANCE.md).
The sealed original plan and approval stay unchanged.

SRAM/WORK g2, WB2 gD, services gC and the extended native loader are built.
The RAM menu, selected-bank Q, controls, old-loader/payload refusal and
BATCH-stop checks passed on both 2512/65C02 and 2609/65C816 emulation.
The final workbench revision also passed reserved-name argument validation
and long RESTORE forms. Unchanged menu/loader evidence was carried forward.
Both ports are released; fresh owner RAM/ZP and SPI metadata are restored.

## Exact installation

| Target on each board | Result |
|---|---|
| B1:B/C/D | One shared native SRAM/WORK payload; replaces retained legacy CLOCK |
| B3:8 | New native-loader final 1 KiB; existing RTC/provider/gateway bytes retained |
| B2:8/9 | WB2 gD, including native R SRAM/R WORK and argument/BATCH guards |
| B3:E | Matching services gC generation/seal |

Seven image erases per board. B2:A is unchanged, preserving its PROGRAM
provider and STATUS bytes; no CLOCK, FLASH, BANK MAINT or MON image rewrite.
Both native menu routes use one RP/1 kind3 image and return directly to MON
with Q. `!` opens shared controls. Bare SRAM/WORK status queries remain.
Interactive storage entry is refused in BATCH; it does not consume queued
text as confirmation. R CLOCK/FLASH/MAINT remain installed and are checked
afterward. This does not close saved EDU, named transfer or wide Store work.

| Board | Image erases | Journal erases | Journal appends | Final sequence | Final C/D/E/F counts |
|---|---:|---|---:|---:|---|
| 2512 | 7 | One B3:D | 8 | 1116 | 55 / 36 / 34 / 24 |
| 2609 | 7 | None | 7 | 1072 | 79 / 49 / 48 / 31 |

**Total: 15 erases.** Counts and sequences in this document are decimal.
The exact planner selects D on 2512 (not the initially suggested C).
Its CF00/seq1109 intent commits before D is erased; D000–D600 then hold
seven new reservations. All 31 original records are archived on the host;
16 old D records are replaced on chip, 15 original C records remain exact,
and the final journal has 23 valid rows. Every tracked count and prior-wear
flag is carried forward. On 2609 all 19 original records remain exact;
D300–D900 receive seven reservations, giving 26 valid rows.

The occupied B1:B–D legacy CLOCK images are archived exactly on the host
before replacement. Current native CLOCK at B2:B–D remains intact. These
targets are not inferred to be scratch. Other original images remain on
chip, including B0 and B1:8–A/E/F. B1:B–D becomes the profile's storage-app
allocation; ordinary explicit owner erase tools retain their existing guard
policy. This change does not add a new global flash protection rule.

## Preservation and execution

F remains the exact frozen 4,096-byte public image. Zero F writes, MON A/B
writes, boot-binding appends, power cuts or resets. Keep saved default B/gD,
enabled masks, bank entries, owner names/offsets, RTC time/trim/control/PF,
SPI PROGRAM/WORKSPACE and fresh owner RAM/ZP. 2205/2604, collection settings
and published downloads remain outside this installation.

Admit all target-bank preimages against the reviewed hashes before the
first write, reserve wear before each erase, verify each programmed sector,
then independently compare complete affected banks with the forecast.
Archive raw old boot/wear history; no journal reseeding or history reset.
Use board-loaded R SRAM/R WORK to test Table/capacity, controls and Q,
including selected-bank return; recheck CLOCK/FLASH/MAINT and restore/read
back owner RAM/ZP. No positive SRAM mutation matrix is repeated here.

The guarded driver requires a scope-hash-bound owner approval file, refuses
stale preimages and never retries an erase automatically. It yields to a
pending RTC request before mutation and will not start within ten minutes
of the next recorded collection deadline. Once begun, the reviewed image
transaction completes before the serial lease is released.

Approval is needed for the exception to the owner's preserve-images/history
requirement: the legacy CLOCK copies and 16 old 2512 D records would move
from on-chip retention to exact host archives. General permission to flash
when necessary does not resolve that retention choice.

Private, excluded-from-kit evidence and prepared targets:

```text
output/qualification/2512-native-storage-g2-RAM-20261101-r3/report.json
output/qualification/2609-native-storage-g2-RAM-20261101-r2/report.json
output/qualification/STORAGE-native-scope-20261101-r3/review.json
output/qualification/STORAGE-native-scope-20261101-r3/{2512,2609}/plan.json
```

Changed-component budgets: storage library 10,370 bytes (three sectors;
1,884 flash bytes spare), WB module 7,160 bytes (6 before CRC), dispatcher
4,082 bytes (12 before CRC), native loader 655 bytes (367 before CRC).
F, MON, PROGRAM, CLOCK, FLASH and BANK MAINT were reused. No simulator or
offline group suite was run. WB required a second compile for the discovered
argument-validation fix; service support was repackaged without recompiling.

Classic startup presentation is recorded in `UNIFIED_SHIPPING_RELEASE.md`.
MON gD and its current banner are unchanged by this storage-only scope.
