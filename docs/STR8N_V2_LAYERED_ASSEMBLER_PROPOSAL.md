# Layered assembler and dynamic linker on STR8-N v2

Proposal, 2026-09-27. No firmware changes or board installation are authorized
by this document. Sizes below distinguish measurements from future design work.

## Recommended direction

Extract ASM-F2's proven assembler and AP linking machinery into a new v2-hosted
toolchain. Replace its HIMON-specific service boundary. Make the dynamic linker
a built-in service of the new runtime, shared by the assembler, shell, and
loader. Avoid a second private linker inside the assembler.

Keep STR8-N responsible for boot and recovery. Initially launch the new runtime
through L/G with F unchanged. Add a small command-extension/discovery interface
only after the runtime contract is proven. Preserve existing S/R/T during that
transition; their present E/F interface is private and build-coupled.

The desired lifecycle is source -> relocatable object -> storage -> link/load
-> candidate test -> activate -> retire/rollback. Storage and execution locations
are distinct. An ordinary SPI RAM device is an object store, not executable
CPU memory; code is loaded into CPU-addressable RAM before execution.

## What can be reused, and what must change

ASM-F2 has qualified instruction encoding, symbol/fixup handling, internal
ABS16/LO8/HI8 relocation, exports/imports, and AP packaging/loading workflows.
Retain the opcode tests, invalid-input rollback tests, exact object fixtures,
and board-test evidence as a baseline. Modified builds need new qualification.

The existing ASM/HIMON ABI requires Bank 3, foreground non-reentrant calls,
and fixed high-RAM service cells. It cannot be installed over the v2 ABI:

- HIMON's $7E00 onward service block overlaps v2 interrupt pointers/code.
- ASM's $7E6A session-resume byte overlaps v2 RAM CON_INIT entry code.
- ASM UDATA at $5000-$6D6D overlaps v2's $6900-$78FF sector buffer.
- Existing manager/tool trays overlap v2's worker and state.
- HIMON cold initialization clears memory needed by v2.

Use a newly located, versioned host descriptor and explicit workspace ownership;
do not emulate the old ABI at its original addresses. Replace private HIMON
address assumptions as well as public doorways.

Measured reference: released ASM-F2 occupies 15,235 ROM bytes and allocates
7,534 UDATA bytes. Its external name areas occupy $0200-$19FF (another 6,144
bytes when used), so 7,534 is not its complete RAM requirement. Released HIMON
occupies 11,754 bytes; the combined padded 8-E carrier is 28,672 bytes.
An older dependency-accounted baseline assigns 3,047 HIMON bytes to AP functions,
with additional shared dependencies. That is not a standalone linker estimate.

## Layers and ownership

| Layer | Responsibility | Placement/lifetime |
|---|---|---|
| STR8-N v2 | Boot, recovery, existing console/flash facilities | Existing resident firmware and reserved RAM |
| Runtime core | Registry, gates, binding ownership, bank contexts, allocation records | Live state and gates in common RAM; other code may be banked |
| Dynamic linker/loader | Validate objects, allocate, resolve, relocate, retain patch records, rebind | Built-in runtime service; implementation can be banked |
| Storage provider | Read/write objects, catalog versions, publish completed records | RAM first, then flash, then SPI |
| ASM core | Parse source, encode instructions, maintain symbols/fixups, emit objects | Development tool with explicitly owned workspace |
| Shell/editor | Command/key dispatch, source input, later simple scripts | Separate client of runtime services |
| Debug/report tools | Disassembly, stepping, xrefs, detailed listings | Optional modules |

Built-in means available through the runtime's interface without HIMON. It does
not require placing the linker in F or keeping all its code in common RAM.
The registry and call path must work without recursively loading the loader
that they need. Keep the initial loader pinned and dependencies explicit.

## Steps and completion criteria

### 1. Freeze a baseline and measure dependency-complete slices

Work on a separate v2-targeted variant, retaining the existing HIMON release.
Inventory every ASM host dependency: join/name lookup, console, line input,
strings, hex conversion, FNV, PACK40, AP operations, flash install, command
buffer, and session ownership. Trace shared callees before proposing removals.

Produce separate measured builds for runtime, loader/linker, assembly core,
interactive wrapper, and optional tools. Report emitted code/data, persistent
RAM, temporary RAM, external pools, table capacities, and stack depth evidence.
Measure ROM and peak simultaneous RAM separately; moving code to another bank
does not reduce total storage.

Done: a reproducible size/dependency report and a RAM plan with no overlap with
v2 reservations. Set numerical budgets from these measurements, not guesses.

### 2. Establish a v2 host boundary and RAM-only registry

Provide a small new host descriptor instead of HIMON's RY block. Register
selected STR8-N RAM ABI services as pinned providers. Add missing string/line
helpers with documented arguments, flags, scratch use, and return behavior.
Preserve 65C02-compatible foreground semantics initially; 816 uses emulation
mode when calling v2 services. No native-call or reentrancy claim yet.

Give each service an identity and compatible interface version, each
implementation an owner/generation, and each binding an explicit lifetime.
Separate dependent references from active calls. Include callback/data-pointer
ownership; a call count alone cannot establish safe unloading.

Done: launch via L/G, register/find/call/release RAM services, replace a test
provider at a quiescent runtime prompt, and return through v2 RAM HOLD.

### 3. Extract the dynamic linker and define retained dependency records

Reuse the AP reader/relocator where its contracts fit. First accept existing AP
v2 objects under their original limits; use a runtime side table to retain
bindings and patch sites. Do not silently change frozen AP v2 semantics.

