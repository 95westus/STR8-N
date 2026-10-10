# Fixed local UTC offset: unflashed beta21 candidate

Current checkpoint: beta23 generation 32 / CLOCK 1.6 is installed on all four
boards. Fractional and boundary offsets, cancellation, immediate TIME display
and J3 persistence passed hardware tests with original offsets restored;
see [four-board evidence](STR8N_V2_BETA23_FOUR_BOARD_STORAGE_2026-10-09.md).
Beta23 compact boot shows one local RTCC line. Explicit TIME/CLOCK retain
detailed UTC and local output. The beta21 design/build account below is historical.

`BUILD/v2-local-time` adds a fixed display offset with CLOCK 1.6. It is an
isolated candidate; this work opens no serial ports, flashes no boards and
does not change the existing beta20 scheduled flash or its pinned artifacts.

## User interface

```text
R CLOCK
OFFSET
OFFSET ?
OFFSET -05:00
OFFSET +05:30
```

The signed `HH:MM` format is mandatory. Bounds are -12:00 through +14:00,
with minute resolution, including half-hour and quarter-hour offsets.
An absent, corrupt, out-of-range or uncommitted setting defaults to +00:00.
Query commands show the active saved offset and explain that daylight saving
requires manual adjustment. A changed offset requires exact `YES`; cancellation
and unchanged settings write nothing. Changes apply immediately to display.

After a successful initial UTC SET, CLOCK asks for an offset when no setting
has been saved. Enter keeps +00:00. Supplying an offset uses the same confirmed
save path. The initial CLOCK display also shows the current offset and help.

Boot status, TIME and CLOCK R/TIME show local time alongside UTC:

```text
RTCC: UTC Fri 2026-10-09 02:55:20
RTCC: Local Thu 2026-10-08 21:55:20 (-05:00)
```

The formatter copies the decoded UTC snapshot and handles weekday, month,
year and leap-day rollover on its private copy. UTC remains authoritative
for the RTC, outage evidence and drift measurements. Local display supports
the boundary days in 1999 and 2100 surrounding the RTC's 2000-2099 range.
No automatic DST rules or geographical timezone database are introduced.

## Persistence and pairing

The RTC EEPROM has no spare ordinary storage and the boot configuration's
bytes are already assigned. Instead, a separate `TZ`,1,0 record shares the
existing 32-slot append-only identity tail at B3:9C00-9FFF. A record contains
a sequence, signed LE16 minute offset, CRC16 and final commit byte. Existing
EI identity records and EEPROM outage records remain independent. Older binding
scanners ignore TZ records while treating occupied slots as unavailable.
Offset changes and identity acceptance therefore share the finite slot capacity.
Full storage, sequence exhaustion and write failure refuse without an erase.
The old offset stays active until the new body is verified and committed.

The separate 1,536-byte sealed local/trim display asset is assigned
**B2:E000-E5FF**, above the AUTO allocator's existing E000 limit. A future
installer must prove that range is available; this candidate does not claim
any physical board's erased or occupied sectors. It stages at 6800-6DFF and
backs up/restores the complete 6B00-6BFF journal scratch page. CRC and header
checks precede execution. Missing/corrupt assets report `Local display
unavailable`; the monitor remains usable. EDU OFF omits local/device blocks.

The main 2,560-byte status asset remains at B2:C800-D1FF and keeps its weekday
trampoline. Normal trim math moves into the checked local asset to make room
for its loader and scratch backup. This changes the status asset and E loader
pairing but leaves the beta20 RTC component, journal code and fixed F intact.
There is no additional permanent application RAM reservation.

CLOCK 1.6 is larger than CLOCK 1.5 and needs a newly planned saved-record
allocation. The builder emits its binary and ordinary S19, but creates no
board-specific installer or flash plan. Any future deployment must pair the
firmware, both sealed display assets and the updated CLOCK saved record, prove
space for the new assets/utility and preserve the complete identity/TZ tail.

## Reproduction

```text
python tools/build_v2_local_time.py
```

Set `STR8_RTC_BUILD=BUILD/v2-local-time`, then run:

```text
python tools/test_v2_local_time.py
python tools/test_v2_local_time.py --extra
python tools/test_v2_rtc_kernel.py
python tools/test_v2_quiet_return.py
python tools/audit_v2_local_time.py
```

The local-time model checks independent calendar results, strict parsing,
confirmation/cancellation, cold/TIME/CLOCK display, reset persistence, old
identity preservation, every interrupted append checkpoint, full storage,
write timeout, corrupt asset refusal, OFF behavior and the initial SET prompt.
Tests execute linked 65C02 instructions without hardware access.

All listed suites and the final candidate audit passed. The helper uses
1,428 code/table/state bytes, the main status formatter uses 2,473 bytes, and
CLOCK 1.6 uses 8,850 bytes at 2000-4291. All 13 programmed-byte interruption
checkpoints passed; the extra suite verifies the setup prompt's confirmed
save path, normal/coarse trim output and sequence exhaustion. The pinned
beta20 build metadata and candidate-audit hashes remain unchanged.
