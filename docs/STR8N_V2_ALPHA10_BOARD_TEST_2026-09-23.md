# STR8-N v2-alpha10 board test — 2026-09-23

Status: passed on the board marked `2205`, using COM3 at 115200 baud. Alpha10
was installed as a guest in Bank 1 from the resident STR8-N 1.35 in Bank 3.
Bank 3 was not programmed. The board was left at the alpha10 `B1> ` prompt and
COM3 was released.

Board 2205 is fitted with a battery, a cryptographic chip, and SPI SRAM. This
session did not exercise those optional devices; they identify the tested
hardware and remain available for later v2 integration and qualification.

## Candidate

| Artifact | SHA-256 |
| --- | --- |
| `str8n-v2-alpha10-e000-ffff.s19` | `3687C430E1039A357700F2D82D8ECF539BCA8663FBFD60699E2315CCD7EBA695` |
| `str8n-v2-alpha10-e000-ffff.bin` | `9213FC033994512849C0FB43FA9550555829094A3E05F1608E174A477C326950` |

The dense S19 and BIN cover `$E000-$FFFF`. The BIN is 8,192 bytes. The build
contains 3,584 resident bytes, a 501-byte RAM flash worker, 56 bytes of RAM
interrupt entry code, and 480 erased bytes before the hardware vectors.

## Installation

The initial monitor was HIMON. Its `STR8` handoff entered the preserved
STR8-N 1.35 recovery monitor. STR8-N 1.35 command `I` then installed sectors
E-F of the alpha10 S19 into Bank 1 and reported `OK`. Launching `J1` produced:

```text
STR8-N 2.0a10 B1
B1>
```

Two earlier physical-reset arm windows expired without RAM or flash writes.
They did not form part of the installation.

## Results

- `?` displayed the expanded multiline command help.
- Every normal prompt identified the selected bank. `B2` produced `B2> ` and
  selecting Bank 1 again produced `B1> `.
- `D F000 F033` showed signature bytes `53 4E 02 00` (`SN`, major ABI 2,
  format 0), followed by all sixteen public three-byte JMP entries. The four
  reserved entries at `$F028-$F031` each targeted the shared RTS at `$F034`.
- A RAM `D/M/D` exercise at `$0200-$0203` changed the first two bytes to
  `$A5,$5A`, observed them, and restored the original `$4C,$27` bytes.
- A Bank 1 sector-F edit received the first exact `Y`, then rejected the wrong
  second response `B2` at the `Type B1>` prompt. It printed `Canceled`; `$FFFF`
  remained `$7E`.
- A Bank 3 edit at `$8000` received the first exact `Y`, then rejected `B2` at
  the `Type B3>` prompt. It printed `Canceled`; no Bank 3 write began.
- A later flash-changing Bank 3 test programmed `$FFF9` from `$FF` to `$AE`.
  It required exact `Y` and `B3`, used the direct-program path, and returned
  `Done` to the Bank 1 resident monitor with Bank 3 still selected.
- A second Bank 3 edit restored `$FFF9` from `$AE` to `$FF`. It required the
  same two confirmations, used the erase-and-rewrite path for Bank 3 sector F,
  verified the reconstructed sector, and returned `Done`. An incomplete
  `F FFF9` command had first returned `Bad hex` without mutation.
- A complete post-restoration `D F000 FFFF` dump produced all 256 rows and
  4,096 bytes. Its SHA-256 is
  `2183B923D1FAAE5E5A86B7126D6CC2C74B2C28AEFA8DF61DA2B1B85AB6779A53`.
  All 4,032 bytes outside the live directory at `$FFB0-$FFEF` exactly match
  the canonical v1.35 recovery BIN. Its 34 differences from the canonical BIN
  are confined to the board's populated directory records. `$FFF9` reads
  `$FF`, confirming restoration of the edited byte.
- `G F007` entered the public HOLD entry and returned to the alpha10 banner and
  `B1> ` prompt without autostart.
- A no-change resident edit of `$FFFF` completed after exact `Y` and `B1`, then
  held in RAM at `OK; press Y to soft reset`. Pressing `Y` performed the
  CPU-level restart and returned to `STR8-N 2.0a10 B1` and `B1> `. The test did
  not assert the electrical RESET line.
