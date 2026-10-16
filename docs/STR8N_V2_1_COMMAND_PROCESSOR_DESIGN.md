# STR8-N v2.1 command processor design draft

Date: 2026-10-12. Status: design proposal; addresses and byte ceilings below
are implementation targets, not assembled or hardware-qualified allocations.

V2.1 introduces one command registry and a bounded command interpreter above
the existing monitor services. It preserves beta23 command syntax, adds HELP
and STATUS, and provides consistent names for entering utility consoles. The
processor decodes a request and returns before the monitor executes it. Flash,
RTC, SRAM and workspace services retain their own validation and write policy.

Beta23 generation 32 remains frozen. Implement v2.1 in separate source and
build directories; never regenerate, patch or install over the beta23 freeze as
part of this design work. V2.1 acceptance requires evidence for its own image.

## Architecture and scope

The normal command path is:

```text
B0 through B3 prompt
  -> existing bounded line reader
  -> validate and load the v2.1 processor into monitor staging RAM
  -> resolve command and decode request
  -> return to the resident B3 executor and release staging
  -> validate remaining operands and invoke a service or launch a utility
  -> print result and return to the prompt, or transfer control
```

The line reader retains its 40-character limit, uppercase input, backspace,
tab-to-space conversion, CR/LF pairing, Ctrl-C behavior and sticky invalid-input
and overflow refusal. The initial release retains existing leading-space
behavior. It does not execute a truncated prefix or silently remove controls.
Addresses, banks and ordinary monitor data retain hexadecimal notation;
utility-specific decimal notation remains within the utility console.

The processor executes from CPU RAM while physical B3 remains selected. Its
loader uses the existing bank-safe RAM worker to read its flash asset. It does
not execute code from B2, so the command layer introduces no new interval of
cross-bank flash execution or dependency on B2 interrupt vectors. The existing
worker and service bank transitions still require their interrupt regressions.

The processor cannot call flash-resident handlers while decoding. It can use
the public RAM console entries for help output and cancellation checks. It
never calls RTC, journal, SPI, storage or WORK while it owns staging RAM. A
successful decode is a request to execute, not evidence that a device is present
or that an operation is authorized by its service.

Decode routines save any live cursor, pointer or register across public RAM
console calls whose preservation is unspecified. Their stack and scratch use
is included in the budgets; they cannot assume that PUTC or CHECK_CANCEL
preserves their parsing state.

Initial v2.1 scope includes the legacy monitor commands, HELP, STATUS and bare
CLOCK, SRAM, WORK, EDU and MAINT names. Utility arguments such as `CLOCK SET`,
`SRAM DELETE` and `WORK CLAIM` remain deferred. The initial processor does not
add scripts, command chaining, pipes, variables, background jobs, dynamic
registration or a public application command-execution ABI.

## Command registry

The authoritative source is a proposed `src/v2.1/commands.json`. Generate the
descriptor table, name strings, grammar references, executor constants and
help index from it. The generator rejects duplicate names, reserved-name
collisions, unknown actions, invalid capabilities and out-of-range references.
It checks the complete registry before emitting artifacts.

Names require an exact token boundary. Only B/J bank suffixes and the existing
M1 through M3 compact forms use explicitly declared compact matching; suffix
matching is never inferred from a command's first letter. Help and dispatch use
the same entries. No command abbreviations are added.

The following 25 entries use fixed action IDs. IDs are private to the v2.1
processor/executor pair and are not public RAM ABI ordinals.

