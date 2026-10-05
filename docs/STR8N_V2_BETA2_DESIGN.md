# STR8-N beta 2 consolidated design

Consolidated on October 3, 2026, and updated for the first 2.0b2 manager/RTS
candidate. The current implementation section and candidate guide describe
built behavior. Remaining proposals below record future configuration and AP
work; they do not authorize board installation.

The proposed direction is a small boot and recovery core, one optional
extension manager, and separately installable command modules. Build the
manager first, with contracts that allow it to become the shared management
and dispatch layer of the later AP dynamic runtime. Configuration editing,
S/R/T, a shell, and assembler tools use that infrastructure. The migrator and
Bank Maintenance remain independent tools.

## Current implementation

The published beta 1 release remains frozen. Its working-source reductions
save 34 core bytes, leaving a 3,995-byte resident image and 53 free bytes before
the configuration pocket. Public entry addresses and the old 1,208-byte
extension remain unchanged in that source tree.

The separate `src/v2-b2` candidate implements one manager with DISPATCH and
LOOKUP, static services plus SERVICE.REGISTER v1 for eight dynamic services,
and runtime registration of eight
pinned command handlers, and optional RTS registering S/R/T. Names and
automatic save placement are included in this first implementation. The core
initializes the extension lazily; absent/corrupt E code leaves boot and built-in
recovery available. An independently registered X command is tested.

The current command-catalog b2 core measures 3,984 bytes (including worker
741 and vectors 180), with 64 free bytes before `$FFD0`. Nine bytes were saved
by removing redundant S/R/T key/pointer entries; the unmatched-command manager
path already handles them. `COMMAND.CORE` v1 exposes a read-only built-in
key/target catalog without occupying extension slots or changing core recovery. The existing `?` syntax summary is unchanged.
Permanent H is an independent provider in B3:C flash, with an initializer at
`$C000`, code/text at `$C300`, and a three-byte registered jump stub at `$7400`
in manager RAM. It uses zero application/overlay RAM and adds zero core/E
bytes. The existing C boot setting runs its initializer after reset; the
initializer returns to the monitor without resetting registration. It shows
all core/K/S/R/T syntax and live registered command letters. There is no
general overlay allocator, automatic provider discovery or persistent catalog.
The earlier RAM-loaded diagnostic H placement is retained only as historical
qualification and a separate optional build. Preserving the configuration
locator in C cost seven bytes relative to the initial candidate's 62-byte free area.
Manager code/directory/catalog uses 569 RAM bytes; its E carrier including
the stored manager image uses 849 flash bytes. This net 18-byte growth includes
25 metadata bytes minus seven equivalent lookup/registration code reductions. K configuration code uses 991 flash bytes
at `$E351`; RTS uses 2,255 flash bytes at `$E730`. E has one free tail byte. The selected `$57FF` application ceiling and
`$6100-$70FF` staging buffer are enforced in b2. Established public ROM/RAM
entry addresses remain fixed; the smaller application range changes the beta
memory contract. See [the candidate guide](STR8N_V2_B2_MANAGER_RTS.md) for
commands, contracts, exact allocations, build and validation instructions.

K now selects/creates/moves a reserved configuration sector with persistent
four-bank sector masks, and CONFIG.LOCATE reports validation and location.
The fixed boot pocket holds its locator. The selected sector is excluded from
effective RTS policy; missing/invalid configuration clears the masks. No
sector is assigned by default, and no other bank is searched for replacement
configuration. Migrator/Bank Maintenance integration, persistent registrations,
general backend handles, SPI SRAM, and AP loading/linking remain unimplemented.
The preceding 3,993-byte core/E pair passed scoped 65C02/FT245 checks on
board 2205 on October 4; the current catalog revision is now host-tested and
installed there through an exact guarded E/F update. H+X also passed startup,
all-selected-bank and RTS coexistence checks;
see [the qualification record](STR8N_V2_B2_2205_BOARD_TEST_2026-10-04.md).
The permanent H provider is host-tested and installed on 2205. Manual help
and automatic registration after software RESET passed. Core/E code and all
application/overlay RAM were unchanged; only B3:C and the existing C boot
pocket changed. Physical RESET/power-cycle qualification remains pending.
65C816/native and ACIA qualification, broader maintenance integration and
release packaging remain pending. The exact-source beta 1 to b2 RAM updater
used for that board does not qualify the older maintenance tools for b2.

