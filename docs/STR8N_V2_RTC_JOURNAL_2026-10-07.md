# Optional RTC power-fail journal — beta8 / CLOCK 1.2

The MCP79411 ordinary EEPROM holds the newest four observed outage events.
On boot, STR8-N saves the latched down/up timestamps, reads back the record,
commits and verifies it, and only then acknowledges the chip's power-fail flag.
This rearms the RTC for the next outage. A failed save leaves the live flag set.
Boot prints whether the outage was saved or the latch was kept.

The owner authorized all 128 ordinary EEPROM bytes for four 32-byte slots.
2205's former bytes 0–23 were backed up before replacement. The separate factory
identity and EEPROM protection register are never written. SRAM remains unused.
The service is optional: 2512 without EDU retains normal monitor operation and
reports unavailable clock/history services.

## CLOCK commands

`R CLOCK` starts CLOCK 1.2. Existing TIME, STATUS, SET, ACK and QUIT remain.

| Command | Behavior |
| --- | --- |
| `HISTORY` | Lists committed events newest first, with stable physical slot numbers 1–4. |
| `SHOW n` | Displays that slot's outage and capture time, where usable. |
| `CLEAR n` | Requires exact `YES`; invalidates only that history slot. |
| `CLEAR ALL` | Requires exact `DELETE ALL`; clears or initializes all four slots. |
| `ACK` | Requires exact `YES`; saves and verifies a live outage before acknowledging it. |

Clearing history changes neither UTC nor the live power-fail flag. Clearing is
logical deletion, not secure erasure. A subsequent outage can reuse an emptied
slot. ACK uses the requested wording:

> ACK clears the power-fail flag and outage timestamps. UTC time keeps running unchanged.

SET preserves a latched outage in EEPROM before changing the clock, because
the existing RTC SET also clears that flag. Failed preservation prevents SET.
Neither boot nor journal operations SET or trim the clock automatically.

Foreign EEPROM contents are not overwritten automatically: history returns
error 90 and boot keeps the live latch. Explicit `CLEAR ALL` initializes the
allocation. Write protection, failed verification and unavailable hardware
also keep live evidence latched.

## Stored format and failure handling

Each 32-byte slot has an eight-byte identity/version/slot header, four-byte
sequence, eight raw down/up bytes, eight capture-calendar/quality bytes, two-byte
CRC16, one clearance-status byte, and one commit marker. The outage chip fields
have month/day/hour/minute precision and no year. Capture time records the
current calendar separately; it does not invent an outage year or seconds.
Clock continuity and battery condition remain unknown.

Writes stay within the chip's eight-byte pages and use bounded completion
polling. The commit marker is invalidated before reuse; payload readback and CRC
validation precede the final commit. Only a verified committed record permits
ACK. An interrupted operation can therefore leave an old record, an invalid
slot, or a pending committed record. A pending record matching the still-latched
chip event is reused on retry. The clearance byte records whether the service
observed the chip flag clear. Sequence exhaustion refuses another save.

There is a narrow ambiguity if power fails after ACK but before the clearance
byte is updated and a later outage has identical minute-resolution fields.
The hardware supplies no event counter. The journal also cannot reconstruct
multiple outages that occurred while the chip flag was already latched.
EEPROM survives loss of the coin cell; RTC continuity does not follow from that.

## Placement and compatibility

Journal code occupies optional B3 sector 9 and has a verified discovery
descriptor. MAINT 1.7 and monitor write policies protect that sector. CLOCK 1.2
uses B2 sectors 8/9; MAINT uses B1 sectors 8/9. The fixed recovery F sector and
vendor B0 images remain unchanged. Updates publish saved-program records only
after both sectors verify.

RTC/I2C public entry points and the 512-byte resident RAM reservation remain
unchanged. The journal's transient workspace is $6B00–$6BFF, shared in separate
foreground phases with existing flash staging; every operation reloads EEPROM.
With the optional service software installed, user/program RAM is
`$0200-$64FF`, inclusive, and `$6500-$66FF` stays reserved even if the EDU board
is absent. User RAM can extend through `$66FF` only when optional service
software is absent or rejected on a cold boot; an already active reservation
persists until RESET. Programs must use the validated discovery descriptor's
RAM limit, rather than infer free memory from RTC availability.
The internal RTC component format is bumped to reject incompatible old gateway
templates safely. Public raw EEPROM access remains denied; other permitted I2C
devices retain the existing interface. Alarms, SRAM and program-record timestamp
formats remain future work. Native 816 calls remain outside this acceptance.

## Evidence

Owner-local evidence is under
`output/qualification/rtc-journal-2026-10-07/<board>/`: repeated complete prior
flash backups, EEPROM inventories, preserved RTC status, exact-source upgrade
plans, installer models/transcripts, and post-reset qualification records.
The allocation authorization is recorded at the evidence root. Original UTC
drift baselines are retained; this update does not synchronize the clocks again.

Host checks cover rotation through four slots, interrupted/corrupt writes,
protected/foreign EEPROM, pending-event retries, explicit clears, SET evidence
preservation, optional-device failure, both monitor slots and saved-record
publication.

Live checks on 2512, 2205 and 2609 passed after physical RESET and main-power
off/on. Both monitor slots, CLOCK history/show, canceled single/all-slot clears,
ACK with no event, MAINT 1.7 sector-9 refusal, and complete four-bank readbacks
were verified. 2512 without EDU remains usable and reports unavailable services.
2205's backed-up legacy EEPROM allocation was explicitly initialized; its
initial outage was saved through confirmed ACK. 2609 saved its initial outage
automatically on boot.

Both EDU journals retain these two real events:

| Sequence | Power down (UTC convention) | Power up (UTC convention) |
| --- | --- | --- |
| 1 | 10-07 12:56 | 10-07 12:59 |
| 2 | 10-07 14:44 | 10-07 14:46 |

Sequence 2 was committed and acknowledged automatically after the final main-
power cycle; sequence 1 remained byte-for-byte intact. Repeated EEPROM reads
matched, both live flags were clear, and UTC continued advancing. Factory
identity, protection status, backup enable, RTC control/trim and original drift
baselines were preserved. The evidence root's `acceptance.json` binds models,
source backups, installers, exact final flash images and EEPROM records.
Battery removal was not repeated. Hardware clearing tests preserved both actual
events by canceling CLEAR; confirmed logical deletion and four-slot rotation
were exercised in the model, while explicit allocation initialization was live.