| ID hex | Name and accepted form | Executor action | Effect and ownership |
| --- | --- | --- | --- |
| 01 | `?` | Grouped help | Read only; rejects arguments |
| 02 | `HELP [command]` | Registry help or command usage | Read only; one exact command name |
| 03 | `STATUS` | New query adapter using existing detailed formatters | Read only; monitor staging only |
| 04 | `B0` through `B3` | Select logical bank | Session state; physical monitor stays B3 |
| 05 | `D start [end]` | Memory display | Read only; existing I/O and range guards |
| 06 | `M addr byte ...`, bare `M`, `M 1` through `M 3`, compact `M1` through `M3` | RAM edit or MAINT map adapter | Edit modifies explicit RAM; map loads MAINT |
| 07 | `G address` | Execute address | Nonreturning handoff after preflight |
| 08 | `L` | Receive S19 into RAM | Stream owns input; existing range policy |
| 09 | `F addr byte ...` | Guarded flash edit | Persistent write; existing confirmation and wear policy |
| 0A | `I start end` | Aligned S19 flash install | Stream and persistent write; existing guards |
| 0B | `C [enable bank address-or-V delay]` | Startup configuration | Query or confirmed journal write |
| 0C | `J0` through `J3` | Bank reset-vector handoff | Nonreturning; J3 cold initialization |
| 0D | `S bank flash-or-AUTO start end [name]` | Flash SAVE | Persistent write with existing SAVE behavior |
| 0E | `R [bank] name [L]`, `R bank flash [L]` | RESTORE or preserving SRAM adapter | Load or handoff; preserves special R SRAM rules |
| 0F | `T [bank-or-first-last]` | Stored-record table | Read only |
| 10 | `W` | Wear report | Read only |
| 11 | `U A`, `U B` | Inactive monitor-slot update | Persistent write; exact generation/slot guards |
| 12 | `P`, `P A`, `P B` | Preferred slot query/save | Query or confirmed journal write |
| 13 | `APPS` | Validated application inventory | Read only; corrupt entries reported explicitly |
| 14 | `TIME` | Existing detailed time adapter | Requires validated RTC capability; no ACK/write |
| 15 | `CLOCK` | Alias of `R CLOCK` | Utility handoff; owns loaded application RAM |
| 16 | `SRAM` | Alias of preserving `R SRAM` | Requires SRAM capability; entry/exit preserve application RAM |
| 17 | `WORK` | Alias of `R WORK` | Utility handoff; owns $5000 through $648A with current WORK |
| 18 | `EDU` | Alias of `R EDU` | Utility handoff; remains available with EDU OFF |
| 19 | `MAINT` | Alias of `R MAINT` | Utility handoff; declares the loaded utility footprint |

The legacy grammar above is an inventory, not a replacement specification for
all accepted spacing and disambiguation. Before implementing compatibility,
capture the exact beta23 parser behavior, particularly M/M1, R qualifiers,
names and AUTO, and encode it as golden cases. Retain the qualified accepted
forms. Malformed forms that currently alias an unintended command must be
rejected and listed as explicit v2.1 corrections.

Built-ins win over application names. Unknown valid tokens fall back to the
checked named-application launcher only after the processor has returned and
released staging. Never fall back after a recognized built-in has bad operands.
Bare utility names are built-ins routing through the stored-record loader;
they are not proof of an installed application descriptor. All five bare
utility aliases reject arguments in this release.

HELP lists optional commands even when unavailable and explains the requirement.
TIME requires SV RTC bit $01; SRAM requires bit $08. Other bare utility aliases
are resolved through the loader and utility discovery rather than assuming
that an SV capability proves their records exist. EDU must work while OFF.

STATUS reports CPU, active application RAM ceiling, active/saved EDU state,
validated optional capabilities and time/service status. It invokes formatters
through a query-only path: no cold initialization, outage logging or ACK,
identity acceptance, storage initialization or settings save. An unavailable
optional device is reported in the status output without preventing the CPU
and memory report. Existing boot entry points cannot be reused blindly as a
STATUS handler.

### Descriptor format

Each descriptor is 16 bytes. The table reserves 32 entries, for a 512-byte
ceiling. Unused rows are zero and excluded by the header's entry count.
All word fields are little endian. Pointers are offsets within the sealed asset,
not absolute flash addresses or pointers into an active A/B monitor slot.

| Offset | Bytes | Field |
| --- | --- | --- |
| 00 | 1 | Action ID, nonzero for an active entry |
| 01 | 1 | Grammar ID |
| 02 | 1 | Effect flags: $01 mutation possible, $02 stream, $04 handoff possible, $08 utility load possible, $10 compact suffix matcher |
| 03 | 1 | Required SV capability mask; zero means no pre-dispatch SV requirement |
| 04 | 2 | Name offset from asset base |
| 06 | 1 | Name length, 1 through 11 |
| 07 | 1 | Help entry ID |
| 08 | 2 | Grammar metadata offset from asset base |
| 0A | 1 | Executor profile ID; zero for ordinary monitor actions |
| 0B through 0F | 5 | Reserved zero |