Sections describing generic module descriptors, persistent registrations,
service-provider registration and backend handles remain future design. The
candidate guide defines the smaller implemented format-1 configuration and
manager contracts.

## User requirements

- S/R/T remains optional. Core boot and recovery must work without it.
- S should find a storage address automatically and save a named record.
- The bank argument should be optional. Configuration determines the default
  search areas; an explicit bank restricts that search.
- Unrelated bank contents, including Bank 2, may be opaque to S/R/T.
- The user can choose which sector holds extended configuration and which
  banks/sectors are available for saved records.
- The WDC migrator and Bank Maintenance can establish those choices.
- Extensibility includes new commands and a shell, rather than only S/R/T.
- There is one extension manager. Configuration editing, S/R/T, and a command
  such as X are modules, not additional managers.
- Existing private S/R/T call addresses need not remain frozen for old
  extension binaries. Rebuild S/R/T against the new contract. Continue to
  preserve and document the established public application interface.

## Components and ownership

| Component | Responsibility | Proposed placement |
| --- | --- | --- |
| Core monitor | Boot, recovery, built-in commands, public services, extension hook | Resident F sector |
| Bootstrap record | Boot settings and configuration-sector locator | Existing fixed F pocket |
| Configuration sector | Manager descriptor, persistent registrations, storage policy, settings | User-selected permitted bank/sector |
| Extension manager | Validate registrations, bind services, dispatch commands, manage module lifetime | Separate code with an explicit execution/RAM allocation |
| C module | Interactive configuration editing and guarded saves | Optional module |
| S/R/T module | Named saves, automatic placement, restore and listing | Optional module |
| Additional modules | X, diagnostics, shell launcher, later tools | Independently described modules |
| Migrator and Bank Maintenance | Bootstrap configuration, reserve/move sectors, install/manage images | Existing host/RAM tool roles |

Configuration storage and executable code are separate allocations. Commands
are entries in the manager's shared service registry. The fixed core service
descriptor exposes callable firmware services, which the manager registers as
pinned providers. It is a host discovery interface, not another dynamic registry.

## Relationship to the AP dynamic runtime

The recorded AP runtime direction already includes service registration,
object loading/linking, retained dependencies, bank-aware calls, replacement,
and dynamic command dispatch. This design must reuse those responsibilities.
The extension manager can be implemented first as the initial management and
dispatch layer. AP object loading/linking is a later capability added behind
that boundary, using the same registry and ownership model. Implementing the
manager does not require implementing AP relocation or replacement first.

Initially, the manager owns registrations and explicit code/state reservations.
Modules may be fixed-address and pinned, with replacement/unload unsupported.
As linking is added, the same layer owns allocations, bindings, module
generations, activation/unload, and bank contexts. Configuration records
describe persistent policy and desired
installations; they do not substitute for the runtime's live binding records.
Command dispatch is a client of the shared registry. Its handled/unhandled
status is an outer monitor interface, not a new calling convention for every
AP-exported routine. Service calls retain their documented register/flag results,
including results needed by a script interpreter.

Retain existing AP v2 object semantics under their original limits. Extra command,
CPU/ABI, or lifetime metadata belongs in runtime side tables or an explicitly
versioned envelope/successor. Firmware version 2.0b2 and object format AP v2 are
separate version identities. S/R snapshots remain fixed-address storage records;
they do not become relocatable AP objects merely by registering S/R/T commands.

The minimum compatibility rules for the first manager are:

- Identify services by name and interface version, with an explicit provider
  owner. Keep the registry's internal layout private.
- Resolve calls through a documented entry/handle contract that can later use
  RAM slots or bank gates. Initial targets may be pinned fixed-address code.
- Do not promise that a cached raw code address survives provider replacement.
  Later direct bindings require retained import/patch records or pinning.
- Describe CPU/ABI, execution location, code extent and RAM ownership explicitly.
  Keep command status separate from each service's register/flag results.
- Version descriptors and advertise capabilities. Reject unsupported relocation,
  cross-bank execution, replacement and unload rather than approximating them.

These rules allow existing command modules to remain pinned when the AP linker
arrives. Newly linked AP objects can publish their exports into the same registry;
commands remain clients of that registry. A simple module registration record
does not need to pretend to be a relocatable AP object.

