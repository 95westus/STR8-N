# Cached VERSION candidate — Phase 11 revision 2

`version-cached-name-fw-v2` is a separate resident-built VERSION candidate
that improves the complete command in every tested offline case, including its asset loader. The
current source, firmware, installers and Phase 1–11 evidence remain unchanged.
The [first Phase 11 candidate](VERSION_FIRMWARE_CANDIDATE.md), including its
measured slowdown, remains preserved as its own result.

This revision retains the Phase 10 final-newline tail call and avoids reading
the same board-name journal twice during named VERSION display. The body stays
**636 bytes at `$6E00–$707B`**, with executable entry `$6E04`. All 64 existing
symbol values remain unchanged. One private symbol is added:
**`BN_SHOW_CACHED = $7047`**. The published firmware interfaces are unchanged.

## Small source change

The existing main command already calls `BN_READ`, loads `BN_LENGTH` and
branches to the unnamed display when that length is zero. Its named path now
calls `BN_SHOW_CACHED` instead of `BN_SHOW`.

The original callable reader/check remains intact:

```asm
BN_SHOW:
JSR BN_READ
LDA BN_LENGTH
BEQ BN_SHOW_DONE
BN_SHOW_CACHED:
LDX #<BN_LABEL
```

The new label emits no bytes. A direct call to `BN_SHOW` continues to perform
its own journal scan and empty-name check. The private cached entry requires a
completed `BN_READ`, a validated nonempty name in `BN_TEXT/BN_LENGTH`, and no
interleaved writer. The command has already completed the read and checked the
nonempty length before taking this entry; journal stability is an additional
calling condition.

For a stable journal, repeating `BN_READ` produces the same selected name,
sequence, free-slot result, working data, pointers and register state. At the
cached entry, the main command has already established the same A and N/Z
values as the skipped length check. The scan's final C/V and X/Y values are
also unchanged for the same journal. The label/text printing and final newline
then follow the existing instructions.

This contract requires a stable journal throughout the command and no
interleaved writer. IRQ-disabled execution alone does not exclude a custom NMI
handler that changes the journal or borrowed state. Concurrent journal mutation
and arbitrary interrupt interleaving are outside this candidate's equivalence
claim. The modeled tests enforce stable bank contents and the existing
nonreentrant monitor/application calling conditions.

The intentional internal differences are one fewer journal scan on the named
command path and its two fewer PCR writes. Final PCR, selected bank, console
output, registers, pointers, private state and live caller frames must match.
Exact I/O transaction-count equivalence is not claimed. The unnamed command
still performs one scan; the named command performs one instead of two.

## Exact bytes and resident resources

Relative to the unchanged current firmware, the complete image changes only:

| Complete-image offset | Bank and CPU address | Current | Candidate | Purpose |
| --- | --- | --- | --- | --- |
| `$F85F` | B2:`$F85F` | `$3F` | `$47` | Main JSR target becomes `$7047` |
| `$FA5C` | B2:`$FA5C` | `$20` | `$4C` | Retained final-newline tail call |
| `$FFF6` | B2:`$FFF6` | `$86` | `$C5` | Asset seal byte |
| `$FFF7` | B2:`$FFF7` | `$43` | `$24` | Asset seal byte |

The body differences are at offsets `$005F` and `$025C`, corresponding to RAM
`$6E5F` and `$705C`. The resealed 2,048-byte asset remains at B2:`$F800–$FFFF`
and loads to `$6E00–$75FF`. Its patch is `C5 24`, and its complete CRC is zero.
The embedded power-fail worker, vector tail, padding and all other firmware
bytes remain unchanged. Banks B1 and B3 are identical to the current build.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Resident body | 636 | `4c5f5a2a638fc66b17b847101cafcb04c908125ab0e8343789ccabcf36f79ac2` |
| VERSION asset | 2,048 | `7d766c7f885bb0b1fc76f77b91985b1670f42d03d7ea4ff28433fa364039b702` |
| Complete candidate firmware | 98,304 | `c78b0c93fa47011b2fe56075d21aaaba6a4e2928ecaf819b46efb9cab90b493a` |

| Resident resource | Use | Limit |
| --- | ---: | ---: |
| Packed source | 4,637 bytes | 7,168 bytes |
| Source records | 304 | Positive unique 16-bit line numbers |
| Symbols | 65 | 256 |
| Output | 636 bytes | 12,544 bytes |

The candidate retains version `2.0rc1`, generation 50, compatibility values,
monitor identity and existing behavior for journal validation and sequence
selection. Its external candidate ID and hashes distinguish it from current
firmware and the earlier candidate.

## Preparation, assembly and package

[version_cached_candidate.py](../tools/version_cached_candidate.py) checks the
frozen earlier evidence and current build, prepares the resident source and
independently assembles the corresponding copied WDC sources. Internal label
addresses are assembled from source. The recipe adds the private label, changes
the main call and retains the previously verified tail call; it does not edit
the authoritative VERSION files.

