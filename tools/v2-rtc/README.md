# Optional RAM RTC service phase 1

This prototype supplies MCP79411 clock and power-fail access to programs without
changing STR8-N firmware. Reserve `$3000-$3FFF` for the driver, buffers, and state
while any caller uses it. The separate client occupies `$2000-$2199`.
The application owns this allocation; the monitor does not protect it from a
later RAM load, RESTORE, RESET, or another program. Recheck discovery after those
events and reload when necessary. This is a provisional application ABI.

Build and execute the linked-code host checks:

```text
python tools/build_v2_rtc.py
python tools/test_v2_rtc.py
```

WDC02AS and WDCLN must be on PATH. Tests require `py65`, using the same optional
`STR8_TEST_DEPS`, `PY65_PATH`, or `BUILD/v*/local/test-deps` search as existing
project tests. Serial tools require `pyserial`. Outputs are under
`BUILD/v2-rtc-phase1`; no release images are rebuilt.

## Load and call

At a qualified STR8-N v2 `B3>` prompt, use `L` to load `rtc-service.s19`, then
`L` to load `rtc-client.s19`, and `G 2000` to read the clock. Do not execute
the service's S19 entry at `$3000`: that address holds its descriptor, not code.
Programs check for `RC`, format 1, entry count 4 at `$3000` before calling the
entries defined in [rtc-api.inc](rtc-api.inc).

| Entry | Function |
| --- | --- |
| `$3004` | Read a coherent, decoded calendar; stopped/invalid time is an error |
| `$3007` | Read hardware status and raw registers; stopped/invalid time can still return transport success |
| `$300A` | Set the clock from the request buffer with an explicit intent key |
| `$300D` | Acknowledge power failure with an explicit intent key |

Return `A` is the status and carry is set for success. X/Y/N/Z/V are unspecified;
I and decimal mode are restored. The result byte at `$3F00` mirrors completed
calls; reentrancy refusal returns `A=8` without modifying the active call's
shared buffers. Do not call from IRQ/NMI or concurrently. Supported calling mode
is 65C02, or 816 emulation with DBR/PBR/direct page zero; native calls are excluded.
The service neither selects banks nor invokes monitor services.

The caller must have exclusive VIA1/I2C ownership. The driver releases PA0 and
PA7 instead of driving them high, bounds clock waits, and restores DDRA and
observed ORA output levels. Hidden latch values for pins configured as inputs
cannot be recovered by reading the VIA; callers that depend on them must keep
their own shadow. No-handshake ORA is used to avoid clearing handshake flags.

## Results and explicit writes

The decoded calendar at `$3F02` is eight bytes: year low, year high, month,
date, weekday, hour, minute, second. Supported years are 2000-2099. SET uses
UTC and weekday 1=Monday through 7=Sunday. CLOCK calculates DOW automatically
from the date entered with SET; users do not supply a separate weekday. The
decoded program-facing weekday uses this same numbering. A clock previously set by another
firmware has an unknown timezone and may use a different weekday convention;
READ does not reinterpret or certify either. It converts 12-hour readings to
24-hour software values; SET selects 24-hour mode.

Flags at `$3F01` report oscillator-start, running, calendar-range validity,
latched power failure, backup enabled, and continuity unknown. The last flag is
always set: software cannot certify battery health or correct prior setting.
Calendar values are usable only with a successful READ or the calendar-valid
flag after successful STATUS. Raw/current-outage buffers are meaningful after
a completed snapshot; transport errors may leave older raw bytes. An invalid
calendar can leave partial decoded values, which callers must reject.

SET uses the same eight-byte layout at `$3F20` and requires `$53,$54` at
`$3F29-$3F2A`. ACK requires `$50,$41` there. Keys are consumed on invocation.
They prevent accidental calls; they are not authentication or memory isolation.
The host's explicit command option supplies operator intent; program access
still requires the application's authorization policy.

SET validates the request before writing, refuses enabled alarms, stops the
oscillator with a bounded wait, and sets the calendar and backup-enable bit.
Control/trim settings are preserved. A failed write may leave a stopped or
partially changed clock; re-read and recover explicitly. SET success confirms
the write sequence, while the oscillator may still be starting. Require usable
READs and observed time progression using bounded retries. SET and ACK first copy
latched outage data into RAM at `$3F30`, with a valid byte at `$3F1C`. This last
capture survives subsequent calls but can be replaced by a newer event or lost
on module reload/RESET. It is not a persistent outage journal.

Writing the weekday/backup register clears the chip's power-fail evidence,
including during SET. Archive evidence before changing time. ACK preserves
weekday and backup enable. Ordinary READ/STATUS never write RTC register data.
No alarms, SRAM, EEPROM, or saved-record formats are implemented here.

## Board tooling and qualification

`backup_str8n_board.py` captures all four flash banks and independently repeats
each read. Its output directory must be new. `qualify_v2_rtc_board.py` likewise
requires a new evidence directory, tests service absence, verifies both loaded
RAM images before execution, reads twice, and calls through all four overlays.
Only explicit `--set-current-utc` and `--ack-powerfail` enable RTC writes.

