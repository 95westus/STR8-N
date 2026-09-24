# STR8-N v2-alpha13 board test — 2026-09-23

Status: primary-console installation, W65C02 detection, direct physical ACIA
transmit, and the final four-bank migration passed on board 2205. ACIA receive
on this board and W65C816 detection remain pending.

STR8-N 1.35 in Bank 3 installed the dense alpha13 `$E000-$FFFF` image into
Bank 1 and reported `OK`. Banks 0, 2, and 3 were not written. Launching Bank 1
over the configured FT245 path produced:

```text
STR8-N 2.0a13 B1 65C02
ABI 65C02 | 816E | 816N-VEC
B1>
```

This proves the W65C02 branch of the `$FB` detector on physical hardware and
that asserted PWE# selects the primary FT245 console. Candidate hashes:

| Artifact | SHA-256 |
| --- | --- |
| Alpha13 S19 | `4A8DD24933735B04682DCBDFA74A6F27BBDD99ED952F5D6662453B6DBCBAB566` |
| Alpha13 BIN | `69B953615FC28829F48EF586B358558E36E2EADAED6C210DEC3D969707D7D09A` |

The ignored evidence log is
`BUILD/v2-alpha13/com3-2205-alpha13-session.jsonl`.

The 165-byte direct ACIA probe was subsequently loaded at `$2000` through the
FT245 console and started with `G 2000`. Its USB-to-TTL adapter was attached to
a different host PC, so it did not appear in the COM-port inventory on the
development PC. The operator confirmed the repeating 19200 8N1 banner on that
second PC. This qualifies the stock W65C51N register mapping, `$1F/$0B`
initialization, fixed-delay transmit path, adapter receive wiring, and CTS
state independently of STR8-N's PWE selection. `Q` did not return through
HOLD, so physical ACIA receive and the adapter-TX-to-board-RX path remain
unqualified. The probe was then expanded to report every received byte as
hexadecimal on FT245.

The host suites additionally cover automatic ACIA selection, S19 loading,
Ctrl-C, and the RAM-resident self-edit reset path.

## Board 2205 ACIA receive diagnosis

The expanded RAM probe confirmed ACIA transmit on the Qwiic white TXD wire.
The USB-to-TTL cable also passed its own blue-RXD-to-green-TXD loopback test.
With the cable signal wires removed, the board's white TXD was connected
directly to its yellow RXD. No received byte was reported through FT245.

The probe was then changed to issue a W65C51N programmed reset at `$7F81`
before writing control `$1F` and command `$0B`. Direct board loopback still
failed. A further diagnostic reported the stable status value `$70`:

```text
ACIA STATUS $70
```

This is DSRB high, DCDB high, TDRE set, and RDRF clear. It establishes that
the ACIA is readable and transmitting but never completes a received byte in
the direct board loopback. The archived BSO2 `02EDU.inc` independently uses
the same `$7F80-$7F83` register map. The operator reports that board 2205 may
previously have been dual-powered by connecting the adapter's red supply wire
while the board was already powered. Treat the ACIA RX input or its board
trace as suspect and repeat the same RAM probe on another stock board before
changing the STR8-N driver. The programmed reset remains a valid defensive
initialization step. It was subsequently installed as part of the final Bank 3
alpha13 image; the earlier Bank 1 test image was replaced by the preserved
R-YORS bank during migration.

After the successful boot evidence, an attempted temporary `BOARD_QUERY` RAM
probe exceeded the monitor's 32-character line limit. A following `G 0200`
therefore entered stale, partly overwritten RAM and stopped responding. The
Bank 1 flash installation had already completed and booted successfully. Press
physical RESET to return through the intact Bank 3 recovery path before the
next board session.

## Final board 2205 bank migration

The final migration was performed live over COM3 while the operator recorded
the board LEDs. No R-YORS or R-YORS-II source was modified. Bank Maintenance
first erased the former Bank 1 contents, cleared directory record D1, copied
all eight sectors of the original Bank 3 to Bank 1, verified the copy, and
enrolled it as `FF RYORS FFFF FCFFFFFF`. It then erased sectors 8 through E in
Banks 2 and 3.

The alpha13 B3 updater copied and verified the original B3 top sector in B2:F
before changing B3:F. The first install attempt stopped before erase because
the confirmation reader uppercases input while the expected string contained
a lowercase `a`. The updater was rebuilt with the uppercase comparison
`STR8-N 2.0A13`; the second run reported:

```text
BACKUP VERIFIED
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 2.0a13 VERIFIED; RESET

STR8-N 2.0a13 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

After V2 was running, an all-`FF` S19 erased the temporary B2:F backup through
the V2 loader. Direct reads established the final layout:

```text
B0 $8000: 57 44 43 00 D8 A2 FF 9A 20 C5 82 A9 00 8D A1 7F
B1 $8000: 46 4E D6 00 74 AD 56 05 0C 80 E6 B9 20 E5 85 B0
B1 $F000: 4C 46 F0 4C F6 FB 4C 02 FC 4C 2E F9 53 52 02 03
B2 $8000: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
B2 $E000: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
B2 $F000: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
B3 $8000: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
B3 $E000: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
B3 $F000: 53 4E 02 00 4C 51 F0 4C 9B F0 4C 3C FA 4C A2 FA
B3 $FF00: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF
```

`J1` from V2 entered the copied STR8-N 1.35 and then
`HIMON V 00.0915(2324)`. HIMON displayed `K=03` for its `STR8` command; source
inspection confirms this is the command-record kind (execute plus confirm),
not a bank number. Confirmed `STR8`, selector `S`, and `J3` returned to
`STR8-N 2.0a13 B3 65C02`.

The accepted final bank roles are:

| Bank | Final role |
| --- | --- |
| B0 | Preserved WDCMONv2 |
| B1 | Full copy of the former B3 R-YORS/HIMON system with STR8-N 1.35 |
| B2 | Fully erased scratch bank |
| B3 | Alpha13 V2 in `$F000-$FFFF`; `$8000-$EFFF` erased |

The APMan, Bank Maintenance, BASIC/AP, and BD contents formerly occupying B1
and B2 were intentionally destroyed. The final migration artifacts and live
evidence are:

| Artifact | SHA-256 |
| --- | --- |
| Clean B3 full-bank BIN | `7461A3A1F46B09144465EA6502DB385F92F7D9A5CEA876B1C7EB8018F2BA0CBF` |
| Guarded B3 top updater S19 | `E1957E72962BBF035C403C1EDFCF721C451CF5E6D67EBAD2055BCC4FB61C65B0` |
| B2:F all-FF cleanup S19 | `8672CE88FCA2642A18807D87F0F860971C63BE82485A2F8313F8AA4BA8BCC7CE` |
| Ignored COM3 JSONL transcript | `86DE481FAE338FEA60AEE26262F80438F318F46991CDF187763E1BF43C015E0E` |
