# Board marked 2512: read-only bank identity check

Date: 2026-09-24. The operator identified the currently attached board as
marked `2512` and said it may be at a different stage from the earlier
qualification session. COM4 reported FTDI adapter serial `A10MQFLCA` at
115200 baud; the active monitor prompt was `B1>`. The adapter identity and
printed marking do not independently establish a board's firmware contents.

Using the monitor's read-only commands, the session selected `B0`, displayed
`$8000-$FFFF`, then restored `B1`. The capture has 2048 consecutive 16-byte
rows, exactly 32768 bytes with no gaps or repeated addresses. The reconstructed
Bank 0 SHA-256 is
`2f0000c74eceec809a814e31f822702977d7bfed5ee6f3bc4869627864ca59a8`.
It matches the retained WDCMONv2 Bank 0 image in the
[factory migration board test](STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md)
and the [board 2512 readback](STR8N_V2_ALPHA19_2512_BOARD_TEST_2026-09-24.md).
The Bank 0 RESET vector is `$F818`, consistent with that complete image match.

An initial full Bank 1 readback also yielded 2048 consecutive rows. Its E-F
SHA-256 is `faca0cd331ec55f03d72703b43bfd902ee9b1cb7a4a876530068a9690d128dce`:
it differs from the frozen alpha19 E-F BIN and matches the local rebuilt
`BUILD/v2-alpha19/str8n-v2-alpha19-e000-ffff.bin`. The whole Bank 1 SHA-256 is
`c0e03b2e8746501b4abb6ca70eb454c8f1382f50b5a82d671881555c1f52eb45`.
That rebuilt image is outside the frozen alpha19 identity, so this preflight
does not extend frozen alpha19 hardware qualification.

This establishes that the attached board's Bank 0 still contains the known
WDCMONv2 image. Banks 2-3 and WDCMONv2 boot behavior were not checked. No
flash was written. The session ended at `B1>`.

The owner-local serial capture and reconstructed readback are retained under
`output/qualification/` as `new-board-b0-dump-2026-09-24.txt` and
`new-board-b0-readback-2026-09-24.bin`, `new-board-b0-full-2026-09-24.jsonl`,
and `attached-2512-b1-readback-2026-09-24.bin`.