- A later flash-changing resident edit programmed Bank 1 `$FF40` from `$FF` to
  `$43`. The command required exact `Y` and `B1`, reported `OK`, and its
  RAM-only soft restart returned to alpha10. `D FF40` then read back `$43`.
- A second flash-changing edit restored `$FF40` from `$43` to `$FF`. This
  required the erase-and-rewrite path, the same two confirmations, and the
  RAM-only soft restart. The worker verified the reconstructed sector before
  reporting `OK`.
- `C` initially reported `No config`, as expected for the erased configuration
  block. `C 01 01 F007 0A` then programmed and verified an enabled Bank 1
  configuration targeting the public HOLD entry with a ten-tenth delay. A
  subsequent Bank 1 start displayed `C 01 01 F007 0A`, presented the
  `S/Ctrl-C hold` window, and reached the alpha10 HOLD prompt.
- `C 01 01 F007 FF` replaced the delay with the maximum `$FF` value. Because
  this required 0-to-1 bit transitions, it exercised the sector-E
  erase-and-rewrite path and reported `Done`. On the next `J1`, input during
  the hold window printed `Canceled` and returned directly to `B1> `. A second
  `J1` was allowed to expire; it jumped to `$F007`, printed a fresh alpha10
  banner, and reached `B1> `. Thus both cancellation and timeout branches were
  exercised with a live configuration.
- The compact forms proposed for the corrected help were then exercised on
  alpha10. `C 0 1 F007 7E` disabled autostart and `J1` held immediately at the
  normal prompt. `C 1 1 F007 7E` re-enabled it; the hold window expired and
  entered `$F007`. Delays `$01` and `$06` were rejected with `Bad range`, while
  the minimum `$0A` was accepted and timed out through `$F007`. These tests
  prove that alpha10 already accepts one-digit enable and bank fields; alpha11
  changes only the misleading help text. The board was left configured as
  `C 01 01 F007 0A`.
- Invalid and incomplete `C` and `F` forms returned `Bad cmd` or `Bad hex`
  without mutation.
- `J3` returned to the intact STR8-N 1.35 recovery monitor both before and
  after the Bank 3 sector-F mutation. Its Bank 1 launch returned to alpha10.
  A later hardware reset also entered STR8-N 1.35, whose warm boot reached
  HIMON V 00.0915(2324).
- A final `D E000 FFFF` captured 512 rows and 8,192 bytes. The parsed readback
  matched the alpha10 BIN exactly. This full readback preceded the later
  `$FF40` mutation-and-restoration exercise; the restoration received the
  worker's complete-sector verification but was not followed by another full
  host-captured dump.

The session also found an alpha10 help defect. `C [on bank addr delay]` reads
as though `ON` and `B1` are accepted tokens, but alpha10 actually requires four
two/four-digit hexadecimal fields: `C enable bank address delay`. For example,
`C 01 01 F007 0A` enables Bank 1 HOLD-entry autostart after ten tenths. The
attempted `C ON B1 F003 99` correctly made no change and returned `Bad hex`,
but the help should state the accepted syntax. `$F003` is now a signature byte,
not an entry point.

The host build and all five regression suites also passed all 33 test groups,
including signature/JMP-table validation and the 8 MHz autostart timing model.
The measured cancellation window was 8,194,243 cycles, or 1.024280 seconds.

## Evidence and remaining coverage

The installation terminal event log is
`BUILD/v2-alpha10/com3-2205-alpha10-install.raw.events.txt`; its paired raw
receive capture is `com3-2205-alpha10-install.raw`. The full flash dump is
`BUILD/v2-alpha10/com3-2205-readback.jsonl`. These generated files are local
build evidence and are not committed source artifacts. The parsed post-edit
Bank 3 sector is
`BUILD/v2-alpha10/com3-2205-bank3-f000-ffff-after-v2-f.bin`.

This session did not exercise v2 `I`, injected flash failures, hardware
NMI/IRQ, physical-reset bank selection, or native-mode W65C816 behavior. Those
remain hardware qualification work. A second exact Bank 1 full-image readback
after the `$FF40` restoration also remains desirable.
