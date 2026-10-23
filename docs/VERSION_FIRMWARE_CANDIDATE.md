# Separate VERSION firmware candidate — Phase 11

`version-board-newline-tailcall-fw-v1` packages the verified Phase 10 VERSION
optimization into a separate firmware image. The current source tree, existing
firmware, installer registry and earlier baselines remain unchanged. Packaging
and verification are offline; neither board is contacted.

The candidate retains the current `2.0rc1` version, generation 50, compatibility
values, monitor identities, fixed interfaces and complete feature set. Its new
external candidate ID and SHA-256 distinguish it from the current image. It is
not registered as the installer's existing `asm-dev` candidate.

## Exact permitted changes

The image remains **98,304 bytes**, with three consecutive 32,768-byte banks in
**B1, B2, B3 order**. Each bank maps CPU addresses `$8000–$FFFF`.

| Complete-image offset | Bank and CPU address | Current byte | Candidate byte | Purpose |
| --- | --- | --- | --- | --- |
| `$FA5C` | B2:`$FA5C` | `$20` | `$4C` | VERSION's final named-board newline becomes a tail call |
| `$FFF6` | B2:`$FFF6` | `$86` | `$CF` | VERSION asset seal, first byte |
| `$FFF7` | B2:`$FFF7` | `$43` | `$2E` | VERSION asset seal, second byte |

All other image bytes remain identical. Only the B2:`$F000–$FFFF` sector changes;
the LOCAL application and gap preceding VERSION in that sector remain exact.
Both B1 and B3 remain byte for byte identical to the current build.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Current firmware | 98,304 | `aef72be59c25f106a4ba5d0d08c0241b5e6adb0471d12d809b5025726e721be6` |
| Candidate firmware | 98,304 | `4761393a3de28a1b3de76f96bf507857e40a0fd281066ae64dad31ec52f8b95d` |
| Candidate VERSION asset | 2,048 | `45eff91880623ee643feb329791d8691e9b9f4d21340b6748dbc205866597d7c` |
| Resident VERSION body | 636 | `04adfbaf52e8e36ece214c2ccfccab9fdcaf24a3623ca48bb3b22a77f443b2d7` |

## Body, seal and shared asset layout

The body and actual resident S19 export are inherited from the hash-pinned
[Phase 10 proof](RESIDENT_VERSION_CANDIDATE.md). All 636 body bytes and all 64
symbol values have already matched the independent WDC candidate. The sole
body change is the opcode at logical `$705C`: `JSR $7E7F` becomes `JMP $7E7F`.
The existing `BN_SHOW_DONE` label and RTS remain available to the empty-name
branch. The executable entry remains `$6E04`; the origin remains `$6E00`.

The current builder's `version_asset` recipe places that body in the existing
sealed asset. The unchanged loader reads B2:`$F800–$FFFF`, validates and copies
all 2,048 bytes to RAM `$6E00–$75FF`, checks the `BS`, version 1, type 3 header,
and enters `$6E04`.

| Asset offsets | ROM location | Loaded RAM | Contents |
| --- | --- | --- | --- |
| `$0000–$027B` | B2:`$F800–$FA7B` | `$6E00–$707B` | 636-byte VERSION body |
| `$0300–$05FF` | B2:`$FB00–$FDFF` | `$7100–$73FF` | Unchanged 768-byte power-fail worker asset |
| `$07F6–$07F7` | B2:`$FFF6–$FFF7` | `$75F6–$75F7` | Recomputed two-byte seal patch |
| `$07F8–$07FF` | B2:`$FFF8–$FFFF` | `$75F8–$75FF` | Unchanged vector tail |

The embedded power-fail asset retains its own CRC. Padding, working-data
layout, application header and vector tail are preserved. The tail remains
`FF FF 20 7E 64 7E 31 7E`, including NMI `$7E20`, reset `$7E64` and IRQ/BRK
`$7E31`.

The asset uses the existing CRC-16 calculation with initial value `$FFFF`.
The two-byte patch changes from `$8643` to `$CF2E`, in stored byte order, so the
CRC of the complete 2,048-byte asset is zero. Simply inserting the optimized
body into the old asset leaves an invalid seal. A generic trailing-CRC append
would also disturb its vector layout; the established asset recipe preserves
that layout while calculating the patch before the final eight bytes.

## Reviewable package

[package_version_firmware_candidate.py](../tools/package_version_firmware_candidate.py)
verifies the unchanged fresh build and pinned Phase 10 evidence before writing
only a new output directory. The default example location is
`BUILD/version-firmware-p11`.

The package has eight data artifacts:

- `firmware.bin`: the complete B1/B2/B3 candidate image.
- `banks/bank1.bin`, `banks/bank2.bin`, `banks/bank3.bin`: explicit bank images.
- `version/asset.bin`: the resealed asset.
- `version/resident.bin`: the verified resident body.
- `version/resident.s19`: the actual Phase 10 resident export, with 16-byte S1
  records and S9 origin `$6E00`.
