# uChess: an ASM 0.5 source session and S/T/R example

Use the full rc1 system with ASM 0.5 installed. The paste-ready source is
[`uchess.a`](../uchess-source/uchess.a); it is byte-identical to the qualified
compact `microchess.asm`. Keep [the full license](../uchess-source/LICENSE.txt)
with it. Microchess is Copyright 1976–2005 Peter Jennings; Daryl Rictor added
the serial chessboard interface and Bill Forster corrected OCR errors.

This worked session was executed using the actual published rc1 instructions
in the W65C02 CPU model, with MON A and MON B. It opens no physical board port.
Use an idle board and save any existing application RAM before trying it.

## 1. Open an ASM source session

At the monitor (`B3>`), enter:

```text
ASM
```

At `ASM>`, enter:

```text
NEW
PASTE
```

Wait for the paste message. Send `uchess-source/uchess.a` as **ordinary text**
using the terminal's normal text/line pacing. After the file has finished, type
a line containing only a period:

```text
.
```

The `.a` file is assembler source. Use ASM's `PASTE` session for it; the
monitor's `L` command expects S-records. The readable source is provided for
reference; use the compact `uchess.a` within the on-board source buffer.

## 2. Assemble and return to the monitor

At `ASM>`:

```text
ASM
```

Expected result:

```text
OK 1439 bytes, origin $0200, buffer $0200
```

`LIST` can inspect the editor source; `DUMP` inspects output; `S19` exports
the successfully assembled bytes. Return to the monitor with:

```text
QUIT
```

The executable occupies RAM `$0200–$079E`, inclusive, with entry `$0200`.

## 3. S — store the assembled game in an erased flash extent

First list bank 1:

```text
T 1
```

The complete rc1 image already contains `UCHESS`. This example uses the new
name **UCHDEMO** so it preserves that supplied copy. If UCHDEMO already exists,
choose a different unused name in every command below.

```text
S 1 AUTO 0200 079E UCHDEMO
```

Expected success includes `Done`. The arguments are bank, automatically
selected erased flash space, RAM start, inclusive RAM end and record name.
`AUTO` finds a sufficiently large erased extent; its address depends on the
current contents. It refuses if no admissible extent exists. This is a flash
programming operation. It does not authorize erasing an occupied sector.

## 4. T — table the stored program

```text
T 1
```

The listing should contain both the supplied `UCHESS` and the new `UCHDEMO`
record, with RAM range `0200–079E` for the game. The stored record occupies
1,463 bytes: a 24-byte header plus 1,439 executable bytes.

## 5. R — restore without executing, then run

```text
R 1 UCHDEMO L
D 0200 020F
G 0200
```

The final `L` requests load-only restoration. `D` lets you inspect the restored
RAM; `G` starts it at `$0200`. The copyright and chessboard should appear.
Press **Q as one keystroke, without Enter**, to return through HOLD to `B3>`.

To restore and run in one command instead:

```text
R 1 UCHDEMO
```

Again, Q returns to the monitor. The model qualification exercised both forms.

### Optional proof that R replaced changed RAM

Before executing the game, change just its first RAM byte and reload it:

```text
M 0200 EA
R 1 UCHDEMO L
D 0200 020F
```

The restored first byte is `$78` (`SEI`). The qualification compared all 1,439
restored bytes with the assembled executable, not just the first byte. Run
the restored copy after the load succeeds; do not execute the modified copy.
`M` changes RAM; `F` is a different command that writes flash.

## What is saved

S/T/R stores and restores the assembled executable and its constant tables.
Keep `uchess.a` on the host for subsequent editing/PASTE sessions. Launching
the game initializes a new position; this stored executable is not an editor
session or a saved mid-game position.

The tested session preserved the original bundled UCHESS, all flash outside
the new erased record extent, RTC, EEPROM and external SRAM. No flash erases
were required. Those are CPU-model results; the current board soaks and RTC
sampling remain stopped. Native 816 applications, ACIA and crypto remain
deferred; normal 65C816 rc1 applications use emulation mode.

See [ASM guide](ASM_GUIDE.md), [S/R/T command reference](COMMAND_REFERENCE.md),
[firmware contents](FIRMWARE_CONTENTS.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
