# Microchess: ASM 0.4 source, RAM executable and S/T/R example

Microchess Copyright 1976 Peter Jennings, benlo.com.

This STR8-N example derives from the KIM-1 Microchess source
[published by Peter Jennings](https://benlo.com/files/Microchess6502.txt),
whose notice is Copyright 1976-2005 Peter Jennings. Daryl Rictor added the
serial chessboard interface in August 2002; Bill Forster corrected OCR
errors in August 2005. The STR8-N adaptation moves working variables and
replaces direct serial hardware access with the existing public RAM ABI.

The upstream source and its complete redistribution notice/disclaimer are
preserved in `Microchess6502-upstream.txt` and [LICENSE.txt](LICENSE.txt).
Keep that notice and these credits with source and executable distributions.
The upstream license remains applicable to these files; the repository's
own copyright does not replace Peter Jennings's notice.

## Files and size

| Item | Use |
|---|---|
| `microchess.asm` | Paste-ready ASM 0.4 source: 647 lines, 7,112 packed bytes |
| `microchess-readable.asm` | Readable source with descriptive names; reference/cross-assembler input |
| `symbols.json` | Readable-name to compact-name mapping |
| Executable | 1,439 bytes, $0200-$079E, entry $0200 |
| Stored executable record | 1,463 bytes including the 24-byte S/T/R header |

ASM 0.4 has 7,168 source bytes, leaving 56 bytes free with the compact
source. Use the compact file for on-board assembly; the readable version
exceeds that source buffer. The conversion preserves instruction semantics;
the qualification compares its output byte-for-byte with an independent
WDC build of the readable source. No ASM firmware enlargement is needed.

Source/symbol/state buffers stay above $3300. The running game owns ZP
$0F-$2F (including the capture sentinel), $60-$80 and $B0-$B7, plus the
CPU stack; it avoids monitor ZP $E0-$FF and the NMI gate. The main program
initializes both chess stacks, the board and opening state at every launch.
Only public PUTC $7E6D, GETC $7E70 and HOLD $7E67 are called. Direct ACIA
initialization and register access have been removed. The game enters with
IRQ disabled and decimal mode clear. An 816 host must use emulation mode.

## Assemble and play

At the monitor:

```text
ASM
PASTE
```

Wait for the paste message. Send `microchess.asm` as ordinary text, then a
line containing just a period. At ASM>:

```text
ASM
DUMP
QUIT
```

ASM reports `OK 1439 bytes, origin $0200, buffer $0200`. At the monitor:

```text
G 0200
```

The program prints its copyright, chessboard and `?` input marker. Commands
are single keystrokes; do not append Enter to C, E, P or Q.

- P: let the computer play (its first opening move is 13 to 33).
- Enter four square digits followed by Enter to make a move, e.g. `6343`.
- C: reset the position; E: exchange sides.
- Q, Escape or Ctrl-C: return through public HOLD to the monitor.

Use the board's printed hexadecimal coordinates. This preserves the
original Microchess engine and its historical playing/command limitations;
it is not a replacement chess rules library.

## Store, Table and Restore

After Q returns to the monitor, review M1 and T 1 for available storage.
AUTO selects an erased extent without erasing an occupied sector.

```text
S 1 AUTO 0200 079E UCHESS
T 1
R 1 UCHESS L
G 0200
```

R with L loads without execution. To restore and run in one step:

```text
R 1 UCHESS
```

The qualification deliberately zeroes the RAM executable before Restore,
checks all recovered bytes, then runs the restored game. Store saves the
program and its constant tables. It does not save the ASM editor session
or the current chess position held in zero page; launching starts a new game.

## Rebuild and evidence

From the isolated beta33 worktree, with the sealed beta33 candidate and its
model dependencies present:

```text
python tools/build_microchess_asm04.py
python tools/test_microchess_asm04.py
```

The second command uses the actual linked ASM 0.4 through PASTE and ASM,
compares an independent WDC build, exercises chess commands, and verifies
S/T/R and retained-data preservation in the CPU model. Outputs are in
`BUILD/microchess-asm04/`: binary, addressed S19, workflow transcript and
qualification receipt. These commands open no serial port and do not alter
the sealed beta33 firmware or install anything on a physical board.