Effect flags describe potential effects and help/testing requirements. They
cannot bypass service guards or manufacture confirmation. Conditional commands
such as C/P/M carry the union of possible effects; the resolved variant determines
the actual action. Descriptor fields and all referenced ranges are validated
before use. The generator emits the B3 action routing table independently;
no untrusted descriptor supplies an executable handler pointer.

## Request and handler contracts

### Decode request

Allocate a private 64-byte request at $7C40 through $7C7F, subject to the complete
RAM ownership audit. No public entry or discovery signature is added there.
The immutable input remains at $7C00 through $7C28, including its terminator.
The processor uses an offset cursor instead of a token array, so the number of
tokens is bounded by line length rather than an artificial argument limit.

| Request offset | Bytes | Meaning |
| --- | --- | --- |
| 00 | 1 | Format, 1 |
| 01 | 1 | Action ID; zero for unresolved application token |
| 02 | 1 | Resolved variant/profile |
| 03 | 1 | Decode result |
| 04 | 1 | Input length, 0 through 40 |
| 05 | 1 | First operand offset within the input line |
| 06 | 1 | Remaining operand length |
| 07 | 1 | Argument cursor within the input line |
| 08 | 1 | Saved logical bank |
| 09 | 1 | Effective effect flags |
| 0A | 1 | Underlying service status, zero until execution |
| 0B | 1 | Active owner/phase: idle, decode or execute |
| 0C | 1 | Error character offset; $FF when not applicable |
| 0D | 1 | Parsed value count |
| 0E through 0F | 2 | Reserved zero |
| 10 through 2F | 32 | Typed operand area: up to eight LE16 values, then bounded name/other spans |
| 30 through 3F | 16 | Private decoding/executor workspace |

The processor initializes the complete request for each accepted input line.
It validates command boundaries and its own grammars; existing complex legacy
grammars initially use a B3 adapter with the original complete input line.
An adapter must finish syntax and range preflight before any mutation. Migrating
a grammar into the processor is a separate measured change with compatibility
checks. Success from decode means only that an executor action was selected.

The loader saves/restores the logical bank around all processor reads. It
validates the E extension before using its loader; an invalid E seal selects
the slot-resident rescue path directly. The copied decode entry is invoked
with JSR and returns with the original stack depth, physical B3 selected and
the required CPU profile. It sets A and request byte 03 to the same result,
with Carry set only for result 00. No application fallback is permitted except
for result 01 with action zero and a syntactically valid unresolved name.

For ?/HELP, the processor may render registry help while its copy is live.
On success it returns resolved variant $80, meaning report already complete;
the executor performs cleanup without invoking another help printer. Other
actions return a pending execution request. This variant is private to those
two help actions and cannot suppress ordinary handler validation.

### Returning handlers

The B3 executor invokes returning handlers with JSR, physical B3 selected,
IRQ disabled and decimal clear. On 816 the required profile is E=1, D=0,
DBR=0 and PBR=0. X/Y and arithmetic flags are unspecified; the handler restores
the stack and returns in that CPU profile. A returns the command result and
Carry is set only for success. The request records the original service status
when a service fails; statuses from different service families are not conflated.

| Result hex | Meaning |
| --- | --- |
| 00 | Success |
| 01 | Unknown command or unresolved application name |
| 02 | Bad arguments or invalid input |
| 03 | Service, record or processor unavailable/incompatible |
| 04 | Canceled |
| 05 | Busy or forbidden reentry |
| 06 | Protected address or policy refusal |
| 07 | Service failure; underlying status retained |
| 08 | Verification failure or corrupt component |

The executor owns the prompt and generic error output. A returning handler may
print its successful report or a contextual service diagnostic, but marks that
diagnostic as emitted in its adapter-local execution state so the executor does
not duplicate it. Legacy adapters can retain established messages while they
transition to the result contract. They must converge on one B3 completion
entry rather than jump past executor cleanup.

