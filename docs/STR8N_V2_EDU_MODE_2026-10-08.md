# Beta15: saved EDU mode and reclaimed application RAM

October 9 update: frozen beta23 generation 32 is installed on 2512, 2205,
2604 and 2609. Its per-board ON/OFF transitions, pending notices, standalone
RAM use and restored ON protection passed hardware checks on all four.
See [current qualification](STR8N_V2_BETA23_FOUR_BOARD_STORAGE_2026-10-09.md).
Beta23 makes the pending status explicit: active `EDU ON`, followed by
`RESET required: OFF` (or the reverse). The existing successful-save notice
`Saved; RESET required.` remains. Cold J3 or main physical RESET activates the
saved mode; ordinary return does not. See the
[current reset contract and RC gates](STR8N_V2_RELEASE_CANDIDATE_PLAN_2026-10-09.md).
The following beta15 transcripts remain historical evidence.

EDU mode is an explicit per-board setting stored in the existing B3:C/D
configuration/wear journal. The firmware image is common to W65C02SXB and
W65C816SXB. The configured mode is latched at RESET, before optional service
RAM is installed. Hardware absence and device failures do not select OFF.

| Active mode | RTC/I2C/SPI/SRAM services | Highest application RAM byte |
| --- | --- | --- |
| ON | Verified optional service software may activate | `$64FF` |
| OFF | Disabled | `$66FF` |

OFF returns all **512 bytes at `$6500-$66FF`** to application programs. Startup
does not initialize or touch those bytes, and monitor return/HOLD does not
reinstall gateways over a program. The validated `SV` discovery descriptor
reports zero capabilities, a zero gateway pointer and `$66FF`. Program authors
must check discovery before accessing a service signature or calling a gateway.
OFF also disables these services for separately attached I2C/SPI devices.

ON retains the reservation even when EDU is absent or the RTC/SRAM is faulty.
An absent, invalid or unknown setting defaults to ON. Invalid configuration
checksums cannot release RAM. Missing/rejected optional software still follows
the prior fail-safe kernel rules; an active reservation never disappears on a
later validation failure. Fixed recovery F, system flash protection and flash
program storage are unchanged.

## User operation

The small **EDU 1.0** saved program is stored within already-used B2 sector C.
It loads at `$2000-$22CC` and changes only the configuration journal. It never
calls or accesses the service RAM that OFF makes available.

```text
B3> R EDU
EDU 1.0
? status; ON OFF Q
EDU> ?
EDU active: ON
EDU saved: ON
EDU> OFF
EDU saved: OFF
Apply after RESET? [y/N]: Y
Saved; RESET required.
EDU> ?
EDU active: ON
EDU saved: OFF
EDU> Q
```

Only a single `Y`, case insensitive, confirms. Enter or any other answer
cancels. Selecting an already-saved mode reports `No change.`. A saved change
does not affect the active reservation until a physical or cold software
RESET. It never takes effect merely by returning to the monitor. Re-enable
ON and RESET before using an EDU board fitted later.

With an EDU physically mounted, saved OFF provides the standalone firmware
profile: RTC/I2C/SPI/SRAM services are disabled and `$6500-$66FF` is available
to applications. Select `R EDU`, `OFF`, confirm `Y`, quit, then use `J3`.
To resume EDU use, select `ON`, confirm `Y`, quit and use `J3` again.
The active and saved modes are specific to that board. OFF does not remove
the hardware electrically; direct application access to its pins or devices
still depends on the mounted hardware.

With OFF active, boot shows `EDU: OFF; RAM top $66FF`; `TIME` reports
`RTCC: unavailable`. CLOCK, SRAM, WORK and the guarded SPI example report
unavailable services without writing reclaimed RAM. WORK 1.1 supports the
[direct KiB console](../tools/v2-spi/WORKSPACE_API.md).

## Size, storage and compatibility

The helpers use **104 bytes at `$EE94-$EEFB`** and **145 bytes at
`$EF50-$EFE0`** in existing E-sector gaps/help space, protected by the complete
E seal. The E launcher stays 1,754 bytes; both monitor slots fit their
3,968-byte limit. Existing reset-cleared monitor bytes `$7D27/$7D28` hold the
active mode and pending setting; no resident user-RAM reservation is added.
EDU's application image is **717 bytes** and its saved flash record 741 bytes.

Configuration byte 13 holds exact `$A5` for OFF; other values select ON.
The ordinary configuration checksum and committed journal CRC protect it.
Beta15's `C` edits and `P` promotion preserve this field, including when no
slot preference was previously recorded. Migration cleaning retains the exact
OFF tag while rebuilding any old slot locator. The setting uses no new sector
and no RTC EEPROM or SRAM bytes.

WORK 1.1 is 5,259 bytes at `$4000-$548A`, with a saved record at B2:B000-C4A2.
EDU uses B2:C600-C8E4. On 2609, the verified flash `DEMO2` record is preserved
at C540-C571; the incomplete agent-created DEMO is removed during the required
WORK sector update. Other saved records and both EDU SRAM arrays are preserved.

## Qualification

The assembled-code models cover OFF's untouched full RAM range, normal
monitor edit/run, high-RAM flash save/restore, WORK/TIME refusal, pending
ON/OFF changes, cold RESET activation, canceled input, preservation through
`C`/`P`, invalid configuration checksums and absent RTC/SRAM with ON reserved.
Existing RTC/journal/TIME/EUI/CLOCK/SPI and WORK interruption/integration models
are bound to beta15. Each board's fresh repeated complete flash backup is
rehearsed through the independent RAM installer, including exact final banks,
stale-preimage and corrupt-payload refusal, and WORK's commit after both B/C
sectors verify. RTC UTC/trim are never set by installation or these checks.

Beta15, WORK 1.1 and EDU 1.0 are installed and verified after main-board
physical RESET on 2512, 2205 and 2609. Final settings are OFF/$66FF on 2512
and ON/$64FF on 2205/2609. Both mode transitions are exercised and restored
on each board; both monitor slots and cold software RESET pass. The complete
512-byte pattern and an S19-loaded program at `$6500` survive normal monitor
return and unavailable CLOCK/SRAM/WORK/SPI clients. The SPI example returns
`$80` in RAM rather than printing an unavailable message. On 2512, ON's cold
boot also reports absent RTC hardware while keeping the reservation.

All boards pass the bank-safe RAM ABI and actual BRK/VIA1 timer IRQ probe,
with restored interrupt pointers. 2205/2609 pass WORK 1.1's confirmed temporary
format, 32/64 KiB resize, readable capacities and no-change result; the original
first 8 KiB of SRAM is restored and verified. Running UTC advances while control
and trim remain `$80/$00`; EEPROM/history and factory/current EUI are unchanged.
Final readback verifies all four flash banks, the expected two append-only mode
configuration records, both new utility records and preserved DEMO2 on 2609.
Full SRAM array comparison is recorded separately in each board's final archive.
The final read-only hardware audit passes for all three boards and both complete
128-KiB SRAM arrays match their repeated pre-install archives byte for byte.
The no-board-backups Git/history/release-ZIP audit passes. No commit, push or
release package is part of this installation; all ports are closed at `B3>`.
Raw flash/EEPROM/SRAM readbacks, serial logs and model receipts remain ignored
and local under `output/qualification/edu-mode-2026-10-08` and `BUILD`.
