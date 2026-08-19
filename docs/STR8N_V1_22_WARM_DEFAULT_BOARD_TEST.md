# STR8-N v1.22 Compact Warm-Default Board Test

Status: board accepted by the operator 2026-08-19. Automatic warm, selector
`S`/`W`/`C`, prompt `W`, cold HIMON initialization, and guarded update were
captured. The operator explicitly cleared the uncaptured canary, prompt `C`,
installed-byte dumps, and uninterrupted `J3`-to-warm sequence as blockers. See
[STR8N_V1_22_CW_SELECTOR_HARDWARE_PROOF_2026-08-19.md](STR8N_V1_22_CW_SELECTOR_HARDWARE_PROOF_2026-08-19.md).

This gate tests the compacted STR8-N resident and its changed default selector
behavior. Physical RESET still starts in Bank 3. If the operator presses no key,
STR8-N must warm-enter compatible Bank-3 HIMON and preserve RAM. Explicit `W`
must do the same; `S` must still reach the STR8-N prompt, where explicit `C`
must cold-enter HIMON.

## Candidate identity

```text
resident              $F000-$FD54, 3413 bytes
free resident margin  $FD55-$FD5B, 7 bytes
stored worker         $FD5C-$FFAF, 596 bytes
vectors               D2 F0 00 F0 E6 F0

top BIN
  BUILD/v1.22/bin/str8n-v1.22-bank3-f000-ffff.bin
  SHA-256 C26F86CC8BAA77DCEA9FCA59DDD79AED8415BFCFB106EFE90DEE03EE228F26A7

guarded updater
  BUILD/v1.22/s19/str8n-v1.22-top-update-2000.s19
  SHA-256 D02805D0907E644B9B6265B9F6F85A4381C57DCA62B8CEA92BE40499213C6F6C
```

`make all` and `make bank-maint-menu` pass for this candidate. The host gates
cover layout, the exact 4K top image, range matrix, RAM load contract, RAM ABI,
embedded updater identity, generated public ABI, and S19 checksums. Record the
two hashes above with the board transcript; the current manifest is from a
dirty pre-proof worktree and its Git commit field is not final release identity.

## Safety preflight

1. Keep the last accepted v1.21 4096-byte top BIN and the v1.22 BIN above
   available to the external programmer.
2. Confirm Bank 1 CPU `$F000-$FFFF` is sacrificial. The updater erases it and
   writes a verified raw backup of the live Bank-3 top sector there.
3. Use the standalone v1.22 updater named above. Do not send the directory
   refresh artifact or the combined Bank Maintenance image for this first gate.
4. Do not press RESET or NMI, remove power, or disturb FTDI/flash hardware after
   the final confirmation until the updater reports verification and enters the
   new RESET vector.

## Gate 1: plant a warm-boot canary

At the HIMON prompt, write and verify one byte in the published free low-RAM
lane:

```text
>M 1A00
1A00: xx A1
>D 1A00
1A00: A1
```

Enter STR8-N and select `S` during the six live selector dots:

```text
>STR8
RUN STR8: BOOTLOADER @F000 K=03 ? y
...
0-2 C W S: ...S
STR8-N>
```

Input during the preceding six `WAIT...` pulses is deliberately discarded; do
not type `S` until the live selector appears.

## Gate 2: guarded top-sector update

At `STR8-N>` type `L` and send exactly:

```text
BUILD/v1.22/s19/str8n-v1.22-top-update-2000.s19
```

Require the v1.22 title and target report:

```text
STR8-N 1.22 TOP UPDATE
BACKUP B1:F; TARGET B3:F
TYPE BACKUP B1F>
```

Type the exact first confirmation:

```text
BACKUP B1F
```

Require `BACKUP VERIFIED`, record the displayed old-sector receipt, then type
the exact final confirmation:

```text
STR8-N 1.22
```

After `ERASING B3:F - NO RESET/NMI/POWER`, do not interact with the board until
it reports:

```text
STR8-N 1.22 VERIFIED; RESET
```

If a write fails, do not reset. At the RAM recovery prompt use `R` to retry the
embedded v1.22 candidate or `O` to restore the verified Bank-1 backup. If the
RAM recovery tool cannot recover, use the external programmer.

## Gate 3: automatic warm Bank-3 entry

The updater jumps through the new RESET vector. Touch no key during either
startup phase. Require:

```text
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: ......
BOOT WARM
```

Fail this gate if HIMON prints `BOOT COLD`, prints `RAM ZERO OK`, or the system
falls into the STR8-N prompt despite a compatible Bank-3 HIMON marker.

At the HIMON prompt, prove the pre-update canary survived:

```text
>D 1A00
1A00: A1
```

## Gate 4: physical RESET preservation

Change the canary to `$A2`, verify it, then press physical RESET. Again touch no
key through the wait and selector intervals. Require `STR8-N 1.22`, `BOOT WARM`,
and:

```text
>D 1A00
1A00: A2
```

This is the primary v1.22 acceptance gate: physical RESET selected Bank 3,
selector timeout entered HIMON warm, and ordinary RAM survived.

## Gate 5: explicit selector regressions

Re-enter STR8-N. During the live selector interval:

1. Press `S`; require the `STR8-N>` prompt and the `STR8-N 1.22` identity.
2. Require prompt help `I L C W J`. At that prompt type `W`; require
   `BOOT WARM` and the unchanged canary.
3. Re-enter STR8-N and press `W` during the live selector; require another
   `BOOT WARM` and the unchanged canary.
4. Re-enter STR8-N, set or retain a canary, issue `J3`, touch no key during the
   restarted selector, and require another warm Bank-3 HIMON entry with the
   canary unchanged.
5. Set the canary to `$A3`, re-enter STR8-N, and press `C` during the live
   selector. Require `BOOT COLD`, `RAM ZERO OK`, and `$1A00` cleared to `$00`.
6. To cover the prompt path too, set the canary to `$A4`, select `S`, and issue
   `C` at `STR8-N>`. Again require `BOOT COLD`, `RAM ZERO OK`, and `$1A00`
   cleared to `$00`.

Do not exercise `J0`-`J2`, installation, erase, copy, adopt, or directory
refresh as part of this narrow top-sector gate.

## Gate 6: installed-byte identity

From HIMON, capture these dumps:

```text
>D F000 F00F
F000: 4C 49 F0 4C 26 FC 4C 32 FC 4C 4F F9 53 52 02 03

>D FC9E FCAA
FC9E: 0D 0A 53 54 52 38 2D 4E 20 31 2E 32 32

>D FD55 FD5C
FD55-FD5B must be FF; FD5C begins 4C 29 02

>D FFFA FFFF
FFFA: D2 F0 00 F0 E6 F0
```

## Acceptance record

This gate was accepted by the operator on 2026-08-19 using the linked retained
transcript and the explicit operator clearance recorded above.

Append the complete terminal transcript to the hardware log before calling
v1.22 accepted. Record the candidate hashes, old-sector backup receipt, visible
STR8-N and HIMON identities, automatic post-update warm result, physical-RESET
warm result, canary dumps, explicit selector `S`/`W`/`C`, prompt `W`/`C`,
`J3` results, and installed-byte dumps. Do not promote the v1.22 manifest into
R-YORS or replace the v1.21 rollback artifacts until this gate passes.