- `symbols.json`: the unchanged symbol information accompanying the body.

`candidate-manifest.json` records the candidate identity, hashes, input
provenance, layout and permitted changes. `candidate.zip` contains exactly the
eight data artifacts and that manifest. The archive excludes itself and uses
sorted members, fixed 1980 timestamps and stored ZIP entries so repeated
packaging reproduces it byte for byte. External verification receipts bind the
archive hash without creating a manifest/archive hash cycle.

There is no ambiguous single S19 for the three-bank firmware. The resident
S19 describes only the 636-byte VERSION body at logical `$6E00`; its terminator
does not replace the executable entry `$6E04`.

No installer kit is produced. The manifest retains
`installation_permitted: false` and `hardware_qualified: false`. Existing
installer profiles and their identity checks remain intact; the new bytes
must not be relabeled as the old registered firmware.

## Offline verification

[test_version_firmware_candidate.py](../tools/test_version_firmware_candidate.py)
checks exact image differences, bank and asset relationships, hashes, CRCs,
vectors and inherited resident proof. Static checks cover deterministic
regeneration, refusal to overwrite, modified or extra files, archive membership
and bytes, stale baseline inputs, and refusal by the existing installer to
accept an unregistered candidate or new bytes under the current identity.

The completed runtime matrix passed **16 actual ROM-loader command comparisons**:
named and unnamed VERSION in each of eight CPU/monitor/EDU profiles. All
**six loader rejection cases** passed, covering CRC/header failures on both CPU
models, returning to the monitor without entering VERSION. Nineteen static
checks and fourteen packaging checks also passed. All 1,229 protected files,
including the 135 current source files and Phase 1–10 baselines, retain their
hashes. The receipts in [Phase 11 evidence](../tests/baselines/phase11.json)
record the completed counts and outcomes. The Phase 10 journal and exhaustive
tail-call proofs remain inherited through their pinned evidence rather than
being counted as newly repeated tests.

Each model uses the packaged firmware bytes as ROM. The real loader validates
and copies the asset; at entry, the fixture checks the complete loaded asset
and resident body. **No candidate RAM substitution is performed.** Negative
fixtures damage only their private modeled ROM copies. CRC failures must refuse
entry; a bad header with a valid recomputed seal independently exercises the
header check.

Differential comparison checks console output, registers, private RAM,
pointers, live caller frames, selected bank and persistent state. Each image's
modeled banks must remain unchanged from its initialized contents. Five RAM
bytes legitimately differ after the actual loader copy:

- `$705C`: the changed VERSION opcode.
- `$75F6/$75F7`: the two copied seal bytes.
- `$7C86/$7C87`: their copies in the loader's final 16-byte `V2_BYTES` buffer.

The verifier first checks these bytes against each image's expected values,
then excludes them and inactive stack residue from the state comparison.
All other private RAM, pointers and live caller frames remain exact. I/O
address auditing is distinct from an ordered bus-transaction comparison.

Timing is measured in separate scopes. VERSION entry up to its final RTS
retains the Phase 10 improvement: **nine fewer modeled cycles and one fewer
instruction for a named board**, and no change for an unnamed board.

The complete packaged command is slower in both CPU models. Its changed body
and seal cause 77 additional polynomial-XOR paths in the loader's existing
data-dependent CRC routine: 8,153 paths versus 8,076. Each extra path adds five
instructions and 18 modeled cycles. An independent bitwise CRC count agrees
with the linked CPU measurements.

| Measured scope | Instruction delta | Modeled cycle delta |
| --- | ---: | ---: |
| Loader before VERSION entry | +385 | +1,386 |
| Named VERSION body | −1 | −9 |
| Unnamed VERSION body | 0 | 0 |
| Complete named VERSION command | +384 | +1,377 |
| Complete unnamed VERSION command | +385 | +1,386 |

All eight configurations agree. The local tail-call optimization preserves
functional behavior; this packaged candidate has a net command-time regression.
The current firmware remains unchanged. These results describe CPU models,
not measured physical-board timing.

The inherited models supply discovery state and retain hardware discovery and
delay shortcuts. They initialize a selected monitor slot; this does not qualify
physical reset, peripherals or electrical timing. Serial imports and network
connections remain blocked, and CPU flash writes are refused. No board access,
installation or update to an existing firmware image occurs.

## Reproduce offline

Use the installed pinned WDC toolchain and existing model dependencies. Every
output directory must be new:

```powershell
python -B tools/build_current.py --out BUILD/phase11
python -B tools/package_version_firmware_candidate.py --build BUILD/phase11 --out BUILD/version-firmware-p11
python -B tools/test_version_firmware_candidate.py --build BUILD/phase11 --package BUILD/version-firmware-p11 --out tmp/p11-proof
```

The verifier defaults to all static and runtime checks. Use `--mode static`
or `--mode runtime` for separate runs, and `--cpu 65c02` or `--cpu 65c816-e` to
split runtime CPU coverage. Keep a distinct new output path for every run.
