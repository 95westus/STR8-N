# STR8-N

STR8-N combines the frozen Foundation with monitors, utilities and ASM/DBG for
WDC W65C02SXB and W65C816SXB boards (65C816 emulation mode).

| Group | Components | Current source |
| --- | --- | --- |
| **F** — Foundation | STR8-N F 0.3.0 / BASE1 / PR05 | [Core](src/core), [public includes](src/include), [freeze manifest](F_FREEZE.json) |
| **MON** — Monitors | STR8-N MON, slots A/B | [Monitor source](monitors/src), [native components and shared services](monitors/native) |
| **UTIL** — Utilities | CONFIG, FLASH, CLOCK, MAINT, MEMORY, MAP, OPAQUE, READBACK, DEMO | [Host tools and build recipes](tools), [native utilities](monitors/native), [RAM helpers](src/core) |
| **DEV** — Development | STR8-N DEV ASM / DBG | [Assembler](monitors/devtools/base1/assembler), [debugger](monitors/devtools/base1/debugger) |

Commands stay short: `CONFIG`, `FLASH`, `CLOCK`, `MAINT`, `MEMORY`, `R ASM`,
`R DBG`, `C A` and `C B`. Components keep their own versions/generations.
Foundation 0.3.0 is F's version, not a shared version for MON, UTIL and DEV.

## Guides and downloads

Start with the [F / MON / UTIL / DEV guide](docs/COMPONENT_GUIDE.md),
[documentation index](docs/README.md) and
[BIN / S19 / S29 and transfer formats](docs/FILE_FORMATS.md) for board and PC workflows.

- **F:** [Foundation manual](docs/USER_MANUAL.md),
  [frozen 0.3.0 release](https://github.com/95westus/STR8-N/releases/tag/v0.3.0),
  [BASE1 operator kit](https://github.com/95westus/STR8-N/releases/download/v0.3.0/STR8N-F-BASE1-0.3.0.zip)
  and [release source kit](https://github.com/95westus/STR8-N/releases/download/v0.3.0/STR8N-F-BASE1-0.3.0-source.zip).
- **MON:** [Monitor/native utilities guide](docs/NATIVE_UTILITIES_MANUAL.md)
  and [preserved MON preview release](https://github.com/95westus/STR8-N/releases/tag/mon-g8-tools-preview1).
  Build current MON from the linked source using the recipe below.
- **UTIL:** [Component guide](docs/COMPONENT_NAMING.md),
  [MEMORY backup/restore guide](docs/MEMORY_UTILITY.md) and
  [current component build/package recipe](docs/CONSOLIDATION_SOURCE_REVIEW.md).
- **DEV:** [ASM/DBG guide](docs/ASM_DBG_BASE1_RAM.md) and
  [current component build/package recipe](docs/CONSOLIDATION_SOURCE_REVIEW.md).

The current named MON/UTIL/DEV kit is a development candidate built from `main`;
it has no dedicated published release yet. The
[release index](RELEASE_INDEX.md) links the preserved Foundation, MON preview and
historical full-system downloads. Those packages retain their original component
versions and qualification scope; they do not contain every current change on
`main`.

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
