# STR8-N 2.0a21 candidate freeze

Date: 2026-09-24. Alpha21 is a new candidate following the
[alpha20 board result](STR8N_V2_ALPHA20_2512_INSTALL_2026-09-24.md).
Alpha20's delayed banner was still missed after a cold USB power cycle. The
capture does not prove why; one plausible cause is that alpha20 sampled PWE#
before the host configured FT245 and latched the ACIA before its delay.

Alpha21 runs a counted reset-only delay **before** `CON_INIT` samples PWE#.
The linked 160 by 256 by 256 loop takes approximately 6.58 seconds at the
nominal 8 MHz clock. Software HOLD skips the delay. Cold ACIA startup also
waits, because console selection happens after the delay. This tradeoff is
intentional and must be checked on hardware.

The public ROM/RAM entry addresses, signature, configuration format, command
set, and vector area are unchanged. The RAM worker uses 765 of 768 bytes at
`$7900-$7BFF`. The resident ends below `$FF20`, retaining the 192-byte
`$FF20-$FFDF` erased expansion tail established by alpha20.

`make v2-check` passed all eight host suites. The CPU model fast-forwards the
side-effect-free counter after asserting that the console remains unselected;
it checks both FT245 and ACIA paths. The exact source, artifacts, host log,
and SHA-256 hashes are retained under
`output/qualification/v2-alpha21-2026-09-24/` and listed in the
[manifest](STR8N_V2_ALPHA21_FREEZE.json).

Board 2512 still contains alpha20 with an exact alpha19 top-sector recovery
copy in Bank 2 F. Alpha21 has not been flashed or physically tested. Cold USB
banner capture, ACIA receive/fallback, W65C816 hardware, and the other open
qualification gates remain pending.

## Post-freeze status

The statements above record the state **at freeze time**. Alpha21 was later
installed and read back exactly on board 2512; cold USB banner capture and
configured Bank 1 handoff passed. See the [board report](STR8N_V2_ALPHA21_2512_INSTALL_2026-09-24.md)
and the scoped [2.0 RC1 decision](STR8N_V2_RC1_2026-09-24.md). The frozen
source snapshot and artifact hashes were not changed.
