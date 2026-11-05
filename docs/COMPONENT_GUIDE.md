# STR8-N F / MON / UTIL / DEV

[STR8-N](https://github.com/95westus/STR8-N) is the canonical repository.
`main` contains current source; release tags identify the exact source and
downloads published at that time. Each component retains its own version and
generation. Foundation 0.3.0 does not assign a version to the whole family.

| Group | On the board | PC side and current source |
| --- | --- | --- |
| **F** | Frozen 4096-byte boot/recovery Foundation, BASE1 / PR05 | [Core](https://github.com/95westus/STR8-N/tree/main/src/core), [public includes](https://github.com/95westus/STR8-N/tree/main/src/include), [freeze manifest](https://github.com/95westus/STR8-N/blob/main/F_FREEZE.json) |
| **MON** | Optional A/B monitors; `REC> B` launches MON B, whose data-bank prompt can be `B3>` | [Monitor source](https://github.com/95westus/STR8-N/tree/main/monitors/src), [native components/services](https://github.com/95westus/STR8-N/tree/main/monitors/native) |
| **UTIL** | CONFIG, FLASH, CLOCK, MAINT, MEMORY agent, MAP, OPAQUE, READBACK, DEMO and shared services | [Host tools/build recipes](https://github.com/95westus/STR8-N/tree/main/tools), including Terminal and the MEMORY backup/restore CLI |
| **DEV** | ASM editor/assembler and DBG debugger; optional installed images or matching RAM packets | [ASM source](https://github.com/95westus/STR8-N/tree/main/monitors/devtools/base1/assembler), [DBG source](https://github.com/95westus/STR8-N/tree/main/monitors/devtools/base1/debugger) |

`B3>` identifies the selected data bank, not a third monitor or an F version.
`C B` in CONFIG saves MON B as default; `B 3 B000` followed by `C 3`
instead saves a bank-3 entry and selects that bank entry. Keep the existing
short commands and prompts. See the [component names](COMPONENT_NAMING.md).

## Source, releases and candidate kits

- **F:** [Foundation 0.3.0 release](https://github.com/95westus/STR8-N/releases/tag/v0.3.0),
  [operator ZIP](https://github.com/95westus/STR8-N/releases/download/v0.3.0/STR8N-F-BASE1-0.3.0.zip),
  [source ZIP](https://github.com/95westus/STR8-N/releases/download/v0.3.0/STR8N-F-BASE1-0.3.0-source.zip)
  and [Foundation manual](USER_MANUAL.md).
- **MON:** [Preserved MON preview](https://github.com/95westus/STR8-N/releases/tag/mon-g8-tools-preview1).
  Current MON source and the named candidate can differ from that release.
- **UTIL / DEV:** Current named components are built from `main` using the
  [source build and packaging recipe](CONSOLIDATION_SOURCE_REVIEW.md).
  The current named MON/UTIL/DEV kit has no dedicated published release yet.

[All releases](https://github.com/95westus/STR8-N/releases) and the
[release index](https://github.com/95westus/STR8-N/blob/main/RELEASE_INDEX.md)
include historical full-system versions. Original tags, asset names and bytes
remain unchanged. Historical `STR8N-F-*`, `rec/MAINT.bin` or
`developer/ASM-RAM.bin` names refer to those packages, not an instruction to
rename an old binary into a newer component.

## On-board and PC workflows

| Task | On-board side | PC side and guide |
| --- | --- | --- |
| Boot/recovery and saved defaults | F; CONFIG changes saved entries/defaults | [Foundation manual](USER_MANUAL.md); Terminal CONFIG preset |
| Interactive inspection and launching | MON A/B; `VERSION`, `APPS`, `R ASM`, `R DBG` | [MON/UTIL manual](NATIVE_UTILITIES_MANUAL.md) |
| RAM program transfer | F raw `L`, or MON `S19` | [Terminal guide](SERIAL_CONSOLE.md), [file formats](FILE_FORMATS.md) |
| Flash-sector replacement | Matching OPAQUE/FLASH tool and its admitted target protocol | [OPAQUE host](https://github.com/95westus/STR8-N/blob/main/docs/OPAQUE_HOST.md), [OIP1](https://github.com/95westus/STR8-N/blob/main/docs/OPAQUE_PROTOCOL.md) |
| Backup/restore and load/offload | Temporary UTIL MEMORY agent | [MEMORY CLI](MEMORY_UTILITY.md); images and receipts stay on the PC |
| Assemble and debug | DEV ASM/DBG; paired providers where required | [DEV manual](DEVELOPER_MANUAL.md); ASM `S19` output is an address-bearing export |

To build from a repository checkout, use a new output directory:

```powershell
python -B tools/verify_base1.py
python -B tools/verify_component_inputs.py
python -B tools/build_named_components.py --out build/components
```

With Python 3.11+, Tk and pyserial 3.5 installed, launch the resulting kit:

```powershell
python build/components/str8n-terminal.py
python build/components/str8n-util-memory.py --help
```

From an extracted named kit, run its root `str8n-terminal.py` and
`str8n-util-memory.py` instead. Its `payload/` filenames are mapped by
`COMPONENTS.json`, `NATIVE-COMPONENTS.json` and `preset-assets.json`.
The manifest determines CPU, placement and hash; the extension alone does not.

The [qualification scope](QUALIFICATION_SCOPE.md) applies to both board and PC
tools. Loading a RAM tool borrows application RAM. Backup/restore covers the
documented memory regions, not a suspended CPU or every I/O register. Preserve
original owner RAM before loading a helper when those bytes matter.

## Foundation freeze

F remains **0.3.0 g00000001 / BASE1 / PR05**, exactly 4096 bytes, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
Current builds reuse it; documentation and MON/UTIL/DEV changes do not rebuild F.

A future boot/recovery defect or required Foundation contract change would
start a separately reviewed F candidate with a new generation and an explicit
compatibility decision. Preserve 0.3.0, its tag, binary and freeze record.
Qualification must cover the affected boot, recovery and ABI paths on the
intended hardware, including interrupted-update recovery when applicable.
There is no scheduled unfreeze, and this documentation update opens none.
