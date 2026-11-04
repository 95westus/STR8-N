# 2604 current recorded inventory

November 2, 2026. [Approved rollout and acceptance](2604_FOUNDATION_ROLLOUT_ACCEPTANCE.md)
completed on W65C02SXB/COM5, USB A10MQGVHA. MON A/B have identical commands.

| Region | Installed content |
|---|---|
| B0:8/9/E/F | Original erased bytes retained;8/9 are physically blank, not an automatic write allowance |
| B0:A/B | ASM/source g2, CPU02 AP/02 |
| B0:C/D | DBGg2 and D800-DFFF SF/1 provider, CPU02 AP/02 |
| B1:8-D | Qualified BANK MAINT2.4/g3, SRAM/WORK and transfer tools |
| B1:E/F | Original rc1/legacy owner bytes retained; not automatically BASE1-qualified |
| B2:8-F | WB2gE, PROGRAMg3, STATUS, CLOCK, FLASH/CONFIG and transfer services |
| B3:8/9 | Native RTC/loader/history code; all9C00-9FFF metadata exact |
| B3:A/B | MON A/Bg00000010, Traditional startup |
| B3:C/D | SNBTseq1252,26 valid records; C/D/E/F64/53/31/30 decimal |
| B3:E | Qualified dispatcher including R ASM/R DBG |
| B3:F | Frozen4096-byte Foundation0.3.0/g1 BASE1/PR05 |

Default B/g10; bank autostarts disabled, entries8000. Name2604, offset-06:00,
RTC trim-12/control00, PROGRAM payload14336 and WORKSPACE114656 bytes retained.
The largest tracked sector is B0:E with1024 attempts, carried forward from
the original history. This is not a new destructive wear test or a health claim.

Original rc1g0034 code/source, full128KiB double capture, all33 WC records and
all replaced images are permanently local and untracked under
`C:\SRC\STR8-N\local-archives\STR8-N-rc1-g0034-2604-20261102`.
The chip now has SNBT instead of WC records. Every tracked lower bound survives;
prior/direct lifetime stays unknown. Do not restore old journal counts blindly.

Owner RAM0200-66FF and ZP00-DF were restored/read back after all checks.
By explicit approval, legacy runtime cache/vectors are archived and matching
Foundation/MON state is initialized. Final REC>, COM5 released; saved B boots
on RESET or can be selected with B at recovery. RTC/NIST collection is readmitted
without resetting baselines. No other board or published download was changed.

Current physical bank SHA256:

- B0: `c7ff88bb43b5cfed1731323b882be975bd178735c9403205a1c4d950aa153fda`
- B1: `de63292f6e867f2d1e15bb861eb4004111e45acdb2842d336fda03a472275795`
- B2: `d221efe027d6407904375ac98ed26a5824342c48d7f5c330784319c6c0151f13`
- B3: `598437f07d259d3cf7871fee253488516e36608f5230d968d9ae059f267834d3`

No new flash/PROGRAM source-write fixture, WORKSPACE mutation or factory
restoration trial was included. Identical shared components reuse their prior
2512/2609 qualification; this receipt records the actual2604 installed checks.