Specify a versioned successor or separate metadata envelope for persistent
extensions: CPU/ABI, alignment, code/constant/state sections, zero-page needs,
imports/exports, service versions, and semantic patch kinds. Existing ABS16
fixups alone do not identify calls versus data addresses. Add explicit call,
jump, address-taken, and data-reference meaning where needed. Hash lookup must
handle collisions rather than treating a hash match as proof of identity.

Call imports normally bind to stable gates. Direct binding is allowed when the
linker retains enough information to rewrite every affected dependency. Reject
unsupported rebinding rather than infer patch sites by scanning machine code.

Done: load the same object at two RAM bases, resolve imports, reject missing or
incompatible providers, and keep failed candidates unpublished. Show actual
operand rewriting in a stopped RAM caller as well as slot-based replacement.

### 4. Port and reduce ASM-F2 using the shared linker

Preserve the tested parser/encoder and useful object generation. Replace its
HIMON-specific wrapper, fixed service cells, private command-buffer assumptions,
manager transitions, and flash-install path. ASM invokes the runtime linker
for load/link/activation. Storage invokes a provider API.

Move reports, catalog browsing, installer UI, and optional diagnostics into
separate tools where dependency measurements justify it. Review duplicated
package validation/serialization before consolidating it; retained validation
must still reject malformed inputs.

Replace large fixed scratch allocations with capacity-declared pools or arenas
where feasible. Plan lifetimes for source, names, fixups, object output, linked
image, and old/new versions. Overlay temporary areas only after their owners
release them; report exhaustion explicitly. Keep source persistence distinct
from machine-code storage: ASM_ASSEMBLE_LINE is not a complete source editor.

Done: on-board source -> object -> dynamic link -> execute without HIMON.
Compare the complete toolchain footprint and peak RAM against the frozen
baseline. Smaller capacities alone must be reported as a feature tradeoff.

### 5. Prove bank-aware execution

Implement gates in common RAM with nested bank contexts, ABI-preserving return
handling, and a documented maximum nesting/stack budget. Start with explicit
loads and pinned implementations. Calls, tail jumps, function pointers, and
cross-bank data references require distinct treatment; a call gate does not
make an ordinary data pointer bank-aware.

Done: bank X -> bank Y -> bank Z -> X returns correctly, including repeated
banks and recursion within supported limits. Check A/X/Y/P results, stack
balance, and selected bank. Verify every participating bank's interrupt/vector
paths, including NMI, before claiming safe execution. Respect existing monitor
and S/R reservations, particularly resident E8xx and F.

### 6. Add persistent storage and replacement transactions

Store relocatable objects and retained source separately, using versioned
records with length/integrity checks and a completion marker. Use append-and-
publish for new versions; garbage collection is a separate operation. Start
with flash, then a HAL-backed SPI provider. SPI SRAM persistence depends on
hardware power/backup; do not promise power-cycle retention.

Candidate testing uses a separate binding context. At a quiescent point,
validate the dependency closure, prepare gates/patches, and publish the new
bindings. Retire old code only after all owned references and calls are gone.
Keep rollback information and define state preservation/reinitialization rules.

For flash callers, default to mutable RAM gates. Physical dependency rewriting
in flash is an explicit later path requiring sector preservation, verification,
and interruption recovery. Sequential multi-sector writes are not atomic.
Existing v2 text helpers with direct internal calls do not become dynamically
bound merely because their public ABI entries are registered.

Done: store/load/restart, test a replacement, activate it, unload safely, and
roll back; incomplete publication never selects an unverified candidate.

### 7. Integrate an extensible STR8-N command shell

Only now revise F to discover one versioned extension descriptor with command
dispatch and service lookup. No extension means normal recovery operation.
Reset clears volatile registration. Withdrawal must precede extension unload.
Resolve bootstrap separately: initially launch the runtime manually; any
automatic start needs its own defined load/entry and recovery policy.

Tokenize exact command names so DIR is not mistaken for D plus arguments.
Retain built-in precedence initially. Preserve S/R/T's existing paths until a
separate compatible conversion. Handlers receive bounded arguments and return
status under a defined input-buffer ownership contract.

Add key dispatch as a registry client, then optional label/IF/GOTO scripting.
DISPATCH(A) looks up a command key, not an address. Script execution keeps a
saved virtual A/X/Y/P state so parsing does not destroy results such as carry.

Done: invoke ASM/LINK/DIR through the extension, return to the prompt, and
recover normally with the extension missing or invalid. Measure F fit and
qualify the matching firmware update before installation.

## First milestone to implement

One small RAM runtime, a v2 console adapter, a retained-dependency linker, and
two simple objects. TEXT.PRINT imports CONSOLE.PUTC. Link both, test a second
PUTC implementation, rebind without reassembly, and demonstrate safe refusal
to unload an implementation that still has references. This proves the new
contract before the full ASM port, storage manager, or F-sector hook.

The first integration milestone then assembles those objects on board using
the adapted ASM core. An initial host-produced object is only a bootstrap test,
not a substitute for the intended on-board workflow.

## References

- `docs/STR8N_V2_RUNTIME_LINKING_DIRECTION.md`
- `src/v2a22/str8n-v2-public.inc`
- `docs/STR8N_V2_A22_TECHNICAL_MANUAL.md`
- `C:/SRC/R-YORS/SRC/ASM/asm-abi-v1.inc`
- `C:/SRC/R-YORS/DOC/GUIDES/ASM/ASM_ABI_V1.md`
- `C:/SRC/R-YORS/DOC/GUIDES/ASM/SIZE_REDUCTION_2026-09-15.md`
- `C:/SRC/R-YORS/DOC/GENERATED/HIMON_AP_BASELINE.md`
