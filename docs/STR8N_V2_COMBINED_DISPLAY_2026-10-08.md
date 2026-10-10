# Combined beta20 display update for October 9 at 1 a.m. Central

This candidate combines boot/TIME trim correction reporting, quiet monitor
returns after M1 and applications, and three-letter UTC weekday labels:

```text
RTCC: UTC Fri 2026-10-09 02:55:20
```

`BUILD/v2-combined-display` is built with `tools/build_v2_combined_display.py`.
The 2,560-byte checked status asset contains 2,527 code/table/state bytes.
Its fixed private weekday trampoline at `$6E07` is called only by the
paired RTC banner after a successful validated READ. The RTC API numbers
Monday=1 through Sunday=7. The formatter uses the decoded RTC weekday and
does not write the clock. Dates and weekdays continue to describe UTC.
Both monitor slots use 3,967 of 3,968 payload bytes.

The weekday call moves shared SPI helper addresses by three bytes. Sector 9
is relinked with those addresses and sealed; its complete identity tail is
merged from each board's verified preimage. The RTC provider, fixed recovery,
saved utilities, B0/B1 and all saved program records are retained. No SRAM
format, UTC SET, trim adjustment or EEPROM operation occurs during flashing.

The board-specific plans under
`output/qualification/combined-display-2026-10-08/{2512,2205,2609}` start
from the same repeated beta17 backups as the superseded beta18 schedule.
They write B3:C, B2:D/C, B3:8/9/E/B/A in that order, including wear accounting.
The RAM installer verifies every preimage and staged payload, halts on any
failure, and finishes awaiting physical RESET. No automatic retry is allowed.
Current serial ports must be resolved by the known board USB serial numbers.

The combined candidate audit requires passing quiet-return, weekday, trim,
kernel, banner, EEPROM-journal and resident SPI models. Per-board installer
models verify exact final four-bank images, sector order, stale-preimage
refusal and corrupt-payload refusal. The schedule manifest pins candidate
metadata, candidate audit, installer plans/model reports, all preimage/final
hashes and execution/verification script hashes.

The existing one-time automation is updated only after these checks pass.
Its 1 a.m. America/Chicago time, October 9 date, target chat, reset requirement,
notification policy and separate drift schedules are retained. Hardware
verification after physical RESET uses the final four-bank image, TIME's
weekday/trim output and M1's quiet return. Board 2512 has EDU OFF and reports
RTCC unavailable. Read-only checks do not SET UTC or adjust trim.
