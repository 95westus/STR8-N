# rc1 operator guide - candidate

Use the [quick start](QUICK_START.md) for an installed board and the
[migration quick start](QUICK_START_MIGRATION.md) for host installation routes.
This guide covers console operation and preserving test campaigns.

## Identify the active context

| Prompt | Context | Return/help |
| --- | --- | --- |
| `B0>` through `B3>` | Monitor, selected bank shown | `?` |
| `CLOCK>` | RTC/calendar/history | `HELP`, `Q` |
| `ASM>` | Assembler/editor | `?`, `QUIT` |
| `DBG>` | DBG1 RAM debugger, generation 50 | `?`, C/S/N; `X` abort |
| `BM>` | MAINT utility | Utility help, `Q` |
| `SRAM>` | External SRAM manager | Utility help, `Q` |
| `WORK>` | Workspace manager | `HELP`, `Q` |
| `EDU>` | Optional-service mode | Utility help, `Q` |

Check the prompt after every return or canceled batch. A command letter can
have a different meaning at another prompt. Monitor `S` stores a program;
CLOCK `S` queries status. Monitor `F` patches flash after confirmation.
Debugger S steps, C continues, U disassembles and F lists BRK functions.

## Operate the DBG1 debugger

Confirm matching generation-50 MON A/B, core and ASM; published rc1 generation
49 lacks DBG1. A RAM application's stopping `BRK xx` opens `DBG>` automatically.
Use C/S/N, shared D/M and U, and up to eight persistent `B address` entries.
`BC address` / `BC *` clear them. A ninth distinct entry refuses without
discarding the first eight. HOLD, X and reset clear breakpoints and all dynamic
registrations. Save application RAM/source before loading an example.

V1g hardware requalification passed on 2604 (65C02) and 2609 (65C816 E=1),
both slots; original preferences and RAM were restored at hardware closeout.
R3, R4 and R5 closed safely in their separate scopes. The expanded R6 workload
also closed cleanly at owner STOP: 12,803.703 monitored/active seconds, 61/60
cycles and 976/960 breakpoint hits on 2604/2609. Both original full application
RAM images were restored/reread after final drift; flash/settings matched and
the worker exited. Its 630-frame ten-pattern programs restored entry LED state
before BRK without CRA/DDRA writes. No workload or RTC sampler was restarted.
Immutable distribution r7 packages the reviewed closeout. Promotion remains
held; see [current candidate status](DBG1_CANDIDATE_STATUS.md).
Native applications/debugging remain outside scope. See [operator details](DEBUGGER_GUIDE.md), [ASM examples](ASM_GUIDE.md#debugging-ram-programs-with-dbg1),
[registration ABI](ABI_REFERENCE.md#dbg1-brk-functions-and-registrations) and
[board results](DEBUGGER_BOARD_RESULTS.md). These documentation examples do not
restart stopped campaigns or perform another installation.

## Record a normal inspection

Record the firmware version, board identity, selected monitor slot, current
application list and stored-program table. Keep complete output for a failure,
including the first error and any subsequent prompt. Record the host UTC time
and relevant power transitions. Do not discard failed measurements or replace
them with earlier successful samples.

Preserve user application RAM before loading utilities, ASM or a RAM installer.
Keep flash, EEPROM and external SRAM backups identified separately. A raw
firmware file does not contain another user's retained data or clock state.

## Run a preserving campaign

The owner-stopped DBG1 continuation has exited with restoration and drift
verified. The following procedure requires separate authorization; it does not
restart a worker or RTC sampler.

Use one coordinated port owner and the shared lease for soak and RTC capture.
A snapshot temporarily borrows RAM, verifies its restoration and allows an
active worker to resume. Confirm actual successful unit receipts, complete
workload cycles and the exact worker process. A running PID alone is not a
passed test. An active restore-needed marker is expected while RAM is borrowed;
a stopped worker needs a verified completed restoration.

Follow the campaign's adopted duration and workload-coverage gates. Stop a
worker only at its safe boundary and verify restoration of its borrowed RAM.
Never restart a completed or owner-stopped worker automatically. Keep a
powered-off board's last sample as a historical observation; it is not a fresh
measurement.

The closed continuation used its authorized four-hour campaign phase and
completed only its final checkpoint during owner-stop closure. Separate RTC
endurance acceptance requires at least 168 hours
in an uninterrupted powered segment, a complete rate interval within +/-5 ppm
and uncertainty halfwidth at most 2 ppm. Pending/inconclusive stays pending;
an out-of-target stable clock rate calls for clock-performance review.

## Respond to a failure

Retain status, stdout/stderr, unit reports, snapshots, restoration markers and
power-transition evidence. Do not substitute comparison fixtures, hide a new
mismatch, clear power history or restart a failed worker automatically. A RAM
restoration failure requires inspection before further use. Installation
failures follow the package's hash-bound recovery route, not an unreviewed
rollback. Ask the owner to operate power/reset only at an exact documented step.

Keep clocks, trims, offsets, configuration and the registered baseline unchanged
during a preserving campaign. If status shows a stopped/invalid clock or an
unexpected setting change, preserve the evidence and mark continuity broken;
an earlier good sample cannot establish current clock health. Obtain a separate
decision before restoring time or starting a new measurement segment. Native 816 applications/testing, ACIA and
crypto remain deferred; startup CPU detection retains its accepted exception.
