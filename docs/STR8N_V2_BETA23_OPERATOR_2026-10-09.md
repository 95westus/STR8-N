# Frozen beta23 operator checkpoint

This is an owner-local qualification guide for beta23 generation 32 / CLOCK
1.6. The published release remains beta4. Beta23 is not yet RC accepted:
the 48–72-hour soak on 2604/2609 and final distributable package are outstanding.
See [qualification evidence](STR8N_V2_BETA23_FOUR_BOARD_STORAGE_2026-10-09.md)
and [RC gates](STR8N_V2_RELEASE_CANDIDATE_PLAN_2026-10-09.md).
Program authors should use the [technical guide](STR8N_V2_BETA23_TECHNICAL_GUIDE.md)
for entry points, request blocks, ownership and failure semantics.

## Boards and console

Use the USB console at 115200 baud. Current owner-local identities are:

| Board | Port | CPU profile | EDU | Normal trim | Display offset |
|---|---|---|---|---|---|
| 2512 | COM4 | 65C02 | ON | 0 | +00:00 |
| 2205 | COM3 | 65C02 | ON | 0 | -05:00 |
| 2604 | COM5 | 65C02 | ON | 0 | +00:00 |
| 2609 | COM8 | 816 emulation | ON | 0 | -05:00 |

Port numbers are local mappings; identify the board before any write.
STR8N-001 ACIA receive on 2512/2205 remains deferred. Qualified USB behavior
does not qualify that ACIA receive path. Native-vector BRK/NMI qualification
does not provide native RTC/I2C services.

## Startup and EDU mode

At cold startup choose A or B, or Enter for the saved default. Both monitor
slots are generation 32. `J3` performs the cold monitor restart used for mode
activation and stale WORK handle tests. Ordinary `Q`, monitor return and HOLD
retain the active EDU mode. After a firmware upload the installer is halted:
press physical main-board RESET. On 2609 use S2/RESB; S1/NMIB is NMI.

Selecting `S` during the cold startup window enters `FIXED F RECOVERY` at
`REC>`. `W` reports wear without a write; `A` or `B` checks and launches that
valid slot. This supplies a recovery entry independent of the selected monitor.

To test an attached EDU board as standalone, use `R EDU`, `OFF`, confirm `Y`,
then `Q` and `J3`. While a setting is pending, EDU status shows the active mode
and `RESET required: OFF` or `ON`. The successful save remains
`Saved; RESET required.`. Enter or a response other than the single `Y` cancels.
Select `ON`, confirm `Y`, then `Q` and `J3` to restore EDU operation.

Active OFF releases `$6500-$66FF` for application RAM and disables optional
service calls. Active ON reserves those bytes and ends application RAM at
`$64FF`. OFF changes the firmware profile; the mounted hardware remains
electrically present. Re-enable and activate ON before drift collection.

## Time, identity and retained data

`TIME` provides detailed UTC/local/trim output. `R CLOCK` offers STATUS,
HISTORY, EUI, TRIM and OFFSET queries. OFFSET is a fixed display offset; it
does not apply daylight-saving rules automatically. Successful OFFSET, UTC
SET and TRIM apply immediately and do not request reset. Their confirmation
requires the full `YES`, unlike EDU's single `Y`.

The current campaign keeps all four clocks at normal TRIM 0 on immutable
fresh-NIST baselines. Do not confirm SET or TRIM during that campaign.
2512 and 2604 remain EUI-unbound; do not ACCEPT an identity as part of a
read-only drift or preservation check.

Power removal with backup batteries installed retained all flash, full SRAM
and advancing UTC on this image. A full four-entry outage ring replaces only
its oldest entry; archive history before tests. Startup logs and acknowledges
a supported outage automatically. 2604 currently has a foreign EEPROM history
layout: logging reports failure, preserves that layout and retains the latch.
HISTORY therefore reports error 90. Its UTC/SRAM retention passed. Do not
CLEAR or ACK that evidence to hide the condition.

Use backed-up, unused destinations for flash/SRAM test records. Native AUTO
save can leave the monitor in the destination bank (for example `B2>`);
select `B3` explicitly afterward. WORK claims survive ordinary return but
become stale after cold restart. Corrupt and unpublished saved records must
refuse restoration/execution; layout recovery requires explicit verified
secondary REPAIR. Never assume an invalid retained layout may be formatted.

## Upgrade and package boundary

The rehearsed owner-local upgrade is exact beta22 generation 31 to the frozen
beta23 generation 32 image on 2512/2205/2609. It requires fresh matching full
flash readbacks, a per-board preimage-bound plan and a successful rehearsal
before upload. A prior plan becomes invalid when any source bytes change.
2604 was user-installed and independently compared/qualified as beta23;
this does not extend the rehearsed source-version upgrade matrix.

The draft artifact ZIP is a validation bundle, not an operator installer.
Final packaging must provide the supported source paths and their documented
prerequisites, verify every member/hash and exclude board backups, raw
qualification evidence, owner-bound installers and stock WDC firmware.
