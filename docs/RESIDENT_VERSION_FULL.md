# Complete resident VERSION command — Phase 9

The entire current VERSION command assembles with unchanged resident ASM:
**636 bytes at `$6E00–$707B`**, ending exclusively at `$707C`. This includes its
header, display logic, text, working data, CRC calculation, board-name journal
reader and board-name display. All 64 source-defined symbol values match the
host link after restoring two explicit intermediate aliases.

The source authority remains the three existing files in
[src/current/version](../src/current/version/version.asm): `version.asm`,
`version-links.inc` and `version-board.inc`. None was edited.
[prepare_resident_version_full.py](../tools/prepare_resident_version_full.py)
generates the [resident source](../tests/baselines/phase9-evidence/prepared/version.asm)
from their pinned bytes. Generated files are proof inputs, not a second source
tree. Firmware images, installers and Phase 1–8 baselines remain unchanged;
neither board was contacted.

## Complete source preparation

The narrow recipe expands exactly the two includes in their original positions,
removes the MODULE/XDEF/CODE/ENDMOD wrappers and comments, and adds `ORG $6E00`
and `END`. Existing internal labels, instruction order, branch trampolines,
duplicate-address labels, data order and fixed ABI values remain intact.
Label addresses are assembled from the source, not substituted from a map.

| Host identifier | Intermediate resident identifier |
| --- | --- |
| `BOOT_CHOICE_SLOT` | `BOOT_CHOICE` |
| `BAD_RUNNING_TEXT` | `BAD_RUN_TEXT` |

These are the only names exceeding the 15-character limit. Renaming applies
to complete identifier tokens outside strings and character literals; it does
not alter emitted text. The manifest maps all 64 original names to their
resident names, and the verifier checks every original value after reversing
that mapping. All six bootstrap imports are also checked against the current
bootstrap symbol map. VPTR and TZ_PTR retain `$D0` and `$D6`.

WDC DB becomes resident BYTE, with explicit colons on data labels. The actual
host link emits zeros for all five DS reservations, so these become explicit
`FILL count,0` statements:

| Reservation | Address | Bytes |
| --- | --- | ---: |
| MON_CALL | `$6F26` | 2 |
| TZ_SUM | `$6F28` | 2 |
| BN_TEXT | `$706E` | 8 |
| BN_SEQ | `$7076` | 4 |
| BN_FREE | `$707A` | 2 |

| Resident resource | Actual use | Limit |
| --- | ---: | ---: |
| Packed source | 4,611 bytes | 7,168 bytes |
| Source records | 303 | Positive unique 16-bit line numbers |
| Longest line | 59 characters | 120 characters |
| Symbols | 64 | 256 |
| Longest name | 15 characters | 15 characters |
| Output | 636 bytes | 12,544 bytes |

Body SHA-256:
`d61ce3177f8571d29c158e1c7436fca051f4c8e3be0cdfc96ad90157431d3747`.

The first four bytes are the existing `BS`, version 1, type 3 header.
**Executable entry is `$6E04`**, a JMP to DISPLAY_VERSION at `$6E07`.
The assembly origin and START are `$6E00`; they are not the executable entry.

## Assembly and packaging proof

[test_resident_version_full.py](../tools/test_resident_version_full.py) admits
the generated PASTE input and compares it with the canonical packed records.
It assembles twice in each CPU/monitor/EDU combination: eight configurations,
16 assemblies. Every run checks all 636 bytes, all 64 symbols, source text,
SYMS, S19 checksums and addresses, upper RAM, modeled flash and transfer counts.
The physical output buffer `$0200–$047B` never executes.

Resident S19 uses S9 origin `$6E00`; the host linker uses S9 `$0000`. Both
describe exactly the same S1 address/data range. Neither terminator replaces
the separately recorded executable entry `$6E04`.

