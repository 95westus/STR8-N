# 2604 rc1 g0034 to Foundation: completed acceptance

November 2, 2026. The owner approved the exact 27-erase scope and the correction
to archive old provider cache/interrupt/HOLD vectors while initializing the
matching Foundation runtime. Original owner RAM/ZP and persistent data remain
preserved. [Current inventory](2604_CURRENT_INVENTORY.md) records the layout.

## What ran

Fresh native source/owner escrow admitted the exact rc1 F and four source banks.
The unchanged qualified RAM engine appended WCseq1225 at D080, then converted
C/F/D: committed SNBT/S root, exact frozen F, newer SNBT/S root. Physical RESET
reached BASE1 REC>; independent four-bank readback and owner restoration passed.
This separately inspected WC conversion did not bypass the public b15/SNBT
upgrader guard or reset counters. It is a private board-bound transaction.

The23 reviewed image sectors were replaced with accepted binaries, using25
native journal appends including the C rotation and final B-default binding.
Three conversion erases plus23 image erases plus one C rotation =27 total.
There was one F replacement, no F rebuild or later F write. Both rollout CPU
resets passed; no power cut, automatic retry, SPI-data/RTC-setting/PF-ACK write
or other-board access occurred. An earlier RAM-probe cleanup needed one
separately requested CPU RESET; that preflight incident and successful owner
restoration remain recorded rather than being counted as a rollout failure.

## Actual installed checks

- MON A/Bg10 VERSION, CPU02/board metadata, fresh TIME/trim and Traditional startup.
- Full CLOCK, BANK MAINT2.4/g3, FLASH and SRAM/WORK/TABLE front doors; APPS lists ASM/DBG.
- Returning BATCH; assemble/export/read back/run a RAM program through public HOLD.
- Real DBG BRK step, continue and restoration of the new default hooks.
- Physical saved-default B boot with EDU ON and original14336/114656 capacity split.
- Nine native TIME/NIST readings and unchanged794-byte62-second LED sampler.
- Final expected four-bank image/settings/journal/F readback and exact owner RAM/ZP restoration.

The RTC host gate initially assumed another board's control80. Original2604
receipt and both successful new sample sets show control00, trim-12. The host
gate was corrected against that original receipt; successful samples were
reused, no clock register was written and no sampling replay was needed.
The failed outer gate and the r2 closeout are both retained. Baselines,
segment boundaries and the other boards' admission entries remain unchanged.

## Preservation and result

All33 original WC rows, raw C/D and every original image are in the permanent
untracked local archive. Zero old WC rows remain on chip after the approved
format conversion. Maximum historical counts carry forward; final C/D/E/F
64/53/31/30, seq1252 and26 valid SNBT records, prior-lifetime maskFFFFFFFF.
Default B remains B, generation binding becomes g10; disabled bank autostarts
remain disabled. Board name2604, offset-06:00 and all9C00-9FFF metadata bytes
are exact. RTC time/trim/control/PF/EEPROM and SPI PROGRAM/WORKSPACE are retained.

F SHA256: `8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`. Owner RAM SHA256: `b8b4220b0863ee70b3913693cf678c3a3938035276ec55f7c2a74b1ef3399538`.
Owner ZP SHA256: `c07817ebe5189395c1ab5ce1d9e72dda0698717180a0d95a0d59933fc580ecca`. Final REC>, COM5 released and RTC readmitted.
2205/2512/2609 hardware and published files were untouched by this rollout.
No firmware build or CPU simulation ran.

Private receipts: `output/qualification/2604-foundation-rollout-scope-20261102-r1/completion.json`,
conversion/profile/default-reset cases, and RTC readmission r2. Permanent
history closes at `local-archives/STR8-N-rc1-g0034-2604-20261102/approved-Foundation-rollout-20261102/ROLLOUT-COMPLETE.json`.

The private conversion and installed smoke checks do not claim new2604
persistent source/STORE/WORKSPACE positives, factory restoration or full replay
of2512's adversarial suite. Public release downloads and candidate ZIPs remain
unchanged; this work does not publish a generic rc1 migration route.
