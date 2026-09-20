# STR8-N v2 development

Development branch: `v2`. The starting firmware is commit `6d1af3d`,
preserved by tag `v1.35`. This document describes the complete intended v2.
The independent [v2-alpha4 flash milestone](STR8N_V2_FLASH_MILESTONE.md)
implements bank-independent startup, B/D/M/G/L/F/I, safe Ctrl-C cancellation,
console/help, J0-J3, and RAM interrupt entries. Configuration commands and
autostart are not yet implemented. Existing v1
sources and normal release targets retain their v1.35 behavior.

## Core boundary

Ctrl-C cancels the current monitor operation at a safe boundary. Discard an
unsubmitted command or incomplete load record; finish an already committing
RAM edit or validated load record. Completed writes remain in place. For
F/I, finish the active flash mutation and verification from RAM before
honoring cancellation; never abandon an erased sector awaiting restoration.
Once G/J transfers control, the application owns input and cancellation.

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
protected-top enforcement for I, and bounded flash completion polling. F is
the operator's explicit flash editor and may modify the monitor sector.
Do not remove additional verification merely to meet a size estimate.

Remove directory descriptions, enrollment, persistent transaction state, and
journal-based interrupted-installation recovery from v2. Remove their tooling
and packaging dependencies from the v2 product. Preserve v1 implementations
in the v1.35 baseline; existing v1 directory tools are not v2 interfaces.

## One binary for both processors

Build one STR8-N binary for W65C02SXB/EDU and W65C816SXB/EDU. The 816 runs
the monitor in emulation mode. Use only instructions with compatible behavior
on both CPUs; exclude the 65C02-only RMB/SMB/BBR/BBS instructions. Do not add
CPU-specific binaries, native-mode monitor execution, or an EDU-only buffer
relocation. Applications own native mode and extended memory.

All monitor RAM and execution remain in CPU bank $00. Flash overlays B0-B3
are a separate concept from 816 CPU address banks. Reserve the full 816
hardware vector area and RAM space for both native and emulation handlers.
Reserved space does not imply a native-mode dispatch implementation.

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
| `I start end` | Install dense ascending S19 into a selected legal flash bank and inclusive sector-aligned range, without directory metadata or journal state. |
| `J0`-`J2` | Boot the selected bank through its RESET vector after bank/vector validity checks. |
| `J3` | Boot Bank 3 through its RESET vector; during guest-bank testing this starts v1.35, not v2. |
| Configuration command (name pending) | Display/set autostart enable, flash bank, address, and delay; compute the integrity check and confirm before writing. |

Initial scope excludes an assembler, disassembler, register editor, and
debugger. The operator may install their own BRK/IRQ handling and use `F`
to insert BRKs in flash code.

## Execution and workspace contract

`G` disables maskable interrupts, clears decimal mode, resets the stack, and
jumps without a return contract. Preserve operator RAM and installed handler
vectors outside explicitly reserved monitor workspace; establish that memory
map before implementation. Targets enable IRQs themselves when ready. BRK
still executes with IRQs disabled, and its saved return address advances two
bytes from the BRK opcode. On the 816, handoff remains in emulation mode with
direct page $0000, data bank $00, and program bank $00. User code manages
subsequent native-mode entry and extended addressing.

Provide a fixed software monitor-entry address, assigned when the ABI is
laid out. It bypasses autostart and holds at the prompt. A software caller
must already have the resident monitor bank visible and establish the common CPU contract:
on the 816, emulation mode, direct page $0000, data bank $00, and execution
in CPU bank $00. Switch flash mappings from RAM before entering. The entry
disables IRQs, clears decimal mode, and establishes the monitor stack; it is
not a callable return or a debugger resume operation. Preserve installed
handler pointers on this software entry; hardware/reset-style initialization
establishes defaults. J3 remains reset-style entry, distinct from prompt entry.

Banked accesses must remain executable while the resident bank is hidden. Use RAM
routines for the necessary access/selection operations and restore the monitor
mapping before returning to its flash code. Keep the operator-selected bank
explicit even if the prompt runs with the resident bank physically selected.

Reserve and document monitor scratch RAM, worker storage, stack usage, and
the sector buffer. Loads and edits must not overwrite live monitor storage;
flash operations must not silently consume space promised to an operator's
handler. Hardware vector ownership and the exact generic handoff ABI must
be resolved against that map. Preservation applies to application RAM and
installed handler pointers, not monitor scratch, stack contents, or an exact
CPU snapshot.

## Proposed RAM map

These addresses are provisional until the first linked implementation and
workspace audit. Freeze public addresses only after measuring actual use.

