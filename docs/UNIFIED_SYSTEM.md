# STR8-N unified component source

`main` contains Foundation **F**, monitors **MON**, utilities **UTIL** and
assembler/debugger **DEV** in one repository. Start with the
[component guide](COMPONENT_GUIDE.md) for source and release links and the
[documentation index](README.md) for board and PC workflows.

| Group | Source ownership | Version and installation |
| --- | --- | --- |
| F | Boot/recovery core and public includes | Frozen 0.3.0 g00000001 / BASE1 / PR05; exactly 4096 bytes |
| MON | Optional A/B monitors and their admitted shared services | Separate monitor generation and slot headers/CRCs |
| UTIL | Board helpers, shared service sectors, PC Terminal and MEMORY CLI | Component-specific versions, RAM/sector/provider dependencies |
| DEV | ASM/DBG plus paired source/opcode providers | Separate versions/generations and RAM or AP/02 layouts |

The common [build recipe](CONSOLIDATION_SOURCE_REVIEW.md) reconstructs all
32 non-F inputs, emits 34 named payloads and reuses frozen F. See
[build policy](BUILD.md) and [helper status](BUILD_HELPERS.md). Historical
b15/PR04 builders and full-system images retain their original provenance;
they are not the current BASE1/PR05 build entry point.

## Board and PC are parts of the same workflow

On-board short commands remain `CONFIG`, `FLASH`, `CLOCK`, `MAINT`, `MEMORY`,
`R ASM`, `R DBG`, `C A` and `C B`. PC Terminal sends matching RAM packets;
UTIL MEMORY captures/restores documented memory regions through a temporary
agent. Source, raw binary, S-record, sector images and backups have different
roles: see [file/transfer formats](FILE_FORMATS.md).

Each board retains its own images, allocation, boot settings, journals, wear
history and optional devices. A shared source tree does not make those states
interchangeable. Use the actual board inventory and manifest for CPU, entry,
paired providers and sector placement. No board settings or saved owner bytes
are supplied by consolidation.

The current named kit is a development candidate. Preserved releases remain
available under their original tags and filenames; they do not contain every
later change on `main`. Hardware acceptance is limited to the exact bytes and
cases in [qualification scope](QUALIFICATION_SCOPE.md). F stays frozen.
