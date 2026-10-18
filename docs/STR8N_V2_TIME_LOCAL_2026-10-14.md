> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Unflashed local-only TIME candidate — October 14, 2026

`BUILD/v2-time-local` is an asset-only candidate based on the qualified beta24
generation 35 FIFO-drain build. No boards are accessed or flashed by its build
or instruction-model tests.

At the monitor, TIME emits one local date/time line with the saved UTC offset:

```text
Fri 2026-10-09 15:11:04 (-05:00)
```

Command echo, blank-line framing and the monitor prompt are unchanged. TIME
makes a read-only RTC snapshot directly, then invokes the local formatter.
It no longer prints the separate UTC timestamp, trim correction or other
clock details. An unavailable, stopped or invalid RTC produces a concise
unavailable message instead of formatting a stale snapshot. EDU OFF does not
access the RTC or reclaimed service RAM; corrupt assets remain boundedly
refused.

R CLOCK is byte-for-byte unchanged, including detailed UTC/local display and
STATUS, TRIM, EUI, HISTORY and OFFSET commands. Its read-only query paths remain
available; explicit setters and confirmation behavior are retained. Boot
formatting and the STR8N-006 label boundary are retained.

The sealed B2 local helper uses 1769/1790 code bytes; the status asset uses
2558/2558 code bytes. Both retain their original asset sizes and fresh CRCs.
To fit the direct-read/error-handling path, the status formatter's duplicate
EUI-unavailable label is shortened to `EUI unknown`; R CLOCK's EUI output is
unchanged. F/E recovery, both monitor slots, RTC/SPI services, MAINT and CLOCK
binaries remain unchanged. No new monitor generation or compatibility cookie
is needed for these compatible display assets.

Build and instruction-model qualification pass. Six suites cover:

- Exact one-line TIME output across eight offset/calendar cases, including
  fractional offsets, leap-day and 2099/2100 rollover; read-only preservation.
- Absent/stopped/invalid RTC, EDU OFF and corrupt assets without stale dates.
- Actual R CLOCK loading and STATUS/TRIM/EUI/HISTORY/OFFSET queries.
- Compact cold-boot layout and detailed CLOCK/EUI output.
- Existing local-time/setup regressions, including all 13 interrupted offset
  append checkpoints and the additional setup/sequence-exhaustion checks.
- STR8N-006 named/unnamed power-fail output and MAINT flash/SRAM transfers.

Build tool: `tools/build_v2_time_local.py`. Targeted tests:
`tools/test_v2_time_local.py`. `qualification-summary.json` binds the six
receipts and sealed asset hashes; previews are also in the candidate directory.
Hardware testing and flashing were explicitly excluded and were not performed.
