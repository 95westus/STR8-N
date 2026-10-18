> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# STR8N-006 fixed, flashed and retested — October 14, 2026

STR8N-006 is closed on physical 2604 (COM5, A10MQGVHA) and 2609 (COM8,
A10MPQXCA). Both run beta24 generation 33 with the fixed sealed local-display
helper. The name now starts on its own line after either power-fail message:

```text
RTCC: PF logging failed.
Board: LAB-2604

RTCC: PF logged, ACK
Board: LAB-2609
```

The fix adds a cold-entry CRLF only when a valid nonempty name exists. Unnamed
boot output and ordinary quiet returns are preserved. Helper code occupies
1760 of 1790 available bytes; the CRC-sealed asset remains 1792 bytes at B2:E.
Its SHA256 is
`d6ffa85417799b9060eba3d65058f6432f914f3ac8e9fbb0da326733332a6281`.
The original candidate remains in `BUILD/v2-board-name`; the fixed candidate
is isolated in `BUILD/v2-board-name-fix006`. Other firmware/storage artifacts
and fixed E/F recovery are byte-identical. The normal monitor still identifies
itself as beta24 generation 33.

| Check | Result |
| --- | --- |
| Targeted PF-success/PF-failure, named/unnamed models | PASS; original image reproduces failure |
| NAME, compact boot and timezone models | PASS, including 20 NAME and 13 TZ interrupted-write checkpoints |
| Fresh complete flash backups, independently read twice | PASS, both boards |
| Exact-backup installer rehearsal and stale/corrupt refusal | PASS, both boards |
| Hardware installer RAM readback and device flash verification | PASS, both boards |
| Captured physical power-on label boundaries | PASS, both boards; complete version headers captured |
| Full 128 KiB SRAM before/after power comparison | PASS, both boards |
| Named EDU OFF/ON cold startup | PASS, both boards |
| Exact final flash and original-name restoration | PASS, both boards |
| Final B/A startup, NAME query and RTC trim/control | PASS, both boards |

Only B3:C wear metadata and B2:E were erased/programmed by each installer,
with the two erase attempts accounted. Configuration selection, generation,
saved EDU profile, other flash records, identity/timezone/name tail and fixed
recovery were preserved. Testing appended two temporary-name records and two
EDU configuration records per board, without further erases.

Final state: 2604's pre-test name `2604` is restored; 2609 is unnamed as before.
Both retain EDU ON. Trims remain 2604 −12 and 2609 −14, with original control
registers, offsets and identities. All SRAM bytes match the fresh references.
2604's foreign EEPROM layout/history is unchanged and its previously latched
outage timestamps remain retained. 2609 committed/acknowledged exactly one
new next-sequence outage record; other slots and factory/status bytes are
unchanged. No explicit UTC SET, trim/offset setter, history administration,
identity acceptance or SRAM formatting was performed.

APPS remains the separate STR8N-004 exception. This scoped repair does not
claim a new extended soak, repeat physical NMI/native qualification, or close
F-only bootstrap. The startup-dot delay is unchanged; ESC skipping would be
a separate fixed-recovery-core change retaining the A/B/recovery menu and
slot-validation rules.

Owner-local backups, plans, model receipts and physical transcripts:
`output/qualification/fix006-2026-10-14/{2604,2609}`. Tools:
`build_v2_fix006.py`, `deploy_v2_fix006.py`, `test_v2_board_name_power_fail.py`
and `retest_v2_fix006.py` under `tools/`.
