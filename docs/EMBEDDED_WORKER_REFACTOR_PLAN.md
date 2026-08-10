# Embedded Worker And Payload-Only `I` Refactor

Status: implemented in source and host-build checked; hardware qualification
is still required before release.

## Protected top-sector budget

The Bank-3 top 4K contains everything STR8-N needs to reset, install, recover,
and hand off:

```text
$F000-$FD35  resident code/data             3382 bytes
$FD36-$FD5B  deliberately unused margin       38 bytes
$FD5C-$FFAF  unified worker                   596 bytes
$FFB0-$FFEF  directory                         64 bytes
$FFF0-$FFF9  reserved identity/config          10 bytes
$FFFA-$FFFF  NMI/RESET/IRQ vectors               6 bytes
```

The mandatory unused margin is 32 bytes. `make` reads the linked maps and
fails if the actual margin is smaller, if a published worker constant is
stale, or if a fixed gate/tail address moves. The report includes the exact
worker size and S19 SHA-256.

## Settled interfaces

- `$F003` is retired and returns failure (`CLC`, `RTS`, `NOP`). Legacy
  TopWriter support is retired.
- `$F006` remains a retired fail-closed gate.
- `$F009` is record service ABI V2. It parses validated S0/S1/S9 input from a
  buffer or the console. Public APPLY_LF is removed.
- `$F010` copies and verifies only the 41-byte selector prefix to `$0200` and
  enters it at `$0203`. This preserves an R-YORS HIMON helper at `$0300`.
- `I` and `J0`-`J3` copy the complete worker and then compare every byte in a
  separate ROM-to-RAM verification pass.
- Worker mode `$06` is removed. A user program needing read-only sector access
  selects its bank through `$F010`/`$0203` and owns its own copy routine.
- Reset always returns to Bank 3. Do not press NMI during flash mutation; no
  extra NMI recovery code is carried in the protected sector.

## Installer range and S19 rules

`I` receives payload-only dense S19. One optional S0 may precede ascending,
contiguous, non-empty S1 records. Exactly one S9 ends the stream. Gaps,
overlaps, omitted `$FF` bytes, unsupported records, bad checksums, early S9,
and trailing input fail closed.

- Banks 0-2 accept any selected 4K-aligned 4K-32K range inside
  `$8000-$FFFF`.
- Bank 3 accepts 4K-28K ending no later than `$EFFF`; sector F is protected.
- A full 32K Bank 0-2 S9 must equal the RESET vector at `$FFFC-$FFFD` and may
  not be `$FFFF`.
- A partial Bank 0-2 S9 is `$FFFF` or points inside the selected range.
- A first Bank-3 S9 points inside the selected range and becomes the immutable
  directory entry.
- An existing Bank-3 S9 is `$FFFF` (no change) or exactly matches its existing
  entry.

The final selected sector stays in RAM until a valid S9 is received and the
operator answers `Y` to `COMMIT?`. Only then is that sector erased, programmed,
and read back.

## Journal and interruption recovery

The four journal bytes are a 32-bit one-way fuse strip. Each transaction uses
one START bit and the following COMPLETE bit, allowing 16 installs before an
external-programmer refresh is required. COMPLETE is always the last persistent
directory action.

An interrupted retry must cover the complete writable bank: 32K for Banks
0-2 or 28K for Bank 3. An unfinished first directory row may be reconstructed
only when every metadata byte is erased or already exactly equal. A sealed row
retains its immutable type, description, and Bank-3 entry rules. A started row
never becomes launchable until the full recovery payload verifies and COMPLETE
is written.

## Host artifacts

`convert_guest_bin_to_s19.ps1` converts a 4K-32K aligned BIN to dense S1/S9.
`compose_str8n_install_s19.ps1` now validates and normalizes payload-only S19;
it never prepends a worker. The old combined-stream format is deliberately not
produced.

## Remaining release gate

The source builds and host layout checks pass. Before calling V2 hardware-safe,
qualify each accepted boundary and interruption point on sacrificial hardware,
archive programmer recovery images and hashes, read back every written byte,
exercise `J0`-`J3`, and prove physical RESET always restores Bank 3.