Returning read-only handlers preserve the saved logical bank. Commands whose
purpose changes it retain their established behavior: B changes selection and
legacy SAVE/AUTO may select the destination. Physical B3 is restored before
the prompt regardless of the displayed logical bank. A private owner guard
rejects nested dispatch before altering an active request.

### Streams and handoffs

L/I/U own the console receive path after dispatch. Their receiver interprets
incoming S19 or binary data; no received payload line enters the command
processor. Existing transfer cancellation, framing and post-upload halt rules
remain authoritative. Release the dispatch request only through completion or
an intentional nonreturning transfer.

G/J, run-mode R and utility entry are tail transfers after complete validation.
They do not return through the command handler's JSR stack. The executor clears
its owner state before transfer and uses the existing stack-normalizing worker
handoff. A failed preflight returns a normal result. Application exit remains
JMP HOLD; RESET/J3 performs cold initialization, not a command-handler return.

HOLD revalidates the processor loader/request ownership, reinitializes private
dispatch state and loads the processor afresh for the next command. No decoded
request, copied processor code or application-provided private pointer is trusted
across application execution. WORK claims retain their existing return/reset
semantics. Optional signatures below the active RAM ceiling are not inspected
before valid capability discovery.

### Confirmation and memory preservation

The processor never puts a generic YES around every command. Preserve the
operation's existing policy: SAVE remains immediate after preflight; EDU uses
single Y; CLOCK administration retains full YES in its utility console. Changing
confirmation rules requires a separate explicit user-interface decision.

Read-only reports must preserve application RAM through the discovered ceiling.
Preserving SRAM entry retains its existing contract. MAINT/CLOCK/WORK/EDU
loads own their documented code and data footprints, and explicit restore or
edit operations intentionally replace their targets. The layer provides neither
memory isolation nor additional public application RAM.

## Memory and flash budget

### Proposed flash allocation

Reserve **B2:F000 through FFFF**, one new 4,096-byte sector, for the sealed
processor asset. This is a new ownership claim, not inferred free space.
Beta23's status asset occupies B2:C800 through D1FF, its local display starts
at B2:E000, and CLOCK 1.6 is stored at B1:B000. B2:D is therefore unsuitable
for a standalone new processor sector.

Keep B2:FFE0 through FFFF erased to avoid introducing reset/interrupt-vector
contents in this data asset. Copy the asset into RAM for execution; never boot
or execute it in flash. Preserve B3:F and its vector bytes exactly.

| Asset component | Ceiling in bytes |
| --- | ---: |
| Header | 32 |
| Bounded parser and request decoding | 768 |
| Command lookup and availability checks | 192 |
| 32 descriptor rows | 512 |
| Grammar metadata | 192 |
| Names and aliases | 192 |
| Help text and index | 768 |
| Decode adapters and diagnostics | 256 |
| Internal scratch | 96 |
| Reserved growth space | 1,054 |
| CRC at B2:FFDE through FFDF | 2 |
| Erased vector tail | 32 |
| **Total** | **4,096** |

The initialized component budget is 2,912 bytes before scratch, reserved space,
CRC and tail.
No component may use the tail or consume growth space without updating the
budget manifest. The asset header records magic `CP`, format 1, host profile 1,
image size, entry offset, registry offset/count, help bounds and executor
compatibility ID. Remaining header bytes are zero. CRC-16/CCITT-FALSE covers
the whole 4,096-byte image except its two CRC bytes, including padding and the
erased tail; the stored CRC is little endian. Validate lengths, offsets and
compatibility as well as CRC before executing the copied entry.

| Header offset | Bytes | Meaning |
| --- | --- | --- |
| 00 | 2 | Magic CP |
| 02 | 1 | Format 1 |
| 03 | 1 | Host profile 1, 65C02 or 816 emulation |
| 04 | 2 | Image size, 4,096 |
| 06 | 2 | Entry offset, initially $0020 |
| 08 | 2 | Registry offset |
| 0A | 1 | Active descriptor count, initially 25 |
| 0B | 1 | Descriptor stride, 16 |
| 0C | 2 | Help area offset |
| 0E | 2 | Help area length |
| 10 | 2 | Grammar metadata offset |
| 12 | 2 | Grammar metadata length |
| 14 | 4 | Executor compatibility ID |
| 18 | 2 | Scratch offset, initially $0C00 |
| 1A | 2 | Scratch length, 96 |
| 1C through 1F | 4 | Reserved zero |

