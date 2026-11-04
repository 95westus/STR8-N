# STR8-N component names

The family name is **STR8-N**. Component display names, release filenames and
current documentation use the same hierarchy:

| Group | Display name | Short commands |
| --- | --- | --- |
| Foundation | STR8-N F | Existing recovery commands |
| Monitors | STR8-N MON, slot A or B | A, B; CONFIG C A / C B |
| Utilities | STR8-N UTIL CONFIG | CONFIG; B, C, W, Q inside CONFIG |
| Utilities | STR8-N UTIL FLASH | FLASH |
| Utilities | STR8-N UTIL CLOCK | CLOCK |
| Utilities | STR8-N UTIL MAINT | MAINT |
| Utilities | STR8-N UTIL MEMORY | MEMORY; backup, restore, load, offload, verify |
| Utilities | STR8-N UTIL MAP / OPAQUE / READBACK / DEMO | MAP, OPAQUE, READBACK, DEMO |
| Development | STR8-N DEV ASM | ASM, R ASM, APP ASM |
| Development | STR8-N DEV DBG | DBG, R DBG, APP DBG |

Other utility/provider exports use the UTIL group. Shared service sectors may
use UTIL SERVICES plus their bank/address suffix. BASE1/PR05 is Foundation's
compatibility profile, not another product family. A/B identify monitor slots;
B0–B3 identify flash placement. Owner-supplied opaque images retain their own
names. Command words, AP component identifiers, ABI symbols, protocol markers
and prompts such as ASM>, DBG> and MEMORY1> retain their existing spellings.

Each component retains its own version and/or generation. A new name does not
reset a generation, change a compatibility profile or assign a new firmware
version. Detailed manifests carry versions, generations, CPU and placement.

## Filenames

Public payload filenames are lowercase, hyphen-separated:

```text
str8n-f-0.3.0-base1-pr05.bin
str8n-mon-0.1.0-dev-g00000010-slot-a.bin
str8n-mon-0.1.0-dev-g00000010-slot-b.bin
str8n-util-config-0.3.0-base1-pr05-ram.bin
str8n-util-flash-g00000002-ram.bin
str8n-util-clock-1.10-b2-b000.bin
str8n-util-maint-2.4-ram.bin
str8n-util-memory-0.1.0-ram.bin
str8n-dev-asm-0.6-dev-g00000002-ram.bin
str8n-dev-dbg-g00000002-ram.bin
```

Suffixes distinguish RAM packets, monitor slots, CPU variants and separately
installed sectors. A filename is not permission to execute a sector header.
Load/entry addresses and dependencies remain in the component manifest.

## Current naming build

The shared catalog is `tools/product_names.json`. It also defines the full
copyright notice and its compact equivalent for constrained components.
New component identities and existing VERSION output include attribution;
the full MIT LICENSE accompanies the binary kit. Foundation stays frozen.
Reused shared service/data sectors retain their original bytes and are covered
by the kit LICENSE. Monitor identity text includes the compact notice.
The [repository/release consolidation plan](REPOSITORY_CONSOLIDATION_PLAN.md)
is documentation only; no migration is executed.
The copyright build has [2512 physical component acceptance](COPYRIGHT_2512_ACCEPTANCE.md).

Build the named BASE1
components into a new directory:

```powershell
python -B tools/build_named_components.py --out BUILD/str8n-copyright-r2
python -B tools/test_product_names.py --build BUILD/str8n-copyright-r2
python -B tools/test_product_names.py --build BUILD/str8n-copyright-r2 --cpu 65c816-e
python -B tools/test_memory_tool.py --build BUILD/str8n-copyright-r2/memory-agent-build
python -B tools/test_memory_tool.py --build BUILD/str8n-copyright-r2/memory-agent-build --cpu 65c816-e
```

The recipe checks the accepted candidate's input hashes, reproduces CLOCK
before changing its title, rebuilds CLOCK's internal pointers, repacks ASM,
updates AP/header/body checksums, retains DBG's paired source provider, seals
MAINT, and emits actual new utility/DEV banners. Foundation stays byte-identical;
monitor notice changes preserve slot headers and update their CRCs. Payloads and sector/CPU
catalogs use the canonical filenames, with no command renaming.

`COMPONENTS.json` inventories every named binary. `NATIVE-COMPONENTS.json`
retains the native install-planning schema with rewritten filenames and hashes.
The named MEMORY launcher is `python tools/str8n-util-memory.py`; the original
`memory_tool.py` module remains a compatibility entry point for existing scripts.

Launch the named terminal with `python tools/str8n-terminal.py --kit BUILD/str8n-copyright-r2`.
Its F5/F6/F7/F8 presets resolve canonical MAP/CONFIG/OPAQUE/DEMO files through
`preset-assets.json`. The key labels and short commands stay unchanged. The
generated kit also has a root `str8n-terminal.py` launcher.
`tools/package_named_components.py` packages the verified outputs without
rebuilding or accessing a board.

The named distribution remains a development candidate. Its copyright component
bytes passed the separate 2512 live installation and scoped tests linked above.
Other boards and an extracted interactive distribution still need acceptance.
No repository migration or release publication has been performed.

## Preserved identities and history

Published packages, release/source snapshots, original build outputs and dated
qualification records keep their original filenames, banners and hashes. Old
names in those records describe the bytes actually tested. Internal build
filenames and machine identity fields are compatibility interfaces, not product
display names. The frozen F descriptor and existing protocol prompts are
preserved. New current distributions use the naming build above rather than
renaming or relabeling old qualified artifacts in place.
