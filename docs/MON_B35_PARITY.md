# MON A/B: full 2.0b35 capability gate

**Current shipping authority (October 30, 2026):**
[one unified STR8N release, all b35 capabilities except ASM/DBG](UNIFIED_SHIPPING_RELEASE.md).
The older checklist below is historical planning evidence. Its ASM/DBG and
new WORKSPACE-message requirements do not override the current shipping scope.
Missing CLOCK SET/administration, CONFIG and b35 command behavior remain open;
the g8 preview or a generic soak does not close them.

Updated 2026-10-29. A and B remain identical. Product naming is **STR8-N / MON
A/B**, with a separate monitor version and generation. Mona is retired; old
artifact filenames, hashes, installed g6 banners and acceptance receipts remain
historical evidence. New build outputs use `STR8N-MON-...` and
`STR8N-WORKBENCH-...`. [g8/WB2 g4 and services](MON_AB_G8_2512_ACCEPTANCE.md) are installed on 2512
for the documented subset. Full b35 parity remains open.

## Baseline and completion rule

The reference is the preserved local `BUILD/v2-beta35-candidate` source/build,
version **2.0b35**, build SHA-256
`2f5319ab1d7bc751d61bc4b00af225466d83b983bc7e5806a33417940be68365`.
Its `candidate/manifest.json`, `overlay/help.json`, `inputs/launcher.asm`,
`inputs/str8n-v2-sr.asm`, `xip/source/utilities.asm`, `store/source/`,
`assembler/` and `batch/source/batch-gate.asm` are the review baseline.
The archived candidate's own installation prohibition remains in effect; use
it as evidence/source, not as a flash image. The later g0034/2.0rc1 reference
is additional compatibility evidence, not a substitute for this baseline.

**The target is everything 2.0b35 can do**, plus the owner's explicit AUTO
flash/SSRAM and WORKSPACE-message requirements. A command name or retained old
binary is insufficient: its successful workflow, failure paths, data formats,
return path and storage ownership must work under frozen BASE1. No legacy
private entry is called merely because its image is still present.

Current evidence is [g8 / WB2 g4 on 2512](MON_AB_G8_2512_ACCEPTANCE.md).
The build manifests intentionally retain their original build-only status;
the later acceptance receipt supplies execution evidence for those exact bytes.

## Required parity checklist

