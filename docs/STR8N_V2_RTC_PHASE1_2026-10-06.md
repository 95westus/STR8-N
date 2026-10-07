# Optional RTC phase 1 board acceptance

Recorded 2026-10-06 America/Chicago. The first optional RAM clock-service
prototype passed host checks, W65C02SXB checks with and without an EDU, and
W65C816SXB emulation checks with an EDU.
The RTC on 2205 was explicitly set to UTC. No flash bank was erased or written.
This qualifies the application prototype's tested operations; persistent
monitor integration and native-mode RTC calls remain separate work.

## Boards and complete flash backups

| Board | Port | EDU | Observed monitor | Final READ result in each overlay |
| --- | --- | --- | --- | --- |
| 2512 | COM4 | Absent | STR8-N 2.0a26, 65C02 | `$01`, bus unavailable, B0 through B3 |
| 2205 | COM3 | Present | STR8-N 2.0b4, 65C02 | `$00`, decoded clock success, B0 through B3 |
| 2609 | COM8 | Present | STR8-N 2.0b4, 65C816 emulation | `$00`, decoded clock success after explicit setting, B0 through B3 |

FTDI enumeration reported COM4 serial `A10MQFLCA` and COM3 serial `A10MPUPNA`.
The user confirmed COM4 is physically 2512. Its initial B1/B2 reads were entirely
`$FF`, rather than the expected v1.35/BSO2 images; the user accepted continuing
and noted those releases could be restored separately. Both boards' B1/B2
readbacks were erased. No bank was booted or changed to establish these results.

Each backup contains four 32,768-byte BINs, a combined 131,072-byte BIN in B0-B3
order, independent repeat BINs, a manifest with SHA256 hashes, and serial evidence.
Every byte matched on repeat reads. Complete post-test reads also matched all
four original banks exactly on both boards.

| Board | SHA256 of combined original flash |
| --- | --- |
| 2512 | `4ecbeed21af4034da877f653d7324e1142098243547032673f7fe03361a8f7c2` |
| 2205 | `935dcfefcfe8c55c9b9fcb73dbc7578bc0c5eb79547929b0acf72e832540da3f` |

Owner-local evidence is under `output/qualification/rtc-phase1-2026-10-06/`,
with separate `2512` and `2205` directories. Each has `full-backup` and
`post-test-flash`; raw firmware stays excluded from Git and release artifacts.

## Qualified candidate and application interface

| Image | Allocation or code span | Bytes | SHA256 |
| --- | --- | --- | --- |
| rtc-service.bin | Owned RAM `$3000-$3FFF`; code/state ends `$355F` | 4096 | `5a6068fbd0f15e86e52783f22241d52a57aadea09d83f5d4324e07174c4bfa3b` |
| rtc-client.bin | `$2000-$2199` | 410 | `7a27ed6e5783549be2b70a1cd7fed7fa888853ba57d204b4f8570fba0b6164ef` |

The driver's image initializes its entire allocation, including buffers and
capture validity. This footprint is a prototype allocation, not 4096 bytes of
resident monitor code. The caller reserves that RAM while the service is active.
The descriptor is at `$3000`, with READ, STATUS, SET, and ACK entries at
`$3004`, `$3007`, `$300A`, and `$300D`. RESET/reload invalidates lifetime assumptions.
Existing ROM/RAM entry addresses and frozen release sources were unchanged.

See [the service guide](../tools/v2-rtc/README.md) and
[API include](../tools/v2-rtc/rtc-api.inc) for the provisional contracts,
intent keys, status flags, and buffer layout. The normalized year range is
2000-2099; UTC is the setting convention. External firmware's earlier timezone
and weekday convention are not certified by READ.

## Host checks

