# STR8-N 2.0a20 candidate freeze

Date: 2026-09-24. Alpha20 is a new qualification candidate derived from the
alpha19 source. Its sole intended runtime change is an approximately 4.94-second
delay before the first FT245 banner byte on reset. The delay runs from the
copied RAM worker after `CON_INIT`; it is skipped on software HOLD and when
the ACIA is selected. The delay uses only CPU registers and has no I/O writes.

The reset entry, public ROM and RAM entry addresses, signature, configuration
format, and monitor commands remain unchanged. The worker now occupies all
768 bytes at `$7900-$7BFF`. The F-sector resident ends at `$FF13`, so the
erased expansion tail is reduced from `$FF00-$FFDF` to `$FF20-$FFDF` (192
bytes). This is an explicit layout change. The vector area `$FFE0-$FFFF`
remains reserved, and the builder checks the new boundary.

`make v2-check` rebuilt the E-F and full-bank images and passed all eight host
suites. The host model fast-forwards only the counted delay after reaching its
FT245 loop. A direct execution of one outer iteration in the linked worker
measured 329,221 cycles; the complete 120-iteration loop is 39,506,639 cycles,
or approximately 4.938 seconds at 8 MHz. These checks do not prove Windows
will capture the cold-start banner on hardware.

The exact source, build outputs, host log, and hashes are retained in
`output/qualification/v2-alpha20-2026-09-24/` and identified by
[the manifest](STR8N_V2_ALPHA20_FREEZE.json). Alpha19 remains a distinct frozen
candidate. Board 2512 still contains alpha19 in Bank 3; alpha20 has not been
flashed or qualified on board. ACIA receive/fallback, W65C816 hardware,
failure/recovery, and the other open qualification gates remain pending.
