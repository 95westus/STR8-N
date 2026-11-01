# Aligning Four Real-Time Clock/Calendars to a Time Standard

*Internet-referenced UTC, local timing, and verified second-tick alignment*

**Abstract.** Setting a real-time clock/calendar (RTCC) to the correct date and second does not necessarily align its second transitions with a reference clock. Serial communication, command processing, and oscillator restart behavior introduce delays. The STR8-N tick alignment program addresses this problem by measuring each board’s timing offset, applying a bounded correction, and measuring the result again. A documented four-board validation achieved RTC-minus-reference intervals entirely within ±100 milliseconds; the largest absolute interval endpoint was 69 milliseconds. The implemented reference is NIST time obtained over the internet. A local high-resolution counter carries that reference between network exchanges.

## The alignment problem

An RTCC presents calendar values in whole seconds, but its internal second transitions can occur anywhere within the reference second. Two boards may display identical times while changing to the next second at visibly different moments.

This creates three separate requirements:

- **Calendar correctness:** the clock shows the correct UTC date and whole second.
- **Tick alignment:** the second transitions occur close to reference second boundaries.
- **Frequency accuracy:** the clock continues advancing at the correct average rate.

A calendar-setting command primarily addresses the first requirement. Tick alignment addresses the second. Long-term drift measurement and oscillator trimming address the third.

Pressing Enter at an exact second boundary is insufficient because the Enter key’s arrival at the host is followed by operating-system scheduling, USB and serial transport, monitor processing, and RTCC register access. The program therefore verifies the resulting clock behavior instead of assuming that a precisely scheduled command produces a precisely aligned clock.

## Where the time standard comes from

