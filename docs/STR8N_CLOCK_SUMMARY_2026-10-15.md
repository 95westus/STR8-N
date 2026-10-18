> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# CLOCK 1.7 summary display

The owner requested the compact CLOCK layout and installation on 2609 only.
`tools/build_v2_clock_summary.py` builds the separate
`BUILD/v2-clock-summary` package from the installed boot-dialog baseline.

The opening screen now shows the saved board name, local and UTC time with
weekdays, fixed display offset, operating flags, power-fail state and EUI.
Matching current/remembered identities occupy one line. A mismatch displays
both values explicitly. A latched outage displays its down/up times in UTC
without saving or acknowledging it. Stopped or invalid time is not rendered
as a current timestamp. EDU OFF keeps a usable CLOCK prompt without device I/O.

The opening footer lists TIME, STATUS, HISTORY, HELP and Q. HELP holds command
syntax, aliases, ranges and confirmation requirements. TIME prints local and
UTC timestamps; STATUS retains detailed flags, trim, identity and raw
registers. Saved history and captured-outage labels explicitly identify UTC.
SET, ACK, OFFSET, TRIM, identity acceptance and history-clear logic retain
their original confirmations and behavior.

CLOCK is now version 1.7, 10,203 bytes at $2000-$47DA. Its SR record still fits
the existing three-sector allocation B1:B000-DFFF. No monitor-generation or
ABI change is needed. The boot dialog, display assets, RTC services, recovery
and other saved programs are unchanged.

`tools/test_v2_clock_summary.py` verifies the exact compact display and
read-only queries, full HELP, invalid/canceled changes, EUI mismatch and
canceled acceptance, latched UTC outage/canceled ACK, confirmed OFFSET/TRIM,
stopped-clock warnings and EDU OFF. The backup-bound installer and actual
saved-program loading are separately rehearsed against the planned image.

Deployment uses `tools/deploy_v2_clock_summary.py` and USB identity A10MPQXCA
for 2609. Fresh complete flash reads are compared twice before planning.
Only B1:B/C/D and B3:C (wear journal) are updated. CLOCK's header is committed
last after complete payload verification. Saved configuration values remain
unchanged. The installer halts for physical RESET.

Evidence directory:
`output/qualification/clock-summary-2609-2026-10-15/`.
Installation on 2609 completed successfully. After the owner pressed physical
RESET, all four banks (131,072 bytes) matched the planned image exactly. Live
R CLOCK showed CLOCK 1.7, Board 2609, aligned local/UTC time, fixed -05:00
offset, operating flags, no latched outage and EUI <owner-local board EUI> matching
the remembered identity. HELP, TIME, STATUS and HISTORY passed read-only
physical checks. The tool returned to B3 and closed COM8. No other board was
opened or flashed.

The prior boot-dialog changes remain byte-identical. B0 and B2 are unchanged;
B1 differs only within CLOCK's three-sector allocation, and B3 differs only
in its configuration/wear journal. Configuration values are unchanged.
See `upgrade/clock-summary.txt`, `upgrade/post-reset-report.json` and the
four `upgrade/post-reset-b*.bin` readbacks in the evidence directory.
