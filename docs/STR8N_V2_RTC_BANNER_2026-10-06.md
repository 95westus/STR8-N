# Optional UTC/status monitor banner

Started 2026-10-06; hardware acceptance completed 2026-10-07 America/Chicago.
The local beta6 candidate, generation 15,
adds a single clock line beneath the ABI line when the optional RTC component
supplies a verified banner extension. The monitor becomes the first RTC client
when it prints this banner. Ordinary command prompts do not poll the clock.

```text
STR8-N 2.0b6 B3 65C816
ABI 65C02 | 816E | 816N-VEC
UTC 2026-10-07 04:29:26
B3>
```

The sample time illustrates formatting, not a new UTC synchronization.

| Condition | Banner line |
| --- | --- |
| READ succeeds with running, valid calendar | `UTC yyyy-mm-dd hh:mm:ss` |
| Clock not running | `RTC stopped - use R CLOCK` |
| Running clock with invalid calendar | `RTC time invalid - use R CLOCK` |
| No response, stuck/busy bus, timeout or unusable snapshot | `RTC unavailable` |
| Optional software missing, incompatible or corrupt | No clock line |

Each path retains the normal prompt. No RTC SET, ACK, alarm, trim, SRAM/EEPROM
or scan operation is added. Missing hardware cannot be distinguished reliably
from bus trouble by this read, so the banner does not claim that the EDU is
absent. A displayed calendar follows the boards' UTC convention; it does not
certify battery health or prior continuity. Use `R CLOCK` and S for details.
Setting stopped/invalid time remains an explicit user operation.

The line appears on startup and normal monitor reentry, including return from
CLOCK/MAINT. It is a bounded READ, with the service's existing timeout and
ownership contracts. It does not continuously update while the prompt waits.
The current [UTC drift baselines](STR8N_V2_RTC_UTC_BASELINE_2026-10-06.md)
remain unchanged.

## Placement, validation and compatibility

The 268-byte private formatter lives at B3 `$8900-$8A0B`, in unused space in
the existing optional sector 8. The common 1760-byte RTC/I2C provider and
512-byte serialized RAM gateway remain byte-identical to beta5. No additional
application RAM is reserved. A two-byte monitor-owned pointer at `$7D0F`
publishes the private banner entry `$8907` after validation.

Both monitor slots contain 3960 bytes, within their 3968-byte limit. E launcher/
kernel code occupies 1754 bytes, within its 1760-byte allocation. Compact header
validation leaves room for the private extension registration while preserving
the existing E entry addresses and full-sector seals. Fixed F remains exactly
the qualified beta4/beta5 recovery core.

The monitor clears the private pointer before verifying E. E verifies the
complete RTC sector before inspecting the `BT`,1,2 private banner header and
calling its registration entry. Code is not executed from unverified optional
bytes. A valid older beta5 component or older E leaves the pointer absent, so
the new monitor safely omits the line. Warm reentry also clears a stale pointer
before inspecting replacement E/component data. Existing SV/RG/I2 discovery,
public tables, client calling conventions and program memory limits are unchanged.
Shared results/diagnostics can be replaced by the banner READ after a program
returns through HOLD. Clients that need their own result afterward copy it into
ordinary application RAM before returning. The drift tool now uses a separate
54-byte sampling client with a private result copy at `$2440-$247F`; the timing
marker brackets that copy, not the monitor's later sample. A rollover test proves
the measured second survives a different second printed by the banner. The
original 43-byte synchronization client and its evidence are retained unchanged.

The banner runs in the monitor's supported 65C02/816-emulation profile, using
the public clock and console APIs and monitor scratch `$E0-$E1`. Native RTC
calls remain excluded. The driver preserves observed VIA state and the caller's
bank as before. Latched chip power-fail evidence is read and captured without
being acknowledged. RAM captures retain their existing lifetime: RESET can lose
them; no persistent outage journal is introduced.

## Build and checks

```text
python tools/build_v2_rtc_banner.py
python tools/test_v2_rtc_banner.py
```