Scratch is initially linked at $7400 through $745F and initialized to zero
in the asset. The initialized components must finish by $7360 under the
specified ceilings. Scratch cannot expand into live code/help or the CRC/tail;
it is included in the seal before runtime use. No scratch byte is relied upon
across reloads. The header's offsets must agree with the compiled private
layout, not merely fall within the overall image.

The B3:E extension owns the loader and executor. Its **net growth ceiling is
128 bytes**, obtained by removing replaced lookup/help code or moving suitable
metadata into the processor asset. Budget approximately 192 bytes for the
loader/verification path and 128 for executor routing/adapters; the build must
prove enough replaced bytes are removed to meet the net ceiling. Existing
launcher validation, service initialization, storage support and CRC seals
remain mandatory. This ceiling is a feasibility gate, not a claim that E has
128 currently unused bytes.

Each A/B monitor slot has a **net growth ceiling of 24 bytes** for entry and
completion routing. Every complete sealed slot must still fit exactly its
4,096-byte allocation with the existing required header/trailer. The frozen
manifest reports 3,967 monitor code bytes per slot, so additions require exact
linker accounting rather than treating all remaining sector bytes as code space.
B3:F has a zero-byte change budget.

### Proposed CPU RAM allocation

| CPU range | Bytes | Owner and lifetime |
| --- | ---: | --- |
| $7C00 through $7C28 | 41 | Existing input and terminator; retained until handler parses it |
| $7C40 through $7C7F | 64 | New private request; survives decode return, released at completion/handoff |
| $6800 through $77FF | 4,096 | Processor copy and internal scratch while decoding/help only |
| $7C80 through $7CFF | 128 | Existing transfer/preflight scratch; loader may borrow after line input |
| $00E0 through $00FF | 32 | Existing monitor scratch; explicit per-phase aliases, no new ZP reservation |
| CPU stack | at most 48 additional bytes | Processor/loader call chain; prove deepest path plus interrupt headroom |

The processor entry is $6820 if the 32-byte header size is retained. All internal
references are linked for the RAM origin; flash metadata pointers are asset
offsets. Scratch lives within the processor's 4 KiB allocation and cannot overlap
live code, registry, help or return paths. The component budget above must
include any initialized data and account explicitly for scratch placement.

The incremental persistent private RAM cost is **64 bytes**, with **zero added
application RAM reservation** in either EDU mode. The 4 KiB decode lease reuses
existing staging; it is not a simultaneous additional allocation. Status/local
display, flash staging, journals and the SRAM manager can overwrite it only
after the decode call has returned. No continuation or handler pointer may
refer into the released copy. Request bytes survive those later leases.

The RAM audit must cover assembled effective addresses and buffer spans, not
only literal searches for $7C40. A collision with a current utility, worker or
private bulk-copy path blocks this allocation. Relocation requires a revised
map and qualification; it cannot silently reduce application RAM.

### Ownership and migration rules

Protect B2:F in normal SAVE, explicit record placement, AUTO, raw flash edits,
installers and MAINT erase/copy policies. AUTO already stops before E in the
current service, but that alone does not protect explicit writes. Teach maps
and ownership displays the new reservation. Ordinary D can inspect it.

A v2.1 migrator must establish that the entire proposed sector is erased or
contains an exact recognized processor preimage. A record extent or any other
occupied/unknown byte causes refusal before mutation. Record migration is a
separate preservation workflow; the installer does not erase a conflict.

Stage the processor asset before activating monitor slots that depend on it.
Bind the asset, executor and both slots to a compatibility ID and artifact
hashes. Exact update order, preference handling and source-version support are
decided by the offline interruption model before an installer is accepted.
Preserve unaffected sector bytes, existing saved records, B3:9 identity/offset
tail, configuration, device contents and erase-attempt accounting.

