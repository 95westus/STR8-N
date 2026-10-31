# Familiar APPS and program workflow above Foundation

Owner clarification, October 30, 2026: use the familiar 2205/b35 and
2604/rc1 operator workflow and full tools. Running their exact old binaries
unchanged is not the compatibility target. Preserve those historical branches
and reference boards. Frozen N-F BASE1/PR05 remains the foundation.

The later [BANK MAINT2.4 transcript](BANK_MAINT_RESTORATION.md) refines this
contract: full BM operations, compact cross-bank Table and richer status
are required. The increment accepted below is not that completed port.

## Operator contract

- APPS is a readable tool catalogue: names, flash locations and launch
  commands, followed by checked compatible owner applications.
- R CLOCK opens the detailed CLOCK app, including SET and administration.
- R FLASH opens the sector/byte/editor tool; R MAINT opens board maintenance
  and BOOT/CONFIG. Direct MAINT retains its storage workbench entry.
- R EDU, R SRAM and R WORK are familiar named entry points to the matching
  existing commands; RESTORE is equivalent to R. Plain EDU/SRAM/WORK still work.
- TABLE/STORE/RESTORE and T/S/R work with flash records and mounted PROGRAM;
  AUTO chooses a storage address inside an admitted area. R name runs;
  R name L loads only. Listing and errors identify the backend/location.
- Programs and tools return coherently to Bx>; returning BATCH retains its
  stop/cancel and live-confirmation behavior. Full tools, rather than help
  screens or a generic soak, determine release completion.

## First increment

The candidate expands APPS from one line to a useful catalogue, adds the
three R/RESTORE aliases and accepts ordinary spaces in native R tool names.
A reserved tool's bad arguments remain syntax errors, not a stored-program
search. No F ABI, storage format or owner-image compatibility is redefined.
The repeated internal loader-address message becomes `Loading tools...`;
RAM ownership remains documented and visible in the workbench.

This does not complete full-b35 parity. Full SRAM management, remaining
Table bank/range/management forms, large STORE-source staging, positive
CLOCK/CONFIG write workflows and factory restoration remain open in the
[unified shipping contract](UNIFIED_SHIPPING_RELEASE.md). The current SRAM
alias queries existing PROGRAM status; it does not add format/delete/reclaim.
WORK remains its existing query/interface, not a new workspace manager.
ASM/DBG remain follow-on work.

## 2512 installation review

Require the RAM trial to pass first. Exactly three utility replacements:
B2:8/9 (WB2 gB, provider reused), B3:E (services g9). B2:A and native apps
are identical and retained. Native journal admission shows five ordinary
pages after D900; reserve only DA00/DB00/DC00. Zero C/D erases, F writes,
boot-setting appends, SRAM writes, RTC settings or power cuts.

Fresh owner RAM/ZP escrow is taken before RAM loading. Each target is freshly
read and admitted against its pinned preimage; retain those three preimages
on the host. Expected sequence1090/29 records; B2:8=600, B2:9=270,
B3:E=32. C54/D35/F24, default B/gB, enabled banks/entries/delay and all
existing journal records are preserved. Restore owner RAM/ZP and EDU session
state; release COM4. Leave 2205/2604/2609 and published downloads unchanged.
This review records the bounded scope under the owner's continuing direction
to fix the utilities and flash 2512 as needed; it is not a new release claim.

## Accepted on 2512

Installed MON A/B gB unchanged, WB2 gB, services g9; native r16 and PROGRAM
g2/cancel r5 are reused. The RAM trial and installed operator workflows passed:
named R/RESTORE EDU/SRAM/WORK, Table/Restore of existing PROGRAM, CLOCK
VERSION/Q, MAINT BOOT/Q, APPS, bad arguments and BATCH error/unavailable stop.
All three replacements were independently read back. All26 prior physical
journal records remain byte-identical; sequence1090/29 records, default B/gB
and entries/enables retained. Owner RAM/ZP were restored, EDU is ON and COM4
is released at B3>. [Machine receipt](../monitors/validation/2512-classic-workflow.json).

The initial RAM-only argument-error trial fell through to the older dispatcher
and replaced an active RAM workbench. It reached recovery with inconsistent
RAM-worker state. Recovery restored owner RAM/ZP; one requested physical reset
reinitialized the worker, and owner/ZP samples matched. Final wrappers report
reserved-name errors locally and preserve BATCH's error result. The corrected
RAM and installed trials passed without NVM writes during RAM testing.
Four WB builds were necessary for carry/error corrections; E was built once,
with existing loader/provider/native bytes reused. No CPU model was run.

WB code now uses7166/7166 bytes, excluding its2-byte CRC; services E has1 byte
free. Further full-tool work needs a reviewed layout/module change rather
than silently taking owner space or unfreezing F. The existing candidate2 ZIP
remains its prior WB gA/services g8 snapshot; it is not renamed in place.

RTC/NTP continuity passed after installation: nine native TIME reads and a
NIST reference appended one audited point. Baseline, trim, prior history and
existing cadence were retained. No other board was accessed.
