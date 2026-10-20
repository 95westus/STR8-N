# STR8-N 2.0rc1 candidate manuals

Target: **2.0rc1 generation 49, CLOCK 1.11, ASM 0.5, FT245/F30D**.
The published release remains generation 49. These manuals also cover the
**local DBG1 generation-50 extension**, now tested on 2604/2609 in both monitor
slots. Debugger sections require the matching DBG1 firmware and assembler;
neither the `2.0rc1` nor `ASM 0.5` title alone distinguishes it.
One firmware set serves 65C02 and 65C816 emulation runtime. The accepted startup
CPU detector briefly enters native mode; applications run with E=1. Native 816
applications/tests, ACIA and crypto remain deferred.

- [Installed-board quick start: name, time, offset and first programs](QUICK_START.md)
- [Migration overview](QUICK_START_MIGRATION.md)
- [Windows migration commands](QUICK_START_WINDOWS.md)
- [Linux migration commands](QUICK_START_LINUX.md)
- [Migration and recovery](MIGRATION_RECOVERY.md)
- [User guide](USER_GUIDE.md)
- [Operator guide](OPERATOR_GUIDE.md)
- [ASM 0.5 manual](ASM_GUIDE.md)
- [DBG1 RAM debugger: C/S/N and eight persistent breakpoints](DEBUGGER_GUIDE.md)
- [DBG1 BRK services and system/user registrations](ABI_REFERENCE.md#dbg1-brk-functions-and-registrations)
- [DBG1 board results and qualification limits](DEBUGGER_BOARD_RESULTS.md)
- [DBG1 v1g current status and continuing-soak evidence](DBG1_CANDIDATE_STATUS.md)
- [Program and command reference](COMMAND_REFERENCE.md)
- [Technical manual and Mermaid diagrams](TECHNICAL_MANUAL.md)
- [Public ABI reference](ABI_REFERENCE.md)
- [Firmware contents and programmer mapping](FIRMWARE_CONTENTS.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Inherited bf1 hardware scope

The empty-bank full-system RAM tools were exercised on physical 2609 (original
65C816 WDCMONV2 in B3) and 2604 (published beta4 in B3). B0/B1/B2 were erased
before each migration. Both completed all 22 device-verified transfers, booted
bf1, discovered/executed UCHESS and passed BATCH checks. These are bounded route
proofs, not arbitrary vendor/legacy or occupied-bank upgrade acceptance.

The portable launchers acquire the exact B3 source twice, archive application
RAM, derive a bound plan and use the same tested transport/worker. All four
bank preimages are checked on-device before any erase. Extra host RAM readbacks
can be skipped explicitly; an acknowledged RAM reload is then not host verification.
The live WDC route in this candidate admits the tested SXB6 65C816 source only;
SXB2 recognition/planning remains available offline. Both CPUs use the same target.

## Limits and release status

These manuals accompany the scoped rc1 release candidate. The owner accepted
recorded stopped soaks. RTC drift is outside release qualification.
Linux extracted scripts are tested on Linux; a Linux physical serial migration
has not been performed. An earlier WDC trial lost RTC continuity; the corrected
empty-bank trial retained a running valid RTC, but the earlier cause and broad
RTC-preservation qualification remain open. No migration tool issues clock,
trim or offset setters. Keep clocks and power evidence under observation.

Early factory-WDC interruptions without a valid rc1 fallback/journal may need an
external programmer and the original private backup. No WDC or intermediate
beta4 image is distributed. Retain the exact kit and all private recovery files.


[Choose boot/core, full-system or component downloads](RELEASE_PATHS.md).


[uChess ASM source session and S/T/R example](UCHESS_ASM_SESSION.md).


## rc1 qualification

Published firmware identity is 2.0rc1, generation 49. Source-build and offline
qualification retain prior bf1 transport/shared-CPU evidence. Subsequent rc1
board installation and the package-revision-2 UTC correction passed on both
boards; see the [UTC hardware update](../STR8N_RC1_UTC_BOARD_UPDATE_2026-10-18.md).
The historical [DBG1 v1e generation-50 trial](DEBUGGER_BOARD_RESULTS.md) passed on 2604
(65C02) and 2609 (65C816 E=1), both MON A/B. Original RAM was host-verified
after restoration and original preferences were restored. Both boards also passed the eight-hour rc1/ASM/DBG1 soak with 431 cycles and
6,896 breakpoint hits each; the final drift snapshot passed. See the same
result summary for slots, offsets and uncertainty. These are bounded
installation/smoke/soak results; they do not publish or promote DBG1. RTC qualification,
native 816 applications/tests, ACIA and crypto are deferred. Those recorded
results are accepted in their original scope, not as v1g endurance acceptance.

Current v1g offline and both-board/both-slot hardware requalification passed,
including MAINT, BRK `$82/$84`, registrations and rollback/reinstall. R3 and
R4 closed cleanly with original RAM, flash/settings and final drift verified.
R5 also closed safely with its original-phase checkpoint and final drift passed.
The ten-pattern LED R6 continuation passed 93 new offline checks, actual CPU
qualification and both-board hardware preflight, then closed cleanly at owner
STOP after 12,803.703 monitored/active seconds. 2604/2609 passed 61/60 cycles
and 976/960 breakpoint hits; both original full RAM images, flash/settings and
final preserving drift were verified, and actual worker exit was confirmed.
R6 had zero periodic checkpoints and one final checkpoint. Immutable
distribution r7 packages the reviewed closeout and checksums for the authorized
selective commit; full/extracted verification passed. The owner has approved scoped RC1 promotion. See [current candidate status](DBG1_CANDIDATE_STATUS.md).


A later separate saved-register qualification passed PC/A/X/Y/P/SP on both
boards and both monitor slots: 5,752 parser checks, 220 actual resumes and 132
unsafe-PC refusals, with original RAM restored and verified, and unchanged flash/settings.
See [register editing](DEBUGGER_GUIDE.md#editing-saved-registers) and
[the separate board results](DEBUGGER_BOARD_RESULTS.md#saved-register-edit-qualification).
R6 retains bare-R query-only scope and immutable r7 predates these tests.
RTC drift is outside release qualification; native applications/debugging remain
excluded and the owner has approved scoped RC1 promotion.

## Package revision 2: power-fail timezone label

The startup heading is `[power-fail UTC]`. Power-down/up timestamps are raw
UTC with minute precision; the separate RTCC line uses the configured display
offset. For example, October 18 04:35 UTC is October 17 23:35 at -05:00.
Only banner text, its data references and the sector checksum changed. Clock/trim values, event
handling, apps and migration/recovery algorithms are unchanged. The corrected
revision was verified offline and subsequently installed/device-verified on
both boards. DBG1 retains that correction.

## Owner-approved distribution r8

The owner authorized staging, archive/checksum verification, the related Git
commit and scoped RC1 promotion. The new package includes the separate R-register
qualification: 5,752 physical parser checks, 220 resume cases and 132 expected
unsafe-PC refusals across both boards and both monitor slots, with original RAM
restored and flash/settings unchanged. Supported runtimes are 65C02 and 65C816
E=1; native applications/debugging are excluded. **RTC drift is not part of
release qualification and is not a promotion gate.** Historical RTC records and
prior held archives retain their original scope and bytes. See the
[release policy](../../release/candidates/rc1-debugger-brkfix-r1/release-policy.json) for the owner decision.
