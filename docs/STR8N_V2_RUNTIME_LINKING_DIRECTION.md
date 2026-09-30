# On-board assembly and runtime linking

Recorded 2026-09-27. User-endorsed direction; implementation and binary format
are not yet specified.

## Intended workflow

Edit source on the system, assemble a relocatable object, store it, resolve
dependencies, load/link it, test it, and run it. Independently replaceable units
are named routines or small modules. A candidate implementation can be tested
before replacing the active version; retain the previous version for rollback.

Objects may live in RAM, flash banks 0–3, or SPI storage. Storage location and
execution location are separate. Ordinary serial SPI RAM requires loading into
CPU-addressable RAM for execution. Code in any flash bank may depend on code in
another bank.

Stable runtime call slots resolve exported names to active implementations.
Calls within a module may be direct; calls between independently replaceable
modules use managed entries. RAM-resident call gates save the caller's bank,
select the callee's bank, regain control in RAM on return, and restore the
caller bank. Nested calls require stacked bank contexts. Interrupt behavior,
register/flag preservation, stack use, and CPU modes need explicit contracts.

Stored objects need code/constants, RAM/state requirements, exports, imports,
relocations, CPU/calling-convention requirements, versions, lengths, and integrity
checks. Local assembler symbols can be optional debug information. Cross-module
dependencies must survive assembly as imports instead of becoming fixed EQU
addresses.

First replacement policy: activate at a quiescent runtime prompt with no managed
routine executing. Later replacement during execution requires keeping old code
resident until active calls return. Persistent state needs preservation,
initialization, or migration rules.

## Starting without an F-sector change

The initial prototype can run in application RAM, loaded with the existing L
command and entered through G. Reserve its code, registry, call gates, bank
context stack, and loaded routines within available application RAM
($0200–$68FF), with an explicit allocation plan. Respect monitor zero-page,
stack, and upper-RAM ownership. G is a handoff, not a returning JSR.

Use the initialized public RAM ABI for console services from any selected bank:
PUTC $7E6D, GETC $7E70, and related entries. RAM HOLD at $7E67 selects the
resident bank and returns to the monitor prompt without returning to the guest.
The runtime supplies its own editor, command loop, allocator, object linker,
and bank-aware call gates. The existing worker's bank-select routine is private;
do not assume it is a new public dynamic-call ABI.

No resident $F000–$FFFF update is required to begin. This does not establish
that arbitrary existing banks have suitable reset/interrupt vector contents;
cross-bank execution tests must inspect their vector paths and keep monitor
recovery intact. Existing public monitor calls require IRQ disabled and decimal
mode clear; 816 calls require emulation mode and the documented bank state.

Initial proof: TEXT.PRINT in one bank calls IO.PUTC in another through a RAM
gate. Test and activate a RAM replacement of IO.PUTC without reassembling
TEXT.PRINT. Begin with RAM-only objects before programming that banked example.

F-sector changes may become useful for monitor command registration, a public
runtime bootstrap/hook, or revised service contracts. They are not prerequisites
for the separate runtime. Existing S/R stores fixed-address snapshots; it is not
the proposed relocatable object store or linker.

## Source references

- `src/v2a22/str8n-v2-public.inc`: ROM/RAM ABI and calling restrictions.
- `src/v2a22/str8n-v2-monitor.inc`: G command handoff.
- `src/v2a22/str8n-v2-worker.asm`: bank selection and execution handoff.
- `src/v2a22/str8n-v2-vectors.asm`: RAM HOLD and interrupt entry code.
- `docs/STR8N_V2_A22_TECHNICAL_MANUAL.md`: memory map and bank window.

This extends the earlier fixed-address storage proposal toward relocatable,
replaceable modules; it does not retroactively change the implemented S/R format.

## Subsequent direction

The user also wants dependency rewriting when required, not only stable slots.
Retain symbolic imports and typed patch locations so the linker can rebind
managed callers. Existing fixed binaries need build-derived metadata first.
RAM patching and flash-sector rewriting have different activation/recovery
requirements.

The proposed extension includes dynamic command registration and optional
script/key dispatch through the same service registry. A script must retain
callee register/flag results across interpreter parsing. Development tools,
including ASM-F2 adapted away from HIMON, should be layered above a small
runtime with a shared built-in dynamic linker.

See [the staged proposal](STR8N_V2_LAYERED_ASSEMBLER_PROPOSAL.md) for the next
steps, compatibility constraints, and completion criteria. This remains a
proposal, not an implemented runtime or permission to install new firmware.
