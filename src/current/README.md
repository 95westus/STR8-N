# Current STR8-N source

This is the authoritative development source for `fixed-f-flow-size`, derived from `fixed-f-size-recovery` and the established `asm-dev` system:
monitor/recovery, assembler with EQU/LST/SYMS/diagnostics, DBG1, named source storage,
MAINT, SRAM, WORK, EDU, CLOCK, providers and UCHESS. Its fresh full-system
image is SHA-256
`c85c4055eac41e5e522f1bc62f2bd354957018e3afc1ccdc25a91e52a55a980e`.
Monitor A/B each save 510 bytes, with their private batch/debugger bindings updated.
Fixed F shortens 69 journal branches and repacks the unchanged vector image,
then shortens 19 more conditionals and 17 private jumps with shared refusal paths,
leaving 204 contiguous free bytes plus 76 bytes in internal gaps (65 more free bytes). Recovery clears
inherited write status using existing padding. A/B, CRC bytes and CRC entry
addresses are unchanged from `monitor-size-branches`.
That image includes UCHESS and generic settings. The previously installed
2604 cleanup and each board's retained data are separate installation states.

Make current firmware changes here. `release/**` remains frozen release material.
The older source trees and transformation builders are in the
[verified history archive](../../archive/README.md), preserving their exact bytes
and original paths for restoration. The normal build uses `tools/build_current.py`;
historical code is absent from the current build and test dependency path.
Current installers use [the shared board/candidate workflow](../../tools/installer/README.md)
through `tools/install_current.py`, independently of the historical preparation chain.
The selected fixed-F installation uses the separately sealed `BUILD/fli-kit`
with its exact candidate hash and 2604-only plan. The root installer's default
`asm-dev` profile remains the historical regression target; it does not follow
`target.json` automatically. Installation requires fresh admission and backups.

## Source map

| Directory | Contents |
| --- | --- |
| `core` | Monitor, reset/recovery, RAM worker/vectors, S/R/T and named dispatch |
| `assembler` | Resident editor/parser/assembler with EQU, LST, SYMS and expanded diagnostics |
| `debugger` | Final DBG1 including console editing, decoding and stepping |
| `source-store` | Named editable-source envelopes and append-only flash storage |
| `maintenance` | MAINT, maps and source/firmware protection |
| `storage` | SRAM manager and editable-source adapter |
| `workspace` | WORK service and console |
| `edu` | EDU configuration and commands |
| `xip` | Utility image composition, shared bank gate and command dispatch |
| `clock`, `provider`, `gateway`, `journal`, `banner` | CLOCK and RTC/journal services |
| `status`, `battery`, `local`, `version`, `pf`, `mode`, `loader` | System providers and loaders |
| `batch`, `bootstrap`, `migration` | Batch gate and source-built migration/bootstrap templates |
| `include` | Shared header definitions; module-local forwarding files preserve include names |
| `apps/uchess` | Compact resident-assembler source, readable reference, credits and existing record |

The utility composition includes each subsystem in its original emission order.
Public ABI entries and component layout retain their established values. Eligible
monitor long branches are shortened and their private bindings relocated. The assembler's
source is assembled directly rather than transformed by historical Python builders.
The development extensions are ordinary source within `assembler/asm-app.asm`.

`layout.json` defines the current image segments and version identity.
`provenance.json` records the imported source bytes, extraction boundaries and
include-only changes for the original consolidation. `baseline.json` retains its
Phase 1/2 firmware hashes and symbols. `target.json` selects the independently
qualified fixed-F fixture in `tests/baselines/f-flow-current.json`.
The preceding F fixture remains in `tests/baselines/f-size-current.json`.
The Monitor A/B fixture remains in `tests/baselines/monitor-size-current.json`.
The earlier console-edit selection is preserved in the rollback evidence.
Historical paths in provenance are audit information; verification never reads them.

## Clean offline build

From the repository root, with Python and WDC02AS/WDCLN available:

```text
python -B tools/build_current.py
```

The default output is `BUILD/current`. Existing outputs are preserved; select
another fresh directory with `--out BUILD/current-r2` for subsequent builds.
`make`, `make all` and `make current` invoke the same implementation.
`make current-check` runs isolated build regressions; `make installer-check` runs
the offline installer suite, and `make check` runs both. Use
`CURRENT_OUT=BUILD/current-r2` to select a build output and `PYTHON=...` to select
an interpreter. Historical Make targets are available in the restored archive.
`tools/verify_current_sources.py` forwards to the current builder without a second recipe.

The legacy WDC tools require a short absolute output path. This command assembles this tree directly,
regenerates executable byte includes, composes the full image and compares all
20 recorded payloads plus all 29 linked symbol maps and the complete firmware
against the selected target fixture, while retaining the unchanged historical manifests.
Shared build code is in `tools/str8build`:
WDC invocation, S19/CRC formats, component images, baseline checks and one recipe.
It imports no historical builder, old BUILD output, qualification receipt,
serial library or emulator, and opens no board ports.

Output includes `firmware.bin`, `build-report.json`, `symbols.json`,
`source-symbols.json` and `debugger-build.json`, with compiler output under `s`,
`source` and `debugger`. The report must say `passed: true`. It does not create
an installer, qualify a board or authorize flashing. Existing application RAM,
storage formats, commands and CPU-mode requirements are unchanged. Building
requires the committed baseline manifests, the Phase 2 direct-source-build
evidence JSON, and the declared compatibility fixture. These are repository
inputs; no private historical qualification directory is required.

## Two preserved binary inputs

`apps/uchess/uchess-record.bin` is the same record used by the Phase 1 builder.
Its editable source is `uchess.a`, with the original license and credits here.
Phase 1 independently assembled that source using resident ASM on both 65C02
monitor-slot models and matched the complete 1,439-byte executable.

Phase 1 also recorded an inherited stale export at
`payload/debugger-a000.bin`. The old console-edit builder updated the debugger
in `firmware.bin` and `debugger/debugger-a000.bin` but did not refresh this
payload file. `tests/baselines/phase1-legacy-debugger.bin` preserves those exact
old bytes solely to reproduce that recorded export. The verifier labels it
`compatibility_only_artifacts` and uses the freshly assembled debugger for
the firmware and `debugger/debugger-a000.bin`. Do not use the compatibility
export as the current debugger component. Phase 1 records remain unchanged.

## Resident development direction

The readable sources and shared interfaces are now in one tree. Full resident
STR8-N rebuilding is not implemented by this consolidation. The existing ASM
limits remain 7,168 bytes of packed source and 256 symbols; large modules still
need a future resident-build decomposition. Console editing, source save/load,
EQU, LST, SYMS, diagnostics and DBG1 remain available exactly as in Phase 1.
