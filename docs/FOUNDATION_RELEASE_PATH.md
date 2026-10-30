# Foundation: release goal and next qualification

**4K Foundation. Up to four banked environments.**

A 4 KB foundation for your own environments. One physical board selects a
compatible image in one of four flash banks. Environments run one at a time,
sharing its CPU, RAM and peripherals. The supported hardware is WDC's
W65C02SXB and W65C816SXB in the qualified CPU modes; matching EDU add-ons are
optional for Foundation and required by the optional EDU storage/RTC services.

Foundation names the stable F-sector role. Its released identity remains
**STR8N-F v0.3.0 g00000001 / BASE1 / PR05**. F is exactly 4096 bytes. C/D
hold the separate persistent boot/wear journal; the remaining 116 KiB holds
owner images. Optional monitors/tools consume part of that image capacity.

## What is already released

| Deliverable | Current evidence |
| --- | --- |
| Frozen 4 KB F.bin | Public v0.3.0; reset, recovery, chooser and journaled boot cases passed within their named scopes |
| WDC-loadable RAM migration tools | Included; reviewed source-driven 2512 migration passed; WDC migration from an extracted published kit remains untested |
| Programmer-installed-F provisioning | Included; reviewed 2512 C/D provisioning passed with F golden; the extracted published-kit route remains untested |
| Python serial terminal | Included; native keys/dialogs on 2512 and core cancel/load checks on 2609 passed |
| Installation/opaque/default-boot manual | Included; the preserving 2512 CONFIG/opaque/default-boot trial passed |
| Optional MON/tools | Public preview 1; MON A/B g8, services g4 and WB2 g5 installed and qualified on 2609; later A acceptance is linked below |

