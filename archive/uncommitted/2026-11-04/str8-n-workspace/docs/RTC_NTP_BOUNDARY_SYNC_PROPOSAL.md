# RTC synchronization at an NTP second boundary

Recorded 2026-10-23. Status: TODO / proposed; implementation and hardware
validation remain outstanding.

- [ ] Implement and validate board-timer-scheduled NTP synchronization using
  VIA1 Timer 2 as the preferred candidate: stage the UTC calendar in advance,
  map NTP time to the board timer, and commit at the second boundary with
  measured latency compensation. Confirm timer ownership and safe failure
  handling, then measure actual RTC transition alignment on hardware.

Prepare the RTC time-setting operation in advance, then commit the staged UTC
time at the intended NTP-derived second boundary. This aims to reduce the delay
and variation caused by starting a complete SET operation at that boundary.

## Proposed approach

- [ ] Obtain fresh NTP samples, retain their uncertainty, and map UTC onto a
  monotonic host timer. Select a future whole-second target with enough time
  to finish preparation, including calendar rollovers.
- [ ] Split preparation from commit: validate and stage the target calendar on
  the board, then leave a short, bounded commit path ready to execute.
- [ ] Determine the MCP79411 write/start sequence that best aligns its actual
  second transitions. Measure oscillator startup and divider behavior before
  assuming that starting a stopped RTC at the boundary aligns its first tick.
- [ ] Use a board timer to schedule the final commit locally. Send the target
  calendar and scheduling information ahead of time; no serial command should
  be required at the second boundary. Compensate for measured commit latency
  and define which hardware event constitutes the commit.
- [ ] Define cancellation, missed-deadline, and transfer-failure behavior,
  including recovery if preparation or commit leaves the clock stopped or
  partially changed. Preserve existing SET authorization, trim/control settings,
  and power-fail evidence policy.
- [ ] Verify subsequent RTC second transitions against the NTP-derived timeline,
  report measured offset and uncertainty, and compare with the current SET path.

## Board timer candidate (source review, 2026-10-23)