The existing HIMON-hosted AP machinery still needs a v2 host adapter and an
explicit RAM plan. Sharing the architecture does not make its current service
cells and RAM allocations compatible with STR8-N. The recorded L/G RAM linker
prototype remains a useful later proof, rather than a prerequisite for the
first extension manager or its core hook. This revises the earlier linker-first
integration order while preserving the runtime linking goal.

## Configuration and boot

The recommended compromise is to retain boot-critical settings and a small
locator in F, while moving growing configuration into the selected sector.
Moving every boot setting out of F was discussed but is not the recommendation
in this draft. Keeping local boot settings limits reset-time dependencies.

The implemented locator uses pocket offset 7 for tag C1, offset 8 for bank,
and offset 9 for sector high byte 80–D0; all-zero locator bytes mean unassigned.
The existing pocket sums cover these fields. Offset 10–13 remain reserved.
The selected sector has a sixteen-byte CF/01 policy header with owner location,
pending/complete marker and two accumulated sums. See the candidate guide for
the exact byte contract. Further manager-descriptor/registration fields and
installation-tool migration rules remain future work.

Recommended default: no external configuration sector assigned. With an absent
or invalid external sector, the core remains usable and follows its local boot
settings or existing monitor fallback. It does not search arbitrary banks for
a plausible configuration signature. An extension failure must not prevent
recovery to the monitor.

The implemented CONFIG.LOCATE version-1 service reports location/validity and
refreshes effective storage policy. It is discovered through the manager, not
a new fixed core slot. Its first header stores policy; a manager description
is future work. The core does not parse that header at reset. Bank 2 being opaque means that its
contents are not automatically interpreted or claimed by S/R/T. It does not
prevent explicit monitor reads or booting that bank.

The sector may be B3:X or another permitted bank/sector. K permits sectors 8–D
in any bank and refuses E/F, which keeps current executable allocations protected.
B3:E was an earlier example,
not an assignment: the current manager/configuration/RTS code occupies that sector.
Turning all of B3:E into configuration would require moving that code.
Neither the core sector nor occupied code/storage is silently appropriated.

The implemented configuration sector holds policy; persistent registration
information remains future work. Saved names
and payload locations are derived from saved records. An ordinary S operation
should not rewrite the configuration sector.

## One manager and the command contract

The core exposes one hook to the optional manager. The manager owns one shared
service registry, including command registrations. A separately installed X
module is added to this registry; adding it should not require rebuilding
either the core or the manager.

This replaces the earlier minimal suggestion of compiling every handler into
one provider. It requires a defined module descriptor and registration process.
Registration metadata must describe ABI/version requirements, command identity,
execution address, code extent/integrity, and RAM/state requirements, using the
AP/runtime contracts rather than an unrelated module format. Storage location
and execution location are distinct.

Recommended initial invocation contract:

- The complete command is available in the published command-line buffer.
- The manager returns A=0 for unrecognized, or A=1 for handled. A module may
  print an operation error and still report that its command was handled.
- A, X, and Y are volatile; flags other than the required CPU mode are not
  result fields in this proposed command contract.
- Returning calls restore the stack and visible bank. Calls remain foreground,
  non-reentrant, IRQ-disabled and decimal-clear. On the 816, use the existing
  emulation-mode and bank-state requirements.
- A shell may keep control until exit, then return through this contract.
  A non-returning monitor reentry remains a separate operation.

Exact command matching, duplicate command registrations, case handling,
registry capacity, and built-in precedence must be specified. Initial
single-letter extension commands avoid the existing first-character dispatch
ambiguity between a built-in such as D and a longer name such as DIR. C and
S/R/T must be explicitly routed to the manager if their built-in implementations
are removed; forwarding only currently unknown commands is insufficient.

The core-service lookup table is complementary to this hook. Modules resolve
services through named definitions and a versioned descriptor instead of
embedding private code addresses. Existing public console entries can be
reused. The earlier S/R-specific list is an inventory of current dependencies,
not yet the final public service list. Each exported service needs inputs,
outputs, flags, scratch ownership, bank visibility, and error behavior defined.

## Fast slots and interrupt policies: deferred to a full decimal version

