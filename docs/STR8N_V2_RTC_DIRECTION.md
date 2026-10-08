# Optional MCP79411 clock service and future storage

Recorded 2026-10-06. An optional RAM service has
[scoped phase 1 acceptance](STR8N_V2_RTC_PHASE1_2026-10-06.md), followed by
[integrated beta5 phase 2 acceptance](STR8N_V2_RTC_PHASE2_2026-10-06.md).
Saved-record timestamps, alarms and chip memory remain future work.

STR8-N should provide programs with an optional real-time clock service for
the EDU board's MCP79411. Saved records should eventually carry timestamps.
Boards without an EDU, and installations without RTC software, must retain
normal boot, recovery, console, maintenance, and SAVE/RESTORE operation.
MCP79411 SRAM and EEPROM implementation was initially deferred; the later
ordinary EEPROM outage-journal decision is recorded under storage direction.

Owner decision, 2026-10-07: keep coarse trim OFF and expose normal signed
digital trim through CLOCK. The unflashed candidate and calibration procedure
are documented in [the trim policy](STR8N_V2_TRIM_EEPROM_POLICY_2026-10-07.md).
Alarms and MFP output configuration remain deferred. No trim adjustment occurs
automatically at boot or during time/status reads.

## Scope and delivery stages

| Stage | Scope |
| --- | --- |
| First | Bounded device probing, clock status/read, explicit time setting, power-fail status, and a callable service for programs |
| Later | Versioned saved-record timestamps and optional persistent outage history |
| Later | Alarm ownership, configuration, polling, acknowledgment, and release |
| After alarm qualification | Optional interrupt notification through verified board wiring |
| Deferred | MCP SRAM and EEPROM access, allocation, and persistence formats |

## Phase 2 direction agreed 2026-10-06

Activate the optional clock service on the first program request for clock access.
Store the component in board flash. Execution placement is a resident B3
extension with a small RAM gateway and workspace; see
[the phase 2 extension proposal](STR8N_V2_RTC_PHASE2_EXTENSION_PROPOSAL.md).
The user approved a separate extension sector. Expose a shared, versioned I2C
transaction interface beneath RTC so programs can use other bus devices without
requiring a working clock. Keep clock and bus discovery separate; activation
is on the first request for either service. The shared transaction ABI is now
implemented, published by the kernel and physically qualified within the scope
recorded in phase 2 acceptance.
Service discovery and activation must work
without relying on RTC SRAM, EEPROM, or a responding EDU.

When RTC support is enabled, reserve its RAM from RESET so the memory map does
not change underneath a running program. Verify flash before installing the RAM
gateway at RESET; initialize the bus/driver only when requested, then keep it
available until RESET. A missing or invalid
component returns unavailable without preventing boot or recovery. Missing
hardware and unusable time remain separate results; loading never sets time or
acknowledges an outage automatically.

Compact the prototype allocation and choose a location clear of MAINT and the
existing monitor workspace. Monitor-controlled loads, edits, restores, and
launches must honor that reservation before overwriting it. Programs must also
honor the published memory ownership. Preserve existing public entry addresses
and expose the optional service through versioned discovery rather than requiring
programs to assume the prototype's `$3000` address. Measured phase 2 placement is
B3 sector 8 and board RAM `$6500-$66FF`, with discovery at `$7D04`.

RTC SRAM remains deferred from phase 2. Its future role is an optional cache of
the last captured outage and associated metadata, retained through RESET and
ordinary main-power loss while backup works. Such a cache needs ownership,
versioning, integrity and interrupted-write handling, and readback verification
before explicit acknowledgment clears hardware evidence. Cache loss must not
prevent clock access or core operation. It is not the permanent outage history
needed to survive loss of both supplies, nor proof of clock accuracy or battery
health. Essential installation/settings state remains in board flash.

Phase 1 used a separately loadable RTC utility for hardware qualification.
Phase 2 adds persistent service lifetime, discovery and protected RAM ownership
while callers execute. Loading another program must honor those boundaries.
Release packaging and a final ABI freeze remain separate from the local candidate.

