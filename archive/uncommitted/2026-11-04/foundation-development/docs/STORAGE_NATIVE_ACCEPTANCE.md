# Native SRAM and WORK: installed checkpoint

## Latest2512 follow-up: installed BATCH and large transfers

November1,2026.2512 now has **SRAM/WORK g4, WB2 gE and the checked NB1/2
native loader**, with MON A/B gF and frozen Foundation unchanged. Actual ROM
decompression and both manager BATCH/Q/remaining-command paths passed:

```text
B3> BATCH R SRAM;T;Q;D 1000
B3> BATCH R WORK;?;Q;D 1000
```

The current workbench also passed source-preserving8KiB PROGRAM Store, record/
payload CRC, registered BT1/2 load/run/public-HOLD return over4700-66FF and the
following BATCH command. All8256 temporary SPI bytes and the retained directory
were restored exactly. The earlier small-manager G positive case was in RAM;
its same g4 body is reused. Manager data/G remain limited to0200-1FFF while
resident; independent `RESTORE P` supplies the larger range. Raw G/L remain
outside returning BATCH. Confirmations stay live, and BATCH cannot enter `!`
controls to unlock a manager.

The combined scope spent exactly14 erases (ten utility sectors, one native C
rotation, three B0:9/A fixture/restoration erases). F/MON, metadata, boot policy
and RTC settings were unchanged; owner RAM/ZP were restored and read back.
Final2512: REC>, COM4 free, seq1164,23 valid rows, C/D/E/F57/37/37/24. All25 old
journal records were archived; nine old D rows remain exact on chip. The16 old
C rows were replaced under the reviewed rotation, with counts carried forward.
Receipt: `output/qualification/2512-storage-BATCH-AUTO-scope-20261101-r1/completion.json`.

This follow-up qualifies2512 only.2609 remains owner-held and was untouched.
The original two-board g2 account below is historical; its then-open BATCH,
small G, large Store and saved-EDU notes do not override the later2512 receipts.

## Original two-board g2 checkpoint

November 1, 2026. **Passed and left installed on 2512 and 2609.** Both use
the same utility bytes: SRAM/WORK g2, WB2 gD, services gC and a five-entry
native loader. F remains Foundation 0.3.0 g1 / BASE1 / PR05; MON A/B gD,
STATUS, PROGRAM, CLOCK, FLASH and BANK MAINT are unchanged.

## Use

At either board's monitor:

```text
B3> R SRAM
SRAM> T
SRAM> Q
B3> R WORK
WORK> ?
WORK> Q
```

SRAM Table lists the existing named PROGRAM records. WORK reports capacity
and current layout. These queries do not start an epoch or change storage.
Q returns directly to MON and retains the selected data bank. RESTORE SRAM
and RESTORE WORK are the long forms; extra arguments are rejected.

Both tools start read-only. `!` opens `STORAGE>` controls: PREP, UNLOCK,
LOCK and EDU ON/OFF. UNLOCK requires a separate live YES; choose S or W to
return to a menu. Q ends the instance and clears its write capability.
This is a cooperative tool guard, not isolation from owner machine code.
Use the monitor's EDU ON command for its session profile; the controls'
EDU selection is local to this loaded tool. Saved EDU across reset remains
open. PREP acknowledges disabled CB flags; it does not format SRAM.

| SRAM menu | Function |
|---|---|
| T | Named PROGRAM table |
| S name start end entry | Append a version from CPU RAM; 0000 entry denotes data |
| R name / G name | Restore / restore and run |
| D name | Append a deletion tombstone |
| C | Reclaim superseded records after checking the retained payload |
| F | Explicit store format with live confirmation |
| ? / ! / Q | Help / shared controls / MON |

| WORK menu | Function |
|---|---|
| ? | Capacity and layout |
| P 16, P 32, P 48, P 64 | Resize PROGRAM allocation in KiB, subject to records/claims |
| U | Upgrade SS1 to SS2 |
| V | Repair primary layout from a valid fallback |
| F | Explicit layout/PROGRAM-directory/claim format |
| HELP / ! / Q | Help / shared controls / MON |

Mutation needs UNLOCK; format/layout administration also follows the exact
live confirmation prompt. Legacy SRAM FORMAT refuses SS2 with $49: use the
WORK owner for that layout. The private resident WORK API provides bounded
owner/slot/epoch/ticket claim/release/read/write services; Foundation's ABI
was not expanded.

