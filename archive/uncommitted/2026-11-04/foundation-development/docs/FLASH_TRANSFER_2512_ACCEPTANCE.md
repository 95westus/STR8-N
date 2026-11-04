# 2512 dense S19 and large flash STORE acceptance

## Latest follow-up: large flash AUTO

November1,2026. The reviewed14-erase combined storage scope is complete on2512.
The independent high worker now uses the saved AREA outside owner source RAM.
A6400-byte source at4E00-66FF was preserved by STORE AUTO at B0:9000, and the
committed SR01 header/payload matched exact flash readback. A later eight-byte
record appeared at B0:A918, after the complete first payload including its FF
bytes. TABLE listed both records at the expected addresses. AUTO never erases;
unknown occupied bytes inside AREA are refused, while owner data outside AREA
does not prevent using a valid window.

The new load-only RESTORE returned OK, but its exact RAM comparison was not
completed: TABLE selected B0 and the host Dump helper required B3. Cleanup
restored B0:9/A and owner RAM exactly. CRC-verified AUTO/tail evidence was kept;
the flash fixture was not repeated. The remaining PROGRAM-only continuation
passed the8KiB returning BATCH test with zero extra flash erases. The separate
exact large flash-Restore acceptance below remains the earlier evidence.

Total: ten utility erases, one native C rotation and three fixture/restoration
erases; all14 used, no retry allowance spent. Final C/D/E/F57/37/37/24, seq1164.
F, MON A/B, saved boot/EDU/name/offset and RTC settings/history were unchanged.
All8256 temporary PROGRAM bytes and owner RAM/ZP are restored, REC>/COM4 free.
The EDU/help and STATUS allocations remain byte-exact. Other boards and
published downloads were untouched. Combined receipt:
`output/qualification/2512-storage-BATCH-AUTO-scope-20261101-r1/completion.json`.

## Earlier explicit-address and dense-S19 acceptance

November 1, 2026. This development increment is accepted on **2512 / 65C02**.
It does not qualify the held 2609 installation or close the shipping release.

The original ten-erase allowance completed the fixture setup, positive writes,
restoration, four utility installs and one native C rotation. Positive evidence:

- A 6,400-byte flash Store/Table/load-only Restore through $66FF preserved its
  original source. SR/01 has no payload CRC; byte verification is not a claim
  that a new persistent payload-checksum format was introduced.
- An 8,192-byte dense S19 stream wrote two full sectors, including checked
  records crossing the sector boundary. Original B0 was restored exactly.
- All 31 journal records were archived before the approved rotation replaced
  16 old C records on chip; settings and tracked counts were carried forward.

Installed compatibility checks then exposed a missed STATUS reservation and
AUTO losing AREA during a full cache reload. Failed receipts remain preserved.
The separately approved correction used exactly three erases at B1:A and
B2:E/F, without rebuilding Foundation or changing MON A/B or B3:E.

## Installed correction evidence

All 12 checks in the correction report passed, including:

- Independent readback of each corrected sector; full final B0/B3 equality
  against the reviewed plan.
- Rich VERSION with CPU, board name, EDU, PROGRAM/WORKSPACE sizes, local RTCC,
  battery policy and wear disclaimer; native TIME includes fresh trim/control.
- Actual ROM fragment loading and sealed dense-library admission, dense-I
  Ctrl-C, and one complete all-FF pass at blank B0:9. That pass changed no B0
  byte, journal row or erase count.
- Wide flash Store confirmation/NO and missing-record Restore refusal;
  AREA/AUTO retained B0:9000 after the SP-only reload and canceled correctly.
- PROGRAM confirmation/NO, monitor S19 Ctrl-C, TABLE, R MAINT naming query,
  R CLOCK TIME/TRIM, M1 and W.
- Original owner RAM $0200-$66FF and ZP $00-$DF restored and read back.

Final state is **REC>, COM4 released**, default B still bound to MON gD.
All 21 pre-correction records remain intact; C500-C700 add seq1131-1133,
giving 24 valid rows. Correction target counts are B1:A=8, B2:E=22, B2:F=18.
B3:C/D/E/F remain 56/36/36/24. Original B0, F, MON A/B and settings match.
No SPI SRAM data, RTC settings/trim/PF history, other boards or published
downloads were written. No reset or power cut was needed for the correction.

F remains the exact 4,096-byte STR8N-F 0.3.0 g1 BASE1/PR05 image, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
RTC host admission is restored from actual STATUS/CPU proof and restored RAM;
the next scheduled sample is a separate collection receipt.

## Use and limits

```text
B3> R FLASH
FLASH/MAINT> BANK 0
FLASH/MAINT> I 9000 AFFF
```

After live YES, send complete ascending ASCII S0/S1/S9 records. Each sector
must be fully supplied. S9 completes intake without running an entry. Errors
or Ctrl-C retain earlier completed sectors; there is no rollback. B0/B1
sectors 8-D are eligible; a required journal rotation is refused.

```text
B3> STORE 0 9000 4E00 66FF EXAMPLE
B3> TABLE 0
B0> RESTORE 0 EXAMPLE L
```

The target must be erased and otherwise admissible; live YES is required.
`L` means load only. Loading may change the selected-bank prompt. Save owner
RAM before loading tools or programs. AREA/AUTO retains the existing narrower
WB source bounds; wide flash Store uses an explicit address. Large returning
BATCH, native MON-level I, named flash/PROGRAM copy, saved EDU, factory execution
and ASM/DBG are separate work. New S19 terminal/extracted-kit acceptance also
remains a shipping gate.

Private evidence, excluded from published downloads:

```text
output/qualification/2512-flash-transfer-positive-20261101-r1/report.json
output/qualification/FLASH-transfer-ten-erase-checkpoint-20261101-r1/report.json
output/qualification/2512-flash-status-correction-RAM-20261101-r1/report.json
output/qualification/2512-flash-status-corrected-20261101-r1/report.json
output/qualification/FLASH-status-correction-scope-20261101-r1/approval.json
BUILD/flash-status-correction-r4/manifest.json
```

B1/B2 evidence is exact corrected-sector readback plus bounded-writer
preservation of other extents. It is not a fresh final whole-bank capture of
B1/B2. Full B0 and B3 captures establish their exact final equality.
