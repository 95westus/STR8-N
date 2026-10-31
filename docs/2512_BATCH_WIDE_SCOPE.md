# 2512 BATCH and large PROGRAM handoff

Continue the owner's requested BATCH/large PROGRAM increment on 2512 only.
F stays golden; 2205, 2604, 2609 and published downloads stay untouched.
No power cuts, RTC SET/trim/ACK, primary SRAM-header or WORKSPACE writes.

## RAM gate already passed

WB9/SP2 ran from RAM above installed MON gA. VERSION/TIME, bank/Table/WORK,
empty-list validation, live STORE cancellation, failure/unsupported/nesting
stop, small load-only, legacy registration refusal and native-loader capability
refusal passed. The existing 12 KB CLK record loaded across $4800 through the
independent tail, with loaded bytes checked; a final BATCH load-only remained
intact. No NVM was written and owner RAM/ZP was restored. The first RAM run
exposed an older dispatcher's error response being treated as success; explicit
capability admission fixed it before any installation.

## Installation

Thirteen utility-sector replacements, each preimage archived and target verified:

| Sectors | New component |
| --- | --- |
| B2:8/9/A | WB9 and SP2, including independent load/run tail |
| B2:B/C/D | CLOCK command-prompt BATCH adapter |
| B2:E/F | FLASH/MAINT command-prompt BATCH adapter |
| B3:8 | Shared native prompt transport and loader admission |
| B3:9 | Return context; preserve the existing final 1 KB RTC metadata |
| B3:A/B | Identical MON gB, private UI/1 command vector and BATCH return |
| B3:E | Services g7, checked errors/AP launch and coherent WB/SP cache |

Keep default B, mask0F, all four $8000 entries and delay30. One CONFIG append
binds that same B default to generation0000000B. Do not rewrite F.

Fresh C/D state is sequence1065, 20 records, C54/D34/F24. The current C sector
has eleven ordinary append pages before its final intent page. This transaction
needs one native **D erase**; archive its sixteen original rows first. The four
original C rows remain on chip; carry the latest wear/boot snapshot forward.
Raw history preservation on the host is distinct from retaining every row on
chip after compaction.

## Temporary functional targets

- PROGRAM slots3/4, plus payload $A000-$D73F: **14,272 exact bytes**, freshly
  backed up. Slots5/6/7 (CLK, CLOCK, NFCOPY), primary format and WORKSPACE remain
  untouched. Install a temporary 14 KB registered PR05 program spanning owner
  RAM $3000-$66FF; exercise load/run/return, CRC refusal and copy cancellation.
  Exercise an ordinary live-confirmed BATCH STORE/Restore/run in the second
  slot. Restore every temporary byte and verify those targets afterward.
- B0:9, presently FF: temporary checked AP/02 application and return thunk.
  Two erases cover installation and exact FF restoration. Initially withheld
  checksum bytes test refusal; completing those FF-to-value bytes needs no
  additional erase. Test that the queue waits for the application's live Q.
- Owner RAM $0200-$66FF and ZP $00-$DF are borrowed for tools/tests, then
  restored from the fresh pre-helper escrow. Native FLASH keeps its queue in
  the saved return context, outside the 4 KB edit buffer.

Maximum **16 erases: thirteen utility, two B0:9, one native D rotation**.
Expected final C54/D35/F24, B0:9=20, sequence1082 and 21 on-chip records,
assuming all thirteen images differ and all planned trials finish. Skip an
identical image and adjust the ledger rather than manufacturing wear.
No erase is automatically retried after an uncertain result.

## Acceptance and return

Use real BATCH monitor edits/dumps, maps/wear/APPS, live confirmations, CLOCK
and FLASH menu transitions, protected-target/error/cancel stop, registered
PROGRAM and AP/02 handoffs, and a wide final load-only without a destructive
tool reload. Raw G/L/reset and unregistered handoffs remain excluded as in
b35; confirmations are never supplied by the command queue. A wide load-only
must be final because reloading tools would overwrite its destination.

Verify the installed saved-default boot with one requested physical RESET,
restore owner RAM/ZP, leave EDU ON for the session and release COM4 at B3>.
Keep prior RTC/NTP evidence and re-admit only 2512's changed monitor reader.
This closes the specified increment, not unrelated full-b35 release gates.

## Installed-test repair addendum

The thirteen replacements and B-generation binding completed. The installed
suite passed through MAINT/native transitions, then its A-slot check exposed
a stale workbench-origin flag: a new MON BATCH could finish in WORKBENCH.
Owner RAM/ZP was restored before repair. Ordinary WB Q now clears that flag;
WB generationA and services generation8 force coherent cache replacement.

Native UI scratch also moves from $6630-$6638 (inside CLOCK's gateway code)
to reserved $5B10-$5B18. Test VERSION followed by TIME before installing this
return-context correction. Native application bodies and F are reused.

Four additional replacements: B2:8/9, B3:E and B3:9. B2:A is identical and is skipped. Preserve sector9's
metadata tail and archive all four current preimages. No additional journal
erase or boot-policy append is needed. Expected post-repair sequence1084;
counts C54/D35/E31/F24. The original D archive remains retained.

The complete trial ceiling becomes **20 erases**: seventeen utility-image
replacements, two temporary B0:9 replacements and one native D rotation.
Expected after those temporary tests: sequence1086, 25 on-chip records,
B0:9=20 and C54/D35/E31/F24. The four-sector repair is required to close the
installed return-path failure; it is not a repeated full-suite reflash.

## Cancellation-message repair and reduced AP/02 scope

The partial wide copy safely returned from its resident tail, but frozen F
intentionally mutes text while its cancel flag remains set. A three-byte
RX_RESET call acknowledges cancellation before printing `Partial; not run`.
Only PROGRAM is rebuilt; support/WB/E/native bytes are reused. The new SP
occupies its exact 3326-byte code limit plus two CRC bytes. RAM qualification
precedes two required image replacements, B2:9/A. Both preimages are pinned;
no B3 image or F write and no C/D erase are included. Counts after repair:
B2:9=269, B2:A=15; sequence1086, 25 on-chip records, C54/D35/E31/F24.

Automatic review rejected the proposed two-erase AP/02 path against the prior
one-erase 2512 allowance. The reduced path reads/verifies B0:9 completely FF,
programs only the temporary application's non-FF bytes using guarded 1-to-0
!M, and uses the one approved erase for exact FF restoration. Header CRC is
withheld for the refusal case, then programmed for the live-Q return case.
No installation erase or retry is allowed. Final sequence1087/26 records,
B0:9=19; C54/D35/E31/F24 unchanged. Actual complete increment ceiling is
**21 erases**: nineteen utility replacements, one native D rotation and one
B0:9 cleanup. All earlier record history remains on chip or in its existing
pre-rotation raw host archive. No power cuts or other-board access.
