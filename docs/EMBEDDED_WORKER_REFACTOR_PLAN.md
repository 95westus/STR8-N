# Embedded Worker and Payload-Only `I` Implementation Record

Status: implemented in STR8-N v1.1, host-build verified, and partially proven
on hardware. This file preserves the refactor decisions and remaining release
qualification work.

## Protected top-sector result

Everything persistent and every flash/selection worker fits in Bank 3's top
4K:

```text
$F000-$FD54  resident code/data             3413 bytes
$FD55-$FD5B  available resident growth           7 bytes
$FD5C-$FFAF  unified worker                   596 bytes
$FFB0-$FFEF  directory                         64 bytes
$FFF0-$FFF9  identity/configuration reserve     10 bytes
$FFFA-$FFFF  NMI/RESET/IRQ vectors               6 bytes
                                              ----------
                                              4096 bytes
```

`make layout-check` reads the linked maps and fails if the resident crosses the
fixed `$FD5C` worker boundary, a published worker constant becomes stale, or a
fixed gate/tail address moves. The v1.22 warm-default candidate with explicit
`C` cold and `W` warm selection leaves 7 bytes available, not reserved.

## Settled interfaces

- Legacy TopWriter support and the general destructive worker doorway remain
  retired; neither is part of the resident ABI.
- `$F003` initializes the console hardware, and `$F006` reports resident ABI
  version `$01` and capability byte `$3F`. The preceding image returns carry
  clear at `$F006`, providing a safe compatibility test.
- `$F009` is record service ABI V2. It parses validated S0/S1/S9 input from a
  RAM buffer or console and does not apply records for the caller.
- `$F010` copies/verifies the 41-byte selector prefix at `$0200-$0228`, then
  enters its return-capable `$0203` entry. This does not overwrite the R-YORS
  helper at `$0300`.
- `$F013`, `$F019`, and `$F03E` are raw CHARIN, CHAROUT, and CHAR_READY
  services. The first two block; CHAR_READY returns immediately and reports
  readiness without consuming a byte. All require Bank 3 and an initialized
  FT245R interface to remain visible.
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
STR8-N 1.22
0-2 C W S: ......                                keys live
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
Its `D` command uses the same record writer to adopt an existing valid-reset
payload into an erased row without rewriting payload sectors. Its `R` command
requires all eight sectors of a Bank 0-2 payload to verify erased before it
stages Bank-3 sector F, keeps a verified original backup in the selected
bank's sector F, clears only the matching D0-D2 row, and rewrites/verifies the
complete protected sector after exact confirmation. The temporary backup is
erased only after B3F verifies. The current image loads at `$2000-$362A`; its
private worker is stored at `$3400-$362A` and copied to `$0200-$042A`.

`make onboard-directory-refresh` creates the guarded RAM tool that backs up
the complete live Bank-3 top sector into Bank 1 sector F, verifies it, then
rewrites the current top image with `$FF` in `$FFB0-$FFF9`. This is the onboard
directory/journal reset path; the checked full-device programmer merge remains
the independent recovery fallback.

`make ryors-full-bank` combines the R-YORS ASM+HIMON `8-E` payload with the
current STR8-N top BIN to produce a Bank-0/1/2 `8-F` image. Neither artifact
adds bytes to the protected 4K resident image.

## Nice-to-have: reset-aware HIMON entry

This is a future direction, not promised v1.22 behavior. The desired policy is:

- physical RESET with a valid HIMON RAM cookie enters HIMON warm;
- power-up, a missing cookie, or an invalid cookie enters HIMON cold;
- explicit `C` enters HIMON cold regardless of any cookie.

The current v1.22 candidate implements explicit `C` cold and `W` warm at both
the live selector and the `STR8-N>` prompt; selector timeout remains warm. A
future reset-aware design
should use a HIMON-owned, versioned, false-positive-resistant RAM cookie that
is distinct from the transient STR8-to-HIMON warm-entry signature. HIMON should
publish it only after successful cold initialization, and incompatible updates
or untrustworthy state must invalidate it.

This policy needs code reduction before implementation can do the distinction
and its failure handling justice: only 7 resident bytes remain. It also needs
a settled RAM ABI and board gates proving retained-cookie RESET is warm, true
power-up and invalid-cookie RESET are cold, and explicit `C` is always cold.

## Nice-to-have: configurable timeout bank and previous-bank command

This is a possible future enhancement, not promised v1.22 behavior. A timeout
default for Bank 0-2 must not depend on RAM that a guest may overwrite. Prefer
either a build-time resident constant or a versioned record in Bank 3's
`$FFF0-$FFF9` configuration pocket. Erased or invalid configuration should
retain the current warm-HIMON timeout. A configured bank must still pass the
existing COMPLETE-directory and RESET-vector gates; failure should remain in
Bank 3 and enter the STR8 menu.

