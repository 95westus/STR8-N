# 2609 ASM/DBG installation scope

**Historical scope: subsequently approved and executed successfully.**
November 2, 2026. See the [installed acceptance](2609_DEVTOOLS_INSTALLED_ACCEPTANCE.md).
The original preparation below made no flash writes.
Canonical private plan: `output/qualification/2609-devtools-flash-scope-20261102-r2/plan.json`.
Addresses are hexadecimal; sequences and wear counts below are decimal.

The owner selected **“Host-backup WDC; use qualified layout.”** The complete
original 32 KiB B0 bank is archived and verified on the host before any future
write. B0:A contains WDC code; its replacement means WDC will no longer remain
as a complete, qualified on-chip fallback. Its remaining signature/vectors
do not establish a usable original image. The full original bank is retained
as `B0-WDC-original.bin`, SHA-256
`1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`.
All original sectors and all journal records are also archived privately.

## Exact write allowance to review

| Target | Purpose | Erases |
| --- | --- | ---: |
| B0:A/B | ASM plus source helper | 2 |
| B0:C/D | DBG g2 and exact private SF/1 provider at D800–DFFF | 2 |
| B3:E | APPS/R ASM/R DBG dispatcher, retaining the current full utility profile | 1 |
| B3:D | One native boot/wear-journal rotation | 1 |
| **Total** | **Five image sectors plus one journal rotation** | **6** |

Six append operations: CB00/1090, CC00/1091, CD00/1092, CE00/1093,
CF00/1094 and D000/1095. CF00 is the reserved peer-erase intent, not an
ordinary slot. It reserves the E target and D rotation counts before erasing
D and committing the new root at D000.

The current journal has 27 valid records at sequence 1089. All 27 are archived
on the host. Eleven old C records remain exact on chip; the rotation replaces
16 old D records on chip. The final journal has 17 valid records at sequence
1095. B0:A–D counts each advance 2→3. B3:C/D/E/F end at **80/50/50/31**.
All prior wear counts and unknown-prior-wear flags carry forward.

Saved default B/g10, bank-enable mask 00, entries 8000, board metadata and
every other boot setting remain unchanged. There are zero F/MON writes,
C erases, RTC-metadata writes, SPI-data/WORKSPACE writes, RTC-setting writes,
resets or power cuts. No retry/rollback erase allowance is included.

## CPU envelope and dependencies

The [2609 RAM qualification](DEVTOOLS_2609_EMULATION_RAM_ACCEPTANCE.md)
passed using the exact candidate2 executable code. Its AP/02 images identify
CPU02 in byte 15; the scanner requires CPU16 for this processor. The reviewed
targets change only byte 15 and header CRC bytes 28/29. Every executable/body
byte, payload CRC and the private source-provider block remain exact. This
CPU tag identifies the processor; it does not enable native16-bit operation.
There is no firmware rebuild or Foundation ABI change.

The dispatcher is the prebuilt R-alias version previously installed/tested
on2512. Its loader/interface sources and B1 dependencies match2609; B2 differs
from its original dependency image only in the already-qualified STATUS extent.
Installed AP/02 wrappers and R routing still require actual2609 acceptance.

Keep B0:8/9/E/F, all B1/B2 and B3:8/9/A/B/F byte-for-byte. Existing CLOCK,
FLASH, MAINT, SRAM/WORK and legacy B1:E/F remain; no utility retirement or
reclamation is included. Published downloads and the candidate2 ZIP stay exact.

## Acceptance and preservation

Future execution must first yield to RTC, acquire the shared COM8 lease,
capture fresh owner RAM/ZP/cache/hooks and re-admit every bank hash, target
preimage and journal slot. Stop if these change; do not expand the allowance.
Use only the reviewed CPU16 targets, not the kit's unconverted CPU02 envelopes.

Installed checks cover APPS/APP/R launch paths; assembly/list/export/readback/
run; DBG start cancellation, real BRK, S/N/C, breakpoints, X/HOLD and CPU-specific
refusals; read-only source-provider/PROGRAM reload and current native-tool
launches. Independently read all four banks, the planned journal root, all 11
retained rows, metadata and F. Restore/read back owner RAM0200–66FF, ZP00–DF,
full6B00–77FF cache and original BRK/HOLD hooks. Finish REC>, release COM8,
leave RTC eligible, and access no other board.

Persistent source-write tests are excluded. There is **no erased SF/1 source
sector in B0:8–D after installation**: vendor8/9 and appsA–D occupy that arena.
No extra B0:9 erase is implied. Positive PROGRAM/FLASH source tests need their
own admitted fixture. Native16-bit developer operation remains outside scope.

The fresh read-only preparation passed: owner RAM/ZP/full cache restored and
verified, REC>, COM8 released. No flash or persistent-data write occurred.
The owner subsequently approved the six erases and16-record on-chip D-history
replacement. The installed receipt records execution and final restoration;
the private plan remains the exact original reviewed input.

Private evidence:

- `output/qualification/2609-devtools-flash-preflight-20261102-r1/report.json`
- `output/qualification/2609-devtools-flash-scope-20261102-r2/plan.json`
- `output/qualification/2609-devtools-flash-scope-20261102-r2/review-document.md`
- `output/qualification/2609-devtools-flash-scope-20261102-r2/review-verification.json`

The earlier r1 forecast is superseded because its CPU02 envelopes are not
admitted on2609. It was never flashed. Private WDC/owner/journal captures are
not part of any release payload.
