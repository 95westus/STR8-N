# STR8-N

STR8-N combines the frozen Foundation with monitors, utilities and ASM/DBG for
WDC W65C02SXB and W65C816SXB boards (65C816 emulation mode).

| Group | Components | Source and guide |
| --- | --- | --- |
| Foundation | **STR8-N F**, BASE1 / PR05 | [Frozen platform](docs/USER_MANUAL.md), `src/core`, `src/include`, `F_FREEZE.json` |
| Monitors | **STR8-N MON**, slots A/B | `monitors/native`, `monitors/src`, [native utilities](docs/NATIVE_UTILITIES_MANUAL.md) |
| Utilities | CONFIG, FLASH, CLOCK, MAINT, MEMORY, MAP, OPAQUE, READBACK, DEMO | [Component names](docs/COMPONENT_NAMING.md), [MEMORY](docs/MEMORY_UTILITY.md), `tools` |
| Development | **STR8-N DEV ASM / DBG** | `monitors/devtools/base1/assembler`, `monitors/devtools/base1/debugger`, [ASM/DBG](docs/ASM_DBG_BASE1_RAM.md) |

Commands stay short: `CONFIG`, `FLASH`, `CLOCK`, `MAINT`, `MEMORY`, `R ASM`,
`R DBG`, `C A` and `C B`. Components keep their own versions/generations.

## Build and use

[Build and verification](docs/CONSOLIDATION_SOURCE_REVIEW.md) describes the
complete source recipes, WDC toolchain requirements and offline tests.

```powershell
python -B tools/verify_base1.py
python -B tools/verify_component_inputs.py
python -B tools/build_named_components.py --out build/components
```

The build reconstructs every non-F binary input from source. F stays at
0.3.0 g00000001 / BASE1 / PR05 and is never assembled by this recipe.
Use a new output directory. See [qualification scope](docs/QUALIFICATION_SCOPE.md)
before installation, [helper status](docs/BUILD_HELPERS.md) for supported entry
points, and [optional local board profiles](docs/BOARD_PROFILES.md) for the terminal.

## Releases and preserved history

[All releases and downloads](https://github.com/95westus/STR8-N/releases) are indexed in
[RELEASE_INDEX.md](RELEASE_INDEX.md). Existing Foundation and historical full-system
versions remain distinct lines; their assets keep original names and bytes.

Main contains the Foundation-based F/MON/UTIL/DEV tree. The previous STR8-N main
is retained at `archive/str8-n/main-before-foundation-20261104`. Foundation repository branches and PR refs are retained
under `archive/str8n-f/*`; its original tags are preserved unchanged. The merge
keeps both published histories. [Archived PR/release records](docs/archive/str8n-f/README.md)
retain source service metadata. STR8N-F is not deleted by this consolidation.

Project code uses the [MIT license](LICENSE). Keep the separate
[third-party notices](THIRD_PARTY_NOTICES.md) and historical release notices.
