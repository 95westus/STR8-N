# Third-party attribution

## uChess / Microchess

Microchess Copyright 1976 Peter Jennings, benlo.com. The preserved upstream
notice is **Kim-1 MicroChess (c) 1976–2005 Peter Jennings, www.benlo.com**.
Daryl Rictor added the serial chessboard interface in August 2002; Bill
Forster corrected OCR errors in August 2005.

The STR8-N adaptation moves working variables and replaces direct serial
hardware access with the public RAM ABI. It does not claim authorship of the
original engine. Keep the complete upstream redistribution conditions and
disclaimer with both source and executable distributions. The project license
does not replace that notice.

The uChess source bundle must include `microchess.asm`,
`microchess-readable.asm`, `symbols.json`, `Microchess6502-upstream.txt`, the
complete `LICENSE.txt`, and its credited README. The compact source is intended
for onboard ASM; the readable source is also provided. The compact source was assembled with the actual rc1 ASM 0.5 instructions
and exercised through S/T/R and gameplay under both MON A and MON B in the
W65C02 model. The session preserves the supplied UCHESS and creates UCHDEMO;
no fresh physical board execution is claimed.

Repository audit copies: [license](../../release/rc1-uchess/LICENSE.txt)
and [source/port notes](../../release/rc1-uchess/README.md). The release
must copy the complete notice into the package; a repository link alone does
not satisfy the binary redistribution condition.
