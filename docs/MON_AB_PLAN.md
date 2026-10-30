# MON A/B: five-checkpoint development plan

**Current shipping contract:** [one unified STR8N environment with all b35
capabilities except ASM/DBG](UNIFIED_SHIPPING_RELEASE.md). The checkpoint
history below does not replace that requirement. A/B have identical commands;
board-specific work is limited to affected CPU/transport/peripheral paths.

Branch: `codex/mona-monb`. Foundation: immutable N-F `v0.3.0`,
**0.3.0 g00000001 / BASE1 / PR05**, with exact dependency pins in
[base1-dependency.json](../monitors/base1-dependency.json).

## Checkpoints

| # | Work and deliverable | Exit condition | Current status |
| --- | --- | --- | --- |
| 1 | Review g0034 compatibility: identify exact A/B reference images, public/private calls, providers, entry shims and RAM ownership | A source-backed reuse/replace decision, named incompatibilities and an evidence inventory; no claim of execution compatibility | Initial review complete; [findings](MON_AB_COMPATIBILITY_REVIEW.md) |
| 2 | Define the shared monitor contract: entry/reentry, identity, console, parsing, bank selection, RAM/scratch, application launch and deliberate recovery return | Written interface and memory allocation; minimal command set and optional-provider behavior defined; no F changes | [G2 contract recorded](MON_AB_CONTRACT.md); expanded usability target specified separately |
| 3 | Implement the minimal shared monitor core: prompt, help, memory inspection and recovery return | A bounded candidate with local parser and public RAM console calls; no required E/B2/EDU provider; slot images and manifest produced by one planned build invocation | A/B/RAM candidates built once; exact hashes qualified on 2512 in checkpoint 4 |
| 4 | Qualify A and B as independent occupants using the same core | Correct slot/header/CRC/private binding and separate identity; authorized real-board entry, commands, handoff/return and preservation checks pass for both | [2512 acceptance passed](MON_AB_2512_ACCEPTANCE.md); originals and owner RAM restored |
| 5 | Complete the full 2.0b35 workbench on BASE1 | Every row of the [parity checklist](MON_B35_PARITY.md), including BATCH, AUTO flash/SSRAM T/S/R, APPS, source/ASM/DEBUG and status; A/B identical | [G8 / WB2 g4 installed on 2512](MON_STORE_AUTO_2512_ACCEPTANCE.md); flash Store/AUTO and existing S/T/R qualified; full parity remains open |

Checkpoint 4 proves the small A/B foundation; it is not acceptance of the full
usable monitor. Checkpoint 5 is incremental and does not change N-F 0.3.0.
Similar A/B candidates are useful
during development so one known-good image can be retained. Different roles
do not require unrelated codebases.

## Scope and working rules

- Keep F frozen; no new F ABI, release-tag change or replacement downloads.
- Keep monitor identity/generation separate from F generation and journal sequence.
- Share source modules compiled into independent slot images first. A mandatory
  shared flash provider is not required for the minimal monitor.
- Do not relabel or patch g0034's header to bypass BASE1's rejection. Its
  private implementation and entry shim are incompatible.
- Reuse logic only after reviewing its dependencies. No automatic full-system
  layout, RTC, EDU/SPI initialization, storage formatting or startup application.
- Begin with inspection rather than flash/config mutation commands. Existing
  CONFIG/OPAQUE tools remain separate until an explicit integration is designed.
- The practical monitor target includes intentional RAM Modify, loading, rich
  startup and an optional debugger. G4 delivers inline D/M and explicit force;
  L, interactive use and optional modules come next. Keep both slots alike.
  The 68 remaining g4 slot bytes do not bound the entire feature suite:
  separately admitted modules may supply larger features without changing F.
- No CPU model, offline regression group, reproduction build or speculative
  second build. Build only when the implementation is ready or changed code
  makes it necessary. File/source evidence checks remain part of this review.
- Hardware work needs an explicit target and reviewed writes, fresh backups,
  original owner RAM escrow and preservation/readback. The owner authorized the
  reviewed 2512/COM4 A/B trial; no other boards or power cuts are included.
  F stays frozen; failure before successful RAM smoke prevents monitor flashing.

## First review result

The exact g0034 A/B pair is **not a binary-compatible BASE1 monitor**. Header
contract mismatch already blocks launch. Its entry shim and optional utility
gateway also overlap BASE1 worker RAM, and several private call addresses moved.
The common public RAM facade remains available at the same addresses.

That review led to the shared BASE1 contract and new core qualified in checkpoints
2-4. Checkpoint 5 began with an explicit read-only RTCC adapter. The owner has
clarified the goal as a highly usable monitor resembling the familiar command
and startup experience. The [revised delivery order](MONA_USABILITY_PLAN.md)
puts basic Dump/Modify/loading first, followed by rich startup and DEBUG.
Dump/Modify and explicit force have now passed in g4 on 2512. A/B remain
identical; separate personalities are deferred. F stays frozen.

The owner's full-environment clarification makes R/T/S Restore/Table/Store,
apps, MAINT/CONFIG/OPAQUE and integrated source/ASM/DBG the completion target.
Their existing data/component images were retained; their old command interface
is not yet restored in MON A/B. Follow the [workbench acceptance workflow](MONA_USABILITY_PLAN.md)
and prioritize reconnecting these services over further standalone D/M polish.

The owner retired the Mona name on 2026-10-29. Future runtime/artifact identity
is STR8-N / MON A/B, with its own version and generation. Historical filenames,
branch spelling and qualified bytes remain intact. BATCH, AUTO T/S/R on both
flash and SSRAM PROGRAM, and APPS are required gates, not deferred polish.
The 367/43/43-byte F/A/B free-space figures and 30-byte WB1 remainder require
a module/layout checkpoint before those features can be added. F stays frozen.

[G7/WB2 g1](MON_AB_G7_WB2.md) now implements the first module/layout increment:
shared result codes, an expanded explicitly loaded RAM module and a bounded
BATCH subset. Each component built once; no execution qualification or install.
The [2512 RAM-only gate](MON_AB_G7_WB2_RAM_SCOPE.md) is prepared. AUTO flash/SSRAM
T/S/R, APPS, complete BATCH and the full workbench RAM budget remain open.

## G8 installed checkpoint

[G8 acceptance](MON_AB_G8_2512_ACCEPTANCE.md) supersedes the build-only g7 state:
both identical slots are installed on 2512, with physical default-B boot,
direct M1/W, board-stored workbench, read-only CLOCK and MAINT/FLASH entry.
The refined module saves 2KB RAM and one flash sector against the g7 prototype.
WORK routing, CRC refusal and BATCH cancellation have a separate repair scope.
F stays frozen. Full AUTO T/S/R, APPS/source/ASM/DEBUG and maintenance parity
remain required; the command manual marks current limits.
