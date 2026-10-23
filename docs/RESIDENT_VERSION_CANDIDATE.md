# Separate resident VERSION candidate — Phase 10

`version-board-newline-tailcall-v1` is a small optimization of VERSION's final
named-board newline. It is a separate RAM-body candidate. The current source,
firmware images and installers remain unchanged, and neither board is contacted.

The body remains **636 bytes at `$6E00–$707B`**, ending exclusively at `$707C`.
All 64 source-defined symbol values, the four-byte application header and the
executable entry at `$6E04` remain unchanged. There is exactly one byte change:

| Body offset | Logical address | Current byte | Candidate byte |
| --- | --- | --- | --- |
| `$025C` | `$705C` | `$20` — JSR | `$4C` — JMP |

Candidate body SHA-256:
`04adfbaf52e8e36ece214c2ccfccab9fdcaf24a3623ca48bb3b22a77f443b2d7`.
The unchanged current body's SHA-256 is
`d61ce3177f8571d29c158e1c7436fca051f4c8e3be0cdfc96ad90157431d3747`.

## Reviewed source recipe

[prepare_resident_version_candidate.py](../tools/prepare_resident_version_candidate.py)
reuses the immutable [Phase 9 preparation](RESIDENT_VERSION_FULL.md). It checks
the pinned Phase 9 manifest, preparation tool, three authoritative VERSION
inputs and complete current build before preparing the candidate. It retains
the baseline preparation in `BUILD/version-candidate-p10/baseline`.

The only optimization is at line 171 of
[version-board.inc](../src/current/version/version-board.inc). In the generated
copy, the final newline changes from:

```asm
JSR $7E7F
BN_SHOW_DONE:
RTS
```

to:

```asm
JMP $7E7F
BN_SHOW_DONE:
RTS
```

For a named board, the newline service returns directly to BN_SHOW's caller.
The existing `BN_SHOW_DONE` label and RTS remain available to the zero-length
name branch. Earlier newline calls and the two original board-name scans remain
unchanged.

The preparer applies this exact edit independently to the generated resident
source and a copied WDC board include. The copied WDC main and bindings include
retain their original bytes. It invokes the same pinned WDC assembler and
linker as the current build, then requires a contiguous 636-byte result, all
64 unchanged symbols and only the single opcode difference above. Resident
output is not used to construct the independent WDC reference.

| Resident resource | Candidate use | Limit |
| --- | ---: | ---: |
| Packed source | 4,611 bytes | 7,168 bytes |
| Source records | 303 | Positive unique 16-bit line numbers |
| Longest line | 59 characters | 120 characters |
| Symbols | 64 | 256 |
| Longest name | 15 characters | 15 characters |
| Output | 636 bytes | 12,544 bytes |

The generated inputs are `version.asm`, `version.paste.txt`,
`version.records.bin`, `expected.bin` and `manifest.json` under
`BUILD/version-candidate-p10`. The manifest records the reviewed patch,
baseline identity, fixed bindings, independent host reference and resource use.
Generated files do not replace the authoritative source tree.

## Optimization and behavior contract

On the named-board path, the final JSR and following RTS become one JMP.
This saves **nine modeled CPU cycles and one executed instruction** for that
newline. Two fewer return-address bytes remain pending during the newline
service. This is a claim about that call site; whole-command peak stack use is
not reduced by inference. The zero-length-name path is unchanged.

The candidate must retain console output, returned state, working data,
bootstrap behavior, journal selection, bank restoration and existing failure
behavior. The verification checks the complete command and board-name reader
against the unchanged current implementation. A separate BN_SHOW fixture
stresses flags and service return behavior under controlled stubs. Model
receipts record measured timing and instruction differences separately from
state equivalence.

## Offline verification scope

[test_resident_version_candidate.py](../tools/test_resident_version_candidate.py)
uses the actual linked monitor and resident ASM to admit the PASTE source,
assemble it twice per configuration, check every output byte and symbol, and
check S19 data and checksums. The complete matrix includes both CPU models,
both monitor slots and EDU/bare configurations. The physical assembler output
buffer at `$0200` is never executed; the candidate's execution address remains
`$6E00`, with entry `$6E04`. The resident S9 origin is not its application entry.

For complete-command execution, the existing loader first validates the
unchanged sealed VERSION asset. The fixture checks the loaded baseline body
and substitutes the candidate only in modeled RAM. It then compares the
current and candidate executions using the actual monitor, bootstrap and
console routines. The separate BN_SHOW flag-stress fixture uses controlled
service stubs and identifies that scope in its receipts.

The completed runtime matrix passed 22 complete-command comparisons, four
invalid-active command-body comparisons and 192 board-name reader comparisons,
plus 2,880 BN_SHOW tail-call comparisons.
All eight CPU/monitor/EDU profiles passed resident assembly twice, matching the
independent WDC candidate byte for byte with all 64 symbol values unchanged.
The receipts in [Phase 10 evidence](../tests/baselines/phase10.json) record the
completed counts and results. All 796 protected files, including all 135 files
in the current source tree and the Phase 1–9 baselines, retain their hashes.

The invalid-active probes cover the existing INVALID display and stop before
the final RTS. An invalid active-monitor value also makes the original loader's
monitor return unsupported; these probes do not claim a successful return to a
monitor prompt. All ordinary complete-command cases include that return.

The differential comparison checks exact console bytes, registers, private RAM,
pointers, live caller frames, banks and persistent state. It excludes only the
changed opcode and inactive stack cells left by returned calls. I/O auditing
checks allowed address sets and final state; it does not compare an ordered
bus transaction trace. The isolated tail fixture covers 256 raw status values
on 65C02 and 64 legal E-mode values on 65C816, with name lengths zero through
eight. Its out-of-ABI flag states are stress tests, separately identified from
the admitted IRQ-disabled, decimal-clear subset.

The inherited model supplies discovery state and skips hardware discovery at
`$E014`; existing delay shortcuts remain. These checks do not qualify physical
console, RTC, EEPROM, SRAM hardware or electrical timing. Serial imports and
network connections are blocked. All CPU execution and substitutions occur in
offline memory models, with no board access or flash writes.

No candidate sealed asset, firmware image or installer is generated. The
current asset's CRC validates its existing bytes, not this changed candidate.
Any later packaging would require a separately generated and verified seal;
the modeled RAM substitution grants no installation authorization.

## Reproduce offline

Use the installed pinned WDC toolchain and existing model dependencies. Each
output directory must be new:

```powershell
python -B tools/build_current.py --out BUILD/phase10
python -B tools/prepare_resident_version_candidate.py --build BUILD/phase10 --out BUILD/version-candidate-p10
python -B tools/test_resident_version_candidate.py --build BUILD/phase10 --candidate BUILD/version-candidate-p10 --out tmp/p10-proof
```

The verifier defaults to all assembly and runtime checks on both CPU models.
Use `--cpu 65c02` or `--cpu 65c816-e` to split CPU runs. Assembly-only runs use
`--mode assembly`. A runtime-only run uses `--mode runtime --resident PATH`,
where PATH is a completed assembly output directory; it validates that receipt
before consuming the resident-produced body. Keep distinct new output paths
for each split run.