## Failure and recovery behavior

If the processor is absent, incompatible or corrupt, never execute its RAM
copy. The normal monitor reports `Command processor unavailable` and exposes
a small independent rescue dispatcher in each validated B3 monitor slot,
outside E and the processor asset. Reserve exact bare `?`, `J3` and
`W` for this fallback. Its help explains entering fixed recovery with J3 then
S, followed by the existing REC commands. It does not send ordinary input to
an unvalidated extension or offer an implicit reformat/reinstallation path.
The fallback is included in the E/slot byte ceilings.

Fixed F recovery must still operate with both normal monitor slots invalid,
and must not require the processor sector or its private request. Updating a
monitor slot through REC does not install a missing processor asset; recovery
documentation must explain that distinction and the supported full migration
path. Retaining fixed F does not resolve the existing erased-flash/bootstrap
limitation, STR8N-005. Do not advertise F-only bootstrap as a v2.1 feature.

APPS acceptance includes valid names/status and corruption refusal. STR8N-004
needs its own identified cause and regression; a new command registry does not
close it automatically. Do not modify the deferred beta23 image to investigate
the v2.1 path during this design task.

## Qualification plan

All gates refer to one explicit v2.1 source/build identity. Earlier beta23
hardware receipts remain historical evidence. Models do not qualify physical
boards, and a design budget does not certify assembled fit.

| Gate | Required work and evidence | Pass criterion |
| --- | --- | --- |
| 0 Source isolation | Dedicated src/v2.1 and BUILD/v2.1 paths; hash beta23 freeze before/after; explicit dependency inventory | Beta23 frozen tree/artifacts unchanged; no builder output points at a beta23 destination |
| 1 Link and ownership | Exact flash/RAM maps, loader/slot sizes, maximum stack path, scratch liveness, reservation checks | All ceilings met; no simultaneous overlap; zero new application RAM reservation; fixed F hash identical |
| 2 Registry and parser | Golden beta23 forms; all 25 entries; unknown/duplicate/reserved names; HELP; boundaries; compact B/J/M; malformed input and line draining | Each input resolves once or refuses; no built-in error falls through to an application; help matches registry |
| 3 Decode and executor | Valid and corrupt/missing processor; wrong version/profile/compatibility; forged offsets/counts/action IDs; request lifecycle; reentry; logical/physical bank results | Unvalidated asset never executes; all returning paths clean up; no continuation in released staging; rescue dispatcher works |
| 4 Services and preservation | EDU ON/OFF; absent/partial services; stopped clock/bus failure; status, time, storage, WORK; application RAM sentinels and retained-device snapshots | Correct unavailable/error results; no optional-state access while OFF; read-only paths preserve application/retained data |
| 5 Streams and writes | L/I/U framing, split reads, CRLF, overflow, Ctrl-C, wrong payload; M/F/S/R/C/P and utility confirmations | Payload never reaches CP; invalid/canceled requests cause no unintended write; service range, CRC, journal and wear rules retained |
| 6 Interrupts and return | Both slots; 65C02 and 816 emulation; IRQ/BRK/NMI at loader copy, decode, dispatch, transfer and return; HOLD and J3 | Stack/register contracts hold; physical B3 restored; native vector contract retained; no native service-call claim |
| 7 Migration and recovery | Fresh repeated full-bank preimages; occupied sector refusal; exact sector write/erase cuts; corruption/stale plan; mixed old/new slots/assets; missing CP; invalid A/B | Refusal precedes mutation where required; a supported recovery route exists at every modeled interruption; fixed F stays independent |
| 8 Four-board hardware | 2512, 2205, 2604, 2609; each tested on A/B, EDU ON/OFF, required USB paths, utility returns, streams and reserved-sector guards | Per-board exact readback and functional/preservation receipts pass; unsupported ACIA/native service paths are excluded explicitly |
| 9 Endurance and package | Frozen v2.1 candidate, deterministic command sequence, at least 1,000 completed commands per board; separate six-hour run on 2604/2609; clean reproduction and release contents | No unexplained failure or cumulative stack/RAM drift; originals restored; artifact hashes match; complete documentation and examples shipped |

