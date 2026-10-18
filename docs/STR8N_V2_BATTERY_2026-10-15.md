> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta25 coin-cell maintenance candidate — October 15, 2026

Build with `tools/build_v2_battery.py`. The separate, unflashed output is
`BUILD/v2-battery`, based on `BUILD/v2-map-assets`. Firmware remains 2.0b25,
generation 37; CLOCK becomes 1.8. Neither builder nor tests access a board.

This is an age-based maintenance policy. It cannot measure battery voltage,
remaining charge, or certify retention. The proposed initial warning is 12
months and replacement reminder is 24 months. A configured month is exactly
30 elapsed UTC days: defaults therefore trigger at 360 and 720 days. These
are provisional maintenance defaults, not guaranteed lifetimes. The SRAM
datasheet supplies no maximum VBAT current. Measure the whole board's cell
current and leakage before making battery-lifetime claims.

## Operation

Boot, R EDU and the CLOCK opening summary display battery status. In CLOCK:

| Command | Behavior |
| --- | --- |
| `BATTERY` | Evaluate status and show the saved warning/replacement thresholds. |
| `BATTERY REPLACED` | Record today's UTC date as installation date. Requires exact YES. |
| `BATTERY yyyy-mm-dd` | Explicitly record a known installation date, 2000–2099, no later than current UTC. Requires exact YES. |
| `BATTERY LIMITS ww rr` | Save two-digit thresholds, 01–99 months, warning less than replacement. Requires an existing installation record and exact YES. |

An initial installation record uses 12/24. Later replacement/date records
preserve the user's selected thresholds. Record a date only when it is known;
first use, reboot, firmware update, a backup and RTC SET do not automatically
establish a battery installation date. Back up SRAM from the beginning rather
than waiting for a reminder. Battery replacement itself is a physical action;
the command only records it.

Unknown age reports `Battery age unknown. Back up SSRAM; use CLOCK BATTERY.`
Before the first threshold, status says `within age policy; condition unknown`.
At the thresholds it asks for a backup and planned replacement, then a backup
before replacement. A missing installation record never produces a healthy
battery indication.

Warnings are persistent floors. Lengthening thresholds cannot clear an already
observed warning. Only explicitly recording replacement/a known installation
date resets it. A stopped/invalid/unavailable clock, disabled RTC backup or a
date earlier than the saved high-water date latches `Battery age uncertain`.
Restoring the clock alone does not clear that latch. Reconfirm the known
installation date to establish a fresh age baseline while preserving policy.
This confirmation must not be used to conceal a battery whose age is unknown.

The high-water date is checkpointed when a warning/uncertainty level advances,
not every boot. Small backward adjustments between checkpoints cannot all be
detected. A plausible clock after an unnoticed retention failure is also not
proof of continuity. Existing `continuity/battery condition unknown` semantics
remain valid. No runtime warning can appear while the computer is off.

## Persistence and placement

BA v1 records share the existing append-only B3:9C00–9FFF tail with EUI, offset
and board-name records. There are 32 shared 32-byte slots total. Ordinary
evaluation does not write. Explicit date/policy changes and newly observed
warning levels append a record. There is no periodic day/month counter and no
automatic erase/reclaim. Repeating a date/policy administration command can
consume another slot; use BATTERY alone for queries.

Each record has `BA,1,0`, sequence LE32, a seven-byte payload, reserved FF,
CRC16 LE at 28–29 and commit zero at byte 31. Payload at 8–14 contains install
ordinal day LE16 since 2000-01-01, warning months, replacement months, highest
stage (0 normal, 1 warning, 2 due, 3 uncertain), and high-water ordinal LE16.
Only valid committed records participate in newest-sequence selection.
Uncommitted/foreign slots remain occupied. The writer checks PJ6 format and
refuses full space or sequence exhaustion. It programs, reads back and verifies
the payload before committing and rereads the committed record afterward.

If persistence fails during evaluation, the newly observed warning still
prints with a save-failure message. It cannot be promised persistent across
reset until the record is saved successfully. Prior committed records survive
interrupted appends. RTC registers, RTC EEPROM, SPI SRAM and other record
types are not changed by battery record writes.

The sealed boot helper occupies B2:D200–DBFF, previously erased space inside
the already reserved status sector. It loads into borrowed $6E00–$77FF staging,
ending before the flash worker at $7800. The status formatter tail-returns into
the shared loader before its staging is replaced. The shared loader checks CRC
and header before execution. The helper now also provides the
[flash-wear reminders](STR8N_V2_FLASH_WEAR_2026-10-15.md). EDU OFF evaluates wear
but skips battery/RTC calls and preserves reclaimed RAM. Missing RTC components
do not permit a call through an uninstalled gateway. TIME and VERSION retain
their existing paths.

The update changes CLOCK in its existing B1:B/C/D allocation, status assets in
B2:C/D, and the shared B3:E loader. F, both monitor slots, MAINT, the local-time
and VERSION assets, identity/offset/name records and application RAM allocations
remain unchanged. CLOCK help is shortened to retain the three-sector limit.
SSRAM's `Allocation uninitialized` label becomes `Uninitialized` to fit the
new status tail route. MAINT 2.1's map still names the original formatter range;
the entire D sector remains reserved, including the new helper documented here.

## Verification and installation boundary

Run `tools/test_v2_battery.py` against the rebuilt candidate. It executes actual
assembled 65C02 code for command validation/confirmation, 403 calendar cases,
warning boundaries, persistent uncertainty, full journal/timeout refusal,
corrupt helper refusal, EDU OFF, missing RTC component and every programmed
byte interruption of a replacement append. The receipt is
`BUILD/v2-battery/battery-test-results.json`. Existing CLOCK summary and compact
boot suites can run with `STR8_RTC_BUILD=BUILD/v2-battery`.

`tools/test_v2_battery_update.py` then prepares synthetic, twice-verified bank
backups and executes the complete generated seven-sector installer in the
existing instruction model. It checks exact final banks, record commit order,
stale-backup refusal and corrupted-payload refusal. Its separate
`battery-update-test-results.json` receipt is model-only.

The rebuilt candidate passed the battery, existing CLOCK summary, existing
compact boot and complete offline installer suites on October 15. All 403
calendar cases and all 18 interrupted replacement-append checkpoints passed.
The linked sizes are CLOCK 12,247 bytes (plus 24-byte SR header, within 12,288),
combined boot helper 2,121/2,558, status 2,548/2,558 and shared loader 237/254 bytes.
F and both monitor-slot template binaries match the map-assets baseline.

Beta26 qualification subsequently found and corrected a VERSION loader
selection error before flashing. The VERSION regression suite is now also
required by the update planner; see the [beta26 report](STR8N_V2_BETA26_2026-10-15.md).

`tools/prepare_v2_battery.py --backup <prior-verified> --out <upgrade>` prepares
an offline update only from an exact supported shared baseline and two matching
full-bank backups with a verified manifest. It checks the feature test receipt
and artifact hashes, rejects an occupied helper allocation and preserves both
monitor slots/F and board-specific records. It updates wear accounting before
the other sectors, installs the helper before its loader/caller and commits
the new CLOCK record after verifying its continuation sectors.

The planner does not open a port or flash hardware. Its generated installer
must pass exact-backup instruction-model rehearsal before a separately
authorized hardware installation. Arbitrary older beta25 shared layouts require
their own qualified migration; do not use raw sector writes to bypass the
preimage checks. Hardware retention/current measurements and physical execution
of this candidate remain separate qualification steps.
