# 2205 current recorded inventory

November 2, 2026. The [approved compact rollout and acceptance](2205_FOUNDATION_ROLLOUT_ACCEPTANCE.md)
passed on W65C02SXB/COM3, USB A10MPUPNA.

- Foundation 0.3.0/g1 BASE1/PR05: exact frozen 4096-byte F.
- MON A/B g00000010: identical commands, Traditional startup; default B/g10.
- ASM/source and DBG g2; CLOCK, WB2 gE, PROGRAM g3, SRAM/WORK g4, STATUS and
  transfer/dispatch services. MAINT/FLASH are host REC-loaded BINs at $0200.
- Compact layout: 92 KiB occupied, nine erased sectors totaling 36 KiB.
- SNBT sequence909; C/D/E/F counts32/15/16/3 decimal. All original33 WC rows
  are archived; all32 cumulative counts carried forward. Tracked max is
  B2:8 at580 attempts; prior/direct lifetime and health remain unmeasured.
- Board name2205, offset-06:00, EDU ON, RTC trim-17/control$80; settings,
  calibration, EUI and power-fail history preserved.
- SPI SS2: 64 KiB PROGRAM / 64 KiB WORKSPACE; PROGRAM payload 63,488 bytes
  and WORKSPACE 65,504 bytes. Native P64 resize passed: exactly 74 management
  bytes changed, with the PROGRAM directory and every payload byte retained.
  Both old CLK records remain intact; their old ABI is not newly qualified.

The original b35 flash, WDC bank, journals, SRAM, owner RAM/ZP and legacy
runtime cache/vectors are permanently local and untracked at
`C:\SRC\STR8-N\local-archives\STR8-N-b35-2205-SPECIAL-20261102`.
Matching Foundation runtime replaces the archived legacy runtime. Original
owner RAM/ZP is restored and read back; final REC>, COM3 released. Native
TIME and LED/NIST collection is readmitted without resetting the baseline.

The consolidated local receipt is
`output/qualification/2205-foundation-rollout-complete-20261102.json`.
Recorded post-rollout bank hashes are in that receipt. Any later authorized
metadata or application update requires a newer inventory checkpoint.
No other board firmware, Candidate4 ZIP or published download changed.

The later 64/64 resize receipt is
`output/qualification/2205-SS2-64K-standardized-20261102-r1/report.json`.
All four boards now have recorded SS2/64K layouts; combined receipt:
`output/qualification/SS2-64K-four-board-complete-20261102.json`.
This metadata-only change used zero flash/journal/RTC-setting writes or resets.
Original SPECIAL and initial 32/96 rollout receipts remain unchanged.
