# Resident batch gate — Phase 7

The existing 92-byte batch gate can be built by the unchanged resident ASM.
Its prepared source produces exactly the current host-linked bytes at logical
`$7C90–$7CEB`, with end symbol `$7CEC`. Both supported CPU models pass in both
monitor slots, with and without EDU. No firmware source or existing image was
changed, and neither board was contacted.

The authoritative source remains
[src/current/batch/batch-gate.asm](../src/current/batch/batch-gate.asm).
[prepare_resident_batch.py](../tools/prepare_resident_batch.py) generates the
resident input from those exact bytes. The [frozen prepared source](../tests/baselines/phase7-evidence/prepared/batch-gate.asm)
is a generated proof artifact, not another source authority. Changes should
begin in the authoritative tree in a later development phase, with an explicit
new baseline and preparation recipe.

## Preparation and module contract

The narrow recipe removes exactly `MODULE BATCH_GATE`, `XDEF B29_GATE_END`,
`CODE` and `ENDMOD`; strips outer indentation; prefixes `ORG $7C90`; and appends
`END`. Every original instruction and label remains in order, including the
NOP that preserves entry offsets. It expands no includes, changes no operands
and renames no symbols. Changed source, unknown syntax, duplicate names,
stale build inputs and existing output directories refuse before publication.

The [preparation manifest](../tests/baselines/phase7-evidence/prepared/manifest.json)
records the nine fields required by the [resident build contract](RESIDENT_BUILD_CONTRACT.md):
source identity, assembly extent/entries, storage placement, fixed bindings,
recipe, source admission, expected bytes, packaging and execution prerequisites.
It distinguishes the sole declared host export `B29_GATE_END` from all 11
symbols checked for equivalence. There are no symbolic imports or aliases;
the existing absolute ABI literals remain explicit in the source and manifest.

| Resident resource | Actual use | Limit |
| --- | ---: | ---: |
| Packed source | 689 bytes | 7,168 bytes |
| Source records | 49 | Positive unique 16-bit line numbers |
| Longest source line | 27 characters | 120 characters |
| Symbols | 11 | 256 |
| Longest symbol | 15 characters | 15 characters |
| Generated body | 92 bytes | 12,544 bytes |

Generated inputs include plain ASCII ASM, CR-delimited PASTE input and canonical
packed records with line numbers 10–490 and zero mode caches. PASTE admission
was checked against those exact records. Two successive ASM commands produced
the same body and all symbol addresses, including after caches were populated.

| Existing entry | Address |
| --- | --- |
| `B29_MON` | `$7C90` |
| `B29_CLOCK` | `$7C94` |
| `B29_ERROR` | `$7C98` |
| `B29_APP` | `$7C9E` |

Body SHA-256:
`8124f2af31b3b17590ceda5e6cdf56a6592af96899ad013b74db7da3534fb0e5`.

## Byte and packaging proof

[test_resident_batch.py](../tools/test_resident_batch.py) runs the actual linked
monitor and ASM instructions. Every one of the eight CPU/monitor/EDU
configurations admits the prepared source through PASTE, assembles it twice,
checks all 92 bytes against the independently decoded fresh WDC link, checks
all 11 symbols, displays SYMS and verifies S19 data, addresses and checksums.
The matrix contains 16 successful assembly invocations in total.

Host and resident S19 text differ legitimately: the host linker writes S9
`$0000`, while resident ASM writes its origin `$7C90`. Their decoded S1 bytes
and addresses match exactly. S9 does not establish a standalone executable
entry for this gate.

The normal build pads the body with four `$EA` bytes, yielding a 96-byte RAM
install image. Its two stored copies are in B3 at `$AF9F` and `$BF9F`, each at
offset `$F9F` within its monitor slot. Monitor entry copies these 96 bytes to
RAM `$7C90–$7CEF`. The verifier checks both monitor payloads and both full-image
placements. Substituting resident bytes plus the unchanged padding into an
in-memory copy leaves all 98,304 firmware bytes identical. Packaging comparisons
remain in memory; no candidate firmware or installer package is published.

Seven distinct host checks cover deterministic regeneration, refusal to
overwrite output, changed source, and corrupted firmware, S19, map and symbol
inventory. Tamper tests use disposable copies. Preparation verifies actual
source files, firmware, payloads and linked symbols rather than trusting a
successful-build flag alone.

The emitted body stays in physical output RAM `$0200–$025B`. Its execution is
blocked by the model test. Existing gate RAM and modeled flash remain unchanged;
no SRAM transfer occurs during the source/assembly/export checks. The gate
depends on initialized worker services, provider state, banking, an original
reader pointer and the existing CPU calling contract. Its byte equivalence
does not make it a standalone RAM program or install it into the current build.
Physical hardware timing and gate execution were not newly qualified here.

The preparer's manifest deliberately reports preparation only. The separate
[Phase 7 verification record](../tests/baselines/phase7.json) binds that exact
manifest to the successful model receipts and preservation checks.

## Reproduce offline

Use the already installed WDC tools and local CPU-model dependencies. Every
output path below must be new:

```powershell
python -B tools/build_current.py --out BUILD/phase7-new
python -B tools/prepare_resident_batch.py --build BUILD/phase7-new --out BUILD/resident-batch-new
python -B tools/test_resident_batch.py --build BUILD/phase7-new --prepared BUILD/resident-batch-new --out tmp/resident-batch-new
```

The final command defaults to both CPUs and all eight configurations. Serial
imports and network connections are blocked. Nothing in these commands opens
a board port or publishes a firmware change.
