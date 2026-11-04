# 2609 current recorded inventory

## November2 installed developer checkpoint — current

The [approved ASM/DBG installation](2609_DEVTOOLS_INSTALLED_ACCEPTANCE.md)
passed16 checkpoints on2609/65C816 emulation. R ASM/R DBG, APP aliases and
APPS now launch the installed tools. F and MON A/B stay unchanged.

| Region | Current content |
| --- | --- |
| B0:A/B | ASM/source helper, CPU16 AP/02 envelope |
| B0:C/D | DBG g2 and exact D800-DFFF SF/1 provider, CPU16 envelope |
| B0:8/9/E/F | Original vendor bytes/filler retained; B0 is no longer a complete WDC image |
| B1 | Existing BANK MAINT, SRAM/WORK/transfer and legacy E/F retained |
| B2 | Existing WB2 gE, PROGRAM g3, STATUS, CLOCK and FLASH/CONFIG retained |
| B3:8/9 | Existing RTC/loader and all metadata retained |
| B3:A/B | MON A/B g00000010 retained |
| B3:C/D | Sequence1095,17 valid rows; C/D/E/F counts80/50/50/31 decimal |
| B3:E | Qualified R ASM/R DBG dispatcher, retaining the full utility profile |
| B3:F | Golden Foundation0.3.0/g1 BASE1/PR05,4096 bytes |

Default B/g10, disabled bank boots, entries8000 and captured board/RTC metadata
remain exact. All27 old journal records are archived on the host;11 old C rows
remain exact on chip and16 old D rows were replaced as approved. The complete
original WDC B0 bank is verified in the private scope archive. No SPI-data,
RTC-setting, reset, power-cut or other-board operation was included. Owner
RAM0200-66FF, ZP00-DF, full6B00-77FF cache and hooks were restored/verified.
Final REC>, COM8 released, RTC eligible.

Current physical bank SHA-256 values:

- B0: `d59014f25aead8087bd591e6899cce4c5ad60f87c66d72cef55c930126d38ba0`
- B1: `de63292f6e867f2d1e15bb861eb4004111e45acdb2842d336fda03a472275795`
- B2: `d221efe027d6407904375ac98ed26a5824342c48d7f5c330784319c6c0151f13`
- B3: `28bb4dca2b9d57e97e4f27d02b28c6b54c2b3cdf0a75c98bf97955390cf3da5a`

Positive source-write tests remain separate; read-only FLASH/PROGRAM source
lookups passed. No erased SF/1 source sector exists in B0:8-D. No utility
retirement or legacy-image reclamation occurred during this installation.

## Earlier November2 developer RAM qualification

The [ASM/DBG g2 emulation RAM trial](DEVTOOLS_2609_EMULATION_RAM_ACCEPTANCE.md)
passed13 groups using the exact extracted candidate2 binaries and console
sender. E=1 and D/DBR/PBR=0 were verified before/after; native16-bit operation
was excluded. All four flash banks stayed exact, including WDC B0, current
utilities, MON A/B, settings/history and golden F. No persistent writes,
reset or power cut occurred. Owner RAM/ZP/full cache/hooks were restored;
final REC>, COM8 released. RTC collection retained priority and other boards
were untouched. This RAM trial preserved the then-current Candidate3 inventory.
The later [six-erase scope](2609_DEVTOOLS_FLASH_SCOPE.md) was separately approved
and executed; the current installed checkpoint above supersedes that baseline.

## Historical Candidate3 installation checkpoint

November2,2026. W65C816SXB,65C816 emulation/FT245,COM8. The latest
[Candidate3 acceptance](CANDIDATE3_2609_LIVE_ACCEPTANCE.md) supersedes the
October31 checkpoint retained below.

