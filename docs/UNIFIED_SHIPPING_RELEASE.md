# Unified STR8N shipping contract

Owner direction, October 30, 2026. **One release and one feature contract.**
STR8N has produced the stable **STR8N-F Foundation v0.3.0 g00000001 /
BASE1 / PR05**. The [familiar workflow requirement](CLASSIC_APPS_PROGRAM_WORKFLOW.md) restores
the 2205/2604 operator experience; it does not require unchanged old binaries.
Above it, MON A and MON B use the same source, commands,
services and application contract. Only their slot identities differ.
The shipping target is **all b35 capabilities except ASM and DBG**.
The [BATCH/large PROGRAM checkpoint](2512_BATCH_WIDE_ACCEPTANCE.md) extends
the [native utilities checkpoint](2512_NATIVE_UTILITIES_ACCEPTANCE.md); full-b35 shipping gaps remain explicit.

This contract supersedes older preview-completion and soak-next wording in
[the release path](FOUNDATION_RELEASE_PATH.md),
[the parity checklist](MON_B35_PARITY.md) and
[the original A/B plan](MON_AB_PLAN.md). Historical receipts and published
archives remain evidence for their exact bytes and scopes.

The [BANK MAINT2.4 reference](BANK_MAINT_RESTORATION.md) is authoritative for
the full maintenance menu, compact Table rows and dynamic startup/status.
The current CONFIG-led panel is an incomplete replacement.

## Common operator experience

| Area | Shipping behavior | Current state |
| --- | --- | --- |
| Identity | VERSION, name/version/generation, active A/B, Foundation identity, CPU/board/status and saved boot policy; V remains an alias | Global VERSION/V and concise TIME accepted on MON/workbench/CLOCK; FLASH/MAINT VERSION identifies SXB/EDU profiles |
| Monitor | b35 Dump/Modify, deliberate force, bank selection, Go, supported loading, cancellation and return | Current D/M/!M/G/B/raw BIN subset qualified; remaining b35 forms need reconciliation |
| Storage | STORE, TABLE, RESTORE; S/T/R aliases; flash and mounted PROGRAM; AUTO start selection, clear backend/location, checked load/run/return | Existing flash/SS1 workflows qualified; full names and flash-to-PROGRAM copy/verified move/run accepted; independent PROGRAM load/run spans 0200-66FF; large STORE-source staging remains |
| Batch | b35 bounded queue, validation, stop/cancel and returning command/app behavior | 34-byte queue now covers guarded MON commands, storage, native menus and registered PROGRAM/AP02 return; explicit raw/protocol exclusions are documented |
| Applications | APPS and APP name; usable native tools and AP/02 images, checked CPU/ABI/CRC, launch and public return | AP/02 previously accepted; native R CLOCK/FLASH/MAINT accepted on 2512 |
| MAINT | Board status and working maintenance actions; direct access to CONFIG, CLOCK, storage and existing flash operations | Working workbench plus resident FLASH/BOOT tools installed on 2512 |
| CONFIG | Show/change bank enables, entries, default/delay and A/B preference; preserve boot/wear journal semantics; return coherently to MON | Resident BOOT/CONFIG implemented; default B save accepted; new OFF/DELAY/RUN positive cases remain |
| CLOCK | Existing b35 read/status/SET and administration: UTC/local display, offset, trim, EUI, power-fail history and battery-policy services | Full b35-derived app installed; STATUS/VERSION/invalid and canceled SET passed; positive SET/ACK/trim remain |
| Flash | Existing b35 programming/editing, journaled erase/update and opaque-image workflows, with the frozen-F/C/D protection policy | Native byte/sector programming, editor, erase, protected-target and HOST paths accepted |
| EDU/storage/work | Existing b35 EDU selection, SRAM PROGRAM management and WORK queries/services, with explicit ownership and bounded unavailable/busy errors | Current SS1 paths qualified; reconcile the remaining b35 backend/management workflows |
| Host kit | Python serial terminal, supported loaders/migrator, installation and opaque/default-boot manual | Published Foundation retained; native candidate/manual prepared locally with remaining gates disclosed |

Source storage/data formats and existing saved contents must remain usable;
excluding ASM/DBG does not discard programs or remove unrelated storage
commands. Source editing that is implemented inside the deferred assembler
must be identified as such rather than silently claimed by the monitor.

The October 30 release scope was expanded: FLASH must provide sector erase,
byte programming, whole-sector writing and a 4 KB buffer/editor. The earlier
choice to defer the editor is superseded. CLOCK and FLASH are named native
apps, available by name and through `R CLOCK` / `R FLASH`; these reserved
system names must not depend on the selected owner data bank. MAINT includes
CONFIG/BOOT, bank enable/entry/default settings and opaque-image operations.
VERSION identifies the SXB CPU/profile and the configured EDU revision, with
unverified hardware identity clearly distinguished from detected capability.
Persistent new
WORKSPACE messages were not a b35 capability; they remain a separate planned
feature with their own append-only allocation, outside PROGRAM and C/D.

