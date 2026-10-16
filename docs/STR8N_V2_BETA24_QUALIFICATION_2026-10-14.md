# Beta24 generation 33 qualification — October 14, 2026

The original candidate results below are retained as evidence. STR8N-006 was
subsequently fixed, flashed and physically retested successfully on both
boards; see the [fix retest report](STR8N_V2_FIX006_RETEST_2026-10-14.md).

The focused automated beta24 suite passed on physical boards 2604 (COM5,
A10MQGVHA) and 2609 (COM8, A10MPQXCA). The owner confirmed physical RESET
after installation. Both complete installed flash images matched their
backup-bound beta24 deployment plans before testing. Functional and retention
checks passed; named power-on formatting exposed the open STR8N-006 defect.

| Test | 2604 | 2609 |
| --- | --- | --- |
| Complete installed 131072-byte flash comparison | PASS | PASS |
| Generation 33 A/B J3 startup | PASS | PASS |
| NAME query, whitespace/overlength rejection, NO/Y cancellation | PASS | PASS |
| Eight-character set; exact CRC/sequence/commit append readback | PASS | PASS |
| Identical-name no-op; quiet ordinary monitor return | PASS | PASS |
| Named A/B J3 retention, rename retention, clear retention | PASS | PASS |
| EDU OFF/ON activation and reclaimed 512-byte RAM read/write/restore | PASS | PASS |
| Monitor/CLOCK/EDU/SRAM/WORK/MAINT command smoke | PASS with APPS exception | PASS with APPS exception |
| RAM console ABI and actual BRK/VIA1 IRQ, vector restoration | PASS | PASS |
| RTC SRAM and external SRAM pattern write/read/verified restore | PASS | PASS |
| Exact final flash; original name and EDU mode restored | PASS | PASS |
| Power-cycle name retention and complete 128 KiB SRAM comparison | PASS | PASS |
| Board label on its own power-on line | FAIL — STR8N-006 | FAIL — STR8N-006 |
| Named EDU OFF/ON cold startup | PASS | PASS |

The isolated candidate's linked-model NAME, compact-boot, timezone and MAINT
storage-transfer suites were rerun and passed. Coverage includes malformed
records, full tail, sequence exhaustion, incompatible journal, flash timeout,
all 20 interrupted NAME writes and all 13 interrupted timezone appends.
Storage-copy refusal, corruption, short-write and timeout cases passed.
Candidate artifact hashes matched the tested build metadata.

The completed hardware runs made exactly five committed BN appends and four
configuration appends per board, without erasing flash. Both original names
were unset, and both original EDU modes were ON. Settings, wear counts,
identity/timezone records, fixed recovery and all saved program bytes were
preserved. Retained clock/history/identity checks passed; trims remain
2604 −12 and 2609 −14. Sampled RTC/external SRAM bytes were verified restored.

Power-retention preparation independently read each complete 128 KiB SRAM
array twice and verified exact equality. After the owner-confirmed main-board
power cycle, both full arrays matched the backups exactly. All four final flash
banks per board matched the expected images, with only the five NAME and four
configuration appends accounted. Temporary `LAB-2604` / `LAB-2609` names were
cleared and both original EDU ON profiles restored. Named EDU OFF startup also
passed, displaying the label without RTC/SPI services.

The first receive window expired before the owner completed the power cycle.
Queued USB output recovered afterward contains each power-fail report, retained
board label, clock line and B3 prompt; the initial version headers were not
captured. Existing full-image checks and subsequent J3 captures identify the
tested firmware. These are partial physical power-on captures, not a separate
physical RESET capture.

2604's EEPROM/history/EUI and trim/control checks passed unchanged. Its foreign
history layout remains untouched. 2609 committed and acknowledged exactly one
new valid outage record with the next sequence; other slots and factory/status
bytes were preserved. RTC calendar advanced, identity and original trim/control
were retained. No explicit SET, ACK, CLEAR-history or ACCEPT was issued.

Both power-on captures join the label directly to the preceding power-fail
message: `RTCC: PF logging failed.Board: LAB-2604` and
`RTCC: PF logged, ACKBoard: LAB-2609`. This is recorded as
[STR8N-006](issues/BETA24_BOARD_NAME_POWER_FAIL_LINE.md). No formatting repair
or replacement firmware was installed during this qualification.

APPS still exhibits the previously recorded STR8N-004 corrupt-name defect;
its correctness is excluded from the command-smoke pass. Record tables and
application launches remain functional. The known 2604 foreign EEPROM history
layout is preserved; it has not been initialized. This scoped qualification
does not close the F-only bootstrap issue, repeat physical NMI/native-vector
qualification, or claim a new extended soak or release-candidate acceptance.

Owner-local receipts, transcripts, device snapshots and exact bank images:
`output/qualification/beta24-tests-2026-10-14/retry1/{2604,2609}`.
Tools: `tools/qualify_v2_beta24.py` and `tools/qualify_v2_beta24_power.py`.
