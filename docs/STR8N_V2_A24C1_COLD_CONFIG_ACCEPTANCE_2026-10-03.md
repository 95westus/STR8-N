# a24c1 cold startup and configuration acceptance

Date: 2026-10-03. Tested board 2205 (W65C02SXB, COM3, FTDI A10MPUPNA)
and board 2609 (W65C816SXB, COM8, FTDI A10MPQXCA). Both began with the
exact packaged a24c1 B3:F image and erased configuration; `C` reported
`No config`. This completes beta checklist item 2 for the cases below.

| Physical-board check | 2205 | 2609 |
| --- | --- | --- |
| Save disabled configuration; `Program Y?` then `Done` | PASS | PASS |
| Full power removal/reconnection; correct CPU banner and B3 prompt | PASS | PASS |
| Disabled configuration survives cold power cycle | PASS | PASS |
| Enable autostart; `Erase+write Y?` then `Done` | PASS | PASS |
| Cold autostart to B3:$F007 with no host input | PASS | PASS |
| Enabled configuration survives cold power cycle | PASS | PASS |
| Physical RESET; S during countdown produces `Canceled` and prompt | PASS | PASS |
| Disable autostart again with verified erase/rewrite | PASS | PASS |
| Full final F readback; checksums valid; firmware/vectors preserved | PASS | PASS |

## Procedure and evidence

The saved disabled setting was `C 0 3 F007 40`; the enabled setting was
`C 1 3 F007 40`. `$F007` is the monitor HOLD entry, already executed on
both boards in the [migration/reset session](STR8N_V2_A24C1_TWO_BOARD_ACCEPTANCE_2026-10-03.md).
This tests fixed-address autostart into a known target without a reset-vector
loop. `$40` is nominally 6.4 seconds at the expected board clock.

For each of two cold cycles the owner was asked to remove all power,
including USB and any separate supply, wait ten seconds, and reconnect;
the owner confirmed completion. Captures show both COM devices becoming
unavailable, reopening, then startup dots, correct CPU banners, and `B3>`.
The cold-cycle captures contain no transmitted bytes. Post-cycle `C` queries
returned the exact disabled and enabled settings respectively.

The enabled cycle reached HOLD after the countdown with no `Canceled`
message. USB reconnection means the captured dots cover only part of the
countdown; this is behavioral acceptance, not a precise timing measurement.
For cancellation, the owner pressed physical RESET while capture was active.
The host sent one `S` on the first startup dot. Both boards printed
`Canceled` and returned to the monitor.

Evidence is owner-local under
`output/qualification/a24c1-acceptance-2026-10-03/`. Per-port files include
`-config-before.jsonl`, `-config-save.jsonl`, `-cold-disabled.jsonl`,
`-config-persist-disabled.jsonl`, `-config-enable.jsonl`,
`-cold-autostart.jsonl`, `-config-persist-enabled.jsonl`,
`-autostart-hold.jsonl`, `-config-final-save.jsonl`,
`-config-final-readback.jsonl`, and `-config-final-f.bin`.
`capture_power_cycle.py` handles USB disconnection/reopening;
`verify_config_acceptance.py` checks the recorded results and complete final
sector against the factory core, and writes `config-verification.json`.

## Final board state and limits

Both boards remain at `B3>` with autostart disabled:
`C 00 03 F007 40`. The initial erased pocket has been replaced with a valid
disabled configuration. Its exact bytes at `$FFD0-$FFDF` are:

`01 00 03 07 F0 40 00 00 00 00 00 00 00 00 3B 1F`

All bytes outside this pocket, including hardware vectors, exactly match
the factory a24c1 image. Both final 4,096-byte F sectors have SHA-256:

`9a54b2b85208887bacd3bbc8f89e3ec6f24b8e188f7e01a6fa62e85679e893fd`

This session does not qualify vector-mode/cross-bank autostart, other guest
programs, headless timing, Ctrl-C cancellation, malformed configuration,
write-failure recovery, or interrupted-write/power-loss recovery. The
broader command, ABI, interrupt, maintenance and recovery matrix remains open.