| Address | Size | Ownership |
| --- | --- | --- |
| $0000-$00DF | 224 bytes | Application zero page |
| $00E0-$00FF | 32 bytes | Monitor fast scratch and pointers |
| $0100-$01FF | 256 bytes | Hardware stack; contents are not preserved |
| $0200-$68FF | 25.75 KiB | Contiguous application RAM, including user handlers |
| $6900-$78FF | 4 KiB | Shared F/I sector buffer |
| $7900-$7BFF | 768 bytes | RAM worker and bank-access code budget |
| $7C00-$7CFF | 256 bytes | Shared command/S-record data buffer |
| $7D00-$7DFF | 256 bytes | State, parameters, and configuration copy |
| $7E00-$7EFF | 256 bytes | Handler pointers and RAM interrupt entry space |
| $7F00-$7FFF | 256 bytes | I/O; excluded from ordinary D/M/L access |

The sector buffer is page-aligned and occupies sixteen pages; it need not
start on a $x000 boundary. Reduce worker/state reservations if measured size
permits. Extended 816 RAM and EDU serial SRAM belong to applications and are
not required for monitor operation.

## Vector ownership and reset

Reserve the resident bank's $FFE0-$FFFF for the complete 816 vector area, including
reserved locations; the v1 configuration pocket at $FFF0 cannot carry over.
The resident bank's implemented emulation interrupt vectors lead to RAM entry routines.
The 65C02/emulation IRQ-BRK entry distinguishes BRK using stacked status and
dispatches directly through the appropriate RAM pointer.

Proposed 16-bit, little-endian RAM handler pointer slots:

| Address | Pointer |
| --- | --- |
| $7E00-$7E01 | Emulation/65C02 NMI |
| $7E02-$7E03 | Emulation/65C02 BRK |
| $7E04-$7E05 | Emulation/65C02 IRQ |
| $7E06-$7E07 | 816 emulation COP |
| $7E08-$7E09 | 816 emulation ABORT |
| $7E10-$7E19 | Native COP, BRK, ABORT, NMI, IRQ, two bytes each |
| $7E20-$7EFF | Entry code, defaults, and reserved handler-entry space |

Native vectors must never route through the emulation dispatcher. User code
owns native entry routines and their different stack/register requirements.
Use bank-zero entry stubs if a native handler resides in another CPU bank.
Separate user-installable slots/stubs from monitor-owned dispatch code before
freezing this page's detailed layout. Define deterministic reset defaults for
unused native entries without assuming an emulation stack frame.

M may deliberately update documented handler-pointer/user-stub locations;
this is an exception to protection of live monitor workspace. L must not
overwrite monitor-owned dispatch code. Preserve installed pointers through
L/F/G. Multi-byte updates require an interrupt-aware publication procedure;
SEI alone does not exclude NMI.

The alpha2 M command gates its emulation NMI dispatch during the short RAM
commit loop, acknowledging an NMI in that window with RTI. This prevents
following a torn NMI pointer; it does not queue or replay that NMI. Software
prompt entry clears the temporary gate while preserving installed pointers.

Other payload banks own their hardware vectors. They may point directly to their own
handlers or deliberately use the RAM entries. The RAM table does not
automatically intercept interrupts when another flash bank is selected.

Verify physical RESET and bank-select behavior on the supported boards;
do not assume pressing RESET always selects Bank 3. Audit each bank's RESET
vector and distinguish power-on, physical reset, J3, and software prompt entry.
Executing a worker from RAM does not make NMI vector fetching safe while
flash is busy. Flash-operation interrupt behavior remains a hardware test gate.

## Flash edit contract

Initially accept edits contained within one sector. Before confirmation,
display the selected bank, addresses, old/new bytes, and whether erase is
required. Changes requiring only 1-to-0 transitions program directly and
verify. Any 0-to-1 transition requires reading the entire sector into reserved
RAM, applying the edits, erasing, rewriting, and verifying the sector while
preserving its unedited bytes. F accepts $8000-$FFFF in every selected flash
bank, including the resident monitor's $F000-$FFFF and Bank 3's code and
hardware vectors. No top-sector prohibition applies to F. I protects the
resident monitor's top sector and Bank 3's recovery top sector.

Before a resident-bank top-sector edit, identify that STR8-N itself is being changed
in the confirmation. The full mutation, verification, and completion/failure
path must execute from RAM with no dependency on code or constants in the
sector being changed. Do not return through old ROM addresses after such an
edit. Define a RAM-resident completion path that reports the result and holds
for explicit reset/recovery. Reassess the worker-size target for this path.
An edit may make STR8-N or its vectors unusable; recovery can require an
external programmer. This is part of F's operator-controlled capability.

Inserting a BRK byte ($00) permits direct programming; restoring the original
instruction generally needs erase/rewrite. There is no journal or rollback:
an interruption during erase/rewrite can destroy the affected sector.

## Autostart contract

