# STR8-N 2.0a22 quickstart

This guide is for the **dot-enabled 2.0a22 Bank 3 E/F pair** on the
W65C02SXB with EDU Kit. It is a board-tested candidate, not a general release.
The older [RC1 guide](STR8N_V2_RC1_GETTING_STARTED_816.md) covers a different
image. For command details see the [operator's guide](STR8N_V2_A22_OPERATORS_GUIDE.md);
for addresses and application calls see the
[technical manual](STR8N_V2_A22_TECHNICAL_MANUAL.md).

## Connect and identify

1. Connect the board's FT245 USB console and open its COM port at 115200 baud.
   COM3 was the port on the tested board; use the port assigned to yours.
2. Power on or press RESET. With autostart disabled, wait for the dots, banner,
   and `B3>` prompt. With autostart enabled, the configured hold window runs
   before guest handoff. Dots appear only while the FT245 transmit path is
   ready; an absent USB host does not stop the guest from starting.
3. Enter `C` to display autostart configuration and `?` for command help.
   A current candidate reports `STR8-N 2.0a22 B3 65C02` and
   `ABI 65C02 | 816E | 816N-VEC` on the tested W65C02 board.

The tested board was last left with autostart **disabled**, Bank 0 vector mode,
delay `$0A`; `C` displayed `C 00 00 V 0A`. This is a recorded board state,
not a default to assume on another board. During an enabled `$99` run, USB
power off/on produced dots and launched the Bank 0 guest without RESET.

## Inspect and boot

All addresses and byte values are hexadecimal; bank numbers are `0`-`3`.

```text
B0              select Bank 0 for monitor reads
D FFFC FFFF     inspect its vectors
J0              launch Bank 0 through its RESET vector
```

`B0` selects a bank; it does not start it. `J0` is a no-return handoff. The
monitor checks a RESET-vector address, not the integrity of the guest image.
`G 2000` similarly runs already loaded RAM code. `L` accepts RAM S19 records,
then `G` can run their entry address. `I 8000 8FFF` installs a dense,
ascending S19 stream into a complete flash sector after confirmation.

## Save, list, restore

`S`, `R`, and `T` require the Bank 3 `$E800` extension. Use `T` first to see
recognized records. A save address is **explicit**; this version does not find
space automatically. The 24-byte header and all payload bytes must fit inside
`$8000-$DFFF` of the selected bank, and **every byte in that proposed record
span must be `$FF`**. The save command performs this check before writing.

```text
T 3                         list recognized records in Bank 3
S 3 9000 2000 201F MYAPP    save 32 RAM bytes at Bank 3:$9000
T 3                         confirm a C (complete) row
R 3 9000                    copy the saved bytes back to $2000-$201F
D 2000 201F                 inspect the restored RAM
```

The `S` line is an **example**, not a verified free location: check your bank
before using it. The tested Bank 3 already has a `TEST` record at `$8FF0`, so
`S 3 8FF0 ...` returns `SR error 02` (occupied). RAM source/destination must
be within `$0200-$68FF`; the end address is inclusive. Labels are optional,
at most 16 printable non-space ASCII characters. `R` copies data but does not
run it. `T` prints `FLASH RAMSTART-RAMEND LENGTH C|P LABEL`; `P` means pending
and cannot be restored. The record has no payload checksum in a22.

## Autostart and recovery

```text
C                  show current configuration
C 1 0 V 0A         enable Bank 0 RESET-vector launch after a 1-second hold
C 0 0 V 0A         disable autostart; retain the 1-second configured delay
```

`C` previews and asks `Erase+write Y?`; review the target before typing `Y`.
Delay is hexadecimal tenths of a second, `$0A-$FF` (1.0-25.5 seconds nominal
at 8 MHz). Type `S` or Ctrl-C during an enabled hold window to stay in the
monitor **when FT245 is ready to receive**. If the host enumerates too late,
the guest still launches when the window expires. Software entry at `$F007`
holds at the monitor; `J3` uses Bank 3's RESET vector and full reset path.

The Bank 3 F sector holds the resident monitor; the E sector holds the S/R/T
extension and configuration. Treat an update to either sector as a matched
E/F firmware update. The installation and recovery sequence for this candidate
is in the [COM3 installation report](STR8N_V2_A22_COM3_INSTALL_2026-09-26.md).