Parser checks include empty/maximal lines, 40 versus 41 printable characters,
paired and lone CR/LF, tabs, invalid controls, deletion, cancellation, extra
arguments, numeric overflow, token-boundary ambiguity and every accepted
legacy form. All rejected mutation cases compare target state before/after.
Measure prompt-to-dispatch latency for representative commands because the
processor reloads 4 KiB each time; record loader time separately from device
work. Agree on an operator latency target after the first linked prototype.

For ownership tests, fill the complete application range with known bytes
except explicitly declared targets, then exercise decode/help/status and
preserving SRAM entry. Repeat with WORK already loaded and live claims.
Exercise status -> SRAM -> TIME -> flash operation -> HELP repeatedly so that
each new staging lease destroys the previous contents. Force HOLD after an
application deliberately changes private CP RAM and verify fresh initialization.

Physical write tests use backed-up test extents and restore their originals.
RTC SET/TRIM, EEPROM history changes and SRAM formatting are separate bounded
cases, not implicit parts of read-only/endurance tests. Expected outage logs,
wear increments, saved test settings and other intentional mutations are
enumerated in each receipt before comparing retained state.

Endurance excludes destructive and administrative writes from its command
count unless a separate preserving procedure authorizes them. Report executed
commands and coverage, rather than equating elapsed time with all-command
coverage. The proposed six-hour gate does not claim a 48-to-72-hour run.

Each gate records the source revision/tree hash, complete artifact hashes,
model report hashes, board/CPU/EDU/slot, executed cases, intentional mutations,
readback comparisons and failures. Keep owner-bound preimages, board backups
and raw serial transcripts outside Git and release ZIPs. Release acceptance
requires no open defect in any advertised command path.

## Implementation sequence and review decisions

1. Capture compatibility cases and complete the RAM/flash liveness audit.
2. Build the registry generator and sealed RAM-linked processor with HELP and
   decode only. Prove slot/E fit, bank restoration and measured latency.
3. Add the B3 executor, rescue path and read-only STATUS/TIME adapters.
4. Route existing commands through their legacy adapters, then add the five
   bare utility aliases. Retain utility consoles and their current contracts.
5. Add B2:F ownership protection and a preimage-bound migration model. Qualify
   mixed-version interruption/recovery before creating a hardware installer.
6. Diagnose the APPS path independently in v2.1, complete the four-board matrix,
   freeze the resulting candidate, run endurance and reproduce its package.

Before implementation, review the one-sector flash cost, 64-byte private RAM
allocation, reload latency and limited initial utility syntax. If the E/slot
ceilings or RAM audit fail, revise this design before increasing reservations.
Do not absorb the new feature into beta23 or move any fixed F entry to make it fit.

## Existing contracts and evidence

- [Beta23 technical guide](STR8N_V2_BETA23_TECHNICAL_GUIDE.md): public RAM ABI,
  discovery, CPU profile, interrupts and current ownership.
- [Storage placement and commands](STR8N_V2_STORAGE_TOOLS_2026-10-08.md):
  preserving R SRAM, WORK footprint, AUTO and MAINT transfers.
- [Beta4 command inventory](STR8N_V2_BETA4_MANUAL.md): original monitor syntax;
  later beta23 contracts take precedence where behavior evolved.
- [Monitor line reader and dispatcher](../src/v2-beta4/str8n-v2.asm),
  [checked application launcher](../src/v2-beta4-launcher/launcher.asm) and
  [status loader](../tools/v2-spi/status-loader.asm): inherited source components;
  exact beta23 behavior is determined by its frozen generated image.
- [Compact boot migration builder](../tools/prepare_v2_compact_boot_upgrade.py):
  frozen status asset length/placement and CLOCK record preservation.
- [Beta23 freeze](STR8N_V2_BETA23_PHASE1_2026-10-09.md),
  [APPS issue](issues/APPS_BETA23_NAMES.md) and
  [F-only bootstrap issue](issues/F_ONLY_RECOVERY_BOOTSTRAP.md).
