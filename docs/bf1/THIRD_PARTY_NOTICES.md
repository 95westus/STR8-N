> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

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
for onboard ASM; the readable source is also provided. Its existing ASM 0.4
example needs a current bf1/ASM 0.5 qualification before final release claims.

Repository audit copies: license (owner-local/repository reference: `../../BUILD/microchess-asm04/LICENSE.txt`)
and source/port notes (owner-local/repository reference: `../../BUILD/microchess-asm04/README.md`). The release
must copy the complete notice into the package; a repository link alone does
not satisfy the binary redistribution condition.