On October 3 the user requested that the following discussion be documented,
and explicitly deferred it to a full decimal-version release, outside b2.
This is a release boundary, not merely a later milestone within b2. No specific
release number is assigned here. These are design options, not implemented
capabilities or frozen ABI allocations. The b2 manager retains
basic DISPATCH/LOOKUP, pinned providers and existing foreground IRQ-disabled
calling restrictions. It need not allocate a fast-slot table or additional
zero-page bytes.

### Indexed call slots

A table of eight 16-bit target pointers occupies 16 bytes; eight actual JMP
instructions occupy 24 bytes. A shared 65C02 trampoline can use
`JMP (table,X)`, with X holding an even byte offset. A caller's JSR to the
trampoline supplies the return address, so the target's RTS returns to the
caller. Selecting a slot this way consumes X; arbitrary service X arguments
require another convention or register-preserving stubs. Slot targets may
eventually be gates rather than raw implementation addresses.

The same scheme can index up to 128 pointers with X offsets `$00,$02,...,$FE`.
A full pointer table costs 256 bytes, excluding provider metadata, validation
and any gates/stubs. Eight was a prototype example, not an architectural
requirement. Supporting a maximum of 128 with a smaller configured capacity
is an option; callers must respect published capacity. Slot count need not
equal total service-registry capacity.

The table can live in ordinary reserved RAM. JMP absolute indexed-indirect
has no special zero-page encoding or timing advantage. `$C0-$CF` was discussed
as a possible eight-pointer area, but remains application zero page: no bytes
there have been reassigned. Current monitor zero page `$E0-$FF` is all assigned,
with some aliases already sharing lifetimes. Further scratch sharing requires
checking called services and nested lifetimes; persistent registry data should
not be placed in transient scratch. Measure any proposed 8-16-byte dedicated
manager zero-page allocation before changing the published application contract.

### Cycle-derived timing at 8 MHz

At 8 MHz one cycle is 0.125 microseconds. For the simple same-bank paths below,
entry latency excludes the callee body and assumes no interrupts or bus stalls.

| Call path | Entry cycles | Entry latency |
| --- | ---: | ---: |
| Direct JSR | 6 | 0.75 microseconds |
| JSR followed by a fixed absolute JMP stub | 9 | 1.125 microseconds |
| JSR followed by JMP (table,X), X already selected | 12 | 1.50 microseconds |
| LDX immediate plus the indexed call | 14 | 1.75 microseconds |