Use a small fixed configuration location for enabled/disabled state, bank,
execution address, and delay. Place it outside the STR8-N code
sector so `F` can edit it; configuration edits preserve neighboring contents
under the same sector-edit contract. Erased or invalid settings stay at the
monitor prompt. The configuration command computes the integrity check so
ordinary configuration changes do not require manual checksum calculation;
F remains a raw editing facility.

Propose the resident bank's $EFF0-$EFFF as a single 16-byte configuration block: format at
+0, enable at +1, flash overlay at +2, little-endian start address at +3/+4,
delay in tenths of a second at +5, reserved bytes at +6 through +13, and an
integrity check at +14/+15. Exact encodings and check algorithm remain open.
There is no record history, journal, or rollback.

This allocation shares sector $E000-$EFFF with payload bytes. F and the
configuration command preserve neighboring contents during erase/rewrite;
I explicitly preserves the resident bank's configuration reservation. Interrupted rewrites
can lose that sector. The alternative is dedicating a full sector, at a
4 KiB payload cost. The shared-sector location remains provisional with the
rest of the address map. Keep the resident bank and Bank 3 $F000-$FFFF
protected from I; F can edit either. Do not reserve configuration bytes in
unrelated target banks merely because their addresses match.

On reset, initialize STR8-N, display a valid configured target, and provide
a minimum interrupt window whenever autostart is enabled. Recognize `S`
immediately, including buffered input, to cancel automatic execution for
that boot and hold at the prompt. Timeout uses the generic `G` handoff to
the configured bank/address, without payload recognition or signatures.

## Installation and testing alongside v1.35

Keep v1.35 in Bank 3 and install v2 as a guest into one disposable Bank 0, 1,
or 2 using v1.35's resident I command. Launch through v1.35's matching J
command. V1.35 owns enrollment/journal activity in its installation process;
v2 neither implements nor depends on that policy. Its image contains only
payload, not v1 directory records or an installation wrapper.

Maintain distinct resident-bank and operator-selected-bank state. Capture
the actual entry bank before initialization changes the bank-control
registers; do not depend on v1 handoff signatures. Worker returns, prompt
entry, configuration access, and self-edit detection use the resident bank.
Use the same binary in Banks 0-3; no per-bank monitor builds.

The planned test artifact is a dense E-F S19 covering $E000-$FFFF, containing
disabled initial autostart configuration, monitor code, and hardware vectors.
Its S9 entry is the reset/start entry within the image. If v1.35 requires
full-bank recovery for an incomplete enrollment, supply a deliberate dense
8-F image with S9 matching RESET. Packaging must explicitly define lower-bank
contents; never silently pad over existing software to make a full image.
Preserve the chosen test bank before installation: E-F replaces both sectors.

Guest-bank v2 I protects its own top sector and Bank 3's v1.35 recovery top
sector. F retains full operator-authorized access to all banks, including
both monitors; confirmation identifies the monitor/recovery sector affected.
J3 boots v1.35 during this test arrangement. The fixed software prompt-entry
address instead enters the current resident v2 and bypasses autostart.

Initialize all required v2 workspace on guest reset entry; assume no useful
v1 RAM state. Keep cross-monitor handoff code in RAM and complete the bank
switch and jump without returning through the previous monitor. Its code
must survive until the final jump; after that, the receiving monitor may
initialize its own workspace. Audit initialization of shared hardware too.

Validate guest-bank RESET and interrupt vectors and actual physical-reset
bank selection. Test launch from v1.35, B/D/F accesses and restoration of v2's
resident bank, resident configuration access, I protection, software prompt
entry, and J3 return. After v1 installation/enrollment, verify recovery-bank
flash remains unchanged by v2 tests that do not explicitly target it with F.
Installation compatibility and board
behavior remain unverified until implementation and tests are complete.

## Console messages

Keep errors short and descriptive in plain language. Do not require an error
code lookup or use a bare ERR/FAIL when the cause is known. Internal status
codes may remain for control flow; translate them at the console boundary.

Examples of the intended vocabulary (final wording may be tightened):

| Condition | Message |
| --- | --- |
| Invalid command | Unknown command |
| Invalid hex input | Bad hex |
| Unexpected control/non-ASCII input | Bad input |
| Invalid bank | Bad bank |
| Reversed or unsupported range | Bad range |
| Write into protected storage | Protected address |
| F edit crosses a sector | Crosses sector |
| Invalid S-record checksum | Bad S19 checksum |
| Invalid S-record structure | Bad S19 record |
| Invalid execution vector | Bad vector |
| Flash operation exceeds its bound | Flash timeout |
| Readback differs from requested data | Verify mismatch |
| User cancels an operation | Cancelled |
| Erased/invalid autostart configuration | Autostart disabled |

