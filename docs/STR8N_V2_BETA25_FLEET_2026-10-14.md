# Unified beta25 fleet upgrade — October 14, 2026

The user authorized taking all connected boards to beta25 using the unified
upgrade. Inventory resolved each board by FTDI identity and captured all four
flash banks twice. All repeat comparisons passed.

| Board | Initial active monitor | Planned action | Retained MON A |
|---|---|---|---|
| 2205 | beta25 B, generation 37 | Verified current image; no writes | beta23, generation 32 |
| 2512 | beta23 A, generation 32 | Upgraded shared changes and beta25 MON B | beta23, generation 32 |
| 2604 | beta24 A, generation 34 | Upgraded shared changes and beta25 MON B | beta24, generation 34 |
| 2609 | beta25 B, generation 37 | Verified current image; no writes | beta24, generation 35 |

2205 and 2609 match their previously qualified complete flash images. Their
shared assets, MAINT, active monitor, valid fallback and saved beta25 preference
were checked. Fresh TIME/CLOCK queries passed. Their flash was not rewritten.

2512 and 2604 each have verified duplicate 128 KiB SRAM backups and read-only
RTC/EEPROM references. Both remain EDU ON. Their saved offsets are +00:00,
trim is -12 on both, and RTC control is 80 on 2512 and 00 on 2604. Their unbound
EUI states are retained. Existing 2205/2609 offsets remain -05:00.

## Unified planning and qualification

The planner chose the inactive slot from the captured active slot and selected
the beta25 profile by source ABI. 2512 uses the already qualified beta23 profile,
which retains the private slot validator at F30D. 2604 uses a beta24 generation-34
profile retaining F318. The generation-35 family retains F31B. All are beta25
generation 37. MON A remains byte-identical in each upgrade plan.

For F318, an equivalent selector saves three bytes before the validator; three
padding bytes after it retain SR_ROUTE and all later journal entries. The builder
checks every old-monitor F reference, journal entry, worker/vector identity and
both new monitors' actual linked validator address. Two independent builds of
the generation-34 profile produced identical firmware, bootstrap utility and RAM
installer bytes.

All six package model suites passed for the new profile, including 11 monitor
interruption points, all 123 journal program interruption points, refusal/fault
checks, APPS, local-only TIME/detailed CLOCK, FIFO drain and MAINT transfers.
Each board's exact mixed image additionally passed both monitor command suites,
read-only preservation, old/new P promotion of either slot, lowercase and timed
default boot, invalid commit/cookie/CRC fallback and damaged-fallback selection.
These tests derive offsets and binding state from source data; they do not
impose the previously tested boards' -05:00/bound-EUI settings.

Each exact installer passed RAM execution, full expected-bank comparison,
sector order, preservation of MON A, final verified MON B commit, stale-preimage
refusal and corrupt-transfer refusal. Qualification is bound to each board's
plan, package hashes and installer hash. The unified audit accepts per-board
mixed-image receipts without replacing another board's qualification.

## Hardware status

2512's ten-sector installer and 2604's seven-sector installer both passed fresh
complete preimage checks and reported `MIGRATION VERIFIED; PRESS PHYSICAL RESET`.
Physical RESET boot capture passed on both boards with complete banners showing
the retained A monitor valid and beta25 B valid/default. Hardware A/a/B/b,
ESC/other-key menu, recovery A, timed default and queued A/B/ESC drain passed.
Both monitor command suites passed local-only TIME, detailed CLOCK, APPS, RAM
edit, EDU/SRAM/WORK/MAINT, name query and HOLD. Actual RAM ABI and BRK/VIA1 IRQ
probes passed, including register/stack/RTI and pointer preservation.

All four final flash banks match each exact plan. MON A is byte-identical.
Each complete 128 KiB SRAM array matches its original backup. EEPROM/history,
EUI/binding, RTC control/trim, stored offsets, names and EDU mode are unchanged.
No clock set, trim change, SRAM format or external SRAM/EEPROM write was issued.
All 32 fixed-F wear counts match each plan, and TIME works afterward with B
still selected. No power cycle or physical NMI was requested or tested in this
fleet run.

2604's pre-existing foreign EEPROM history (`History unavailable/error 90`) and
latched older outage remain unchanged. Boot refuses to log over that foreign
layout (`PF logging failed`); no ACK, CLEAR or ACCEPT was issued. Its whole
EEPROM snapshot and prior history response compare exactly after the upgrade.
The SRAM allocation on 2512/2604 remains uninitialized as before; raw contents
were preserved rather than formatted.

All four boards are now running beta25 generation 37 in MON B, with their MON A
fallbacks retained. The aggregate bound result is `report.json` under the
evidence root. Detailed upgrade hardware results are `<board>/retest/report.json`;
already-current results are `<board>/report.json`. Separate package receipts
are `BUILD/v2-beta25-b23/hardware-qualification-2512.json` and
`BUILD/v2-beta25-b24g34/hardware-qualification-2604.json`. Firmware build metadata
remains frozen; hardware evidence is attached separately.

STR8N-004 now meets affected-board hardware close criteria on 2604 and 2609.
STR8N-005's destructive physical F-only acceptance remains pending; normal
upgrades and model interruption tests do not replace that test.

Evidence root: `output/qualification/beta25-fleet-2026-10-14`.
The unified entry points are `tools/upgrade_v2_fleet.py`, `tools/migrate_v2.py`,
`tools/test_v2_migration_mixed.py` and `tools/retest_v2_migration.py`.
The intended family-wide forward-upgrade contract and legacy conversion limits
remain documented in [STR8N_UNIFIED_MIGRATION.md](STR8N_UNIFIED_MIGRATION.md).

## Subsequent October 14 qualification

The earlier foreign-layout and STR8N-005 pending observations above describe
the fleet-upgrade run. They are superseded by subsequent work on 2604:
[clock repair and physical F-only acceptance](STR8N_V2_RECOVERY_ACCEPTANCE_2026-10-14.md)
passed, closing STR8N-005. The [unified b4-to-beta25 test](STR8N_V2_B4_TO_BETA25_2026-10-14.md)
also passed, followed by restoration of the original beta24 A / beta25 B.
Full SRAM and repaired EEPROM history/settings remain preserved. Its additional
23 recovery-test and 19 b4-test/restoration erases are accounted in appended
wear records; the current 2604 full-flash reference is
`output/qualification/beta25-b4-unified-2026-10-14/final/report.json`.
Historical receipts above remain unchanged. Other boards were not accessed.