| Region | Content at this earlier checkpoint |
| --- | --- |
| B0 | Preserved WDC/SXB6 image; outside this upgrade |
| B1:8-D | Candidate3 BANK MAINT and SRAM/WORK/transfer tools |
| B1:E/F | Retained owner/legacy contents |
| B2:8-A | WB2 gE, PROGRAM g3 and shared STATUS components |
| B2:B-D | Unchanged CLOCK1.10 |
| B2:E/F | Current FLASH/CONFIG/transfer components |
| B3:8/9 | Current RTC/loader; B3:9 code and1024-byte metadata unchanged |
| B3:A/B | Identical-command MON A/B g00000010, BASE1/PR05 |
| B3:C/D | seq1089,27 valid rows; counts C/D/E/F80/49/49/31 |
| B3:E | Candidate3 shared dispatcher/services |
| B3:F | Frozen Foundation0.3.0 g1, BASE1/PR05,4096 bytes |

Saved default B/g10; bank boots disabled, entries8000. Board name2609 and
local display offset-05:00 retained. RTC trim0E (-14), control80 retained;
native TIME and the unchanged62-second LED sampler readmitted. Original
owner RAM0200-66FF and ZP00-DF are restored/read back. Final REC>,COM8 free.
All26 pre-upgrade journal records are archived;10 old D rows remain on chip.
No F write, power cut, SPI/RTC settings write or other-board access occurred.

Physical bank SHA-256 values at this earlier checkpoint:

- B0: `1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`
- B1: `de63292f6e867f2d1e15bb861eb4004111e45acdb2842d336fda03a472275795`
- B2: `d221efe027d6407904375ac98ed26a5824342c48d7f5c330784319c6c0151f13`
- B3: `868638f6c9d6192728005ea89393c4bc51e9f284c21eec3edd13138d0c60688c`

The exact prepared targets and independent live readbacks are retained with
the approval/closeout receipts. Their settings and owner data are not part of
the distribution. No automatic flash action remains.

## November2 stored CLK cleanup

The owner requested removal of the multiple CLK records. PROGRAM slots4-7
(sequences4/3/2/1) are now retired; TABLE P has no CLK entries. All four
payloads and their original directory are archived privately under
`output/qualification/2609-CLK-cleanup-20261102-r1/`.
Only commit bytes0017F/001BF/001FF/0023F changed fromA5 to00. Payload bytes
remain untouched and their pages are available for PROGRAM allocation.
The installed native `R CLOCK` app still launches. F, images, boot/settings,
journal, RTC calibration/history and WORKSPACE remain unchanged. Fresh owner
RAM/ZP was restored/read back; final REC>,COM8 free. No flash erase, reset,
power cut or other-board access occurred. Receipt: `report.json` in that archive.

## Historical October31 inventory

The following inventory and hashes describe that older checkpoint.


October 31, 2026. **W65C816SXB, 65C816 emulation / FT245, COM8.**
Updated after [MON gC/STATUS](MON_STARTUP_STATUS_ROM_ACCEPTANCE.md) and the
approved [full CLOCK/native utility installation](CLOCK_2205_EQUIVALENCE.md).
The later [BANK MAINT acceptance](BANK_MAINT_ACCEPTANCE.md) is complete:
R MAINT opens BM>, with the same installed MAINT/WB2/services images as2512.
The [MON gD TIME update](MON_TIME_TRIM.md) is also installed and qualified;
native sampling now reads live control and trim on each observation.
The utility install, live CLOCK/read-only tool checks and owner-RAM restoration
passed. Current B2/B3 readbacks match the exact reviewed images and journal.

## Installed flash