The candidate is built under `BUILD/v2-rtc-banner`; the qualified beta5 outputs
under `BUILD/v2-rtc-kernel` remain untouched. Full kernel regression uses
`STR8_RTC_BUILD=BUILD/v2-rtc-banner` with `test_v2_rtc_kernel.py`.
Machine-code checks cover default/A/B boot, monitor reentry, normal prompts,
stopped/invalid time, NACK, stuck bus, power-fail preservation, headless operation,
corrupt/absent optional software, valid older components/E, stale pointers,
reserved-memory guards, RST, MAINT and unchanged legacy MAINT compatibility.

Fresh complete backups and independent repeats bind each board's update plan.
The independent RAM installer is modeled with exact four-bank images and stale-
preimage/corrupt-payload refusal before hardware execution. The normal five
sector updates are B3 C, 8, E, B, A; F, MAINT in B1, CLOCK in B2, B0 and B3
sector 9 are preserved. Journals retain settings/wear and retag accepted A/B
preferences to generation 15, preaccounting the planned erase attempts.

Both EDU boards' current RTC/status data were archived before the firmware
update and RESET. No time was set or power-fail flag cleared. Earlier RAM outage
captures remain archived in the original UTC sync records even when the live
capture has already been lost through the user's prior RESET.

| Artifact | SHA256 |
| --- | --- |
| Optional RTC/I2C/banner sector | `877105502c8879165649b465788331e65349e302e25dc8826a041da1248eec4a` |
| Slot A | `dd521a5b3aba04fffa8e1e5ef64dbc580af9f93192d63f5a31d2feffb1a77da3` |
| Slot B | `fa8e5a35922a5cef6afe0b87b0b882321b0dc2956158cc0c16bf8abc1e4a68a6` |
| E | `8674c1bc516155ca0f870bf791888c8ca3237ab9317d48397e0ae05f959a1b67` |
| Fixed F, unchanged | `be0c53e1700eb7f35daa556cd07a52f1ee037ff43bfd940d36c6e3a19bbe9962` |

Owner-local evidence is under `output/qualification/rtc-banner-2026-10-06`:
each board has repeated `prior` backups, an exact modeled `upgrade` and a
post-RESET `banner-check`. The root acceptance audit binds all artifacts,
installer results, physical RESET confirmation, both slots, CLOCK/MAINT return
paths, full final flash images, retained settings/wear and drift-report hashes.
Vendor firmware backups remain excluded from Git/release artifacts.

## Hardware acceptance

All three boards restarted and passed A/B/A slot selection, the banner after
CLOCK and MAINT return, ordinary-prompt behavior, protection guards and exact
four-bank readback. Each final image matches its modeled update. B0/B1/B2,
MAINT, CLOCK, B3 sector 9 and fixed F are preserved. Accepted settings/wear
match the plan. All ports were closed after checks and boards left at `B3>`.

| Board | Live banner |
| --- | --- |
| 2512 / COM4 / 65C02 / no EDU | `RTC unavailable` |
| 2205 / COM3 / 65C02 / EDU | Valid UTC below ABI; normal prompt usable |
| 2609 / COM8 / 65C816 / EDU | Valid UTC below ABI; normal prompt usable |

The user confirmed restarting 2205 and 2609 by power off/on. Both RTCs retained
running time and backup enable, with newly latched power-fail evidence. Their
control/trim bytes are unchanged. Read-only banner/CLOCK/MAINT checks preserve
the chip's flags and outage fields and retain the captured event across HOLD.
No SET or ACK was issued. The first check required the power-fail bit to remain
unchanged, which was too strict for a power cycle; its transcripts are retained
in `banner-check-new-powerfail`. The corrected check verifies backup enable,
refuses clearing an already-latched event, and records a newly latched event.

| Board | Raw power-down fields | Raw power-up fields |
| --- | --- | --- |
| 2205 | `03 05 07 70` | `04 05 07 70` |
| 2609 | `04 05 07 70` | `04 05 07 70` |

These fields have minute precision and no year; they do not establish an exact
outage duration. Retained time during this event does not certify battery life.
The events remain unacknowledged and archived in the owner-local records.
Original UTC sync/drift reports retain their exact hashes, so the drift baseline
has not been replaced. The private sampling client also passed live READ-only
checks on both EDU boards, preserving its result across the later banner READ.