The target's RTS adds 6 cycles (0.75 microseconds): the last path has 20 cycles
of selection/call/return overhead, or 2.50 microseconds. These are instruction
calculations, not a measured manager benchmark. See the
[WDC W65C02S datasheet](https://www.westerndesigncenter.com/wdc/documentation/w65c02s.pdf).
Name/version lookup has implementation-dependent cost; resolving once avoids
repeating it on each call. A previously resolved ordinary service can have
similarly small overhead. Register preservation, bank gates and policy wrappers
must be measured separately. Fast slots avoid lookup; they do not outperform
direct JSR merely by being indexed.

### Interrupt policy is independent of lookup speed

A jump slot does not change interrupt state. Future services could separately
declare IRQ-disabled, short atomic, or interrupt-capable contracts. A fast slot
may target an interrupt-capable service, and a slow lookup may resolve an
IRQ-disabled service; access path and interrupt policy are distinct attributes.
No interrupt-capable contract is advertised by the b2 manager.

SEI defers maskable IRQs, not NMI. Any future wrapper changing interrupt state
must restore the agreed caller state while preserving the callee's documented
result flags. Interrupt-capable banked execution additionally requires valid
handlers, vectors and state while each bank is visible, plus explicit scratch
and reentrancy rules. IRQ deferral is the entire disabled interval, including
the callee and any lookup or gate work, not just dispatch latency. Establish
those contracts and measured bounds before enabling such calls.

## Execution and RAM lifetime

The recommended first implementation executes extensions from resident-bank
ROM or reserved/claimed RAM. Executing directly from other flash banks requires
RAM call gates that restore bank state; nested calls and a dynamic linker are
larger capabilities described in earlier proposals, not included in the small
interface estimate below.

Supporting code stored in any bank is a separate promise from executing it
there. A module stored elsewhere may require validation and copying into RAM.
The loader, manager, and active module state must have known ownership and
lifetime. L, G, R, prompt reentry, reset, and unloading must not leave hooks
pointing into overwritten application RAM. This bootstrap/lifetime contract
is a prerequisite, not an implementation detail to postpone.

The earlier a24c2 proposal reserves `$7100-$78FF` for an RST worker, moves
staging to `$6100-$70FF`, and lowers application RAM to `$5FFF`. It remains a
historical, unimplemented layout. On October 3 the user selected a further
2 KiB reduction for b2, reserving a separate area for possible overlays.

The selected b2 planning allocation is:

| Address range | Use | Size |
| --- | --- | ---: |
| `$0200-$57FF` | Application RAM | 22,016 bytes (21.5 KiB) |
| `$5800-$5FFF` | Overlay/module workspace reservation | 2,048 bytes |
| `$6000-$60FF` | Reserved; purpose unassigned | 256 bytes |
| `$6100-$70FF` | Flash-sector staging buffer | 4,096 bytes |
| `$7100-$78FF` | Shared manager/module reservation | 2,048 bytes |
| `$7900-$7BFF` | Existing RAM worker reservation | 768 bytes |

Zero-page, stack, and allocations at `$7C00` and above retain their current
boundaries. Application RAM loses 4,352 bytes (4.25 KiB) relative to the
implemented `$0200-$68FF` range. Public entry addresses can remain fixed, but
this is a change to the application memory contract.

The overlay reservation has no general loader or allocator. Permanent H
executes in B3:C and uses a three-byte stub in manager RAM, leaving all
`$5800-$5FFF` available. Future overlay code, private state and transfer
workspace must fit the declared allocation. When general overlays are
implemented, only explicitly
owned and inactive overlay contents may be replaced; the manager, return path
and any active call state must survive. Ordinary application loading/restoring
must not overwrite either reservation. Protected module installation needs its
own bounded path rather than bypassing application checks.

The pinned manager/RTS candidate fits its declared allocations, with RTS code
in resident E flash. The complete AP runtime fit has not been measured.
With the existing ASM state/name allocations of 13,678 bytes,
the new application range would leave 8,338 bytes before other runtime, object
and buffer allocations, assuming assembler code remains in flash.

Beta 1 retains its RAM map. The b2 candidate moves staging references and
enforces the `$57FF` application ceiling, with boundary, staging and module
lifetime checks. Installer and maintenance tools still need b2-specific updates
and qualification.

## Optional named storage

S, R and T may be separate optional command modules sharing one storage service.
S owns save/placement, R owns restore and T owns listing. Record discovery, name
matching, integrity validation and configured-area policy are shared rather
than copied into all three. R/T can be installed without S. Separate modules
do not by themselves reduce RAM; placement and loading policy determine that.

Design that storage interface for multiple backends. Start with flash; an
optional qualified EDU SPI-SRAM driver can later register another backend with
the same manager. Installing an EDU board does not alone establish that the
SRAM chip is populated, accessible or qualified. Absent hardware leaves the
flash path and core recovery usable.

Commands use record handles and bounded transfers, not an assumption that
every stored byte has a CPU-addressable pointer or bank/sector location.
Backend offsets must accommodate more than 64 KiB; a 24-bit byte offset is a
candidate representation, not a frozen ABI. Backend capabilities describe
capacity, transfer bounds, write/erase constraints and retention guarantees.
Flash erase/program policy and SPI transfers belong behind this interface.

Configuration explicitly enables storage backends and their allocatable areas.
New hardware is not automatically claimed as free storage. Name ambiguity
rules apply across enabled search areas. SPI SRAM can hold snapshots, source,
AP objects or staging data, with separate ownership and record types. Serial
storage does not enlarge directly executable application RAM: code must be
copied into CPU-addressable RAM before execution. Power-loss retention depends
on the installed part and backup circuitry; validate retained records before
using them. Driver size and transfer workspace remain to be measured.

Implemented first-candidate command syntax:

```text
S 2000 2FFF DEMO       Save with automatic placement in configured storage
S 2000 2FFF DEMO B1    Restrict placement to configured Bank 1 areas
R DEMO                Restore a named record to its recorded RAM address
R DEMO B1             Restrict the name search to Bank 1
T                     List records across configured storage
T B1                  Restrict the listing to Bank 1
```

The configuration specifies permitted bank/sector areas. Four six-bit sector
masks are implemented in CF/01. The explicit bank argument
does not override an exclusion. Core, configuration, manager, and module code
must be protected from automatic storage allocation.

Recommended first allocator: choose the first wholly erased extent large enough
for a complete record within permitted contiguous sectors in one bank. It must
not cross an excluded sector or bank boundary, infer ownership from erased
bytes outside the configured pool, or erase existing contents to make room.

The candidate uses the existing SR/01 fixed 16-byte field as its name, with
structural validation and the pending/complete protocol. It has no payload
checksum. The older variable-length/checksummed record proposal is a different,
future format and is not silently adopted by this implementation.

Implemented initial name policy: 1–16 printable non-space characters,
normalized uppercase at the monitor; reject duplicates within the selected
search pool and refuse ambiguous restores. The CLI uses automatic placement;
the low-level save service retains address-based requests. Replacement,
deletion and reclamation remain future work.
Restoring and executing remain separate operations unless explicitly changed.

## Configuration tools and C

The migrator can ask the user to choose a configuration sector and storage
areas during setup. Bank Maintenance can inspect or change those choices later.
They share the format and validation policy; the migrator must also work before
the installed services exist. Reserving an area does not erase it. Creating,
formatting, moving, and reclaiming storage are distinct guarded operations.

The recommended direction is for C to invoke an optional configuration-editor
module. It can edit boot settings, the locator, permitted storage, and extension
registrations through separate operations. C can be installed without S/R/T.
Without the manager/C module, configuration remains manageable through the
migrator or Bank Maintenance; core boot does not depend on that editor.

Configuration moves need a verified new copy before changing the locator, a
defined invalid/incomplete-update response, and consistent protection rules in
all writers. The exact update/recovery protocol is still to be designed.

## Size accounting

The table below preserves the pre-implementation beta 1 measurements and
broader configuration-interface estimates. The measured first-candidate sizes
are in Current implementation and the candidate guide. The candidate keeps C
in the core and places its service directory in manager RAM. Its external
locator/K implementation is now measured separately from the broader estimate.

| Item | Bytes | Evidence or scope |
| --- | ---: | --- |
| Current free resident space | 53 | Measured, contiguous |
| Existing S/R/T dispatcher | 53 | Measured; replaceable by general dispatch |
| Existing C editor | 197 | Measured; excludes boot reader/checker |
| Existing C display | 54 | Measured; potential move with editor |
| Existing S/R/T code | 1,208 | Measured; excludes proposed new features |
| Service table and query alone | About 35 | Earlier design estimate for a limited service set |
| Small core extension interface | 160–245 gross | Preliminary estimate, not assembled |
| Net growth after replacing S/R/T dispatch | 107–192 | Arithmetic from that estimate |
| Further space needed with C still in core | 54–139 | Net growth minus current 53 free bytes |

Moving the C editor and display offers 251 measured bytes before replacement
stubs, retained helpers, and integration changes. This makes room plausible;
it is not a verified b2 layout. Editing code moves into a module and still
consumes storage there.

The 160–245 estimate covers a small service directory, locator, configuration
header checks, invocation path, and associated core changes. It does not size
the complete manager, independent-module loader/registry, shell, dynamic linker,
configuration UI, or new S/R/T allocator and name scanner. The earlier 24–48-byte
RAM allowance was similarly for interface state, not the entire runtime.
A 26-byte example X handler excludes all shared manager and registration costs.

A dedicated configuration sector reserves 4 KiB of flash even if its first
format uses only a small header and a few records. No combined manager/module
fit for the full proposed manager/linker/configuration stack in the older
2 KiB RAM reservation has been established. The pinned manager/RTS milestone
fits the b2 reservations by retaining RTS executable code in flash.

## Decisions and implementation order

### First manager milestone

The user has selected one manager with two public entry points, DISPATCH and
LOOKUP. Management operations can be discovered services; they do not each need
a new fixed core entry. The candidate guide and public include assign the
format-1 entries and descriptor fields.

The first prototype is independently built as 2.0b2. It contains a static
versioned service directory, eight command slots, named RTS and an independently
registered X test handler. It preserves built-in precedence and C in the core.
Duplicate commands are rejected; service lookup requires exact versions.
General service-provider registration is future AP work.

LOOKUP resolves a service once to its documented callable entry. Initially
providers are pinned, so a returned entry remains valid for the initialized
manager session. A later replaceable-provider capability must supply a stable
slot or retained binding contract; it cannot reuse that promise for movable
raw addresses. There is no repeated name lookup on the ordinary call path.

The prototype does not advertise AP relocation, dynamic replacement, module
unload, or arbitrary cross-bank execution. It distinguishes lookup failure,
interface incompatibility and unsupported operations. Code/state ownership,
stack balance, reset/reentry and protection against application overwrites are
part of the first proof, alongside size measurements and CPU-mode restrictions.
Indexed fast slots, larger slot capacities and per-service interrupt handling
are deferred to a full decimal-version release. They are outside b2 scope,
including later b2 milestones.

The user has selected the `$57FF` application limit and a separate 2 KiB overlay
reservation as recorded above. The first candidate initializes on the first
extension command. Absence or an invalid image keeps core recovery available.
No external configuration sector is assigned yet.

Default implementation choices: 65C02-compatible code, 816 emulation-mode
monitor calls, foreground execution, pinned initial providers, versioned
descriptors and capability checks. Use the existing public RAM console services.
Measure manager and module state independently of the earlier core-hook estimate.

The candidate settles pinned execution, RAM lifetime, command matching,
service inventory, saved-name policy, persistent storage policy and the
configuration locator/K editor. The next work is installation-tool updates and board
qualification. The following sequence records the overall direction; steps
1–2, step 3's core hook/locator, and step 4's named RTS/configuration management
are implemented. C remains the core boot editor; K is the optional extended
configuration editor. Installation tooling and full generic descriptors are
not implied by those completed portions.

1. Define the manager's versioned service/command contracts, pinned-provider
   policy and explicit RAM ownership, keeping the later AP binding path open.
2. Prototype the manager with pinned core services and an independently
   registered X command. Measure code/state and test dispatch, reset/reentry,
   and protection of registered code/state. No AP linker is required.
3. Integrate the small core hook and locator, keeping absent/corrupt-extension
   boot and recovery working. Measure the actual need to move C.
4. Add configuration management and optional S/R/T using the same manager and
   service contract; implement automatic placement and named lookup.
5. Update migrator and Bank Maintenance, test configuration moves and exclusion
   policies, then qualify both CPU families and package the b2 candidate.
6. Add AP loading/linking behind the manager's service boundary. Measure its
   dependency-complete code/RAM requirements and prove relocation and service
   resolution using the recorded RAM console-provider example. Add retained
   bindings, replacement and bank-aware execution in separately tested stages.

The implementation uses a separate 2.0b2 banner, build directory and filenames;
release packaging remains future work. The service table, manager/module descriptors, and
saved-record format have their own versions. Preserve the established public
interface where promised; document any adopted RAM-boundary change separately.
General cross-bank linking, live replacement, and the assembler remain staged
AP runtime work. Their scope and size must be measured separately; this small
host-interface estimate neither includes them nor cancels the recorded direction.

## Related records

The latest installed [selective autoload candidate](STR8N_V2_B2_AUTOLOAD.md) now
implements the independent configuration startup list. It retains one manager,
one logical service namespace and the existing AP linking direction. K selects
resident returning command providers; C independently selects application boot.
This source revision is installed and checked on 2205 with application autostart
disabled and R/S/T/X/H selected independently through K.

- [Current public ABI](../src/v2-config/str8n-v2-public.inc)
- [Current configuration implementation](../src/v2-config/str8n-v2-config.inc)
- [Current S/R/T implementation](../src/v2-config/str8n-v2-sr.asm)
- [Earlier RAM reservation](STR8N_V2_A24C2_RAM_LAYOUT.md)
- [Earlier storage and command-hook proposal](STR8N_V2_COMPONENT_STORAGE_PROPOSAL.md)
- [Runtime linking direction](STR8N_V2_RUNTIME_LINKING_DIRECTION.md)
- [Layered assembler and runtime proposal](STR8N_V2_LAYERED_ASSEMBLER_PROPOSAL.md)

Earlier proposals retain their historical status. This draft identifies where
they need reconciliation; it does not turn their unimplemented features into
current behavior or silently cancel previously recorded decisions.