```text
python tools/qualify_v2_rtc_board.py --port COM3 --board 2205 --out output/qualification/rtc-new-run
```

This tool overwrites the client's RAM, the driver's entire allocation, and
client zero-page scratch `$D0-$D1`. It returns through the existing monitor HOLD
entry. Existing firmware's prompt initialization may perform its own device
queries; the RTC service does not add EEPROM access to it.

See [the board acceptance record](../../docs/STR8N_V2_RTC_PHASE1_2026-10-06.md)
for the exact candidate and scope, including 2205's reported main-power outage,
latched-event acknowledgment, and total-power-loss recovery. 816 hardware and
native calls were excluded from those initial 02SXB runs. The 2609 follow-up
qualifies the same images in 816 emulation; native RTC calls and installation as
a persistent system service remain separate work.
2609 also passed main-power retention and fresh-event acknowledgment. Battery
removal on 2609 was declined by the user; expected behavior follows the 2205
result as an assumption, without a separate 2609 hardware test.

For 816 entry-state measurement only, build `tools/build_v2_rtc_816_probe.py`.
Its separate fixture uses `$2400-$243C` and captures E/P/DBR/PBR/D/S at
`$2500-$2507`. Run only on a positively identified 816; its instructions are
not compatible with the 65C02. The build checks exact linked instruction bytes
to catch WDC assembler width resets. RTC service/client artifacts are unchanged.

The phase 2 extension candidate now provides a shared public bus transaction
service; RTC register operations use the same engine. See
[the provisional I2C interface](I2C_API.md) for discovery, buffers, limits,
partial-progress results and managed-device policy. Its linked-code models
pass with a second slave while RTC is absent. Kernel bootstrap/protection,
MAINT relocation and scoped physical checks are now implemented in beta5. See
[phase 2 acceptance](../../docs/STR8N_V2_RTC_PHASE2_2026-10-06.md).

The phase 1 RAM layout above is retained for the original prototype. Integrated
clients first check the `SV` descriptor at `$7D04`, then discover clock `RG` at
`$6500` or bus `I2` at `$6510`. Clock results are at `$66C0`; the remaining
phase 1 result/request offsets are unchanged relative to that base. The kernel
reserves `$6500-$66FF` from RESET when the verified component is present.
With EDU mode ON and that optional software installed, user/program RAM ends at `$64FF`,
inclusive, even without an EDU board. An absent EDU alone does not release the
reservation. User RAM can extend through `$66FF` only when optional service
software is absent/rejected on a cold boot, or beta15's explicit EDU OFF is
latched at RESET. OFF disables the services and leaves the reclaimed RAM
untouched; see [EDU mode](../../docs/STR8N_V2_EDU_MODE_2026-10-08.md).
An active reservation remains
until RESET after later validation failures. Read the validated `SV`
descriptor's RAM limit; do not infer free RAM from RTC presence or read errors.
`kernel-client.asm` demonstrates this discovery and both interfaces.

The later unflashed [beta12/CLOCK 1.4 candidate](../../docs/STR8N_V2_RTCC_BINDING_2026-10-07.md)
adds monitor TIME, full EUI display and explicit remembered-identity acceptance
in the spare tail of existing B3 sector 9. It uses the current date/time format
and consistent RTCC status prefixes. User-program time access remains read-only;
[time-example.asm](time-example.asm) is the runnable example. No additional
sector or user-RAM reservation is introduced. Identity-tail preservation is
required when preparing a compatible firmware update.

The [CLOCK 1.0 utility](../../docs/STR8N_V2_CLOCK_1_0_2026-10-06.md) is a
user-facing client saved on all three qualification boards. Launch with
`R CLOCK`; R displays UTC, S shows status, SET accepts a full UTC calendar
with explicit YES, and Q returns to the monitor. Its integrated symbols are
in [kernel-rtc-api.inc](kernel-rtc-api.inc). Build with
`python tools/build_v2_clock.py`; verify with `python tools/test_v2_clock.py`.
Live qualification canceled SET to keep the current drift baselines valid.

The [beta6 banner](../../docs/STR8N_V2_RTC_BANNER_2026-10-06.md) performs a
clock READ on monitor entry/reentry. Shared RTC/I2C diagnostics may consequently
be replaced after HOLD; copy your own results before returning. The host drift
tool's sampling client does this at `$2440-$247F` and retains its timing marker.

[Beta7 and CLOCK 1.1](../../docs/STR8N_V2_RTC_POWERFAIL_2026-10-07.md) add the
power-fail marker and validated, yearless down/up times. CLOCK's explicit ACK
requires YES, captures evidence before clearing, verifies the latch, and retains
the RAM event for STATUS afterward. Time/trim are not reset. Boot and reads
preserve the latch; ACK rearms the chip to log the next outage. Current events
were archived and ACK-tested on both EDU boards, with the drift baselines intact.