The current program uses **internet time from a NIST NTP server**, with `132.163.96.6` as its default address. NIST’s Internet Time Service distributes its realization of UTC using NTP. Network conditions affect the accuracy available at the receiving computer. [NIST Internet Time Service](https://www.nist.gov/pml/time-and-frequency-division/time-distribution/internet-time-service-its)

The program also uses a **local monotonic performance counter**. This counter measures elapsed time; it does not independently know UTC. Network exchanges establish a mapping between the counter and UTC:

\[
T_{\mathrm{UTC}}(p)=p+C
\]

Here, \(p\) is the performance-counter reading and \(C\) is the estimated UTC origin.

Thus, the implemented method combines an internet reference with local interval timing. It does not change the Windows system clock or rely on the Windows clock remaining unchanged during a measurement.

| Reference arrangement | Current support | Meaning |
|---|---|---|
| NIST NTP over the internet | Implemented and used in the documented validation | UTC reference supplied directly by NIST |
| Local NTP server | Configurable through `--server`; requires separate qualification | Accuracy and traceability depend on that server |
| Windows calendar clock alone | Not the alignment reference | Does not provide the program’s verified UTC relationship |
| Local hardware pulse-per-second reference | Would require additional hardware and software | Could support more direct measurement of second boundaries |

A local server is therefore possible, but “local” does not itself mean more accurate. Its reference source and delivery path must be established.

## Establishing a bounded reference

The program collects five NTP exchanges, separated by at least 4.05 seconds. It records local send and receive counter values along with the server’s receive and transmit timestamps.

Each exchange produces an interval of plausible UTC origins. The program expands that interval using the server’s reported timing information and an additional margin, then intersects the intervals from the exchanges. It rejects unsynchronized responses, inconsistent timing, excessive round-trip duration, or an origin interval wider than 100 milliseconds.

A final NTP exchange checks whether the reference remains compatible with the initial estimate.

These bounds are operational uncertainty estimates under the program’s assumptions. They are not a formal metrology certification, and the response checks do not provide cryptographic authentication.

## Measuring a clock that reports only whole seconds

The program temporarily loads a small measurement routine into each board. A host/board handshake starts each observation after monitor launch processing has completed.

If an observation returns RTC second \(s\), and the read occurred between reference times \(a\) and \(b\), the RTC offset is compatible with:

\[
s-b-u \leq \Delta < s+1-a+u
\]

where \(u\) represents reference uncertainty and \(\Delta\) is RTC time minus reference time.

One observation leaves a broad interval because the RTC reports integer seconds. Repeated observations around successive transitions narrow the interval. The program intersects the observations and requires samples spanning at least three distinct RTC seconds.

This approach bounds the timing offset without pretending that the host knows the exact instant of an I²C read.

## Applying and verifying the correction

The MCP7941x RTCC exposes oscillator start control through the ST bit in its seconds register. Its digital trim mechanism is a separate facility for frequency correction. [Microchip MCP79410/11/12 datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/MPD/ProductDocuments/DataSheets/MCP79410-MCP79411-MCP79412-Battery-Backed-I2C-RTCC-DS20002266.pdf)

The alignment program first calibrates a delay loop on the selected board. It then uses a bounded pause/restart operation to shift the RTC’s phase. Where necessary, it includes a guarded one-second addition while avoiding the minute-rollover boundary.

After each correction, the program measures the offset again. Feedback estimates the actual pause/restart response and compensates for the difference between the requested and observed adjustment. It permits at most five correction attempts.

Success requires the **entire measured offset interval** to fit inside the requested tolerance. An interval midpoint near zero is insufficient if its uncertainty extends beyond that tolerance.

Large calendar errors are outside this phase-correction mode’s scope. They require an explicitly authorized calendar-setting operation first.

## Preserving board state

The temporary routine occupies CPU RAM addresses `$2000–$2434`. The host reads the original block twice, verifies the staged image, and restores and verifies the original bytes afterward. It also restores the original monitor or recovery prompt.

The implementation uses board-specific loading transports, including the established S-record loader on 2604. Its preservation claim concerns the borrowed RAM block; normal monitor stack and runtime activity are not represented as a complete machine-state snapshot.

Phase alignment preserves trim, control settings, and power-fail timestamps. It requires a clear power-fail latch and disabled alarms. It performs no PF acknowledgement, history clearing, EEPROM or flash programming, or automatic CPU reset.

These checks matter because a timing result should remain distinguishable from unrelated configuration changes or lost event evidence.

## Documented four-board results

The saved validation report records the following results on November 1, 2026. Positive values mean RTC time was ahead of the reference; negative values mean it was behind.

| Board | Verified RTC-minus-NIST interval | Corrections |
|---|---:|---:|
| 2205 | +1.6 to +69.0 ms | 2 |
| 2512 | −45.7 to +21.1 ms | 1 |
| 2604 | −59.4 to +7.4 ms | 2 |
| 2609 | −35.1 to +37.2 ms | 1 |

All four intervals satisfied the ±100 ms target. These are individual measurements against a common reference taken during sequential board runs. They do not establish simultaneous, zero-skew transitions across all four boards.

Validation included 30 CPU/I²C model cases across 65C02 and 65C816 emulation, host-side checks, live board measurements, and RAM and state-restoration audits. The results are documented in the [saved alignment report](RTC_TICK_ALIGNMENT_RESULTS_2026-11-01.md).

## Starting a new drift baseline

Phase correction changes the clock’s offset and creates a discontinuity in the measurement history. A drift fit must not cross that adjustment.

For subsequent elapsed time \(t-t_0\), a simple model is:

\[
\Delta(t)=\Delta_0+\epsilon(t-t_0)
\]

The corresponding average frequency error is:

\[
\mathrm{ppm}=10^6\frac{\Delta(t)-\Delta_0}{t-t_0}
\]

For example, one ppm produces 86.4 milliseconds of accumulated error per day. Consequently, a successful alignment can gradually degrade even when the original setting was accurate.

The program retains earlier measurements and baselines while establishing a new segment after an adjustment. Tick alignment establishes the starting offset; later observations determine frequency error. The documented phase procedure leaves trim unchanged.

## Engineering implications

The demonstrated method provides measured alignment at the tens-of-milliseconds scale using existing serial connections and temporary board code. Its strongest feature is verification: it reports a bounded result after correction and retains the evidence needed to inspect that claim.

Closer alignment would require reducing the uncertainty in both reference delivery and board observation. A potential extension is a qualified local time source with a hardware pulse-per-second signal and hardware timestamping of the board’s second transitions. That would require a new measurement path and validation; replacing the internet server with a local address alone would not establish improved accuracy.

The present implementation is therefore best described as **one-time RTCC phase alignment to internet-delivered NIST UTC, measured using a local monotonic counter**, followed by a new drift baseline. It establishes a verified initial relationship to the reference rather than continuous phase lock.

Implementation details are available in the [alignment source](../tools/rtc_phase_align.py) and [operating notes](RTC_TICK_ALIGNMENT.txt).
The [board routine](../src/rtc-phase/phase.asm), [offline builder](../tools/build_rtc_phase.py), and [CPU/I²C tests](../tools/test_rtc_phase.py) accompany the host implementation. See the [source and protocol notes](../src/rtc-phase/README.md) for the RAM interface and build identity.
