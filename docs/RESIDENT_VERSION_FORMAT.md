# Resident VERSION formatting helpers — Phase 8

The existing VERSION formatting helper block builds with unchanged resident
ASM and matches the current host build exactly: **35 bytes at `$6EBB–$6EDD`**,
ending exclusively at `$6EDE`. The selected block contains `SLOT_LETTER`,
`MON_PRINT` and `PRINT`, with their internal branch labels. It excludes the
rest of the 636-byte VERSION command, its string data and board-name helpers.

The authoritative source remains
[src/current/version/version.asm](../src/current/version/version.asm).
[prepare_resident_version.py](../tools/prepare_resident_version.py) extracts
source lines 97–118 and generates the [prepared input](../tests/baselines/phase8-evidence/prepared/version-format.asm).
That input is a generated proof artifact. No authoritative source, existing
firmware image, installer or previous baseline was changed. Neither board was
contacted.

## Source preparation and bindings

Preparation retains all 22 original helper lines in order and spelling, strips
outer indentation, prefixes the following bindings/origin, and appends `END`:

```asm
VPTR EQU $D0
MON_CALL EQU $6F26
ORG $6EBB
```

Defining VPTR before the instructions preserves the original zero-page forms
for `STX`, `STY`, indirect-indexed reads and `INC`. MON_CALL remains an absolute
indirect vector. No names are shortened, includes expanded or data translated.
The output service literal `$7E6D` remains unchanged and is verified against the
current RAM-vector map.

| Entry or binding | Address | Contract |
| --- | --- | --- |
| `SLOT_LETTER` | `$6EBB` | Input A selects the slot letter; tail-calls console output |
| `MON_PRINT` | `$6EC6` | Dispatches through the initialized MON_CALL pointer |
| `PRINT` | `$6EC9` | X/Y point to a NUL-terminated string; emits bytes through console output |
| `VPTR` | `$D0/$D1` | Borrowed monitor zero-page pointer, modified by PRINT |
| `MON_CALL` | `$6F26/$6F27` | Existing VERSION state containing an indirect formatter target |

Actual resident admission uses **26 records, 371 packed bytes and eight
symbols**: six labels plus the two bindings. The longest line is 18 characters
and longest symbol is 11. Records have line numbers 10–260 and zero canonical
mode caches. PASTE must reproduce those records exactly; assembler mode caches
may subsequently change while source text remains unchanged.

Body SHA-256:
`e5d6900a166da102a7ce245738c159d9c5c2dd46b58f8a77fd11ae40dc9075b5`.

The [preparation manifest](../tests/baselines/phase8-evidence/prepared/manifest.json)
records the source pin, line mapping, imports, entries, output extent, storage,
packaging and execution prerequisites required by the resident build contract.
The preparer reuses the unchanged Phase 7 build validator and adds VERSION map,
S19, body, asset CRC, embedded worker, vector-tail and placement checks.

## Offline verification

[test_resident_version.py](../tools/test_resident_version.py) verifies actual
resident PASTE, two successive ASM commands, SYMS and S19 in every CPU/monitor/EDU
combination: **eight configurations and 16 successful assemblies**. Every run
compares all 35 bytes and all eight symbol values with the independently decoded
fresh host link. It checks source text, upper RAM, modeled flash and SRAM
transfer counts. The physical output buffer `$0200–$0222` never executes.

S19 exports the helper's logical addresses with valid checksums and S9 origin
`$6EBB`. The host file contains the whole VERSION command and S9 `$0000`; its
selected S1 address/data range is the comparison target. Raw S19 files describe
different extents and are not expected to match.

Separate isolated CPU fixtures execute both the host and resident helper bytes
at their original addresses, using controlled PUTC and indirect-formatter ABI
stubs. Each CPU runs 269 comparison cases:

- All 256 slot input bytes, verifying the existing A/B threshold behavior.
- Eleven string cases: empty, page crossing, high-bit bytes, lengths 255, 256,
  257 and 513, and the four current VERSION text strings.
- Two indirect formatter targets, verifying pointer selection and entry registers.

That is **538 host/resident behavior pairs and 1,076 helper executions** across
the two CPUs. Checks include expected output, matching traces/registers, return
stack balance, pointer/index rollover and RAM changes confined to the stack and
VPTR. The fixtures use IRQ masked, decimal clear and, on 816, E=1 with
DP/DBR/PBR zero. These are helper tests with ABI stubs; they do not qualify
physical console timing or execution of the complete VERSION command, loader,
bootstrap or board-name storage paths.

Nine host checks cover deterministic regeneration, existing-output refusal,
changed source and disposable corruptions of firmware, VERSION asset, S19, map,
symbol inventory and staged source. Refusals occur before output publication.

## Packaging preservation

VERSION's 2,048-byte asset is stored at B2:`$F800` and loaded to RAM `$6E00`.
The helper occupies asset offsets `$BB–$DD`, corresponding to B2:`$F8BB–$F8DD`.
Substituting only the resident helper bytes into in-memory copies leaves both
the entire asset and all 98,304 firmware bytes identical. Other VERSION code,
text, fill, embedded power-fail worker, vector tail and CRC seal retain their
original bytes. No generated helper is installed into a board or the current
firmware build.

[Phase 8 evidence](../tests/baselines/phase8.json) binds the preparation manifest,
model reports, behavior fixtures and preservation checks. The preparer's own
manifest describes preparation only; successful verification is a separate
receipt tied to its exact hash.

## Reproduce offline

Use the installed WDC toolchain and existing local model dependencies. Each
output path must be new:

```powershell
python -B tools/build_current.py --out BUILD/phase8-new
python -B tools/prepare_resident_version.py --build BUILD/phase8-new --out BUILD/resident-version-new
python -B tools/test_resident_version.py --build BUILD/phase8-new --prepared BUILD/resident-version-new --out tmp/resident-version-new
```

The verifier defaults to both CPUs and all eight assembly configurations.
Serial imports and network connections are blocked; all execution uses offline
CPU/peripheral models or the isolated RAM fixtures.