`python tools/build_v2_rtc.py` built the linked machine images, and
`python tools/test_v2_rtc.py` executed the service in a bit-level I2C/VIA model.
Checks covered positive reads, 12/24-hour conversion, calendar/BCD bounds,
leap years and full-year boundaries, stopped-clock status, absent-device NACK,
both stuck lines, clock timeout, bounded rollover retries, I/decimal-state and
VIA restoration, guarded SET, enabled-alarm refusal, reentrancy refusal, and
power-fail capture/acknowledgment. Modeled reads caused no RTC data writes;
SET/ACK wrote only their allowed clock registers, with no SRAM/EEPROM access.

The build manifest and `test-results.json` bind the tests to the service hash.
These model checks do not certify electrical timing or physical battery behavior.

## Board checks

Both boards exposed `RA`, format 1, count 13 at their initialized RAM ABI.
The host verified loaded service/client images byte-for-byte before execution.
A deliberately missing service descriptor produced `RTC service unavailable`
and returned safely to the monitor. The separately loaded client then exercised
the installed service, demonstrating the application-call path.

On 2512, READ returned `$01` with continuity-unknown flag `$20`; the unavailable
bus did not hang. On 2205, repeated reads returned `$00` and advancing seconds.
Each service call retained DDRA and driven VIA output levels. Calls under all
four flash overlays preserved the selected bank and returned the expected status.
The existing a26 prompt on 2512 independently printed its pre-existing EDU/EEPROM
status; those queries are outside this new driver's operations.

2205 initially reported raw clock/control/trim:
`D3 39 20 3B 06 10 26 C3 00`, with flags `$3F` including latched power failure.
The outage bytes were `37 11 06 70 37 11 06 70`. Read-only captures preserved the
hardware flag and timestamps. These bytes do not supply an outage year or seconds.

After raw evidence was saved, explicit SET requested
`2026-10-07T01:40:12.488296+00:00` and returned raw
`92 40 01 2B 07 10 26 C3 00`, flags `$37`. The next read advanced to second `$14`.
Control `$C3` and trim `$00` remained unchanged; backup remained enabled.
Writing the calendar cleared hardware power-fail evidence, while the previous
outage bytes remained in the service's RAM capture and owner-local files.

An explicit ACK call subsequently returned success and preserved weekday and
backup enable. A fresh latched outage was not generated on hardware for that
ACK run; acknowledgment of a latched event and evidence retention were exercised
in the host model. Both monitors remained responsive at `B3>` afterward.

## Remaining qualification

The follow-ups below qualify retention through the reported main-power outage,
acknowledgment of its newly latched event, and reported loss of both power
sources on 2205. Battery depletion detection/lifetime and 816 emulation hardware
were not covered by the initial 02SXB runs. The 816 emulation calls are qualified
by the 2609 follow-up below; battery depletion detection/lifetime remains
unqualified. Chip
SRAM/EEPROM implementation, alarms, saved-record timestamps, and persistent
service installation remain deferred. The current
module is callable while its application-owned RAM allocation remains intact;
it is not automatically reinstalled after RESET.

This implements the first prototype of
[the agreed RTC direction](STR8N_V2_RTC_DIRECTION.md). Further firmware integration
requires a placement/lifetime design and continued ABI compatibility checks.

## Main power outage follow up on 2205

After the user reported 2205 had been powered off, COM3 reconnected with the
same FTDI serial and beta4 prompt. The unchanged, verified service and client
were reloaded into RAM. No clock setting was issued in this follow-up.

The initial READ returned `$00`, flags `$3F`, with raw registers
`D2 53 01 3B 07 10 26 C3 00`: 2026-10-07 01:53:52 UTC. A second READ advanced
to 01:53:54. The first complete console reading arrived at host time
01:53:53.399750 UTC, consistent with the clock retaining time through the
reported outage. This is a scoped retention result, not a battery-life estimate
or a measurement of the exact power-off interval.

New outage bytes were `53 01 07 70 53 01 07 70`. Both read-only snapshots
retained the hardware power-fail flag and identical outage bytes. Power-down and
power-up fell within the same calendar minute; no exact duration or outage year
is inferred from those hardware fields.