| Region | Current content / status |
| --- | --- |
| B0 | Preserved WDCMONv2/SXB6 bank, restored exactly after AP/02 testing |
| B1:8/9/A | BANK MAINT2.4 / BASE1 PR05 g1; old UCHESS arena archived on host |
| B1:B-F | Retained owner/legacy contents, including CLOCK |
| B2:8/9/A | WB2 gC + PROGRAM/SP1 g2; shared STATUS g1 extents retained |
| B2:B/C/D | Full CLOCK 1.10 / BASE1 g1 |
| B2:E/F | Native FLASH/MAINT g1/r16; shared STATUS g1 retained |
| B3:8/9 | Native RTC provider/gateway/loader revision3 and BM BATCH reader; history/return and target metadata retained |
| B3:A | MON A **0.1.0-dev g0000000D**, **PR05**, ROM-tested on 65C816 emulation |
| B3:B | Identical-command MON B **0.1.0-dev g0000000D**, **PR05**, ROM-tested on 65C816 emulation |
| B3:C/D | Valid boot/wear journal, **19 records**, latest **D200 / 1065** |
| B3:E | Services gB: maps, wear, APPS and named/native tool dispatch |
| B3:F | Frozen **STR8N-F 0.3.0 g00000001 / BASE1 / PR05**, 4096 bytes |

The full B2 bank is byte-identical to2512's current tool bank. Both MON slots
match the same prebuilt gD candidates installed on2512.
Historical marker fields about older debugger/monitor generations are retained
history; the actual current slot headers above identify the installed A/B images.

## Boot policy and journal

Saved default **MON B / generation0000000D**, all bank boots disabled (mask00),
stored entries8000. The original default-B change was C500/seq1052. After the
approved gD installation, D200/seq1065 rebinds that same B default to generationD.
Foundation's software startup selected B gD automatically. Owner RAM/ZP
were restored/read back; final context **B3>**, COM8 released. At REC>, `B` and Enter
starts qualified MON B; `A` starts qualified MON A. Their Q returns to recovery.
These selections do not change the saved default. A and B have identical commands.
Original PR04 A is preserved in verified host archives rather than on chip.

Tracked C/D/E/F counts are **79/49/47/31**; B3:A/B are54/57 and B0:9 is6.
These are conservative tracked attempts, not lifetime totals. Ordinary pages
D300-DE00 are free; DF00 is reserved. The approved gD update archived all31
pre-update rows, replaced16 old D rows with one native D rotation, retained
all15 old C rows exactly and carried every count forward. The older CLOCK and
MAINT captures remain retained. Erased-looking or retained regions do not
imply permission to overwrite.

## Current usable tools

MON A/B provide Dump/Modify, guarded force Modify, bank selection, concise TIME,
rich VERSION/startup, maps, wear and APPS. MAINT LOAD brings in the matching
board-flash workbench. R CLOCK starts full CLOCK1.10; R FLASH starts the
FLASH/CONFIG panel, and R MAINT starts BANK MAINT2.4 at BM>. EDU/SRAM/WORK,
PROGRAM and flash/SRAM Table/Store/Restore,
AUTO and BATCH are in the same current utility images as2512.

Installed CLOCK summary, detailed queries/history, cancelled settings and Q
passed on65C816 emulation. FLASH VERSION, sector read/view, BOOT inspection and
C/D/F protection passed without a flash edit. Positive PROGRAM Store/Restore/run
and AP/02 were previously qualified under the older g4/WB5/SP1 profile; this
CLOCK trial did not repeat positive storage writes under the new profile.
APPDEMO was temporary; original WDC B0 remains preserved.

PROGRAM uses the retained SS1 layout and CLK records; WORKSPACE is separate.
No SRAM reformat or duplicate cleanup on2609 is included here. The owner later
set board name **2609** and fixed display offset **-05:00**. Two32-byte metadata
records at B3:9C00/9C20 were appended with no erase. The MAINT name-clear/restore
test added two BN rows at9C40/9C60;28 metadata slots remain.
RTC UTC time, control/trim, raw EEPROM history and all boot/wear records were
preserved. Battery age remains unset; STATUS uses --* for unavailable metadata.
Resident ASM/DBG and old X named flash/PROGRAM transfer remain deferred.
MAINT copy/compare, naming, TABLE and the sector editor passed, including
positive flash operations and exact WDC B0:9 restoration. Positive CLOCK
setting qualification remains separate. Native816 execution is not claimed.

## Owner RAM and RTC/NTP

