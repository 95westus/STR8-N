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
recorded stopped soaks; full endurance and RTC qualification remain deferred.
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

Published rc1 is generation 49. These manuals also describe the staged
**v1g DBG1 generation-50 candidate**. Its full offline suites and BRK edge
regressions pass, and both-board/both-slot hardware requalification with rollback/reinstall passed. The owner-stopped expanded R6 workload passed with both original full RAMs, flash/settings and final drift verified; see [soak closeout](DBG1_SOAK_CLOSEOUT.md). Promotion remains held. Earlier generations/builds have separate
hardware receipts, which do not qualify v1g. See the
[offline results](DEBUGGER_BOARD_RESULTS.md) and
[candidate labels and scope](V1G_STAGING_STATUS.md).

The inherited base-rc1 UTC correction remains in this image; see the
[historical UTC hardware update](../STR8N_RC1_UTC_BOARD_UPDATE_2026-10-18.md).
Native applications/debugging, full endurance/RTC qualification, ACIA and
crypto remain outside this staging checkpoint. Packaging changes no board or
campaign state and does not authorize a hardware operation.

## Package revision 2: power-fail timezone label

The startup heading is `[power-fail UTC]`. Power-down/up timestamps are raw
UTC with minute precision; the separate RTCC line uses the configured display
offset. For example, October 18 04:35 UTC is October 17 23:35 at -05:00.
Only banner text, its data references and the sector checksum changed. Clock/trim values, event
handling, apps and migration/recovery algorithms are unchanged. The corrected
revision was verified offline and subsequently installed/device-verified on
both boards. DBG1 retains that correction.