## Memory and current limits

The three-sector payload is at B1:B–D, replacing the archived legacy CLOCK
copy. Current native CLOCK remains at B2:B–D. The library borrows CPU RAM
$2000–$4881, context $5B00–$5DFF and scratch $6400–$6ACF. Normal Q restores
MON state/ZP and invalidates the cache; it does not restore all application
RAM. The live qualification separately restored and read back fresh owner
RAM/ZP using the host preservation tool.

Actual SRAM-manager CPU save/restore and API data buffers are limited to
$0200–$1FFF while this library is resident. Table can inspect larger records.
For existing large PROGRAM loads, use the independent monitor path
`R P name L` (load only), qualified through $66FF. Large Store-source staging
remains open. Q ends the library instance; reload it before another call.
Small SRAM-manager G is implemented but was not a new positive execution
case in this checkpoint; that acceptance remains open. Prior independent
PROGRAM run evidence is retained separately.

Interactive R SRAM/R WORK is refused in BATCH before altering its parent.
Checked BATCH continuation for these managers remains open. Existing
returning monitor/workbench/native CLOCK/MAINT and registered PROGRAM/AP02
BATCH behavior is retained. No persistent WORKSPACE message journal is
claimed by this checkpoint.

## Acceptance and preservation

Both physical CPU paths passed combined and named menu entry, actual
Table/capacity, `!` controls, UNLOCK/YES/LOCK without a storage mutation,
selected-bank Q, bad arguments/long forms, and BATCH refusal. New WB refused
the old loader, and the RAM loader refused an absent/wrong payload before
installation. The installed tests then used board-loaded app bodies and
rechecked existing CLOCK/FLASH/MAINT.

The approved installation used exactly 15 erases: seven image sectors on
each board plus one native D rotation on 2512. Independent complete reads
of affected B1/B2/B3 banks matched the exact forecast. All other bytes in
those banks matched the original images. F and MON slots are unchanged;
B0 was outside every write path. SPI metadata matched before/after; no
SPI-data or RTC-setting writes, resets or power cuts occurred. Fresh owner
RAM $0200–$66FF and ZP $00–$DF were restored and read back. Both boards finish
at B3>, with their serial ports released and saved B/gD policies unchanged.

| Board | Final sequence | Valid rows | C / D / E / F tracked counts |
|---|---:|---:|---|
| 2512 | 1116 | 23 | 55 / 36 / 34 / 24 |
| 2609 | 1072 | 26 | 79 / 49 / 48 / 31 |

All values above are decimal. Both old B1:B–D CLOCK images and all original
journal rows are archived exactly on the host. The approved 2512 D rotation
replaced 16 old rows on chip while retaining 15 old C rows; 2609 retains all
19 old rows on chip. Every count and prior-wear flag was carried forward.
No journal reseed or default-binding change occurred.

The RTC reader, baseline, history and schedule were not changed. Read-only
campaign admission still accepts both boards; no port or NTP request was
opened for that host-only compatibility check. 2205/2604 and published
downloads remain untouched. Classic startup is selected for a later MON
presentation increment; the current gD banner remains unchanged.

**Subsequent correction:** host-only admission did not establish working live
STATUS. The B2:8 replacement erased STATUS text extents8040-80FF/8240-82FF
that its bundle preparer treated as padding. Both boards have now had those
exact384 bytes restored with program-only1→0 writes: zero erases, C/D appends,
F writes, owner-RAM borrowing or RTC-setting changes. Rich VERSION and native
TIME/trim plus the latest journal row passed. See the repair receipts under
`output/qualification/{2512,2609}-STATUS-literals-repair-20261101-r1/`.
Future service bundles require the STATUS manifest and preserve these extents;
the original15-erase receipt alone is not proof of complete live startup status.

Private receipts, excluded from kits:

```text
output/qualification/2512-native-storage-installed-20261101-r1/report.json
output/qualification/2609-native-storage-installed-20261101-r1/report.json
output/qualification/STORAGE-native-installed-closeout-20261101-r1/report.json
output/qualification/STORAGE-native-scope-20261101-r3/{2512,2609}/
```

See the [approved scope](STORAGE_NATIVE_2512_2609_SCOPE.md) and
[remaining release checkpoints](UNIFIED_ENVIRONMENT_REMAINING.md). This is
an installed development checkpoint, not full b35 parity or a new release ZIP.
