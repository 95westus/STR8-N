# STR8-N alpha19 frozen artifact identity check

Date: 2026-09-24. This read-only check covered the frozen candidate in
`output/qualification/v2-alpha19-2026-09-24/candidate/` and the retained
board 2512 readbacks in `output/qualification/board-2512-2026-09-24/`.

SHA-256 of every one of the 103 files listed under `candidate_files` in the
[freeze manifest](STR8N_V2_ALPHA19_FREEZE.json) matched its recorded value;
there were no missing files. The frozen Bank 1 E-F install S19 had SHA-256
`8137d389683dc5310831618c4e14b64def185e33dd737cd95d2d72e11fb99053`,
matching the [board 2512 session](STR8N_V2_ALPHA19_2512_BOARD_TEST_2026-09-24.md).
The last 8192 bytes of both `b1-post-install.bin` and `b1-final.bin` matched
the frozen `str8n-v2-alpha19-e000-ffff.bin` byte for byte. Both board files
are 32768 bytes, covering Bank 1's `$8000-$FFFF` window.

The frozen E-F install S19 also passed the repository's `build_v2.read_s19`
parser, which checks record lengths, checksums, overlaps, and the S9 terminator.
It contains exactly 8192 data bytes at `$E000-$FFFF`, with no missing or
out-of-range addresses, and S9 entry `$F004`. Decoding its data in address order
produces the frozen E-F BIN byte for byte.

This verifies retained candidate identity and the board readbacks from that
session. It does not qualify a later build or current board state. Release
package verification and the remaining hardware matrix are still pending.