A `P` command could reuse the published `BJ` Bank Jump Record at
`$7DFD-$7DFF` as a best-effort repeat of the last successful jump. It must
validate the signature and bank and then use the normal guarded launch path.
Because Banks 0-2 may overwrite that RAM, `P` cannot promise persistence or
accuracy across arbitrary guest execution or power loss. Do not write Bank-3
flash on every jump merely to make `P` durable; reliable persistent history
would require suitable external nonvolatile storage. Also settle whether `P`
means the last jump, including `J3` as the current record does, or a distinct
last guest bank before changing the published ABI semantics.

## Deferred Bank Maintenance usability goals

These are design notes, not current `v1.22` behavior or scheduled work. The
factory-onboard-firmware preservation run succeeded, but using a full-bank
`C`, declining its enrollment, and then issuing a separate `D` made the
copy/adopt process more convoluted than it should be.

- Consider separating payload copy from directory enrollment and extending
  `C` (or a distinct advanced command) to accept explicit source and
  destination sectors/ranges. An optional compare-first mode could write only
  differing sectors. A partial or differential copy must never imply that a
  complete guest exists or auto-enroll it; retain exact confirmation,
  protected-sector guards, per-sector readback verification, and an explicit
  later `D` when whole-bank adoption is actually valid.
- Consider displaying a retained B3:F backup role instead of leaving B1:F as
  generic `U`. Keep current `P` reserved for the live protected B3:F sector.
  `S` is attractive for positively identified STR8-N/system content, while
  `B` would describe a verified backup role without confusing content with
  protection. Choose the final one-character map vocabulary only with an
  unambiguous legend.
- Consider a `W` map marker for positively recognized factory onboard
  firmware in Banks 0-2. First define and prove a stable signature with low
  false-positive risk; the observed banner and board-local `WDC*` directory
  labels alone are not sufficient provenance. Until then, such sectors remain
  `U` rather than receiving a guessed identity.

## Host verification

- `make layout-check` checks top-sector ownership and fixed interfaces.
- `make range-matrix-check` checks all documented top-aligned sizes and
  representative middle spans.
- `make ram-load-contract-check` checks `L` record and S9 boundaries.
- `make bank-maint` validates the maintenance S19 and private-worker hash.
- `make ryors-full-bank` validates and composes the full 32K image.

## Hardware evidence and remaining qualification

Retained terminal sessions have shown the startup display, a full-speed
Bank-3 `8-E` install, HIMON start, separate ASM `8-B` installation and start,
RAM maintenance loading, mapping, guarded onboard directory refresh, and an
eight-sector verified copy with COMPLETE directory enrollment. Selector `2`
launched that Bank-2 copy and its `J3` returned through physical Bank 3. The
earlier raw-copy test also proved that used flash without directory enrollment
is correctly refused by `J0`-`J2`. The current Bank Maintenance artifact also
has retained hardware acceptance for metadata-only D1/D3 directory adoption,
its precommit guards, and a subsequent `C` regression. The 2026-08-13
stale-directory recovery run additionally accepted `R` for D0: an incorrect
confirmation caused no mutation, exact `CLEAR D0` completed the verified B3F
backup/rewrite path, and the immediately following eight-sector B3-to-B0 copy
completed and enrolled D0. The 2026-08-14 successor's guarded D3
journal-compaction branch is also board-accepted through verified B3F rewrite,
identity retention, `FCFFFFFF` post-map, and erased-scratch cleanup. Earlier
explicit STR8-N `J3` captures printed `J B3` but were followed by operator-
identified physical resets. A new continuous rerun explicitly identifies the
RESET after `J B3` as synthetic and proceeds through the cold timeout to
matching HIMON `00.0814(1157)`. The compacted-D3 launch integration is accepted
for the installed STR8-N `1.2` / R-YORS `1157` image.

The 2026-08-14 STR8-N `1.21` top updater is also board-accepted. It verified
the B1:F backup, reported sum `$08F8`, erased and verified B3:F, and entered a
live STR8-N `1.21` resident. The current R-YORS `1303` Bank-3 `8-E` payload
committed and warm-booted successfully. A later transfer failed after the six
pre-commit dots, returned before `COMMIT`, and rejected the remaining stream at
the shell; a clean retry committed and again reached HIMON `1303`. The cause is
not established, but failure containment and retry recovery are accepted.

The final current-image continuation completes the STR8-N `1.21` integration
smoke. An intentional physical RESET retained `1.21` and cold-booted HIMON
`1303`; the fixed `$C000` head and ASM-F2 `1303` identity matched. The renamed
Bank Maintenance tool loaded, produced the expected protected-sector/directory
map, and quit without mutation. The operator identified every later RESET in
that capture as synthetic, so explicit `J3` causally passed the D3 gate and
returned through the Bank-3 RESET vector to matching `1.21`/`1303` identities.

Still retain board-proof runs for the generated Bank-0/1/2 `8-F` image, every
boundary size, interruption/recovery points, explicit `J0`/`J1`/`J2` commands,
AP put, and rejected `L` limits. The current `1.21` top installation,
physical-reset persistence, renamed RAM-tool smoke, and `J3` identity handoff
need no further repetition.
Archive exact binaries, hashes, flash readbacks, and terminal transcripts. Host
checks complement but do not replace hardware qualification.
