# STR8-N v2 development

Development branch: `v2`. The starting firmware is commit `6d1af3d`,
preserved by tag `v1.35`. This document describes intended changes;
the firmware still implements v1.35 behavior.

## Core boundary

STR8-N v2 has no directory, enrollment, or journaling functionality or policy.
Boot selects a bank and hands off through its RESET vector, subject to bank
and vector validity checks. There are no directory records or journal states
to consult, maintain, or expose through an optional component or interface.

STR8-N v2 has no HIMON dependency or special HIMON handoff protocol. Remove
the HIMON-specific C/W commands, image recognition, warm/cold reset signatures,
and automatic HIMON startup. Payloads use generic boot/load paths and the
configurable autostart described below.

Use the lowest practical subroutine directly. Introduce a higher-level helper
only when it provides a concrete benefit; there is no mandatory
SYS/COR/BIO/PIN call chain or dependency hierarchy.

Retain console and recovery RAM loading, bank selection and boot handoff,
and a basic flash installer. Retain S19 checksums, address bounds,
protected-top enforcement, and bounded flash completion polling.
Do not remove additional verification merely to meet a size estimate.

Remove directory descriptions, enrollment, persistent transaction state, and
journal-based interrupted-installation recovery from v2. Remove their tooling
and packaging dependencies from the v2 product. Preserve v1 implementations
in the v1.35 baseline; existing v1 directory tools are not v2 interfaces.

## Agreed monitor commands

Addresses and byte values are hexadecimal. Share a compact hex parser.

| Command | Contract |
| --- | --- |
| `B0`-`B3` | Select the bank used by monitor access without executing its payload. |
| `D addr [end]` | Display memory, defaulting to 16 bytes. Ordinary display avoids memory-mapped I/O reads with side effects. |
| `M addr bytes...` | Modify ordinary RAM, protecting the monitor's live workspace. |
| `F addr bytes...` | Edit flash in the selected bank, subject to the flash contract below. |
| `G addr` | Jump to existing code in the selected mapping, with no expected return. |
| `L` | Load S19 into permitted RAM without running it; report the S9 entry for subsequent `G`. |
| `I` | Install S19 into a selected legal flash bank/range without directory metadata or journal state. |
| `J0`-`J2` | Boot the selected bank through its RESET vector after bank/vector validity checks. |
| `J3` | Restart STR8-N through Bank 3's RESET vector. |

Initial scope excludes an assembler, disassembler, register editor, and
debugger. The operator may install their own BRK/IRQ handling and use `F`
to insert BRKs in flash code.

## Execution and workspace contract

`G` disables maskable interrupts, clears decimal mode, resets the stack, and
jumps without a return contract. Preserve operator RAM and installed handler
vectors outside explicitly reserved monitor workspace; establish that memory
map before implementation. Targets enable IRQs themselves when ready. BRK
still executes with IRQs disabled, and its saved return address advances two
bytes from the BRK opcode.

Banked accesses must remain executable while Bank 3 is hidden. Use RAM
routines for the necessary access/selection operations and restore the monitor
mapping before returning to its flash code. Keep the operator-selected bank
explicit even if the prompt runs with Bank 3 physically selected.

Reserve and document monitor scratch RAM, worker storage, stack usage, and
the sector buffer. Loads and edits must not overwrite live monitor storage;
flash operations must not silently consume space promised to an operator's
handler. Hardware vector ownership and the exact generic handoff ABI must
be resolved against that map.

## Flash edit contract

Initially accept edits contained within one sector. Before confirmation,
display the selected bank, addresses, old/new bytes, and whether erase is
required. Changes requiring only 1-to-0 transitions program directly and
verify. Any 0-to-1 transition requires reading the entire sector into reserved
RAM, applying the edits, erasing, rewriting, and verifying the sector while
preserving its unedited bytes. Keep the STR8-N recovery sector protected.

Inserting a BRK byte ($00) permits direct programming; restoring the original
instruction generally needs erase/rewrite. There is no journal or rollback:
an interruption during erase/rewrite can destroy the affected sector.

## Autostart contract

Use a small fixed configuration location for enabled/disabled state, bank,
execution address, and delay. Place it outside the protected STR8-N code
sector so `F` can edit it; configuration edits preserve neighboring contents
under the same sector-edit contract. Exact location and encoding remain to
be assigned. Erased or invalid settings stay at the monitor prompt.

On reset, initialize STR8-N, display a valid configured target, and provide
a minimum interrupt window whenever autostart is enabled. Recognize `S`
immediately, including buffered input, to cancel automatic execution for
that boot and hold at the prompt. Timeout uses the generic `G` handoff to
the configured bank/address, without payload recognition or signatures.

## Implementation sequence

1. Establish a v2 build identity and validation path without overwriting
   the v1.35 baseline artifacts.
2. Remove directory gating from guest boot, retaining bank and RESET-vector
   validity checks. Verify that boot does not read or depend on the former
   directory storage, regardless of its contents. Remove HIMON-specific boot
   paths and commands, and define generic reset selection behavior.
3. Simplify resident installation to bank/range selection and payload writing;
   remove metadata prompts, directory writes, and journal recovery machinery.
   Define Bank 3 S9 entry handling independently of directory metadata.
4. Remove unused worker modes, directory storage reservations, and helpers;
   relink and measure actual ROM savings. Audit public ABI and RAM contracts,
   including handler ownership and reserved monitor/sector-buffer storage.
   Implement B/D/M/F/G, load-only L, and configurable interruptible autostart
   against those contracts; measure the resulting footprint again.
5. Update host checks, operator documentation, image composition, and packaging
   for the new behavior. Exercise malformed input, protected-range rejection,
   flash failures, and successful load/install/handoff paths.
6. Validate on hardware before declaring v2 release-ready. Direct boot does
   not establish that a payload survived an interrupted installation.

## Documentation artifacts

Track book editorial sources and generators in the main repository.
Ignore generated `output/` and temporary `tmp/` files. PDF and HTML snapshots
are committed separately in the ignored `local-books/` Git repository,
which has no remote. The current book describes v1.35, not the planned v2.