See the [stable release](https://github.com/95westus/STR8N-F/releases/tag/v0.3.0),
[Foundation manual](USER_MANUAL.md), [Foundation evidence](RELEASE_STATUS.md),
[MON preview](https://github.com/95westus/STR8N-F/releases/tag/mon-g8-tools-preview1)
and its [acceptance](2609_MON_FEATURE_ACCEPTANCE.md). Existing archives and
their tags remain immutable. Adding the Foundation wording does not rebuild F.

## Closed qualification: positive PROGRAM on 2609

2609's installed preview now passed [positive PROGRAM acceptance](2609_PROGRAM_POSITIVE_ACCEPTANCE.md),
including Store/AUTO, latest-version Restore/run, directory-full and CRC
refusals, public return, complete SRAM equality and owner RAM/ZP restoration.
It used the installed, byte-identical preview payloads and the separately
[approved PROGRAM trial scope](2609_PROGRAM_POSITIVE_SCOPE.md). The following
describes that completed gate; it grants no further write permission.

First capture the complete 128 KiB SRAM twice through guarded reads, compare
all flash banks, and restore/read back owner RAM/ZP. Admit temporary targets
from that actual mounted layout, then review their exact write scope before
running Store. Restoring a stale capture without fresh target admission is
not allowed. Existing record names or erased bytes alone do not grant space.

The proposed trial covers AUTO/NO, commit-last Store, short names, same-name
versions, explicit placement, full-directory refusal, checked load-only,
public-HOLD run/return, and payload-CRC refusal before copying RAM. Every
temporary directory/payload byte must be restored, and the complete SRAM
compared afterward. No WORKSPACE allocation, flash/journal write, boot change,
format, mode-register write, clock setting or power cut is part of this gate.
Retained CLOCK records stay intact. Use the shared serial lease so RTC/NTP
collection can defer safely; finish at REC> and release COM8.

The restorer is a private, narrowly allowed qualification fixture. Its one
necessary build changes only its exact target allowlist; Foundation, MON,
services, WB2 and PROGRAM are reused. No CPU simulation or second firmware
build is required. This document grants no storage-write permission.

## Following checkpoints

The owner has deferred [resident ASM and DBG](MON_ASM_DBG_RELEASE_GATE.md)
as follow-on work; they no longer block the current monitor/tools release.
The remaining CPU/backend qualification must match the advertised release
scope. Existing Foundation and preview 1 downloads remain their original
scoped releases.

1. **Closed:** services-g4 RAM and matching board-flash reload
   [passed on 2512/65C02](2512_SERVICES_G4_INSTALL_ACCEPTANCE.md), including
   physical saved-default B boot and complete owner RAM/ZP preservation.
   The approved five erases are complete; they grant no further write allowance.
2. **Closed:** current PROGRAM positive SS1 Store/Restore/run and CRC refusal
   passed on [2609](2609_PROGRAM_POSITIVE_ACCEPTANCE.md) and
   [2512](2512_PROGRAM_POSITIVE_ACCEPTANCE.md). The 2512 host directory-slot
   planning error and restoring continuation are explicit; every original
   SRAM/RAM byte is restored. Its original narrow scope is not marked passed.
3. **Closed:** [AP/02 named flash-app launch on 2609](2609_AP02_ACCEPTANCE.md),
   help/public return, exact retained-WDC restoration and RTC readmission.
   Exactly two B0:9 erases and two wear appends; all 17 old rows retained,
   zero F writes or C/D erases. This adds no further write permission.
4. Proposed next checkpoint: a bounded soak on the unchanged installed
   images with the existing RTC/NTP schedule. Check the actual response,
   image/RAM preservation and clock-continuity evidence; do not infer
   unobserved behavior from an occasional sample. No new soak was started
   by this qualification closeout.
5. If qualifying the packaged WDC or programmer-F routes, use only a fresh
   extraction and review C/D/F replacement separately. That requires an
   admitted target; the no-flash PROGRAM trial cannot authorize it.
6. Continue SOURCE/ASM/DEBUG and remaining command parity as separate module
   increments. Keep 2604's rc1 reference intact until replacement workflows
   pass. Keep 2205 out of firmware changes and retain historical branches.

A later monitor/tools candidate can add its new receipts and manual while
carrying forward the same Foundation bytes. Promotion must state the tested
CPU/backend combinations and remaining gaps; full b35 parity is a separate
goal from the already released 4 KB Foundation.

Current MON/tools evidence:

| Scope | 2512 / 65C02 | 2609 / 65C816 emulation |
| --- | --- | --- |
| Installed MON B g8, current g4 maps/wear and TIME | Passed | Passed |
| Matching flash MAINT LOAD, CLOCK, PROGRAM Table, BATCH and AUTO/NO | Passed | Passed |
| Positive current SP1 SS1 Store/Restore/run and CRC refusal | Passed explicit Store; host scope error exactly repaired | Passed AUTO/explicit Store |
| Positive AP/02 flash-app launch through current g4 | Passed current g4; original FF sector/B0 restored | Passed; original WDC restored |
| Resident ASM/DBG | Deferred; nonblocking | Deferred; nonblocking |

The [2512 current-g4 AP/02 acceptance](2512_AP02_G4_ACCEPTANCE.md) also passed,
using one B0:9 restoration erase and CC00/seq1042. Its 28 old records,
original images, B default and owner RAM/ZP are preserved; native TIME/NTP
continuity passed. No new soak or published download was created.

2609's separate [permanent MON A g8 acceptance](2609_MON_A_G8_ACCEPTANCE.md)
closes its matching A/B profile, physical A startup and RTC readmission.
One A erase and one D300/seq1034 append retained all 19 prior records; default
S, other images, frozen F and owner RAM/ZP are preserved. The current journal
has 20 records. This adds no further write permission or published-kit change.

The 2512 positive trial used AUTO preview/NO and explicit payload placement;
its earlier AUTO and application receipts remain separate historical scopes.
The scope-planning failure, actual slot order and full preserving recovery
are retained in its composite receipt. No published archive, release tag or
frozen F byte changes with these later source receipts.
