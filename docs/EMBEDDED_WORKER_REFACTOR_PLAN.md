# Embedded Worker and Payload-Only `I` Implementation Record

Status: implemented in STR8-N v1.1, host-build verified, and partially proven
on hardware. This file preserves the refactor decisions and remaining release
qualification work.

## Protected top-sector result

Everything persistent and every flash/selection worker fits in Bank 3's top
4K:

```text
$F000-$FD53  resident code/data             3412 bytes
$FD54-$FD5B  enforced unused reserve            8 bytes
$FD5C-$FFAF  unified worker                   596 bytes
$FFB0-$FFEF  directory                         64 bytes
$FFF0-$FFF9  identity/configuration reserve     10 bytes
$FFFA-$FFFF  NMI/RESET/IRQ vectors               6 bytes
                                              ----------
                                              4096 bytes
```

`make layout-check` reads the linked maps and fails if the reserve falls below
8 bytes, a published worker constant becomes stale, or a fixed gate/tail
address moves.

## Settled interfaces

- `$F003` is retired and returns failure (`CLC`, `RTS`, `NOP`). Legacy
  TopWriter support is retired.
- `$F006` is also a retired fail-closed tombstone.
- `$F009` is record service ABI V2. It parses validated S0/S1/S9 input from a
  RAM buffer or console and does not apply records for the caller.
- `$F010` copies/verifies the 41-byte selector prefix at `$0200-$0228`, then
  enters its return-capable `$0203` entry. This does not overwrite the R-YORS
  helper at `$0300`.
- `I` and `J0`-`J3` copy the worker bytes they need and read back each byte.
- `L` accepts complete S1 spans only inside `$2000-$7AFF` and automatically
  executes an in-range S9. It never invokes the flash worker.
- Worker mode 6 is removed. A RAM user selects a bank with `$F010` and owns
  any read/copy loop it requires.
- Physical RESET always selects Bank 3. NMI must not be pressed during flash
  mutation; no additional flash-time NMI recovery is carried in the 4K image.

## Startup and full-speed transport result

Startup has two approximately six-second phases:

```text
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...  keys ignored
STR8-N 1.1
0-2 H S: ......                                  keys live
```

STR8-N flushes queued input between the phases. This provides a visible
board-alive indication while allowing USB and the terminal to attach before
the identity and selector are printed.

For `I`, `WRITE? Y` now copies/verifies the worker and opens the persistent
transaction before `S19` is printed. START and any first-enrollment metadata
therefore finish before the terminal begins streaming. No per-character or
per-line pacing is required.

## Installer and S19 result

`I` receives payload-only dense S19:

- zero or one leading S0;
- ascending, contiguous, nonempty S1 records covering the exact selected
  extent, including explicit `$FF` bytes;
- exactly one S9 and no trailing records;
- Banks 0-2: any 4K-aligned 4K-32K span inside `$8000-$FFFF`;
- Bank 3: any 4K-aligned 4K-28K span inside `$8000-$EFFF`;
- full Bank 0-2 S9 equals the non-erased RESET vector;
- partial Bank 0-2 S9 is `$FFFF` or inside the selected extent;
- first Bank-3 S9 is inside the extent and becomes its immutable entry;
- later Bank-3 S9 is `$FFFF` or exactly matches that entry.

All complete non-final sectors can be programmed and verified while the S19
arrives. The final sector remains in RAM until valid S9 and `COMMIT? Y`.
COMPLETE is written only after final readback succeeds.

## Journal and recovery result

Each directory row has a 32-bit one-way journal with 16 START/COMPLETE pairs.
`WRITE? Y` consumes or resumes START. COMPLETE is always the final persistent
action. An interrupted bank cannot pass `J0`-`J2`.

Recovery must cover the full writable bank: `8-F`/32K for Bank 0-2 or
`8-E`/28K for Bank 3. A sealed identity is immutable. An unfinished first row
can be reconstructed only when every programmed byte is erased or already
matches exactly.

## Maintenance and full-bank artifacts

`make bank-maint` creates the self-contained RAM maintenance S19. Its `C`
command copies and verifies eight sectors, then enrolls only an erased
destination row with START, identity/seal, and COMPLETE-last ordering.

`make ryors-full-bank` combines the R-YORS ASM+HIMON `8-E` payload with the
current STR8-N top BIN to produce a Bank-0/1/2 `8-F` image. Neither artifact
adds bytes to the protected 4K resident image.

## Host verification

- `make layout-check` checks top-sector ownership and fixed interfaces.
- `make range-matrix-check` checks all documented top-aligned sizes and
  representative middle spans.
- `make ram-load-contract-check` checks `L` record and S9 boundaries.
- `make bank-maint` validates the maintenance S19 and private-worker hash.
- `make ryors-full-bank` validates and composes the full 32K image.

## Hardware evidence and remaining gate

Retained terminal sessions have shown the startup display, a full-speed
Bank-3 `8-E` install, HIMON start, separate ASM `8-B` installation and start,
RAM maintenance loading, mapping, and an eight-sector verified raw copy. The
raw-copy test also proved that used flash without directory enrollment is
correctly refused by `J0`-`J2`.

Still retain board-proof runs for the enhanced `C` enrollment, generated
Bank-0/1/2 `8-F` image, every boundary size, interruption/recovery points,
journal exhaustion, and rejected `L` limits. Archive exact binaries, hashes,
flash readbacks, and terminal transcripts. Host checks complement but do not
replace hardware qualification.
