# 2205 SPECIAL archive and Foundation rollout

November 2, 2026. The owner approved the clean compact, 34-erase profile for
2205/COM3 (USB A10MPUPNA, W65C02SXB). The original b35 system is permanently
archived locally and remains excluded from Git and distributions:

`C:\SRC\STR8-N\local-archives\STR8-N-b35-2205-SPECIAL-20261102`

The archive contains independently matching full-flash reads, original MON A
g28/B g2F, the original WDC bank, all 33 legacy WC journal records, owner RAM,
ZP, legacy provider cache/vectors and the complete 128 KiB SPI SRAM. Its
`archive-manifest-complete.json` records the pre-migration hashes. Do not
restore an old wear journal blindly over newer cumulative counts.

## Installed and verified

The exact published 4096-byte Foundation 0.3.0/g1 BASE1/PR05 image replaced
legacy F once. It remains frozen and golden. The compact installation uses
the qualified Candidate4 CPU02 components: MON A/B g00000010, ASM/DBG g2,
CLOCK, WB2 gE, PROGRAM g3, SRAM/WORK g4, STATUS and shared services. MAINT and
FLASH remain host-loaded REC BINs at $0200, with no resident duplicates.

| Sectors | Current use |
| --- | --- |
| B0:A/B | ASM/source g2 |
| B0:C/D | DBG g2 and SF/1 provider |
| B1:A | Shared transfer support |
| B1:B-D | SRAM/WORK |
| B2:8-A | WB2/PROGRAM/loaders |
| B2:B-D | CLOCK |
| B2:F | STATUS |
| B3:8/9 | RTC/history code; original $9C00-$9FFF metadata preserved |
| B3:A/B | MON A/B g10, Traditional presentation |
| B3:C/D | New SNBT boot/wear journals |
| B3:E | Services/dispatcher |
| B3:F | Frozen Foundation |
| B0:8/9/E/F, B1:8/9/E/F, B2:E | Retired legacy fragments; nine erased sectors, 36 KiB |

All four banks independently matched the approved expected images. The
34 erases comprise three conversion erases, 29 image/retirement erases and
two native journal rotations. Final sequence is 909; C/D/E/F counts are
32/15/16/3 decimal. All 32 cumulative tracked counts survive; prior/direct
wear remains unmeasured. Old raw records remain in the SPECIAL host archive.

Saved default remains B, now bound to g10. Opaque-bank autostarts remain
disabled. Board name 2205, local offset -06:00, metadata history, RTC time,
trim -17/control $80, EUI and power-fail history are preserved. Legacy
runtime cache/vectors are archived; matching Foundation runtime is initialized.

Installed checks passed for both monitors' VERSION/TIME, CLOCK STATUS/HISTORY,
EDU/SRAM/WORK/TABLE queries, APPS, returning BATCH, ASM assemble/export/run/HOLD,
DBG real-BRK step/continue and cleanup, and the actual REC-loaded MAINT/FLASH
menus and VERSION. No new positive persistent source-write fixture was used.
The final physical reset verified saved-B startup without a chooser key.
Original owner RAM $0200-$66FF and ZP $00-$DF were restored and read back.

## Preservation closeout

Full post-rollout SPI comparison and native TIME/LED RTC readmission passed.
Every one of the 131,072 SPI bytes matches the SPECIAL backup. Nine native
TIME/NIST readings and the unchanged 62-second LED sampler verified trim -17
and control $80. Owner RAM/ZP was restored again afterward; final REC>, COM3
released. Campaign baselines/segments and the other three boards' admission
remain unchanged. Normal RTC collection is readmitted for 2205.

The existing SS2 layout stays at 32 KiB PROGRAM / 96 KiB
WORKSPACE, with 30,720 PROGRAM payload bytes and 98,272 WORKSPACE bytes. Both
old CLK records are retained as data; their old ABI is not newly qualified.
The separate three-board 64/64 standardization does not authorize resizing
2205. RTC campaign baselines, calibration/history and other-board routing
remain intact. No SPI data or RTC-setting writes occurred.

The consolidated receipt is
`output/qualification/2205-foundation-rollout-complete-20261102.json`.
The permanent archive's `rollout-Foundation-completion` companion contains
the approved plan, individual receipts and a separate post-rollout full-flash
image. Original SPECIAL files are unchanged. The frozen F SHA256 remains
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.

Private receipts are under `output/qualification/2205-foundation-*20261102-r1`.
The exact reviewed plan and approval are in
`output/qualification/2205-foundation-rollout-scope-20261102-r1`.
No power cut, firmware rebuild, CPU simulation, other-board firmware change,
publication or candidate ZIP/download modification is part of this rollout.

## Subsequent 64/64 standardization

The later instruction “change 64/64 on 2205.” authorized a separate native
WORK P64 resize. It passed with exactly 74 changed management bytes across
192 permitted addresses: layout generation 3 and WS revision/epoch 2.
Both CLK records, all payload bytes, all four flash banks, settings/history
and fresh owner RAM/ZP/cache/hooks were preserved. No flash or RTC-setting
writes, reset or power cut occurred; RTC retained priority. This supersedes
the initial 32/96 layout for current inventory, without altering the historical
SPECIAL backup or the initial rollout receipts. Final REC>, COM3 released.

Receipt: `output/qualification/2205-SS2-64K-standardized-20261102-r1/report.json`.
Private resize preimages and completion evidence:
`C:\SRC\STR8-N\local-archives\2205-SS2-64K-20261102`.
