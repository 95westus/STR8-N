# 2609 MON B and tools preview acceptance

**Installed and passed October 30, 2026: 65C816 emulation / FT245 only.**
[Installed receipt](../monitors/validation/2609-mon-feature-install.json),
[RTC receipt](../monitors/validation/2609-mon-feature-rtc.json),
[operator manual](MON_FEATURE_PREVIEW.md).

For the latest slot/journal/RAM state, see the
[current recorded inventory](2609_CURRENT_INVENTORY.md). The installation
checkpoint below was followed by positive PROGRAM and AP/02 acceptance.

2609 now has frozen N-F 0.3.0 g1 BASE1/PR05, MON B 0.1.0-dev g8,
services g4, WB2 g5 and PROGRAM/SP1 g1. At this installation checkpoint,
MON A remained retained b15 firmware and was unqualified under BASE1. It has
since been replaced by [qualified MON A g8](2609_MON_A_G8_ACCEPTANCE.md).
At REC>, type `B` and Enter; on RESET, select B at the chooser.
The saved default remains S/recovery.

## Usable increment

The physical MON B boot preserved all owner RAM/ZP. Identity, Dump/Modify,
F/C/D force guards, bank inspection, TIME, M1/W and APPS inventory passed in
the combined RAM/ROM checks. CLOCK loaded from board flash, refreshed and
returned. MAINT LOAD now explicitly reloads the current tools; cold, warm,
spaced and bad-argument cases passed in RAM and installed forced reload passed.

The existing SS1 PROGRAM directory and four retained CLK records were listed.
Guarded SRAM PREP acknowledged disabled VIA CB flags when required, with no
SPI clocks. `BATCH T;T` completed; malformed separators were refused. Missing-
name Restore and AUTO Store preview were checked, with NO canceling the Store.
Q returned from tools to MON B and from MON B to REC>.

At this initial installation checkpoint, positive PROGRAM Store/Restore/run
and AP/02 owner-app launch retained only the separately scoped earlier receipts.
Later positive 816 trials are linked below. Full SOURCE/ASM/DEBUG, complete core/app BATCH parity,
advanced CLOCK, the 4KB FLASH editor and CONFIG integration remain open.

## Writes and preservation

The [approved first scope](2609_MON_FEATURE_INSTALL_SCOPE.md) replaced
B2:8/9/A and B3:E/B, with five wear appends CA00-CE00 and no C/D erase.
All 11 old raw rows were retained at that checkpoint. The physical boot then
exposed MAINT LOAD forwarding its consumed option to the workbench. A narrow
dispatcher fix was built once; F, MON, WB2, PROGRAM and loaders were reused.

The separately [approved D/E repair](2609_MAINT_RELOAD_REPAIR_SCOPE.md) replaced
E again and rotated D. Total: seven sector erases, seven new journal records,
zero F writes, zero C erases, no power cuts. All 15 pre-repair C rows remain
at their original locations. Old D000/seq1014 is preserved in a complete,
hash-verified host D-sector archive rather than on the chip.

Installation checkpoint journal: 17 valid rows, latest D000/seq1031. C=78, D=48, E=45, F=31;
B2:8=603, B2:9=262, B2:A=14 and B3:B=55. Default S, mask00, entries8000 and
other boot-policy bytes are unchanged. B0/WDC, B1, other B2 sectors and
B3:8/9/A/B/F outside the explicit target/history changes match their expected
images. B3:B changed only in the first approved scope and was unchanged by
the repair. No SRAM-data, EEPROM, RTC SET/trim/PF acknowledgement was issued.

All four banks matched exact final postimages. Owner RAM0200-66FF and ZP00-DF
were restored/read back. Final REC>, COM8 released. 2205, 2512 and 2604 were
not changed by this installation; 2604 remains the integrated rc1 reference.

## RTC continuity

The unchanged qualified RTC RAM instrument passed nine fresh NIST/NTP reads,
full before/after double bank comparisons, exact read/load/restore trace audit,
and owner RAM/ZP restoration. Trim remains -14; no clock/trim/PF write occurred.
Its new admission records the installed flash hashes and MON B generation.
The hourly four-board schedule, random extra 2512 sample, baselines and all
historical points remain intact. Busy operator sessions remain deferrals.

## Current footprint

F has 367 free bytes and stays frozen. MON A/B g8 each have 67 free bytes;
services g4 has 82. WB2 g5 has 30 free bytes in its 7KB module; PROGRAM/SP1
has 487 free bytes. The combined flash tool bundle occupies B2:8/9/A.
Loaded tools borrow RAM4800-66FF and PROGRAM code6B00-77FF; application RAM
while loaded is0200-47FF. These tails are internal component space, not free
owner sectors. No assembler or CPU simulator was run for the installation;
only the necessary dispatcher repair was assembled, once.

Private evidence is retained under the 2609 feature-install, g4-repair and
RTC-qualification directories in the parent project's output/qualification.
Published N-F 0.3.0 bytes and existing downloads remain unchanged.

## Subsequent positive PROGRAM gate

The same installed tools later passed the
[2609 PROGRAM Store/Restore/run trial](2609_PROGRAM_POSITIVE_ACCEPTANCE.md).
Its separate receipt adds positive SS1 storage/run evidence with all temporary
bytes restored and no flash/journal writes. The earlier query/cancel-only
checkpoint above remains historical. The separate
[AP/02 flash-launch trial](2609_AP02_ACCEPTANCE.md) also subsequently passed,
leaving 19 records at seq1033 with original WDC restored. Native 816 tools and
the deferred, nonblocking [ASM/DBG port](MON_ASM_DBG_RELEASE_GATE.md) remain separate.
