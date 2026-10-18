# uChess / Microchess source for rc1 ASM 0.5

Microchess is Copyright 1976–2005 Peter Jennings, www.benlo.com.
Daryl Rictor added the serial chessboard interface in August 2002; Bill
Forster corrected OCR errors in August 2005. The full original conditions and
disclaimer are in [LICENSE.txt](LICENSE.txt) and the credited original source
is retained in `Microchess6502-upstream.txt`.

`uchess.a` is the paste-ready compact source for the included rc1 ASM 0.5.
It is byte-identical to `microchess.asm`, originally adapted for ASM 0.4.
`microchess-readable.asm` is the descriptive reference source, and
`symbols.json` maps descriptive to compact names. Use the compact source
inside the board's limited source buffer. The assembled executable is 1,439
bytes at $0200–$079E; entry $0200. The game uses public PUTC/GETC/HOLD calls;
normal 65C816 runtime is emulation mode.

Follow [the complete ASM session and S/T/R walkthrough](../docs/UCHESS_ASM_SESSION.md).
It demonstrates source PASTE/assembly and stores the compiled game as UCHDEMO,
preserving the supplied UCHESS. Source assembly and Store/Table/Restore were
executed with the actual rc1 MON A and MON B instructions in the W65C02 model;
no physical board was opened. Keep this source, all notices and full license
together when redistributing. Peter Jennings's license remains applicable;
the repository license does not replace it.
