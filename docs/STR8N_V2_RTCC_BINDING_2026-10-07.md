# Remembered RTC identity and consistent messages — unflashed beta12

The owner declined ISO 8601. Calendar display remains `YYYY-MM-DD hh:mm:ss`;
healthy lines retain `UTC`. Unavailable/stopped/invalid boot and TIME messages
use `RTCC:` consistently:

```text
RTCC: EUI unavailable
RTCC: Time unavailable
```

Other time failures are `RTCC: Time stopped - use R CLOCK` and
`RTCC: Time invalid - use R CLOCK`. CLOCK errors and unavailable software also
use the RTCC prefix. Partial chip outage timestamps retain month/day and minute
precision; no year or seconds are invented.

## Boot identity states

| Situation | Identity line |
| --- | --- |
| Remembered identity matches | `RTCC: EUI 54:10:EC:B6:64:D3` |
| First use, no committed binding | `RTCC: EUI 54:10:EC:B6:64:D3, unbound` |
| Different RTC/EDU | `RTCC: EUI 54:10:EC:B6:64:AF, changed` |
| Identity unreadable | `RTCC: EUI unavailable` |

Boot reads and compares; it never adopts a new identity. Missing EDU preserves
the remembered value. A changed identity warns without stopping the monitor,
rejecting a healthy UTC read or clearing any history. Time, identity and
power-fail results remain independent. The accepted PF messages remain:

```text
RTCC: PF logged, ACK
RTCC: PF logging failed.
RTCC: PF logged, unverified ACK
```

## CLOCK 1.4

The installed version remains 1.4. The unflashed CLOCK 1.5 candidate adds
confirmed normal `TRIM` adjustments with coarse mode OFF; see
[the trim policy](STR8N_V2_TRIM_EEPROM_POLICY_2026-10-07.md). This does not change
the installed board settings or the qualification recorded here.

Both MCP79411 alarms, Alarm 0 and Alarm 1, are deferred by owner direction
(2026-10-07). CLOCK adds no alarm commands or alarm notification behavior.

STR8-N uses day-of-week (DOW) values **1 = Monday through 7 = Sunday**.
CLOCK calculates DOW automatically from the entered date when executing
`SET yyyy-mm-dd hh:mm:ss`; the user does not enter a separate weekday.
For example, 2026-10-07 is Wednesday, DOW 3. This convention also applies to
the decoded weekday returned to programs by RTC_READ. It is STR8-N's convention;
time previously set by other firmware may use different weekday numbering.

`R CLOCK` remains; there is no RTCC alias. CLOCK entry, EUI and STATUS display
the current value and its binding state. When a remembered identity exists,
CLOCK also shows `Remembered EUI: ...`, including when current hardware is
unavailable. New command `ACCEPT EUI` displays the identity and requires exact
`YES` before accepting it in flash. Cancellation writes nothing. An already
matching identity needs no confirmation or write.

Acceptance refreshes the chip identity and compares it with the value shown
before confirmation. A swapped/unreadable chip at that point is refused. Time,
ordinary EEPROM outage history, factory identity and RTC registers remain
unchanged. Users/programs remain read-only time clients; explicit CLOCK and
boot paths own clock/power-fail administration.

## Existing-sector allocation

No additional sector is allocated. Already-owned B3 sector 9 is split into:

| Region | Use |
| --- | --- |
| `$9000-$9BFF` | Verified ROM code, with CRC16 seal at `$9BFE-$9BFF` |
| `$9C00-$9FFF` | 32 append-only identity records, 32 bytes each |

The private component format is `PJ`,4,1 and banner format `BT`,3,3. Boot checks
the entire immutable code prefix before publishing its entry. Mutable identity
records have their own CRC and last-byte commit marker; they are not included
in the ROM code checksum. Public RTC/I2C entry points remain unchanged.

A record contains `EI`,1,0, a monotonic LE32 sequence, six EUI bytes, fourteen
reserved FF bytes, CRC16/CCITT-FALSE over bytes 0–27, FF and commit 00. Acceptance
uses a wholly erased slot, verifies the complete body, then programs/verifies
the commit marker. It never overwrites a programmed byte and never erases the
sector automatically. The RAM flash-byte worker performs all command writes and
polling; IRQ is masked and the RAM NMI gate holds dispatch during each write.
Worker zero page and LED state are restored afterward.

The latest committed valid identity wins. Interrupted appends are ignored and
cannot replace a prior committed value. Full storage refuses further identity
changes with `RTCC: Identity store full; no change.` A future maintenance or
firmware update can compact the same sector using a saved copy; automatic
compaction is not implemented. Boot and repeated matching acceptance cause no
flash wear.

`merge_identity_tail()` in [build_v2_rtc_binding.py](../tools/build_v2_rtc_binding.py)
preserves all tail bytes during a compatible code upgrade and refuses a corrupt
code prefix. Initial migration from older whole-sector-sealed journal formats
creates an empty identity area. Any eventual installer must use this merge
and retain its normal complete flash backups before erasing/replacing sector 9.
This preserves data in a completed update; a power cut during a whole-sector
firmware replacement still requires the saved installer/backup for recovery.

User RAM still ends at `$64FF`, inclusive, with service software installed,
even without EDU. `$6500-$66FF` remains reserved. Only absent/rejected optional
software on a cold boot can allow RAM through `$66FF`; active reservations
remain until RESET after later validation failures. No new RAM reservation is
introduced; transient binding scratch uses the existing flash-staging workspace.

## Candidate and checks

Build with `python tools/build_v2_rtc_binding.py` and
`python tools/build_v2_clock_binding.py`. Isolated outputs are
`BUILD/v2-rtc-binding` and `BUILD/v2-clock-1.4`. Monitor code remains 3967 bytes
per slot; E remains 1754 bytes; fixed F is unchanged. This candidate includes
the shorter PF messages, compact TIME command, read-only time example and EUI
display. It supersedes separate beta9/beta10/beta11 deployment.

Models cover boot comparison states, explicit acceptance, stale confirmation,
each interrupted replacement-write point, flash timeout, full storage, compatible
upgrade preservation, CLOCK history/SET safeguards, read-only TIME and existing
kernel/banner behavior. Hardware qualification remains pending; no boards were
accessed or flashed during preparation. A changed EUI also invalidates any
assumption that a previous chip's drift baseline still applies.