Include bank/address or expected/actual bytes only when they help identify
the failure, using the shared hex-output routines. Keep success output and
prompts minimal. Mutation confirmation must still identify bank, address or
range, proposed changes, and erase requirement as required by the F contract.

Reuse identical strings and useful common fragments where this reduces the
total linked code/data size. Avoid long banners, repeated explanations, and
synonyms for the same condition. Prefer simple zero-terminated strings and
existing output helpers; add no compression or token-decoding machinery
unless measured total ROM savings justify it. Measure strings together with
their printing code, not just their character count.

## Agreed optimization targets

Share one flash worker between F, I, and configuration writes. Skip unchanged
bytes and erase only when requested changes require a 0-to-1 transition.
After erase, program only non-$FF bytes, then verify the entire reconstructed
sector. Retain bounds, I's protected-top enforcement, and bounded completion
polling. Use the same flash-edit path for configuration updates; I preserves
the configuration bytes while constructing the affected sector image.

Use one hex parser for D/M/F/G and configuration input. Share command and
S-record storage only where lifetimes permit: F must retain replacement
bytes while reading the sector, and I must retain each record until consumed.
G, autostart, and J share the final RAM handoff routine after their distinct
target-selection and validation steps.

Target a 512-byte worker instead of the provisional 768-byte reservation.
The v1.35 worker is 568 bytes, including 100 bytes of directory-record code;
F still needs byte programming, so that removal is not a guaranteed net
saving. Also investigate combining monitor state, vector pointers, and entry
code into one 256-byte page instead of two. Keep the separate 256-byte record
buffer and 4 KiB sector buffer. Meeting both targets would recover 512 bytes
and allow 26.25 KiB of contiguous application RAM starting at $0200.

These are measured-fit targets, not frozen allocations. Keep the proposed map
above until the linked implementation proves fit and all buffer lifetimes and
handler ownership boundaries are checked. Native/user vector slots and stubs
must never overlap temporary scratch. Publish revised addresses together when
freezing the ABI.

Keep interrupt dispatch to hardware vector, small entry stub, and operator
handler. Only the shared emulation IRQ/BRK entry requires discrimination.
Initialize defaults at reset and preserve installed pointers during monitor
operations; do not carry forward repeated v1 signature-validation machinery
in each interrupt path. Native handler entries remain user-owned.

Retain the 16-byte configuration reservation: shrinking its byte count does
not reduce sector erase cost. Select a compact integrity check with explicit
format/enable encodings, computed by the configuration command. Measure code
size and runtime behavior before claiming any optimization savings.

## Implementation sequence

1. Establish a v2 build identity and validation path without overwriting
   the v1.35 baseline artifacts. Enforce the common CPU instruction subset
   and one-binary emulation-mode contract.
2. Remove directory gating from guest boot, retaining bank and RESET-vector
   validity checks. Verify that boot does not read or depend on the former
   directory storage, regardless of its contents. Remove HIMON-specific boot
   paths and commands, and define generic reset selection behavior.
3. Simplify resident installation to bank/range selection and payload writing;
   remove metadata prompts, directory writes, and journal recovery machinery.
   Define S9 entry handling independently of directory metadata and implement
   resident-bank tracking and guest-bank test packaging.
4. Remove unused worker modes, directory storage reservations, and helpers;
   relink and measure actual ROM savings. Audit public ABI and RAM contracts,
   including handler ownership and reserved monitor/sector-buffer storage.
   Implement B/D/M/F/G, load-only L, the configuration command, software
   prompt entry, and configurable interruptible autostart against those
   contracts; measure the resulting footprint again before freezing addresses.
5. Update host checks, operator documentation, image composition, and packaging
   for the new behavior. Exercise malformed input, protected-range rejection,
   flash failures, and successful load/install/handoff paths. Check RAM/vector
   preservation, configuration preservation and invalid-config hold behavior,
   reset versus software entry, and compatibility on both CPUs.
6. Validate on hardware before declaring v2 release-ready. Direct boot does
   not establish that a payload survived an interrupted installation.

## Hardware references

- [W65C02SXB memory map](https://www.westerndesigncenter.com/wdc/documentation/W65C02SXB.pdf)
- [W65C816SXB memory map](https://www.westerndesigncenter.com/wdc/documentation/W65C816SXB.pdf)
- [W65C816 CPU and vector tables](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf)
- [W65C02EDU](https://www.wdc65xx.com/wdc/documentation/W65C02EDU.pdf)
- [W65C816EDU](https://www.wdc65xx.com/wdc/documentation/W65C816EDU.pdf)

## Documentation artifacts

Track book editorial sources and generators in the main repository.
Ignore generated `output/` and temporary `tmp/` files. PDF and HTML snapshots
are committed separately in the ignored `local-books/` Git repository,
which has no remote. The current book describes v1.35, not the planned v2.
