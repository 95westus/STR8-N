> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# STR8-N 2.0bf1 candidate manuals

Target: **2.0bf1 generation 48, CLOCK 1.11, ASM 0.5, FT245/F30D**.
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
- [Program and command reference](COMMAND_REFERENCE.md)
- [Technical manual and Mermaid diagrams](TECHNICAL_MANUAL.md)
- [Public ABI reference](ABI_REFERENCE.md)
- [Firmware contents and programmer mapping](FIRMWARE_CONTENTS.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Tested candidate scope

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

These are local candidate tools/manuals. Publication and full release acceptance
remain held. Longer soak/RTC gates are not waived by owner-stopped workloads.
Linux extracted scripts are tested on Linux; a Linux physical serial migration
has not been performed. An earlier WDC trial lost RTC continuity; the corrected
empty-bank trial retained a running valid RTC, but the earlier cause and broad
RTC-preservation qualification remain open. No migration tool issues clock,
trim or offset setters. Keep clocks and power evidence under observation.

Early factory-WDC interruptions without a valid bf1 fallback/journal may need an
external programmer and the original private backup. No WDC or intermediate
beta4 image is distributed. Retain the exact kit and all private recovery files.