The owner accepts B2:8-F and B3:8-E for this full environment. F remains golden
and C/D remain the boot/wear journal. This is a 64 KiB allocation ceiling
including F and journals, not a measured fit or permission to replace occupied
sectors without a preservation review. B0/B1 remain owner space.

“Put WDCMONv2 back at B3” means a deliberate restore-to-factory-firmware
workflow. It does not mean replacing Foundation during normal app use. Use an
exact, CPU/board-matched verified host backup and archive the current system
and journal first. Restoring the WDC reset sector replaces Foundation and is
outside the ordinary FLASH app's F/C/D guards. A firmware restoration does not
claim to reset jumpers, RTC, EEPROM, SRAM or hardware to factory settings.

## Why components live above F

- F stays small and frozen because it is the recovery foundation.
- A/B are alternative occupants of the same monitor contract, not separate
  products or personalities. Their version/generation is separate from F.
- Shared services and explicit RAM-loaded tools supply the larger b35
  workflows without copying them into both 4 KB monitor slots. Measured
  flash/RAM bounds and return paths decide the layout; spare bytes are not
  assumed from a map or a source estimate.
- Existing data formats, confirmations and failure handling carry forward.
  Changed private bindings are adapted to BASE1; old private addresses are
  not invoked just because old bytes remain installed.
- Loading a tool must not silently destroy the source of a STORE operation.
  RAM borrowing, unavailable providers and storage ownership remain explicit.

CLOCK SET must retain b35's power-fail preservation behavior. The MCP79411
clears its PWRFAIL state when RTCWKDAY is written; its time stamps must be
handled deliberately before that write. The existing b35 CLOCK saves a
latched event before RTC_SET. Reusing that behavior is preferable to a small
setter that loses the evidence. See the
[Microchip DS20002266K data sheet](https://ww1.microchip.com/downloads/aemDocuments/documents/MPD/ProductDocuments/DataSheets/MCP79410-MCP79411-MCP79412-Battery-Backed-I2C-RTCC-DS20002266.pdf).

Every deliberate deviation from a b35 workflow needs a row recording the
original behavior, replacement behavior, reason, data/ABI consequences and
acceptance evidence. A missing implementation is an open item, not a
justified deviation. Missing EDU can report unavailable; it does not require
a different command set or a separate release.

## One acceptance standard; targeted hardware checks

The supported current monitor modes are W65C02SXB and W65C816SXB emulation,
using their declared serial/EDU profiles. There is one common workflow suite
and one release checklist. Full independent feature requalification per board
is not the default.

Exercise a common implementation once with its success, cancellation,
failure and preservation cases. On another CPU/transport/EDU path, check the
specific startup, calling convention and physical I/O differences that can
change behavior. Repeat a workflow when it contains such a branch or a real
failure justifies repetition. CPU-specific image tags, where required by an
existing format, are package metadata under the same release contract.

A generic soak and repeated help output are not substitutes for VERSION,
Store/Table/Restore, app launch, CONFIG save/boot or CLOCK SET. Feature
completion comes first. The final acceptance is an end-to-end operator
workflow from a clean extracted candidate, plus the targeted hardware checks.

2609 already has the same current MON/tools as 2512. Its default is S/recovery;
2512's is B/g8. Entering B then MAINT LOAD on 2609 reaches the installed tool
set. Owner images, stored programs and profiles remain board data; they are
not overwritten to make screens look alike. Saving a common startup choice
is an explicit installation/configuration action, not a new software fork.

## Implementation order and release boundary

1. Complete VERSION and full storage names; keep short aliases and BATCH
   parsing consistent. No extra build until the concrete increment is ready.
2. Complete a shared MAINT/CONFIG/CLOCK layout, reusing the b35 behavior and
   existing BASE1 journal/worker logic. Report the resulting memory budget.
3. Close every remaining b35 row, with reasons for intentional changes.
   Qualify real operator workflows; use RAM trials before admitted flash work.
4. Build a local unified candidate with the unchanged F, A/B, common modules,
   terminal, migration/install tools and one manual. Test only that extracted
   candidate before calling it shipping-ready.

ASM/DBG are the explicit b35 exclusions. The generic soak is not the next
release gate. No new F ABI is assumed. Board writes/RTC setting trials need
their concrete preservation scope; a SET test may require a new measurement
segment while retaining prior RTC/NTP history. 2205 and 2604 remain untouched.
All source commits stay local; existing published downloads and tags remain
unchanged. This document does not authorize a new board write or publication.

## First implementation checkpoint

[MON g9](../monitors/candidates/g00000009-words/README.md) and
[WB2 g6](../monitors/candidates/wb2-g00000006-words/README.md) were each built
once. The workbench reused its unchanged loader. F was not rebuilt; no CPU
model or board access occurred. Current slot free space is 22 bytes each;
the workbench has 29 bytes, with its state/CRC bounds intact. These candidates
are not installed or execution-qualified. They do not complete CLOCK/CONFIG
or the unified shipping gate.