After the default-B change, RTC collection uses the separate
**MON-UI1-GD-TIME-TRIM** reader. It accepts REC> or B3> and restores the
original prompt; the earlier gC/fixed-prompt readers remain unchanged. The sampler
uses MON TIME without a RAM upload; the existing baseline and hourly schedule
remain unchanged. Each nine-sample burst verifies current trim/control;
accepted values are-14 steps, OSCTRIM$0E and control$80, matching CLOCK.
No time, trim or power-fail acknowledgement was issued. The current latched
outage is retained; preflight admission does not establish power continuity.

The October31 CLOCK installation took a fresh native owner RAM/ZP escrow,
then restored and read back its own captured bytes. Historical reconciliations
and installer/AP02 captures remain retained. Future trials must capture and
restore fresh owner data; never substitute an older escrow.

Reference RAM SHA-256:
`7e2bde1b539960111a3619b1c28ccb60abf5e375e58d7267903b26284dfbcc76`.

Reference ZP SHA-256:
`c6b086f132bd3d7c98f93e52313d131a7821d896f57562601dcbd2685ea890af`.

## Qualification and WDC boundary

Historical [MON A g8 acceptance](2609_MON_A_G8_ACCEPTANCE.md) and its review
remain preserved. [MON gC/STATUS acceptance](MON_STARTUP_STATUS_ROM_ACCEPTANCE.md)
and the [approved CLOCK scope](2609_CLOCK_NATIVE_SCOPE.md) describe the newer
checkpoint. The CLOCK update used11 utility erases and one native C rotation.
The later MAINT update used seven image erases plus two B0:9 acceptance/restore
erases, with no C/D erase. The gD update then used two A/B erases and one
approved native D rotation, retaining every count and archiving prior rows.
All approved actions are complete; no pending
automatic flash action or unused retry allowance remains.

The 2512 WDC launcher is pinned to a **65C02/SXB2** ROM. It is not installed
or qualified on 2609's **SXB6** ROM. The recorded B0 reset vector is F818,
but its serial vectors and firmware differ. A 65C816 launcher needs its own
entry/mode review. Existing BASE1 F and SNBT also mean 2609 is not a fresh
factory-migration fixture; NFM2 provisioning must not erase its retained history
merely to obtain a WDC-source test.

Evidence: [CLOCK/native profile](CLOCK_2205_EQUIVALENCE.md),
[historical MON/tools](2609_MON_FEATURE_ACCEPTANCE.md),
[PROGRAM](2609_PROGRAM_POSITIVE_ACCEPTANCE.md), [AP/02](2609_AP02_ACCEPTANCE.md).
Private CLOCK restoration receipt:
`C:\SRC\STR8-N\output\qualification\2609-CLOCK-native-install-20261031-r1\final-receipt.json`.
Subsequent default-B change and current restoration:
`C:\SRC\STR8-N\output\qualification\2609-default-MON-B-20261031-r1\report.json`.
Subsequent name/display-offset update and current restoration:
`C:\SRC\STR8-N\output\qualification\2609-name-offset-20261031-r1\report.json`.
Current MAINT installation and owner-RAM restoration:
`C:\SRC\STR8-N\output\qualification\2609-BANK-MAINT-installed-20261031-r1\report.json`.
Current gD installation and fresh-trim NTP registration:
`C:\SRC\STR8-N\output\qualification\2609-MON-trim-installed-20261031-r1\report.json` and
`C:\SRC\STR8-N\output\qualification\MON-trim-RTC-admission-20261031-r1\final-receipt.json`.

Recorded bank SHA-256 values:

- B0: `1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`
- B1: `5b6d99ade31a79fe362e5ff7869f89bf9b8e89fcf89190b25523ffcd2b1b63b8`
- B2: `54879c0fbe70ab0da018f8839ab4462c589be79cc016010cfbd9b575c28f979d`
- B3: `f47bcff60d441c65be767f405194b5188b518595164079ffd77e87e7d40e5066`
