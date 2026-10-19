# STR8-N rc1 quick start

Target: STR8-N 2.0rc1 generation 49, CLOCK 1.11 and ASM 0.5. One firmware
set serves 65C02 and 65C816 emulation-mode runtime. The existing startup CPU
detector is the accepted exception; native applications, ACIA and crypto are
deferred. This rc1 guide covers the scoped release candidate; full endurance/RTC qualification is deferred.

For the local **generation-50 DBG1 extension**, see the
[RAM debugger quick guide](DEBUGGER_GUIDE.md) and
[ASM C/S/N example](ASM_GUIDE.md#c-s-and-n-example). Published generation 49
does not include it. `VERSION` distinguishes the generations; the ASM title
remains 0.5. Native applications/debugging are outside scope.

## Start with an installed board

Use the FT245 console and the board's established terminal configuration.
Wait for a monitor prompt such as `B3>`. These commands identify the installed
version and available programs:

```text
VERSION
APPS
?
T 1
```

`APPS` and `T` describe different inventories: applications/utilities and stored
program records. The selected flash bank matters when displaying addresses.
Do not infer that a separately supplied application is installed from its
presence in a ZIP.

At an idle board, read the RTC without changing its settings:

```text
R CLOCK
STATUS
TIME
Q
```

`CLOCK>` is a program prompt; `B3>` is a monitor prompt. Use the command
reference for the current context. `Q` returns from CLOCK. Do not use SET,
TRIM, OFFSET, ACK or CLEAR during a preserving measurement campaign.

## First-use setup on an idle board

These are optional setup instructions for a board you intend to configure.
They change saved data. Back up the board first and end any active soak or
drift campaign before following them. They are not steps for the current
laboratory campaign.

### Set a board name

At `B3>`, enter `MAINT`. At `BM>`, query or set the friendly name:

```text
MAINT
NAME
NAME BENCH09
YES
NAME
Q
```

Enter `YES` only when the confirmation prompt appears. Replace `BENCH09` with
your own name: 1–8 printable characters, without spaces; input is converted
to uppercase. `NAME` alone displays the current name; `NAME CLEAR` removes it
after confirmation. This friendly name does not change the board's hardware
identity or EUI. `Q` returns to the monitor.

### Set the calendar and clock in UTC

At `B3>`, enter `R CLOCK`, then inspect `STATUS` and `TIME`. Obtain the correct
current **UTC** date/time from a trusted source. The following date is an
example, not the time to copy into your board:

```text
R CLOCK
STATUS
TIME
SET 2026-01-02 12:34:00
YES
```

Replace the example with the intended UTC date/time before sending `SET`.
Check the displayed requested UTC value, then type `YES` at its confirmation
prompt. `SET` changes the calendar and clears the chip's power-fail flag;
preserve outage/history evidence beforehand. Enabled alarms cause SET to be
refused. If SET reports a failure, inspect `STATUS` before retrying.

After a successful SET, CLOCK may offer an initial local-offset setup prompt
if no offset is saved. Press Enter to keep UTC (`+00:00`), or enter the desired
offset and confirm it when asked. Finish with `TIME` and `STATUS` to check the
result, then `Q` to return to the monitor.

### Choose the local display offset

The RTC remains in UTC. A saved fixed offset changes the local display; it
does not adjust the oscillator or automatically follow daylight saving time.
For example, a location currently five hours behind UTC would use:

```text
R CLOCK
OFFSET -05:00
YES
OFFSET
TIME
Q
```

Choose your actual offset, not the example. The supported range is `-12:00`
through `+14:00`; use `OFFSET +00:00` for UTC. `OFFSET` alone displays the
saved value. Confirm a changed value with `YES`. Update it manually when your
local daylight-saving rule changes. Leave `TRIM` unchanged until a measured
drift analysis supports a deliberate calibration.

## Choose an installation route

| Starting point | Required delivery |
| --- | --- |
| Recognized factory WDCMONV2 | Direct WDCMONV2-to-rc1 migration package |
| Recognized published STR8-N v2.0b4 | Separate beta4-to-rc1 upgrade package |
| External programmer / fresh provisioning | STR8-N-only complete application image and address layout |
| Interrupted migration | The matching package's recovery procedure and original local backup |

Choose the Windows or Linux package for the host. Both packages must install
the same pinned firmware bytes and include bounded recovery. The current live
source/empty-bank scope and known limits are documented in the platform guides.
See the [migration quick start](QUICK_START_MIGRATION.md).

## Assemble a first program

Follow the short example in the [ASM manual](ASM_GUIDE.md). ASM owns application
RAM while running. Save source and exported S-records on the host before
loading another application. `ORG` sets a logical origin; it does not relocate
the output buffer automatically.

uChess source and its original license/credits must accompany its executable.
See [third-party attribution](THIRD_PARTY_NOTICES.md) and the new candidate's
[firmware inventory](FIRMWARE_CONTENTS.md), including remaining distribution gates.

## During a measurement campaign

Do not run the first-use setters or open a board's serial port while a soak,
snapshot or installer owns it. Keep the registered baseline and power-event
evidence. A stopped/invalid RTC or an unexpected setting change breaks time
continuity; preserve the observations and investigate before setting time or
starting a new measurement segment.

Continue with the [operator guide](OPERATOR_GUIDE.md), [user guide](USER_GUIDE.md),
[command reference](COMMAND_REFERENCE.md) and [technical manual](TECHNICAL_MANUAL.md).
