# STR8-N v2-alpha9 size and erased tail

The alpha9 build confirms **3303 resident bytes**, including stored RAM
images, with **761 bytes erased before the hardware vectors**. This is
**154 bytes smaller than alpha8**. The builder enforces the reserved blank page.

## Placement

| Address | Use |
| --- | --- |
| $EFF0-$EFFF | Resident configuration, unchanged |
| $F000 | Reset/start entry |
| $F003 | Held-prompt entry |
| $F006-$F021 | Remaining public call entries, spaced three bytes apart |
| $F000-$FCE6 | Monitor code, text, tables and stored RAM images |
| $FCE7-$FDFF | Erased gap below the reserved page |
| $FE00-$FEFF | Reserved blank 256-byte page |
| $FF00-$FFDF | Erased gap |
| $FFE0-$FFFF | Hardware vector area, unchanged |

The builder links at $F000 and requires the resident end to be at or below
$FE00. It fills every byte from the resident end through $FFDF with FF and
points RESET and S9 at $F000. The total erased tail is 761 bytes.
I still protects the whole resident/recovery F sector; F can edit that sector.
These pages share one erase sector and cannot be erased independently.

## Size reduction history

The preceding pass saves **62 bytes**. Along with the earlier
string/instruction changes, the total
reduction before the public call table is **132 bytes**, from **3457 to 3325**.
Ten additional three-byte public entries add **30 bytes**, bringing the
estimate to **3355 bytes**. The latest input/parser pass saves another
**19 bytes**, bringing the estimate to **3336 bytes**. Shorter prompts and messages save
another **16 bytes**, for **3320 bytes**. Making `D addr` display one byte
while retaining `D start end` removes **17 bytes** of default-range handling,
for **3303 bytes**, or **154 bytes below alpha8**. The complete
public table occupies $F000-$F023; the last entry starts at $F021.

| Preceding change | Estimated net bytes saved |
| --- | ---: |
| Zero-page state and register/stack flash timeout counters | 26 |
| Shared `Bad ` prefix; displayed error messages unchanged | 17 |
| Shared S19 error lookup | 10 |
| Shared inclusive record-end calculation | 3 |
| Equivalent F/I flag and boundary checks | 6 |
| **Total** | **62** |

The latest pass uses LSR to consume strictly zero-or-one receive-error,
paired-LF and cancellation flags without saving A (13 bytes), and to return
pending-cancel status in carry without changing its stored flag (2 bytes).
The hex parser counts down its digit allowance and uses Y for shifts,
removing a stack save/restore while retaining token validation (4 bytes).

The wording pass shortens protected-address and sector-span errors, uses
`Canceled`, `Self edit; reset`, `Erase+write` and `OK; reset`, and removes
the trailing space after `Y?`. Confirmation and reset instructions remain
explicit; error causes and the shared `Bad ` prefix are retained.

Flash polling still permits 2 x 65536 program polls or 8 x 65536 erase polls.
X/Y replace the lower counters; a balanced stack byte holds the upper count.
Intentional BIT padding preserves the lower-counter instruction timing,
and the upper-counter rollover is slightly longer. I already saves its
record position across mutation. Timeout success and failure both pop the
extra byte before returning. The flash suite exercises successful writes, program/erase timeouts,
verification failures, bank restoration and RAM-only self-edit holds.

Freed zero-page bytes hold receive-error state at $F1, receive-drop state at
$F2, and the selected bank at $F3. The J target shares $FB with the S19 sum
outside transfers; startup ticks share $F7 after configuration validation.
The resident bank remains at $7D00. All $E0-$FF remains monitor-owned.

The JSON retains full error wording. Leading error strings store only their
tails; the common message routine emits one shared `Bad ` prefix. A small
table maps the existing S19 error results to the same messages, with Ctrl-C
continuing through its existing cancellation cleanup.

## Verification ? 2026-09-19

`make v2-check` passed all five suites (33 test groups) against the final
alpha9 image in `BUILD/v2-alpha9/`. Checks include public entry spacing and
targets, erased tail and reserved page, exact messages, command boundaries,
Ctrl-C handling, flash failures, scratch reuse and v1.35 guest handoffs.
The v1.35 installer validator also accepted the E-F S19 for Banks 0-2.

The first run exposed a stale checksum-message expectation and an autostart
window shortened by the optimized polling path. The test now checks each
rejection's specific message. Increasing the tick loop from $31 to $32 adds
no bytes and restores the minimum hold window: **8,066,242 cycles**, or
**1.008280 seconds at nominal 8 MHz**. The full rerun passed after these fixes.

Linked breakdown: 2531 executable ROM bytes, 34 table bytes, 256 text bytes,
426 stored RAM worker bytes and 56 stored interrupt-entry bytes. The resident
ends at $FCE7 (exclusive); $FCE7-$FFDF is filled with $FF.

A subsequent [COM4 board smoke test](STR8N_V2_BOARD_TEST_2026-09-19.md)
installed Bank 1 sector F through v1.35 and verified exact readback, basic
commands and bidirectional handoffs. Actual v2 flash mutation, native
65C816 and interrupt/NMI behavior still require hardware qualification.
