# 2512 usable-utilities installation

Owner direction: fix and install the utilities, then test on the board. Stop
repeating full-board backup/checksum passes. Keep Foundation golden and retain
owner RAM. ASM/DBG follow this increment. Other boards and published downloads
are outside this installation.

The FLASH/BOOT RAM trial passed READ/VIEW, buffer EDIT, WRITE/BYTE/ERASE
cancellation, C/D/F refusal and Q. Its single fresh owner-RAM escrow was restored
by the existing readback/restore service. No flash or journal write occurred.

Install twelve changed image sectors:

| Target | Component |
| --- | --- |
| B3:A/B | Identical MON g0000000A / UI/1 |
| B3:8 | RTC provider, RAM gateway and native-app loader |
| B3:9 | RTC/history code; retain its existing final 1 KB metadata tail |
| B3:E | Services g6: cold command loading and APPS |
| B2:8/9 | WB2 g8; B2:A's identical PROGRAM-provider continuation is retained |
| B2:B/C/D | Full b35-derived CLOCK: read/status/SET, EUI, history, trim, offset, battery policy |
| B2:E/F | RAM FLASH/MAINT: sector editor, byte/sector programming, erase, BOOT/CONFIG, OIP1 |

Two ordinary append pages remain in C. Native journal rotation requires one D
erase. Preserve the current complete raw C/D archive already captured during
the RAM trial; retain C's records on chip and carry the latest boot/wear state
into D. This is compaction with the old D records archived, not a claim that
every old D record remains physically present. Final expected C/D/F counts:
53/34/24. F is never written. B0/B1, SRAM PROGRAM/WORKSPACE and RTC settings are
not installation targets.

One final CONFIG append retains default B and its bank enables/entries/delay,
binding B to the installed generation A. The expected sequence is 1056 after
twelve replacements, one rotation intent and this binding. Any identical target
is skipped and the recorded totals adjusted rather than manufacturing wear.

Read each target once before replacement and retain that preimage. Use the
existing OIP1 transfer/readback checks and durable erase reservation. These are
operation checks, not repeated full-board checksum or backup campaigns. Restore
the fresh owner RAM after the installation/test session.

Exercise actual VERSION/TIME, R CLOCK, detailed status, invalid/canceled SET,
R FLASH/R MAINT, APPS, MAINT, EDU ON, SRAM/WORK and TABLE. No successful CLOCK
SET, power cut, factory-firmware restoration, or deletion of owner programs is
part of this first installation. CLOCK's existing battery-policy stage latching
can append metadata when a warning stage changes; it does not set the clock.

Firmware factory restoration is a separate deliberate host operation using the
board's exact WDC backup. Ordinary FLASH continues to refuse B3:C/D/F.