The command is the first 636 bytes of a 2,048-byte VERSION asset stored at
B2:`$F800`. The loader validates and copies the whole asset to `$6E00–$75FF`
before executing `$6E04`. Substituting the resident body in memory leaves both
the entire asset and all 98,304 firmware bytes identical. Fill, embedded
power-fail worker, seal patch and vector tail remain unchanged. No replacement
asset or firmware candidate is published.

Thirteen host checks cover deterministic regeneration, refusal to overwrite,
independent changes to each of the three source inputs, and disposable
corruptions of firmware, VERSION asset, S19, map, symbol inventory and all three
staged sources. The preparer reuses the frozen earlier build validators and
adds full-command source, binding, alias and reservation checks.

## Runtime proof in CPU models

[test_resident_version_runtime.py](../tools/test_resident_version_runtime.py)
consumes the actual emitted profile binaries. It pairs host and resident
executions and compares output, registers, complete RAM, SRAM and bank hashes,
instruction counts, selected name/sequence/free slot, modeled I/O, and restored
PCR, monitor slot and selected-bank state. CPU writes to modeled flash raise.

The runtime matrix has **214 host/resident pairs, 428 executions**:

- 22 complete VERSION command pairs. All eight profiles run unnamed and
  eight-character names; each CPU's MON A/bare profile additionally runs a
  one-character name, latest/equal sequences and an empty-name tombstone.
- 192 separately scoped BN_READ/TZ_CRC pairs: all 24 journal fixtures in each
  of the eight profiles. These cover malformed, uncommitted and bad-CRC records,
  length/character/padding validation, numeric sequence ordering, first/free/last
  slots, full journals and currently accepted reserved-byte variations.

Full commands use actual monitor, loader, asset CRC, VERSION, bootstrap and
console instructions. The loader first validates the original sealed asset;
at `$6E04`, the fixture verifies the loaded host body and substitutes only the
636 resident bytes in modeled RAM. No console or bootstrap routine is stubbed.
The complete-command cases use the baseline valid A/B monitors and default A;
invalid-monitor and alternate default-selection permutations are not newly
runtime exercised. Their code remains included in the byte-equivalence proof.

The inherited model skips hardware discovery at `$E014`. To make the command
available, the fixture supplies the banner pointer `$EF06` at `$7D0F/$7D10`,
as the verified status-mode initializer publishes it, and the corresponding
EDU/bare mode. This is modeled discovery state, not a firmware patch. Existing
delay shortcuts also remain. No physical console, RTC, EEPROM, SRAM hardware
or electrical timing is qualified by these tests.

Current behavior is preserved even where it is more permissive than comments:
equal sequences choose the later record; sequence ordering does not wrap;
CRC-covered reserved bytes 17–27 need not be FF; byte 30 is ignored; and a zero
BN_FREE high byte denotes a full journal. Named display still performs its
two original journal scans. All CPU-executed bank/flash and SRAM contents remain
unchanged from their initialized fixture state.

[Phase 9 evidence](../tests/baselines/phase9.json) binds the prepared inputs,
assembly receipts, runtime receipts and preservation hashes. Preparation alone
does not mark resident verification complete; its manifest and the successful
test receipts are recorded separately.

## Reproduce offline

Use the installed WDC toolchain and existing model dependencies. Every output
path must be new:

```powershell
python -B tools/build_current.py --out BUILD/phase9-new
python -B tools/prepare_resident_version_full.py --build BUILD/phase9-new --out BUILD/resident-version-full-new
python -B tools/test_resident_version_full.py --build BUILD/phase9-new --prepared BUILD/resident-version-full-new --out tmp/resident-version-full-new
```

The verifier defaults to both CPUs, all eight assembly configurations and the
runtime matrix. Split runs can use `--mode assembly` and `--mode runtime`; a
runtime-only run also requires `--resident` pointing to its completed assembly
output directory. It validates that receipt before reading the emitted bytes.
Serial imports and network connections are blocked. All execution is offline.