| Capability | Current implementation/evidence | Required before completion |
| --- | --- | --- |
| D/M/G/L and bank prompt | Hex/ASCII dump, inline RAM Modify, force `!M`, bank selection, G and ROM raw-BIN L qualified | Interactive editing/continuation, legacy S19 monitor loading, cancellation and application return workflows; retain raw BIN and F's existing semantics |
| `T` Table | WB2 lists selected-bank flash SR01 records | Bank/range listing and automatic discovery across admitted flash and SSRAM PROGRAM; show backend/location, pending/corrupt records and unambiguous identity |
| `S` Store | Explicit address or AUTO append start in a declared B0/B1 AREA; preflight/YES/commit-last/restore/run qualified in WB2 g4 | SSRAM PROGRAM Store/AUTO; correct capacity/overlap checks, duplicate policy, readback and source/output SAVE integration |
| `R` Restore/run | Selected-bank unique name or address, optional load-only L | Automatic resolution across admitted flash and SSRAM PROGRAM; explicit backend/location override, ambiguity refusal, checked load/run and return |
| `BATCH cmd;cmd` | WB2 g4 (g3 implementation retained) returning-module subset installed; normal/failure paths and positive ESC/Ctrl-C stop qualified | Complete core/native-app parity: legacy 34 text-byte queue, separator checks before execution, failure stop and checked prompt/handoff behavior |
| `APPS` and named launch | Native service catalogue/dispatcher installed; legacy images retained and unqualified | Discover/validate/list installed compatible apps and availability; named launch/return for native services and owner apps; do not list incompatible retained bytes as runnable |
| SOURCE / ASM | Source and assembler assets retained | Edit, assemble, diagnostics, symbols/output ownership, Store/Restore/source SAVE/LOAD, run and return; no edits to PROGRAM by WORKSPACE logging |
| DEBUG | Retained legacy component, incompatible private bindings | Disassembly, registers, memory, RAM breakpoints, step/continue and exit/hook restoration; mode-specific CPU qualification; no implicit flash breakpoint erase |
| M1/M2/M3 and W | Direct E-based M1/M2/M3 and all 32 W counters qualified; core maximum retained | Grid/ranges/full tracked counts, WDC recognition, reservations and compatible app/record boundaries; concise shared physical-health caveat |
| F/I, MAINT | `!M` provides guarded 1-to-0 bytes; legacy maintenance retained | Familiar journaled edit/erase, sector buffer/read/edit/fill/CRC/write/verify, copy/compare and flash/SSRAM transfer; protected F/C/D; no implicit owner-sector allocation |
| CONFIG, C/P/J, U, opaque images | Matching standalone CONFIG/OPAQUE tools and reviewed host updaters | Coherent monitor launch, boot enable/entry/default/delay, deliberate bank navigation, admitted A/B update and opaque installation; preserve boot/wear history |
| EDU, SRAM, WORK | Explicit EDU and guarded SS1 layout/capacity reads qualified; SS2/fallback not positively hardware-qualified | Full PROGRAM manager, mount/query/save/restore/run/delete/reclaim/explicit format; WORK services and existing allocation ownership; bounded absence/error handling |
| Rich board/status and TIME/CLOCK | Explicit TIME sample; core status rows; no automatic profile collection | Board/profile identity, EDU/RAM/PROGRAM/WORKSPACE, calendar/local/UTC/offset and clock service, backup/power-fail history and battery service policy; label health/prior wear with the existing `*` caveat |
| Python terminal | Existing N-F console and raw-BIN workflow retained | Command/module/loader workflow documented alongside console function keys; loader choice and cancellation remain explicit |
| Persistent messages/metadata | Not implemented | Separate append-only allocation in validated SSRAM WORKSPACE only; read/replay and absence errors; no PROGRAM-format or C/D journal reuse |

SR01 has no payload checksum; preserve that compatibility fact. New formats or
checks must be named and versioned, not silently attributed to legacy records.
Battery policy and tracked erase counts do not measure battery health or prior
physical flash wear. Missing EDU/SSRAM must report unavailability promptly.

## Store AUTO and separate discovery contract

AUTO means **determining the storage start address** for Store. The owner
clarified this on 2026-10-29. It does not choose a backend or run an image.
Table/Restore discovery is a separate required feature. T/S/R retain one front
end for flash and SSRAM PROGRAM, with explicit bank/address/backend selection.

- `T`: enumerate the configured/admitted scope on both backends and identify
  each result by backend and bank/address or SRAM record identity.
- `S ... AUTO ...`: determine a start only inside the already selected, admitted
  record arena or mounted PROGRAM allocation. Display the bank/backend and start
  before confirmation. Never guess ownership from erased bytes or silently spill
  to another backend. Full, unavailable, unmounted or overlapping storage fails
  clearly. WB2 g4 qualifies append-tail placement for flash; PROGRAM is pending.
- `R name [L]`: search the configured scope, refuse multiple matches, validate
  the chosen record and its destination before copying, then load only or run as
  requested. An explicit qualified location resolves ambiguity.
- Owner opaque images, source/compiler reservations, F and C/D are excluded
  from allocation. WORKSPACE messages never consume PROGRAM slots or payload.
- Backend adapters expose success/failure/cancellation consistently to BATCH.
  A queued line is never fed to a YES prompt, loader or unrelated app prompt.
  No batch or AUTO setting removes a flash/format confirmation.

## Next checkpoints

1. **Module/layout and storage contract:** WB1 is full. Review replacement or
   split-module entry/loading/state ownership and flash/PROGRAM allocators using
   the preserved b35 sources. Preserve the core fallback, application RAM limits,
   source/output separation and explicit owner admission. No new flash regions
   are allocated by this plan and no F ABI expansion is required.