Prefer **VIA1 Timer 2**, in PHI2 interval-timer mode, for an initial foreground
prototype. The RTC uses VIA1 at `$7FC0`; T2 low/high are `$7FC8/$7FC9`, ACR is
`$7FCB`, IFR is `$7FCD`, and IER is `$7FCE`. T2 uses flag/enable bit 5. This
register mapping follows the existing VIA1 addresses and the
[WDC W65C22 datasheet](https://www.westerndesigncenter.com/wdc/documentation/w65c22.pdf),
sections 2.8, 2.9 and 2.14.

Evidence and alternatives:

- The [storage timing hardware record](STR8N_V2_STORAGE_TIMINGS_2026-10-08.md)
  already demonstrates borrowing idle Timer 2 on board 2609 with interrupts
  masked, accumulating modulo-65536 CPU-clock counts and restoring idle state.
- Source review of `src/current` found no explicit T1/T2 register allocation in
  the current RTC/SPI provider. This is a candidate resource, not proof that a
  running application or attached peripheral leaves it available. Check timer
  ownership, interrupt state, and ACR shift-register modes before borrowing it;
  Timer 2 also participates in some shift-register modes.
- **VIA1 Timer 1** at `$7FC4-$7FC7` is an alternative if periodic interrupts or
  a software-extended tick counter are needed. Its IRQ path has prior hardware
  proof in the [alpha11 board test](STR8N_V2_ALPHA11_BOARD_TEST_2026-09-23.md).
  Preserve PB7 behavior and ACR settings if using T1.

At nominal 8 MHz, 65,536 clocks span **8.192 ms**. Neither timer can hold a
one-second countdown directly at that clock rate. For T2, extend the timeline
in software with counter samples less than one wrap apart, then use a final
short countdown or poll near the deadline. Account for timer load/underflow
semantics and instruction overhead in the cycle model. Measure each board's
clock rate or include its frequency error in the scheduling uncertainty.

The current RTC provider enters with `SEI`, and the public service is foreground
and nonreentrant. Therefore start with a dedicated foreground operation that
owns the timer and I2C bus, polls the timer, and executes the prepared commit.
A timer interrupt cannot preempt that masked path. An IRQ-based design would
need an explicit interrupt-safe scheduling/commit contract and bounded interrupt
latency; do not simply call the existing RTC API from an IRQ handler.

Additional TODOs:

- [ ] Define timestamp exchanges that associate the board's extended timer
  with the host's NTP-derived monotonic timeline. Repeat exchanges and bound
  transport asymmetry; a local timer removes final-command delivery jitter,
  but does not remove uncertainty in this initial time mapping.
- [ ] Check idle ownership before touching timer state. Preserve unrelated
  ACR/IER bits, port behavior, and pre-existing pending flags; refuse an active
  timer rather than attempting to recreate its running phase afterward.
- [ ] Bound every operation while tracking wraps, reserve a quiet final window,
  and reject a late or ambiguous deadline. Restore borrowed idle state on all
  completion/cancellation paths.
- [ ] Model timer scheduling and then verify on hardware with observed RTC
  transitions. No timer was programmed and no RTC was set during this review.

## Expected accuracy and measurement targets

These are engineering estimates and prototype targets, not measured performance
or a guaranteed UTC error bound. For the existing host/USB path, plan initially
for **tens of milliseconds (roughly 10-100 ms)** of absolute RTC-to-UTC error
under favorable NTP and transport conditions, subject to measuring the RTC's
write/start response. Poor samples, transport asymmetry, or variable oscillator
startup can make the error larger. Reject a sample or report a wider bound when
the measured uncertainty does not support the target.

| Contribution | Planning expectation |
| --- | --- |
| Timer resolution at nominal 8 MHz | 0.125 microseconds per tick; resolution is not UTC accuracy |
| Local deadline-to-commit repeatability | Target below 100 microseconds after modeling polling and compensating the I2C commit path; unverified |
| NTP reference and host-to-board mapping | Likely dominant millisecond-scale terms; measure each run rather than assigning a fixed guarantee |
| RTC write/start and first transition | Unknown until measured; may dominate despite an accurate local trigger |
| Board clock error during countdown | Frequency error in ppm multiplied by wait time; e.g. 100 ppm adds 0.1 ms over one second |

The existing [storage timing record](STR8N_V2_STORAGE_TIMINGS_2026-10-08.md)
observed roughly 16-ms USB quantization in host command timing. That is evidence
against promising sub-millisecond synchronization through the present transport,
not a measured limit for the proposed timestamp-exchange implementation.
Repeated exchanges can identify low-delay observations but cannot prove away
fixed directional delay asymmetry. NTP offset, round-trip delay and dispersion
must be retained as described in [RFC 5905](https://www.rfc-editor.org/rfc/rfc5905.html#section-8).

Treat **1-10 ms absolute alignment as a stretch target**, requiring measured
improvements to time mapping and confirmation of RTC behavior. Do not advertise
microsecond UTC synchronization from timer resolution alone. A hardware timing
reference such as PPS would be a separate future option, outside this software
proposal and the current no-hardware-modification scope.

Verify actual second transitions, not just integer calendar readback. Bound
read acquisition times or capture a suitable hardware signal if already wired
and available; report initial phase error separately from later crystal drift.
For scale, a residual RTC rate error of 1 ppm accumulates 86.4 ms per day, so a
precise SET does not replace oscillator calibration or periodic synchronization.

## Current behavior and acceptance

`src/current/provider/rtc-provider.asm`, at `SET_CLOCK`, validates the request,
stops the oscillator, waits for it to stop, and then writes the calendar. That
work currently lies in the SET execution path.

Accept the proposal only after measurements show improved boundary alignment
with a documented error bound and safe failure handling. NTP and host scheduling
provide an estimated boundary, not an exact hardware timing pulse. No accuracy
target is claimed until the trigger path and RTC response have been measured.

Reference: [Microchip MCP79410/11/12 datasheet, DS20002266J](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf).

## November 3, 2026: qualified 2604 RAM prototype

A dedicated 65C02/2604 Foundation MON g10 prototype is implemented in
`BUILD/ntp2604-r8`. Its 2,566-byte RAM image and 39 CPU/VIA/I2C/FT245 model
cases are recorded in `build.json` and `proof.json`; the reproducible source
and Python host are in `source/`. This is a foreground RAM program, not a
permanent firmware installation. General firmware integration, other boards
and broader calendar-setting cases remain outside this qualification.

The host defaults to `time.nist.gov` and supports `--server`. Repeated causal
timestamp exchanges map the software-extended VIA1 Timer 2 counter onto the
NTP-derived host timeline. Both stop and resume deadlines are staged ahead
of time. Fine alignment uses a measured 2–3 second pause with a bounded
integer-second advance and measured startup compensation. It does not assume
that restarting the oscillator establishes a fresh second-divider phase.
The coarse same-date calendar operation preserves RTCWKDAY/PF evidence.

The accepted live baseline follows at least 64 seconds after verified
oscillator operation and a separate 62-second read-only acquisition. All nine
pre/post NTP references, aged under the recorded 100 ppm reference model,
were used to refine the same saved capture: RTC minus NIST **+0.023024 s**,
compatible interval **[-0.022025, +0.068074] s**. Successful board work was
not repeated for this refinement. Bounds include the stated timer/reference
and within-capture RTC-rate allowances; they are not statistical confidence
intervals or a universal accuracy guarantee.

Owner RAM/ZP, provider cache/hooks, original REC prompt and all four flash
banks were verified restored or unchanged. The qualified BASE1 W/Y restore
transport stages the temporary agent; no monitor M RAM writes are sent to
2604. Default agent images are write-disabled. The explicitly authorized
initialization disabled OSCTRIM, preserving its original raw value 0x0C.
Subsequent collection makes no RTC data writes. No PF acknowledgement,
EEPROM/flash/SPI write, firmware install, CPU reset or power cycle was
performed by this calibration.

The campaign takes hourly 62-second measurements and keeps clock/trim
changes in separate fit segments. A trim proposal requires at least 24 hours,
12 accepted points and a compatible drift-rate interval no wider than one
normal trim step. The proposed trim requires owner approval and is never
applied by this collector.

- Control: `output/qualification/2604-untrimmed-ntp-campaign.json`
- Report: `output/qualification/2604-untrimmed-ntp-report.md`
- Accepted receipt: `output/qualification/2604-ntp-accepted-20261103T212738Z/report.json`
- Independent audit: `output/qualification/2604-ntp-accepted-20261103T212738Z/reference-refinement-audit.json`