After raw evidence was archived, explicit ACK returned `$00`, flags `$37`,
with hardware outage registers zeroed. The valid RAM capture still contained
the original outage bytes. Weekday, backup enable, control `$C3`, and trim `$00`
were preserved, and clock seconds continued advancing. All four bank overlays
returned successful reads and retained bank selection. No flash operation was
issued. A complete four-bank flash readback and independent repeat matched the
original backup byte-for-byte. 2512 was not accessed during this follow-up.

Owner-local evidence is in `2205/power-cycle-read`, `2205/power-cycle-ack`, and
`2205/power-cycle-audit.json` under the evidence root above; final flash evidence
is in `2205/post-power-cycle-flash`. The audit binds the
reports with SHA256 and checks time progression, host-time agreement, preservation
on reads, acknowledgment, and retained capture. It supersedes the earlier
limitation that latched-event ACK had only been exercised in the host model.

## Total power loss and explicit recovery on 2205

The user confirmed completion of the requested sequence: main power disconnected,
CR2032 removed, a 30-second wait, battery refitted, and main power restored.
The unchanged candidate was reloaded into RAM and read before any RTC data write.

Both initial READs returned `$04`, flags `$24`, and identical raw registers
`00 00 00 01 01 01 01 80 00`. The software interpretation was
2001-01-01 00:00:00, with a calendar in range but a stopped oscillator and backup
disabled. All hardware outage bytes were zero, with no valid captured evidence.
The clock did not advance or start during read-only calls. Calls in all four
bank overlays returned the same bounded error and retained bank selection.
This demonstrates why plausible calendar values and a clear power-fail flag
cannot certify retained time.

Explicit recovery requested `2026-10-07T02:00:26.700740+00:00`. SET returned
success with flags `$35`: start requested, calendar in range, backup enabled,
and continuity unknown, while oscillator-running was not yet asserted. The
next READ reported flags `$37`, but its seconds still matched the first SET
snapshot. Later read-only samples advanced from 02:01:45 to 02:01:46 UTC.
Recovery therefore passed after observing actual progression, rather than
assuming immediate oscillator startup from SET success alone.

Control had reset from the pre-loss `$C3` to `$80`; recovery preserved the
observed `$80` and trim `$00`, without silently restoring old output settings.
The service's SET success means the accepted write sequence completed; callers
must separately verify a running, advancing clock. The qualification tool now
allows at most ten 1.2-second follow-up intervals and refuses completion if the
clock does not become usable and advance within that bound.

The updated verifier passed a live UTC SET at
`2026-10-07T02:02:55.233288+00:00`, followed by an advancing successful READ and
successful calls in all four overlays. Evidence is in
`2205/total-power-loss-final-utc`; the audit includes its report hash.

Evidence is under `2205/total-power-loss-read`, `2205/total-power-loss-recovery`,
and `2205/total-power-loss-running`. `2205/total-power-loss-audit.json` binds the
reports and validates rejection, explicit recovery, progression, restored backup
enable, and complete flash preservation. `2205/post-total-power-loss-flash`
contains all four final bank readbacks and independent repeats, each matching
the original backup byte-for-byte. SRAM/EEPROM contents were not read or tested;
2512 was untouched.

## W65C816SXB emulation follow up on 2609

The user confirmed 2609 was ready with its EDU fitted. COM8 enumerated with
FTDI serial `A10MPQXCA`; the monitor reported CPU `$16`, `RA` format 1/count 13,
and `STR8-N 2.0b4 B3 65C816`. Before RAM execution, all four flash banks were
backed up and independently read again with byte-exact comparisons. The combined
131,072-byte original flash SHA256 is
`80fa68ed86927a9e689702584b638385e89be4d5fd422a386fbc3d3bfe7bab22`.