2. **Dual-backend T/S/R and APPS:** implement complete mounted-storage workflows,
   compatible discovery and deliberate launch/return. Qualify RAM first with
   freshly backed-up, explicitly admitted disposable targets.
3. **BATCH:** reconnect the checked command-result interface and bounded queue;
   qualify normal sequences, bad separators, failure stop, ESC, missing modules,
   duplicate names, unavailable/full storage, prompts and return from native apps.
4. **Source/ASM/DEBUG, maintenance/config/maps and status:** port each baseline
   workflow, updating this checklist with an exact artifact and live evidence.
   Completion requires all rows, not only this checkpoint's command subset.

Build once per concrete implementation increment. No routine CPU model, offline
regression group or reproduction build. Before any zero-C/D-erase trial, use
`tools/native_journal_room.py` against a fresh capture; peer-rotation intent pages
are not ordinary append capacity. Preserve images, boot policy and owner RAM/ZP.
No board access, flash write, release ZIP or published download change is part
of this requirements/naming checkpoint.

## Built space, without rebuilding

`python tools/monitor_space.py` verifies hashes and erased trailing bytes in the
existing frozen F, g6 A/B images and WB1 g3. It reports built bytes, not source
estimates and not application/owner storage availability.

| Component | Region bytes | Linked/body bytes | Reserved bytes | Free bytes |
| --- | ---: | ---: | ---: | ---: |
| Frozen F | 4096 | 3697 | 32 vectors/tail | **367** |
| MON A g6 | 4096 | 3925 | 128 header/reservation | **43** |
| MON B g6 | 4096 | 3925 | 128 header/reservation | **43** |
| WB1 g3 code block | 5120 | 5088 | 2 CRC trailer | **30** |

F's space remains frozen. These remnants cannot hold full b35 parity; features
must use reviewed modules/layout. The renamed g7/WB2 candidates have separate
hashes and measured space: MON A/B each 36 bytes and WB2 3609 bytes. WB2 temporarily
expands the module to 4000-63FF with application RAM 0200-3FFF while loaded. This
does not close full workbench memory parity. Qualified g6 artifacts and their
installed banner are not renamed or rewritten in place. See the
[candidate checkpoint](MON_AB_G7_WB2.md).


## G8 installed checkpoint

[g8 acceptance](MON_AB_G8_2512_ACCEPTANCE.md) closes direct map/wear, the native
service front door, board-stored workbench loading, read-only CLOCK and MAINT
return on 2512. The initial five erases/six appends plus the reviewed WORK/ESC
repair total eight erases/nine appends, retaining all old journal rows and owner
RAM/ZP. Current free bytes: F 367, MON A/B 67 each, E 981, WB2 273. The refined
module uses 7KB rather than the earlier 9KB prototype.

Positive ESC and Ctrl-C cancellation during BATCH Table passed without executing
the next command. Provider-only and module-only CRC refusal/repaired admission
passed in RAM; installed B passed WORK routing and both cancellation keys.
The earlier size table is historical. Complete BATCH/core/app coverage, AUTO
flash/SSRAM T/S/R, advanced CLOCK/FLASH/CONFIG and source/ASM/DEBUG remain gates.

## WB2 g4 flash AUTO checkpoint

[2512 acceptance](MON_STORE_AUTO_2512_ACCEPTANCE.md) closes automatic flash
Store start-address selection, including complete/pending FF payload extents,
cross-boundary/full/corrupt refusal, NO and Store/Table/Restore/run. It uses
three erases/appends, restores B0 fully and preserves the fresh RAM/ZP snapshot.
Current free bytes are F367, A/B67 each, E981, WB2 **63**; the preceding g8 size
report is historical. A valid cached g3 was restored with owner RAM: B2/G8000
explicitly loads current flash g4. SSRAM PROGRAM Store/AUTO and cross-backend
Table/Restore discovery remain separate open ports. One ordinary journal append
remains; the next larger flash trial requires a reviewed C/D rotation scope.
