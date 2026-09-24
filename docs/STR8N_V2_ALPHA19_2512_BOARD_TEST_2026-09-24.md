# STR8-N alpha19 qualification on board 2512

Date: 2026-09-24. Partial hardware qualification of the
[frozen alpha19 candidate](STR8N_V2_QUALIFICATION.md). FTDI, cross-bank RAM ABI,
BRK/IRQ/NMI, flash operations, and the tested autostart paths passed.
Direct ACIA transmit passed; receive did not. Full qualification is incomplete.

## Setup and preservation

- Board marked 2512; alpha19 reports `65C02`.
- FTDI: COM4, adapter serial `A10MQFLCA`, 115200 baud.
- ACIA: COM7, adapter serial `BG02PM7ZA`, 19200 8N1, no flow control.
- Initial firmware: STR8-N 1.35 and HIMON `00.0917(1534)` in Bank 3.
- Operator authorized Bank 1 as disposable.

Two complete HIMON Bank 3 readbacks matched. The read-only RAM archive tool
then captured all four banks as dense S19 and BIN files. Extraction verified
record checksums, address coverage, and the board's FNV1A receipts. The archive
Bank 3 image also matched the two earlier reads. These owner-local backups
are retained under `output/qualification/board-2512-2026-09-24/backups/`.

The physical RESET returned from the archive tool to Bank 3. STR8-N 1.35 `I`
installed Bank 1 E-F, accepted the final commit, and reported `OK`. `J1` printed
`STR8-N 2.0a19 B1 65C02`. The install S19 SHA-256 was
`8137d389683dc5310831618c4e14b64def185e33dd737cd95d2d72e11fb99053`,
identical to the frozen stream.

A complete four-bank readback established:

- Bank 1 E-F exactly matched the frozen 8192-byte BIN; lower sectors were unchanged.
- Banks 0 and 2 were unchanged.
- Bank 3 changed only at `$FFCE`, from `$FF` to `$FC`, in the v1 installer
  directory/journal. Its firmware and all other bytes were unchanged.

## Accepted checks

| Check | Evidence/result |
| --- | --- |
| FTDI console | Command/response, S19 transfers, full-bank dumps and prompts worked |
| Monitor RAM operations | M/D at `$0200-$0203`, followed by exact restoration |
| Input and access guards | M rejects flash and live workspace; malformed hex rejected; D rejects ACIA I/O and reversed ranges; I rejects resident top; F rejects sector span |
| L and G | Frozen RAM probes loaded, read back byte for byte, then executed explicitly with G |
| Cross-bank RAM ABI | `B0 B1 B2 B3 RAM ABI: PASS`, then HOLD restored the B1 prompt |
| BRK and VIA1 timer IRQ | `V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS` |
| Physical NMI | Operator pressed NMI; `V2 NMI / A-X-Y / STACK / RTI: PASS`, then returned to B1 |
| Physical RESET/relaunch | RESET exited the ACIA probe into v1.35 B3 recovery; J1 relaunched alpha19 |
| F direct programming | B1:E000 `$FF->$00`; full-sector readback matched the expected byte and unchanged neighbors |
| F erase/rewrite | B1:E000 `$00->$FF`; full-sector readback exactly restored the original sector |
| I installation | Dense B1:E image with an `$A5` marker installed/read back, then all-FF image installed/read back to restore it; S9 was not executed |
| Fixed-address autostart | `C 1 1 F007 0A`, restart, timed handoff to HOLD, B1 prompt |
| Vector autostart | `C 1 3 V 0A`, restart, handoff through Bank 3 RESET into v1.35 |
| Autostart cancellation | S during the hold window printed `Canceled` and retained B1 |
| Disabled autostart | `C 0 3 V 0A` persisted through restart without a hold window |

After configuration tests, F restored all sixteen configuration bytes to `$FF`;
C reported `No config`. A final complete four-bank readback matched the
post-install images exactly. All temporary flash changes were therefore restored.

## ACIA receive issue

The exact frozen direct ACIA probe was loaded and read back at `$2000-$216B`.
It bypasses monitor console selection. COM7 received the repeating
`ACIA 19200 8N1 - TYPE; Q EXITS` banner. Sending `A` produced no corresponding
`ACIA RX $41` report on FTDI. A separate `Q` attempt likewise produced no
`ACIA RX $51` or return to the monitor. FTDI repeatedly reported
`ACIA STATUS $70`; physical RESET was required to exit the probe.

The [W65C51N datasheet](https://www.westerndesigncenter.com/wdc/documentation/w65c51n.pdf),
status-register table, identifies `$70` as DSRB/DCDB high, TDRE set, and RDRF
clear. This observation does not identify the root cause. Cable/board receive
wiring, handshake inputs, and receive clock behavior remain diagnostic work;
do not infer damaged hardware or a validated backup-console driver from this run.
The symptom also occurred in the earlier
[2205 ACIA session](STR8N_V2_ALPHA13_BOARD_TEST_2026-09-23.md#board-2205-acia-receive-diagnosis).
The ACIA probe made no firmware changes.

## Final state and evidence

At the end of this session, the board was at alpha19 `B1>`, selected Bank 1,
factory-erased configuration,
autostart inactive. Both serial ports were released. Bank 3 v1.35 recovery is
retained. Complete final-bank SHA-256 identities:

| Bank | SHA-256 |
| --- | --- |
| 0 | `2f0000c74eceec809a814e31f822702977d7bfed5ee6f3bc4869627864ca59a8` |
| 1 | `3670a7b9f1865d41a5d6e00730f79fe9a130100d3cbbd1dcdd817f328e96e05d` |
| 2 | `2444130717cea5a10fa02982523f984f7de2bd06f696b2c5349ca576ea120740` |
| 3 | `e08b871a106b5cdeb3d3122cf56b5ac1e29cbafe7ba52e92cf6936a6cfc7a255` |

Append-only serial logs, scripts, backups, intermediate/final readbacks, and
test receipts are owner-local in `output/qualification/board-2512-2026-09-24/`.
`qualification-receipt.json` lists their SHA-256 identities; its own SHA-256 is
`3d787d8230a549328b152b98367d1879ea5dfc1c3e1a76e35ac0c2b0d55988ce`.

Pending gates include ACIA receive and actual fallback-console operation,
cold power-cycle startup, visual LED observations, broader cancellation/error
and controlled failure/recovery cases, resident self-edit, and W65C816 hardware.
This run does not complete the release matrix.
