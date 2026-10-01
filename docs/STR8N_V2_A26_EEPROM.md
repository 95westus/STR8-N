# Alpha26 EEPROM settings candidate

Alpha26 moves autostart settings from flash to the MCP79411 EEPROM on the
EDU board. Additional EEPROM uses are deferred. The settings reader works
independently of the RTC calendar/oscillator test. A stopped clock can therefore
report EDU INCONCLUSIVE while EEPROM settings remain valid.

## Display

```text
STR8-N 2.0a26 B3 65C02
ABI 65C02 | 816E | 816N-VEC
EDU KIT       DETECTED
  RTC         Wed 26-09-30 18:40:16
  EEPROM      VALID
    AUTOSTART ENABLED
    TARGET    B0 RESET VECTOR
    DELAY     1.0 SEC
B3>
```

The startup display uses aligned Option 1 labels. Fixed entries display as
`B0 $C000`. Disabled autostart still displays its saved target and delay.
The `C` command retains its compact numeric display and existing input syntax:
`C 0|1 bank address|V delay`, with numeric arguments in hexadecimal.

| EEPROM state | Meaning | Settings display |
| --- | --- | --- |
| VALID | Two usable copies, or one usable copy and one erased slot | Saved fields |
| RECOVERED | One usable copy; the other contains invalid/incomplete data | Surviving fields |
| EMPTY | Both slots entirely `$FF` | SETTINGS NONE |
| INVALID | No usable copy, or conflicting/ambiguous generations | SETTINGS NO VALID COPY |
| UNAVAILABLE | Bus/device read failed | SETTINGS UNREADABLE |

With no usable settings, autostart stays off. Boot and display perform no
EEPROM writes. The existing FT245-only console readiness behavior is retained.
An absent/incompatible E extension prevents configuration access and autostart;
it does not prevent entering the monitor. No automatic migration from flash
or automatic repair writes occur.

## EEPROM record

The MCP EEPROM uses I2C address `$57` (`$AE/$AF` control bytes). Records A and
B occupy `$00-$0B` and `$0C-$17`; `$18-$7F` remains unused. The protected
EEPROM/EUI area, RTC registers, and battery-backed SRAM are not written.

| Offset | Bytes | Field |
| --- | ---: | --- |
| +0 | 1 | `$A1`: committed format 1; zero while updating |
| +1 | 1 | Generation, modulo 256 |
| +2 | 1 | Autostart enable, 0/1 |
| +3 | 1 | Bank, 0-3 |
| +4..5 | 2 | Fixed entry, little endian; zero for vector mode |
| +6 | 1 | Delay, `$0A-$FF` tenths of a second |
| +7 | 1 | Mode: 0 fixed address, 1 current RESET vector |
| +8..9 | 2 | Reserved, zero |
| +10..11 | 2 | Two accumulated sums over +1..9 |

Start both sums at zero. For each covered byte, add it to sum 1, then add
sum 1 to sum 2, each modulo 256. Validation also checks the commit marker,
reserved bytes, field ranges, and the existing fixed-entry address policy.
This is the same checksum algorithm as the previous flash configuration,
applied to the compact EEPROM record. It detects accidental corruption;
it is not authentication or a guarantee against every possible corruption.

When both copies validate, a generation difference of 1-127 selects the newer
copy, including 255-to-0 wrap. Equal generations require identical records;
an exact difference of 128 is ambiguous. Conflicts disable autostart.

Confirmed changes target the older/invalid slot. The writer invalidates and
reads back its marker, writes the payload/checksum, reads and validates the
payload against the requested settings, then commits the marker last and
validates again. The other slot is untouched. Each changed save uses 13 byte
writes with bounded acknowledge polling; an unchanged save uses none.
The first save creates A; a subsequent changed save creates B. An interrupted
first save can leave no settings; interrupted later saves retain the prior copy.

## Flash and RAM layout

| B3 CPU range | Bytes | Use |
| --- | ---: | --- |
| `$E000-$E663` | 1,636 | RTC/status and EEPROM access/validation/save |
| `$E664-$E7FF` | 412 | Free |
| `$E800-$ECB7` | 1,208 | S/R/T extension, fixed entry table retained |
| `$ECB8-$ECFF` | 72 | Free |
| `$ED00-$EEB7` | 440 | EEPROM status/settings display |
| `$EEB8-$EFFF` | 328 | Free, including the former configuration pocket |

**B3:E has 812 free bytes.** `$EFF0-$EFFF` has no configuration meaning or
reservation in a26. `I` no longer skips those bytes when installing a legal
target sector. B3:E remains protected as executable extension storage by the
existing `F`/`I` policy; freeing its last 16 bytes does not remove sector protection.
F occupies 4,061 bytes through `$FFDC`, leaving three bytes before vectors.

The private `RT` descriptor advances to version 2. Its entries are startup at
`$E004`, configuration read at `$E007`, and save at `$E00A`. E/F must be installed
as a matching a26 pair. ROM/RAM public monitor entries and S/R/T entries remain
fixed. EEPROM work uses `$7D90-$7DD0`, overlapping S/R/T scratch only during
separate command phases; the existing `$7D80-$7D8F` RAM configuration remains.

## Build and validation

```text
make v2-a26-check
```

Outputs are under `BUILD/v2-alpha26`, including separate E/F BINs, dense S19,
`build.json`, `eeprom-test-results.json`, and `a26-regression.json`.
Host tests execute linked 65C02 code with an EEPROM transaction model, cover
checksum corruption, field validation, generation ordering, write protection,
interruption at each write boundary, restart, unchanged saves, command
confirmation/cancellation, USB/headless autostart and hold, and Option 1 output.
RTC checks retain calendar/weekday, 12/24-hour, stopped/NACK/stuck-bus coverage.
Shared regressions cover monitor, load, flash, public ABI, interrupts and S/R/T.

Board 2205 with EDU passed guarded E/F installation, exact host flash readback,
EEPROM saves and recovery, autostart hold/handoff, and physical RESET with saved
settings; see the [2205 record](STR8N_V2_A26_2205_INSTALL_2026-09-30.md).
Battery removal and complete power loss remain untested. Board 2609 passed a
guarded installation and software reentry without an EDU or host flash readback;
see the [2609 record](STR8N_V2_A26_2609_INSTALL_2026-09-30.md). Its no-EEPROM
startup keeps autostart off. No automatic flash-setting migration occurs.
Board 2512 also passed a guarded installation, exact E/F host readback, and
software reentry without an EDU; see the
[2512 record](STR8N_V2_A26_2512_INSTALL_2026-09-30.md).