[test_version_cached_candidate.py](../tools/test_version_cached_candidate.py)
uses the actual monitor and resident ASM to admit the prepared records,
assemble twice per profile, and compare all bytes and all 65 symbols with the
independent WDC result. The complete assembly matrix has both CPUs, both monitor
slots and EDU/bare configurations: eight profiles and 16 assemblies.

Packaging consumes the actual resident binaries and S19 exports from successful
assembly receipts. It requires all eight profiles to agree before resealing the
asset and composing the separate firmware image. The physical resident output
at `$0200` is never executed.

The package retains the explicit B1/B2/B3 order and contains eight data files:
`firmware.bin`, three `banks/bankN.bin` files, `version/asset.bin`,
`version/resident.bin`, `version/resident.s19` and `symbols.json`. The symbols
inventory adds only `BN_SHOW_CACHED` to VERSION's existing symbols; other linked
units remain unchanged. The resident S19 describes the body at `$6E00`, with
16-byte S1 records; it is not a three-bank firmware S19 or an entry at `$6E04`.

`candidate-manifest.json` records provenance, hashes and scope. The deterministic
`candidate.zip` contains those eight files and the manifest, with sorted stored
members and fixed timestamps. It excludes itself. No installer kit or registry
entry is created; installation permission and hardware qualification remain
false.

## Runtime proof and timing scope

[test_version_cached_runtime.py](../tools/test_version_cached_runtime.py) uses
the complete candidate image as modeled ROM. The real loader validates and
copies the asset before executing VERSION. No application RAM substitution is
used. Model snapshots are separated by image identity.

The completed full-command matrix passed **60 baseline/candidate pairs**: all 24
existing journal fixtures on each CPU's MON A/bare profile, plus named and
unnamed cases in each of the other six profiles. All six CRC/header refusal
probes passed: invalid assets never entered VERSION and returned to the
monitor. All 16 resident assemblies and 24 static checks also passed. The
[revision 2 receipt](../tests/baselines/phase11r2.json) records the completed
results and preserves the earlier candidate separately.

The journal fixtures cover malformed and uncommitted records, CRC/name/padding
validation, full journals, numeric sequence comparisons, equal sequences,
tombstones and the currently accepted reserved-byte behavior. Current quirks
are retained. The reader remains unchanged; the new command path must reproduce
its final state while avoiding the redundant second read.

Differential comparisons check exact console bytes, registers, private RAM,
pointers and live caller frames. Each image's bank and persistent contents must
remain unchanged. Six expected RAM bytes differ because of the loaded image:
`$6E5F`, `$705C`, `$75F6/$75F7` and the loader scratch copies at
`$7C86/$7C87`. Their concrete values must be checked against the selected image
before excluding them and inactive stack residue. All other RAM remains exact.
The deliberately reduced reader/PCR operation counts are recorded separately.

Timing includes the loader. An independent bitwise CRC calculation gives
**8,069 polynomial-XOR paths** for this asset versus **8,076** for the unchanged
current asset. The linked CPU measurements confirm **35 fewer instructions
and 126 fewer modeled loader cycles**. The unnamed body does not
use the cached entry, so its complete-command saving comes from the
loader. Named bodies additionally avoid the second journal scan, duplicate
length check and the already optimized newline call.

Runtime receipts measure loader, VERSION body and complete command separately.
All 60 paired tests improved end to end: 50 named cases and ten unnamed cases.

| Complete command | Modeled cycles saved against current firmware |
| --- | ---: |
| Named board, across tested journals | 24,823–253,292 |
| Unnamed board | 126 |
| Eight-character example in every CPU/monitor/EDU profile | 25,126 |

The named range depends on how much work the second journal scan would have
performed. The full-journal fixture saves the most. Registers, output, final
private state and live caller frames remain equivalent under the calling
contract above. The earlier candidate's measured slowdown remains recorded in
its original evidence. All 1,618 protected files, including the 135 current
source files and Phase 1–11 baselines, retain their hashes.

All results are offline CPU-model results. The inherited discovery/delay
shortcuts and selected-monitor initialization remain; physical reset,
peripherals and electrical timing are not qualified. Neither board, existing
firmware nor installer configuration is changed.

## Reproduce offline

Use the pinned installed WDC toolchain and existing CPU-model dependencies.
Reuse the verified unchanged build or make a fresh build in another new path.
Preparation, proof and package output directories must all be new:

```powershell
python -B tools/version_cached_candidate.py prepare --build BUILD/phase11 --out BUILD/version-cached-r2
python -B tools/test_version_cached_candidate.py --build BUILD/phase11 --prepared BUILD/version-cached-r2 --package BUILD/version-cached-fw-r2 --out tmp/vcr2-proof
```

The default verifier mode `all` performs assembly, packaging, static checks and
runtime verification. Split runs use `--mode assembly`, `--mode package` or
`--mode runtime`. CPU filters are `--cpu 65c02` and `--cpu 65c816-e`. Package and
runtime split runs require `--assembly` for each completed assembly output
directory; packaging requires all eight profiles. Runtime consumes an existing
package. Keep distinct new output paths for each run.
