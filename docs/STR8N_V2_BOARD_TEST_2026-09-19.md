# STR8-N v2-alpha9 COM4 smoke test ? 2026-09-19

STR8-N 1.35 installed the validated 4096-byte alpha9 image into Bank 1,
sector F ($F000-$FFFF). Its installer reported `OK`; J1 displayed
`STR8-N 2.0a9 B1`. Only sector F was supplied as payload; the v1 installer
also maintains its own installation journal/directory. Sector E was not
included, and v2 reports `No config` for the existing configuration pocket.

Passed on the connected board:

- Exact readback of all 4096 bytes, including public entries, erased tail
  ($FCE7-$FFDF), reserved page and hardware vectors.
- D single-byte and inclusive-range display; reversed-range and I/O rejection.
- M writes, protected-address rejection, malformed-command atomic rejection
  and Ctrl-C cancellation. RAM $0200-$020F was saved and restored exactly.
- L checked S19 load/readback; G executes a RAM JMP to the F003 held entry.
- F self-edit preview and cancellation, plus sector-crossing rejection;
  I rejects mutation of the running monitor's sector F. Sector F still
  matched the image after these tests.
- C inspection; B0/B2/B3/B1 selected-bank display and resident restoration.
- J3 returns to STR8-N 1.35; subsequent J1 boots alpha9 again.

Final state: v2 Bank 1 held prompt, selected bank 1.

Local evidence (ignored build output): `BUILD/v2-alpha9/board-com4.jsonl`,
`board-smoke-results.json`, `board-bank1-f-readback.bin`, and
`board-ram-0200-before.bin`.

Sector-F readback SHA-256: `ac4c3ebb3e5f204e7abfdd44d472db0c9d67c08b3e5cc345237c6f2859bc070a`.

This is a board smoke test, not complete hardware qualification. Actual
v2 F/I/C flash mutations, physical reset, configured autostart, injected
flash failures, interrupt/NMI behavior and native 65C816 execution were not
tested here. The install exercised the v1.35 flash worker. Host regression
results remain recorded separately in the alpha9 layout milestone.
