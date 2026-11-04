# Candidate3 installed acceptance on 2609

November 2, 2026. The approved 2609/COM8 upgrade and targeted 65C816-emulation
checks passed using the exact extracted Candidate3 components already accepted
on 2512/65C02. Both now run the same optional MON/tools profile above frozen
Foundation. Board data and CPU identity remain specific to each board.

Candidate: `STR8N-MON-g00000010-candidate3.zip`, SHA-256
`6b1b3220cf5c05be0b49bf98c055f1df82e3870531512e2d3f94f3363b4bc789`.
The archive and published downloads are unchanged. These later receipts
supplement its packaging-time pending flags; no firmware was rebuilt.

| Check | Result |
| --- | --- |
| Installation | 15 image erases plus one native B3:C rotation; all 17 appends verified |
| Common profile | MON A/B g10, WB2 gE, SRAM/WORK g4, PROGRAM g3, current native tools |
| Exact components | All changed targets independently read back; four identical targets skipped, including CLOCK and B3:9 |
| Runtime | 816 emulation, VERSION/TIME, APPS, CLOCK STATUS/HISTORY, BANK MAINT and SRAM/WORK routes passed |
| BATCH | Installed SRAM/WORK Q returns executed the following monitor Dump |
| Loaders | Extracted-console S19 cancellation/load with independent KEYS readback; SEND BIN Ctrl-C and normal RAM BIN/public-HOLD passed |
| RAM execution | G marker/public-HOLD return passed |
| Physical startup | One physical RESET selected saved B g10 automatically; Traditional output, board2609, EDU ON and both SRAM capacities without PREP |
| RTC | Nine native TIME/NIST readings and the unchanged 794-byte/62-second LED sampler passed; current trim0E (-14), control80 retained |
| Owner RAM | Full0200-66FF and ZP00-DF restored and read back after the runtime, reset and RTC checks |

Saved B remains B, rebound from gD to g10; bank enables remain00 and entries
8000. Final journal is seq1089 with27 valid rows; C/D/E/F tracked counts are
80/49/49/31. All26 old rows are archived on the host. The approved rotation
replaced16 old C rows on chip and retained10 old D rows. Tracked attempts
are not a lifetime wear measurement.

B0, B1:E/F, B3:9 provider/metadata, board name/offset/battery/EDU settings,
RTC time/trim/power-fail history, EEPROM and SPI PROGRAM/WORKSPACE are
preserved. Zero F writes, power cuts or RTC setting/trim/ACK writes occurred.
No other board was accessed by this trial. RTC baselines, historical points,
old instruments and other-board routing remain retained.

Two host-side interruptions are recorded rather than hidden. After the first
verified A replacement, an inspector attempted a protected C/D read through
the wrong interface. Owner RAM was restored; canonical READBACK independently
verified A and its append before continuation, without another A erase.
The first LED sampler completed acquisition but compared the entire PIA CRA:
B4 changed to34 while the six control bits and LED value matched. Owner RAM
was restored immediately. The corrected versioned 2609 host reader compares
CRA0-5 and records IRQ flags6/7 separately; a repeated unchanged sampler
passed. Original failure receipts and readers are retained. Reading port A
clears these flags according to the [WDC W65C21 datasheet, p15](https://www.wdc65xx.com/wdc/documentation/w65c21.pdf).
This is not an RTC power-fail ACK or a firmware change.

Private receipts, relative to the workspace root:

- `output/qualification/2609-candidate3-installed-20261102-r2/report.json`
- `output/qualification/2609-candidate3-runtime-20261102-r1/report.json`
- `output/qualification/2609-candidate3-reset-20261102-r1/report.json`
- `output/qualification/2609-candidate3-RTC-readmission-20261102-r2/report.json`
- `output/qualification/2609-candidate3-closeout-20261102-r1/completion.json`

Final REC>, COM8 released, owner/worker/reset guards clear and RTC readmitted.
The16-erase allowance is exhausted. This closes the latest-profile 816 upgrade
gate; it does not repeat every 2512 positive-write fixture on2609. No fresh
WDC migration, live factory restoration, 816 native-mode execution, source-only
rebuild, publication or reference-board rollout is claimed. ASM/DBG follow.