Beta4 already uses Bank 3 `$E000-$E7FF` for launcher support and
`$E800-$EEFF` for RESTORE/SAVE/TABLE. The earlier alpha plan to place the RTC
driver in an optional E sector needs a new size and layout review against
[the beta4 memory map](STR8N_V2_BETA4_MANUAL.md#ram-and-flash-map).
The reserved tail is not an allocation promise.

## Optional hardware and application access

Software availability, device response, clock operation, and time quality are
separate results. Programs must discover the service before calling it; a
service that is installed must report absent or unresponsive hardware safely.
An I2C acknowledgment alone does not prove the exact chip model or establish
that every EDU peripheral is present. Verify the fitted part and board revision.

All transactions and retry/recovery paths need finite bounds, including a stuck
bus. Return an error when recovery fails. Preserve unrelated VIA configuration,
coordinate ownership of shared I2C signals, and do not use LEDs or the buzzer as
presence tests. Reads must not initialize the clock, change alarms, write memory,
or consume power-fail evidence.

The application service should expose discovery/status, clock read, explicit
clock set, power-fail read, and explicit power-fail acknowledgment. These are
functional requirements, not fixed function names or assigned addresses.
Publish version, buffer size, registers/flags, error returns, scratch ownership,
bank handling, CPU mode, interrupt requirements, and reentrancy rules before
freezing the ABI. Retain existing entry addresses and static-bank compatibility.
Bank-independent application access is the target; native 816 calls require a
separate contract and qualification.

## Time representation and quality

The proposed convention is UTC, a full year, and 24-hour time, decoded into a
documented software format rather than exposing raw chip registers as the ABI.
Year interpretation, supported range, field encoding, and buffer layout still
need definition. Local-time conversion belongs at display boundaries.

A read returns a coherent calendar snapshot and separate quality/status fields.
Bounded rollover handling must prevent combinations such as an old date with a
new midnight time. On error, callers must not mistake stale output for a new
valid reading.

Distinguish unavailable service/device, communication failure, stopped clock,
invalid calendar, and running clock with uncertain continuity. A running clock
and plausible calendar do not prove correct setting or uninterrupted backup.
Expose detected problems and uncertainty rather than claiming battery health
or verified accuracy. A primary-power outage alone does not invalidate time.

Time setting is an explicit user-authorized operation, with a separate policy
for program callers. Ordinary reads never repair or reset time silently.
Setting time must preserve outage evidence first and define what happens to
armed alarms. The policy for accepting time for record timestamps remains part
of the service design; uncertainty must be representable to callers.

## Power loss and battery behavior

With backup enabled and working, the chip retains time, alarms, and SRAM through
main-power loss. Battery removal while main power is good does not itself stop
the clock. Loss of both supplies makes retained clock/alarm/SRAM state
untrustworthy; EEPROM retains data. There is no dedicated battery-health flag:
`VBATEN` enables backup and `PWRFAIL` reports primary-power loss.
[Microchip datasheet, sections 5.7 and 6](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf)

At startup or first service access, inspect the clock and power-fail evidence
before initialization writes. Preserve available evidence, report stopped or
invalid time, and require explicit setting after detected time loss. Complete
power loss can destroy the evidence too; a clear `PWRFAIL` flag cannot certify
battery retention. Default battery condition is unknown. A controlled retention
test demonstrates backup for that test, not remaining battery life.

Power-fail timestamps contain month, date, hour, and minute, without year or
seconds. Clearing `PWRFAIL` erases them and rearms capture; writing RTCWKDAY
also clears the flag. Backup and a running oscillator are needed for meaningful
capture. [Microchip datasheet, RTCWKDAY and section 5.7.1](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf)

Initially, reading status leaves evidence intact and acknowledgment is explicit.
Expose the hardware fields without inventing a year or exact outage duration.
Later, an outage journal may archive evidence in board flash before acknowledgment;
its retention, wear, and commit policy need a separate design. This mechanism is
outage history, not an emergency CPU SAVE window.

## Saved record timestamps

Future SAVE should sample usable time near the beginning of the operation and
define the timestamp as the save attempt's start time. The usual record commit
determines whether the record is complete; the timestamp is not proof of commit.
If time is unavailable or rejected by the quality policy, SAVE still succeeds
with an explicit unavailable timestamp state.

Use a versioned record format with integrity coverage for timestamp and status.
Keep reading existing beta4 records, which have a
[24-byte header](STR8N_V2_BETA4_RST.md#save-an-additional-copy), and identify
their time as unavailable. Do not silently reinterpret existing header bytes.
Define how older firmware handles the new format before publishing it.
TABLE can display timestamps and their quality. Existing timestamps are immutable
when the RTC is reset, corrected, removed, or unavailable. Time is metadata,
not a replacement for record identity, integrity, or ordering guarantees.

## Alarm direction

Owner decision, 2026-10-07: **defer both Alarm 0 and Alarm 1**. No alarm
configuration, ownership service, polling, acknowledgment or MFP/VIA interrupt
integration is planned for the current RTCC/CLOCK work. The direction below is
retained for a later explicitly authorized phase.
MFP output-mode/frequency/polarity configuration is also deferred by owner
direction; no output-control commands are being added to CLOCK.

The MCP79411 has two calendar-match alarms, software-cleared pending flags,
and a shared MFP output. MFP alarm output and square-wave output are mutually
exclusive. The EDU Rev D schematic routes MFP to `VIA_CA2_MFP`.
[Microchip datasheet, sections 5.4 and 5.5](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf),
[WDC EDU schematic](https://www.wdc65xx.com/wdc/Schematics/Schematic_W65C02EDU_REVD.pdf)

Programs should claim an alarm before configuring it, then check pending state,
acknowledge, disable, and release it. Define ownership across program exit,
RESET, and replacement; a reset must not transfer an old alarm to an unrelated
program. Alarm management uses dedicated RTC registers and does not depend on
implementing SRAM or EEPROM.

Start with polling. Later, verified VIA interrupt handling can flag an event
for foreground processing. Interrupt handlers should not execute stored programs
or perform flash operations. Verify MFP polarity, shared output behavior, VIA
configuration, and interrupt coexistence on both supported SXB board types.

Define one-shot versus recurring behavior, acknowledgment during an active match,
missed-event policy, and clock-change handling. Calendar matching is not a
general monotonic timeout service. Require usable time for new schedules and
explicit rearming after detected time loss. Alarm output does not by itself
provide power switching to wake an unpowered SXB. Timestamps need only a clock
read; a program may separately use an alarm to schedule a sample and SAVE it.

## Deferred memory direction

The initial direction below preceded the 2026-10-07 decision to allocate all
128 ordinary EEPROM bytes to four persistent power-fail events. See
[the beta8 journal](STR8N_V2_RTC_JOURNAL_2026-10-07.md) for the current layout,
save/verify/ACK policy and CLOCK history commands. SRAM remains deferred.

The chip provides 64 bytes of battery-backed SRAM, 128 bytes of ordinary EEPROM,
and 8 bytes of protected EEPROM containing the MCP79411 factory EUI-48.
[Microchip datasheet, sections 6 and 6.4](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf)

| Resource | Future direction |
| --- | --- |
| SRAM | Small, frequently changed state that can be discarded or reconstructed after battery loss |
| Ordinary EEPROM | Small, infrequently changed persistent settings, potentially calibration or board metadata |
| Protected EEPROM | Preserve factory identity; consider read-only identification later |

No bytes were allocated in the initial clock phases. Future layouts need ownership, versioning, integrity
checks, and initialization/migration rules. EEPROM writes additionally need wear
and interrupted-write handling. Essential boot configuration, saved records, and
their metadata stay in board flash so they work without an EDU. Neither chip
memory is a prerequisite for the initial clock service.

## Qualification and remaining choices

Host checks should exercise optional discovery, bounded failures, calendar
validation and rollover, status propagation, and ABI preservation. Later record
checks must cover old/new formats, unavailable time, integrity failures, and
interrupted commits; alarm checks must cover ownership and repeated matches.

Board qualification must cover both W65C02SXB and W65C816SXB, with EDU present
and absent, including clock setting/readback, a stopped or unset clock, bus
failure, main-power retention with backup, and controlled total-power loss.
Validate clock setting with shipped EDU firmware first. Record exact hardware
revision, fitted device, firmware/artifact identity, and transcripts. The old
absent-EDU menu's RTC `OK` message is a negative-control observation, not
qualification. Do not touch crypto or deferred chip memory during clock tests.

Before implementation, settle service loading/lifetime and memory placement,
the concrete ABI and time format, timestamp quality policy, and clock-set
authorization. Record-format changes and alarm support follow separately.
The separate-sector choice is implemented in the local beta5 candidate on
2512, 2205 and 2609. See [phase 2 acceptance](STR8N_V2_RTC_PHASE2_2026-10-06.md)
for discovery, ownership, migration and qualification. The published beta4
release remains unchanged; timestamps, alarms and chip memory follow separately.