An 816-only fixture at `$2400` captured the actual G entry state:
`E=1`, stacked P `$B4`, `DBR=PBR=D=0`, and stack `$01FF`. It briefly changes E
to measure its incoming value and restores canonical emulation state before
HOLD; it makes no RTC calls in native mode. Its corrected 61-byte image SHA256
is `5b3ece35fc3fcb50bcc31cae77681e58c1af955549988e84fca080a688b8a71f`.
The first fixture used misplaced assembler width directives and generated
16-bit immediates for an 8-bit execution context; that capture is rejected.
The corrected build places the directives after CODE and validates every linked
instruction byte before publishing a runnable image. Only the corrected
`entry-state-corrected` report establishes the entry-state result.

The same RTC service and client hashes listed above were loaded and verified
before execution. Missing-service discovery returned safely. Initial read-only
calls returned `$04`, flags `$24`, and raw
`00 00 00 01 01 01 01 80 00`: responding hardware with a stopped/default-like
clock. Every bank overlay returned the same error without changing bank selection.

Explicit UTC SET requested `2026-10-07T02:09:40.206419+00:00`. SET returned
`$00`, flags `$35`; the bounded follow-up READ advanced to 02:09:41 with flags
`$37`, establishing a running clock and enabled backup. Control `$80` and trim
`$00` were preserved. Explicit ACK also returned success and retained weekday
and backup enable. No event was latched for this 816 ACK run; fresh-event
acknowledgment was separately demonstrated on 2205.

All four bank overlays subsequently returned `$00` while preserving selection.
VIA DDRA and driven output levels were unchanged across calls. No native-mode
RTC calls, alarm operations, SRAM/EEPROM access, or flash writes were issued.
Complete final flash readbacks and independent repeats matched every original
bank byte-for-byte. A ZIP containing the verified full backup was also checked
against the original bank BINs.
The physical main-power-cycle follow-up below qualifies retention and a fresh
event on 2609. The user declined battery-removal testing on 2609 and directed
that the same behavior as 2205 be assumed. That is an accepted design assumption,
not a measured 2609 battery-removal result.

Evidence is under `output/qualification/rtc-phase1-2026-10-06/2609/`, including
`full-backup`, `entry-state-corrected`, `read-only`, `set-utc-and-ack`, and
`post-test-flash`. The final audit compares every original/repeat/final bank BIN
and binds the RTC/state reports; its file is `final-audit.json`, and the backup
archive is `board-2609-full-flash-backup.zip`. Owner-local raw firmware remains excluded from
Git and release artifacts.

## Main power outage follow up on 2609

The user confirmed the requested main-power cycle with the CR2032 left fitted.
After reconnecting COM8, the unchanged service/client images were reloaded and
verified. No clock setting was issued in this follow-up.

READ returned `$00`, flags `$3F`, and raw
`C4 14 02 3B 07 10 26 80 00`: 2026-10-07 02:14:44 UTC. The repeated READ
advanced to 02:14:45, with identical latched outage bytes
`12 02 07 70 13 02 07 70`. Those fields report power-down at 02:12 and power-up
at 02:13, date 07/month 10. They contain no year or seconds, so they do not
establish an exact outage duration. Read-only calls preserved the hardware flag,
timestamps, and captured evidence.

After archiving that evidence, explicit ACK returned `$00`, flags `$37`.
Hardware outage fields were cleared, while the valid RAM capture retained all
eight original bytes. Weekday, backup enable, control `$80`, and trim `$00`
were preserved. Successful READs continued under all four bank overlays, with
bank selection and VIA DDRA/driven outputs unchanged.

The expected total-power-loss behavior on 2609 is adopted from the measured
2205 result by user direction: lost/unusable clock state must be rejected,
outage evidence may be lost, and explicit clock setting is required for recovery.
No battery was removed for this 2609 run, and no SRAM/EEPROM contents were tested.
Battery health and remaining life are not certified by retention during this
reported outage.

Evidence is under the 2609 root in `power-cycle-read`, `power-cycle-ack`, and
`power-cycle-audit.json`. Final four-bank readbacks and independent repeats are
in `post-power-cycle-flash`; the audit compares them with the original full backup.
2512 and 2205 were not accessed during this follow-up.
