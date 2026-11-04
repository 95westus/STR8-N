# 2512 FLASH/STATUS and AUTO correction review

November 1, 2026. **Correction built and RAM-qualified; three new erases await approval.**
All ten originally approved erases were completed exactly. The6,400-byte
flash Store/Table/load-only Restore through66FF and two-sector dense S19
positive writes passed. B0 was restored byte-for-byte, all31 records were
archived before the approved C rotation, and owner RAM/ZP were restored.
The four reviewed utility sectors were programmed and independently read back.

Installed compatibility checks caught two regressions before closeout:

- The expanded FLASH body reached into STATUS's reserved B2:FA50-FFF9 allocation.
  That reservation was missed in the first layout. Rich STATUS is currently
  unavailable; Foundation and MON A/B are intact.
- Loading the new gate displaces the PROGRAM cache. AUTO then used the normal
  full loader, whose WB_INIT clears the declared AREA. AUTO needs an SP-only
  reload that preserves the live workbench state.

2512 is left at **REC>, COM4 released**, with original owner RAM/ZP verified.
The current STATUS incompatibility is explicitly recorded in device admission;
RTC collection on2512 must wait for actual STATUS/CPU output to be restored.
RTC code, cadence, baselines/history and settings have not been changed.
2609 remains owner-held;2205/2604 and published downloads remain untouched.

## Corrected layout

The corrected FLASH body is6680 bytes and ends before the protected FA50
boundary (body maximum6704 bytes). All four STATUS allocations are preserved
against the original accepted image:8040-80FF,8240-82FF,AC00-AFFF andFA50-FFF9.
The1450-byte details allocation is restored exactly, including its own CRC.
New packer checks reject this overlap rather than treating padding as free.

Dense control code is a581-byte sealed RAM library at4000, copied from three
existing BANK MAINT padding fragments: A31D/99 bytes, A64A/308 bytes and
AEB7/174 bytes. Its complete CRC and identity must pass before I is enabled.
The original BANK MAINT body/header remains unchanged. The gate and high-record
worker retain their independent seals; the complete RP image is resealed.
No extra sector allocation or new F ABI is required.

The gate's AUTO path reloads only the exact admitted PROGRAM worker from B2,
checks PROGRAM and WB CRCs, then uses the existing WB command handler without
WB_INIT. A short tail below6B00 survives replacement of the RAM gate. The
high-record frontend also reuses the frozen text hex parser to conserve space;
the numeric parser's source line is explicitly at7C00. Foundation is read,
never rebuilt or modified.

## RAM evidence already accepted

`output/qualification/2512-flash-status-correction-RAM-20261101-r1/report.json`
passed all four checks:

1. Fresh complete-bank readbacks match the exact final ten-erase plan.
2. Dense fragment concatenation, CRC/identity admission and I confirmation/NO.
3. Corrected wide-Store frontend/hex parsing, NO and source preservation.
4. AUTO's SP-only reload retains AREA and selects B0:9000, followed by NO.

The RAM loader test changes only its fragment source-address table to RAM
fixtures; its instructions, fragment lengths, library and CRC are unchanged.
AUTO uses the real installed PROGRAM ROM source. B0/B3 are unchanged; owner
RAM/ZP are restored and read back. Zero flash/journal/SPI/RTC writes, resets
or power cuts occurred during these correction checks.

## Requested additional allowance: three erases

| Sector | Purpose | Tracked count |
|---|---|---:|
|B1:A|Corrected sealed gate, high records and dense-library fragments|7→8|
|B2:E|Compact FLASH body and fragment loader|21→22|
|B2:F|Restore exact STATUS details and seal the FLASH image|17→18|

Three wear appends at **C500-C700, sequence1131-1133**. All21 current records
remain on chip, producing24 valid records. **Zero C/D erases, zero B3:E,
MON A/B or Foundation F writes**. C/D/E/F remain56/36/36/24.
These three erases are additional to the completed ten; they are not covered
by that earlier allowance. This review does not authorize them.

Preserve boot choice/binding/entries, name/offset/battery policy, RTC time/trim/PF
history, SPI SRAM/WORKSPACE, the entire original B0 and fresh owner RAM/ZP.
No power cuts. Other boards and published downloads remain outside the scope.

After installation, independently read back the three exact targets and verify
rich VERSION/STATUS/TIME/trim, actual ROM fragment loading, dense-I cancellation,
wide-Store NO, AREA/AUTO confirmation/NO, PROGRAM NO and the existing named tools.
An optional complete all-FF dense pass at the freshly verified blank B0:9 may
exercise the installed library without changing any byte, erase count or journal
record; stop if the sector is not all FF. No new fixture write is included.
Restore/read back owner RAM/ZP and release COM4 at recovery afterward.

Private pinned plan/artifacts:
`output/qualification/FLASH-status-correction-scope-20261101-r1/plan.json` and
`BUILD/flash-status-correction-r4/manifest.json`. Factory restoration, ASM/DBG,
wide flash AUTO and large returning BATCH remain separate work.
