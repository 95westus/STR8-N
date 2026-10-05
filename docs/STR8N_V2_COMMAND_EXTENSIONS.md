# Writing a 2.0b2 command extension

**Installed and checked on 2205:** `COMMAND.REGISTER` v2 adds named
commands to the same manager. The X example publishes `HELLO` and `ECHO`,
alongside its existing X command. Core size is 4,039 bytes (9 free); user
RAM and established v1 entry addresses are unchanged. Full readbacks and
direct/legacy command checks passed on October 4, 2026. See the v2 contract below.

The latest installed candidate adds a returning EX/1 initialization contract and
selective `K AUTO` startup. See the [autoload guide](STR8N_V2_B2_AUTOLOAD.md).
It is installed and checked on 2205; the earlier board history and size measurements below
refer to the earlier H/X version. Current H/X builds include C00A/C70A returning
entries as well as compatible C000/C700 manual entries.

October 4, 2026. This guide describes the implemented format-1 manager and a
buildable H+X example. The example is tested in the banked 65C02 host model
and installed on board 2205, with software-reset autostart and all selected
banks checked. See the [qualification record](STR8N_V2_B2_2205_BOARD_TEST_2026-10-04.md).
It does not change the core,
E carrier, public ABI, RAM layout, or the normal permanent-H build.

## What command names work today?

A registered top-level command is **one uppercase letter, A–Z**. The manager
accepts that letter only when the next character is a space or the line ends.
It passes the entire line to the handler. These examples therefore differ:

| Input | Meaning today |
| --- | --- |
| `X` | Invoke registered X with no arguments |
| `X HELLO` | Invoke X; its handler can interpret HELLO |
| `X ECHO SOME TEXT` | Invoke X; its handler can interpret ECHO and its argument |
| `XY` | Does not invoke X |
| `HELLO` | Cannot be registered as a top-level name with format 1 |

Built-in commands have precedence. Choose a letter outside `B D M G L F I C J`
and outside already registered keys. H, K, S, R and T are extensions in the
present installation; `?` is a built-in outside the A–Z registration range.
Registering an otherwise valid built-in letter does not override its core
dispatcher. The registry has eight extension slots; subcommands within X do
not consume additional slots.

The core line reader accepts at most **40 characters**, plus a terminating
NUL at `$7C00`. It converts lowercase ASCII to uppercase and tabs to spaces.
That conversion applies to arguments too: `X ECHO Hello` receives `X ECHO HELLO`.
Overlong or invalid lines are rejected as a whole. Quoting, case preservation,
and parsing arguments are not services supplied by the manager.

## The complete example

The example adds two subcommands:

```text
X HELLO
HELLO FROM X

X ECHO Hello world
HELLO WORLD

X
Use X HELLO or X ECHO text
```

`X HELLO` permits trailing spaces but rejects extra arguments. `X ECHO` prints
the remaining text after leading spaces, or an empty line when no text is
supplied. `X HELLOX`, `X ECHOX text`, and unknown subcommands print usage;
they are not accepted as prefix matches.

The example shares **B3:C** with the existing permanent H provider:

| Allocation | Address | Size |
| --- | --- | ---: |
| Existing H initializer | `$C000–$C170` | 369 flash bytes |
| Existing H handler/text | `$C300–$C628` | 809 flash bytes |
| X initializer | `$C700–$C870` | 369 flash bytes |
| X handler/text | `$C900–$C9F3` | 244 flash bytes |
| Existing H trampoline | `$7400–$7402` | 3 manager RAM bytes |
| X trampoline | `$7403–$7405` | 3 manager RAM bytes |

X adds **613 flash bytes, three manager RAM bytes, and one registry slot**.
Together H+X use 1,791 code/text bytes in the existing 4 KiB sector, leaving
2,305 zero-filled padding bytes. Padding belongs to this provider sector;
it is not RTS storage. No bytes are added to core F or carrier E. No
application or overlay RAM is allocated. Application RAM remains
`$0200–$57FF`: **22,016 bytes (21.5 KiB)**; `$5800–$5FFF` remains a separate
2 KiB overlay reservation.

X temporarily uses monitor foreground scratch `$E0–$E4`. Those bytes are not
an application allocation and are not retained between invocations. This
example owns `$7403–$7405` explicitly; the manager is not a general RAM
allocator and registration does not reserve arbitrary private state for you.

Source files:

- [X command body](../tools/v2-apps/str8n-v2-b2-command-x.asm)
- [X initializer](../tools/v2-apps/str8n-v2-b2-command-x-init.asm)
- [Builder and sector composition](../tools/build_v2_b2_command_example.py)
- [Host tests](../tools/test_v2_b2_command_example.py)
- [Manager ABI](../src/v2-b2/str8n-v2-manager-public.inc)
- [Core ROM/RAM ABI](../src/v2-b2/str8n-v2-public.inc)

## Step 1: choose a lifetime and allocate storage

The registry holds a handler address, not a copy of the handler. Code, text,
and private state must stay valid while registered. Loading a handler at
`$2000` and then replacing that application would leave a dangling command;
the manager refuses ordinary application RAM as a registration target.

Format 1 accepts handler targets in `$5800–$5FFF`, `$7100–$78FF`, or resident
`$E000–$EFFF`. It does not directly accept `$C900`. Consequently this example
registers a tiny pinned RAM trampoline:

```asm
; At 7403, bytes 4C 00 C9:
                        JMP $C900
```

Core dispatch makes the resident bank available for the foreground command.
The RAM JMP enters X's flash body, which returns through the manager's caller.
This has the same arrangement as permanent H. The trampoline is a JMP, so it
adds no extra return address to the stack.

This does not make arbitrary flash banking transparent. X must not change the
mapped bank while executing its flash body or reading its flash text. A
command that needs bank switching or flash mutation needs a suitable RAM
worker and a defined return path, as RTS has. Allocate any larger buffers or
persistent module state explicitly in the reserved module area before adding
such features.

## Step 2: initialize and discover registration

The initializer runs with `SEI` and `CLD`. It checks that the monitor resides
in bank 3, that bank 3 is selected, and that E contains the expected `EM`
descriptor. Calling `$E008` validates and initializes the matching manager;
failure returns to the monitor without copying the X trampoline.

The essential discovery sequence is:

```asm
                        LDA #<REGISTER_NAME
                        LDX #>REGISTER_NAME
                        LDY #$01
                        JSR STR8MGR_LOOKUP
                        BCC UNAVAILABLE
                        CPY #$01           ; must be a callable service
                        BNE UNAVAILABLE
                        STA CALL_PTR       ; save returned low byte
                        STX CALL_PTR+1     ; save returned high byte
...
REGISTER_NAME:          DB "COMMAND.REGISTER",0
```

`STR8MGR_LOOKUP` is `$710E`. Its input A/X is the low/high name pointer;
Y requests an exact interface version. On success carry is set, A/X is the
result pointer, and Y distinguishes a callable service (1) from data (0).
Names are case-sensitive, NUL terminated, and at most 31 bytes. Missing and
incompatible services fail with carry clear. Lookup can overwrite monitor
scratch; save its result after the call, rather than expecting scratch values
to survive it.

Do not cache a lookup result across reset, manager reinitialization, or core
replacement. Also do not call a data result as code: `COMMAND.CORE`, for
example, describes built-in commands but its targets are monitor control-flow
entries, not RTS-callable command services.

## Step 3: preflight ownership and register the handler

Before changing RAM, the initializer scans the format-1 registry. Its count
is a **byte count**, advancing by three per entry, not the number of commands.
Each entry is a letter followed by the handler pointer's low and high bytes.
The initializer refuses a conflicting X, an entry pointing into its three-byte
stub, a malformed/oversized count encountered by its bounded scan, or a full
registry. Reinitialization is idempotent when existing X points to the correct
stub and all three stub bytes match.

It then copies the stub and calls the discovered service:

```asm
                        LDA #'X'
                        LDX #<$7403
                        LDY #>$7403
                        JSR CALL_ENTRY
                        BCC UNAVAILABLE
...
CALL_ENTRY:             JMP (CALL_PTR)
```

The 65C02 has no indirect JSR instruction. `JSR CALL_ENTRY` pushes the return
address; the helper's indirect JMP reaches the service, whose RTS returns to
the original caller. Registration returns carry set/A=0 on success, or carry
clear with A=1 invalid, A=2 duplicate, or A=3 full.

Registration checks target ranges and duplicate letters, not ownership of
every byte of RAM or flash. The explicit allocation is still a provider
contract. This example's scan detects registry targets in its stub; it cannot
discover unrelated private buffers belonging to an undocumented module.

On successful initialization, X jumps to H's existing initializer at `$C000`.
H registers itself or verifies its existing registration, then enters
`STR8V2_RAM_HOLD`. Each initializer handles its own failure; this chain is
not an atomic multi-provider registration transaction. A fresh H+X boot needs
two free slots; if only X fits, H reports a full registry and the monitor
remains usable. This explicit chain is an example bootstrap, not a newly
implemented configuration list of extensions to load.

## Step 4: implement the command body

The handler receives the complete NUL-terminated line at `STR8V2_LINE`
(`$7C00`). It runs in the monitor foreground with IRQ disabled and decimal
mode clear; the 65C816 contract is emulation mode, DBR/PBR zero. X/Y and flags
are volatile. Keep the stack balanced and return **A=1 with RTS** when the
command is handled, including when you print its usage error.

X starts at offset 1, skips spaces, and compares complete subcommand tokens.
`MATCH_TOKEN` checks the following space/NUL delimiter, which prevents HELLO
from matching HELLOX. On failure, X restores the original subcommand offset
before trying ECHO. That saved offset is essential because a failed match
may already have consumed characters.

The command prints through the public bank-independent RAM console ABI at
`STR8V2_RAM_PUTC` and `STR8V2_RAM_NEWLINE`, rather than calling private core
functions. `EMIT` saves its own X/Y loop registers around PUTC. `PRINT` walks
a NUL-terminated flash string; ECHO walks the core's input buffer. Finally:

```asm
HANDLED:                LDA #$01
                        RTS
```

Return to the dispatcher here. `STR8V2_RAM_HOLD` is appropriate for the
initializer/application entry, not for a normally returning command handler.
If a future handler intentionally hands control to a shell, that needs its
own documented ownership/reentry contract. For long-running commands, add
explicit cancellation checks and define interrupt behavior; this short
printing example does not establish a background-driver contract.

## Step 5: build, test, and initialize

With Python, py65, and the existing WDC assembler/linker environment:

```text
python tools/build_v2_b2_command_example.py
python tools/test_v2_b2_command_example.py
```

Tests use the existing built b2 firmware under `BUILD/v2-b2`; build that with
`python tools/build_v2_b2.py` first if it is absent or stale. The example
builder does not rebuild or alter firmware. It rebuilds H in a private output
directory, composes X into H's zero-filled sector tail, checks region overlap,
and emits a complete 4 KiB sector with a `$C700` S9 entry. It does not add
bytes to the normal H artifact. Output files are:

```text
BUILD/v2-b2-command-example/str8n-v2-b2-h-x-c000-cfff.s19
BUILD/v2-b2-command-example/str8n-v2-b2-h-x-c000-cfff.bin
BUILD/v2-b2-command-example/manifest.json
BUILD/v2-b2-command-example/command-example-tests.json
```

The host tests execute actual assembled command opcodes: parsing, lowercase
and tab normalization, prefix rejection, repeated initialization, command
lifetime after application replacement, all selected banks, conflict/full
refusals, invalid E descriptor, reset/autostart, H coexistence, and RTS
save/restore. They verify that command use does not change flash or application/
overlay RAM. They do not qualify physical hardware or native 65C816 execution.

For a later board installation, this is a **complete replacement B3:C image**
containing the repository's H plus X. It is not an L-loadable application or
a small patch to an arbitrary existing C sector. Preserve a readback first;
if C contains anything besides this known H provider, compose against that
allocation instead. The b2 sector-install sequence would be:

```text
B3
I C000 CFFF
Y                         [at the monitor's confirmation prompt]
                          [send the complete example S19 file]
G C700
X HELLO
H
```

After verifying the installed sector and commands, boot configuration can
select the combined initializer with `C 1 3 C700 40`, followed by `Y` at its
confirmation. `40` is hexadecimal 64 tenths, approximately 6.4 seconds of
boot hold. `$C700` registers X and chains H; the old `$C000` boot address
registers H alone. Reset withdraws runtime registrations, so this startup
choice reconstructs both RAM stubs and registrations. The separate K storage
configuration need not change. This installation sequence was subsequently
performed on 2205 at the owner's request, after the matched E/F catalog update.
Physical-button RESET and power-cycle qualification remain pending.

## Named commands: COMMAND.REGISTER v2

Look up `COMMAND.REGISTER` with Y=2 using `STR8MGR_LOOKUP`. Version 1 remains
available with its original A=letter, X/Y=handler contract. Version 2 takes
A/X=low/high address of a four-byte descriptor, Y=0:

```asm
HELLO_DESCRIPTOR: DW HELLO_NAME,HELLO_HANDLER
HELLO_NAME:       DB "HELLO",0
```

The descriptor is copied as two pointers into one of eight additional named
records. The descriptor itself may be temporary; the name and handler must
remain pinned until reset. Accepted pinned regions are overlay RAM 5800–5FFF,
module RAM 7100–78FF, or resident B000–EFFF flash. Names contain 1–15 uppercase
letters and a NUL terminator. Empty, overlong, lowercase and punctuation names
are rejected. A name's terminator must also be in an accepted pinned region.
Both service discovery and registration clobber monitor scratch; protect a
discovered function pointer in your own storage if reusing it across calls.

Success returns C=1, A=0. Failure returns C=0 and A=1 invalid/reserved,
2 duplicate, or 3 full. Duplicate detection compares string contents,
including names stored at different addresses. A one-letter name must not
collide with a legacy registration; the reverse registration order is also
checked. Built-in one-letter commands and compact address forms such as
`DABCD` or `MFFFF` cannot be registered through v2.

The core attempts named dispatch before its existing first-letter dispatcher.
An exact name must be followed by a space or end of line. Thus `HELLOX` does
not invoke `HELLO`; `DIR TEST` can invoke a registered DIR handler rather
than the built-in D parser. Unmatched input retains the existing core/legacy
dispatch, including B3, D1000 and recovery without a valid manager.
An empty named registry bypasses the additional dispatch/validation work for
core commands. No named registrations are inferred from a matching prefix.

Named handlers receive X=the first argument's offset in the original
NUL-terminated `STR8V2_LINE`, after spaces. With `ECHO   TEXT`, X is 7; with
bare ECHO, X points at its NUL. The line is not shifted or rewritten. Return
A=1 for handled or A=0 to permit legacy/core fallback. Stack balance, IRQ
disabled, decimal clear and the established 816 emulation contract still
apply. The complete input line remains limited to 40 characters.

The example initializer still registers X through v1. It discovers v2 and
publishes HELLO/ECHO with resident flash names and handlers. Reinitialization
accepts an existing record only if all four descriptor bytes match; a foreign
duplicate is a conflict. On older managers without v2, legacy X remains usable.
The returning autoload entries C00A/C70A and legacy entries C000/C700 remain;
X's private handler now lives at CA00. It still owns only its three RAM stub
bytes at 7403–7405. See the actual sources:

- `tools/v2-apps/str8n-v2-b2-command-x-init.asm`: discovery and registration.
- `tools/v2-apps/str8n-v2-b2-command-x.asm`: legacy and named handlers.
- `src/v2-b2/str8n-v2-named.asm`: validation, records and dispatch.

With X selected, the following pairs work:

```text
HELLO                 X HELLO
ECHO SOME TEXT        X ECHO SOME TEXT
```

H prints `Named: HELLO ECHO` separately from the legacy registered letters.
K AUTO still selects modules: disabling X and resetting also withdraws its
HELLO/ECHO records. Named records reset with the manager. A failed autoload
initializer rolls back named, legacy-command and dynamic-service counts.
The named implementation participates in the runtime CRC validation.

Measured increase over the installed startup-order build: 26 core bytes,
666 named-helper bytes, 34 copied-manager bytes, 6 carrier bytes, 12 autoload
bytes and 269 H/X example bytes: **1,013 code/text bytes** total. Named metadata
uses 34 bytes at 7690–76B1; copied-manager growth uses another 34 bytes within
the existing reservation. Application RAM remains 22,016 bytes, with a separate
2 KiB overlay. Named metadata, like other manager metadata, is unavailable
for provider code, names or data storage.

All **41 assembled-opcode host groups passed** for this source revision: the
existing 37 manager/RTS/configuration/service/autoload/H/X/ABI groups plus
four named-command groups. The named checks cover direct and legacy examples,
all selected banks, argument offsets, exact-token boundaries, collisions,
validation/capacity/reset, failed-provider rollback and authenticated-code
corruption. `make v2-b2-autoload-check` runs all groups;
`tools/qualify_v2_b2_autoload.py` binds the nine receipts to the exact current
images in `BUILD/v2-b2/autoload-qualification.json`. The exact B/C/E/F updaters
also passed 24 host cases before installation on 2205. Full physical readbacks,
direct HELLO/ECHO and legacy X forms, all selected banks, exact-token rejection,
H's name listing and repeated initialization passed. Settings, application RAM
and B0/B1/B2 were preserved. See the
[board record](STR8N_V2_B2_2205_BOARD_TEST_2026-10-04.md).

## Larger shells

The v2 implementation above fulfills the earlier plan for longer top-level
names: separate compatible records, complete-token matching, argument offsets,
core routing and help enumeration. Public record/count definitions are in
`str8n-v2-manager-public.inc`; H reads the named table separately from legacy
records. A separately discoverable enumeration service is not implemented.

The monitor still normalizes its 40-character input line to uppercase. A larger
or case-preserving shell can own an input loop and parser while using the same
manager's services. That is a separate input contract and does not require
another extension manager.

## Could an ACIA driver be an extension?

Yes, a driver can be a provider loaded and initialized through this framework.
It may expose **no command at all**, or have an optional command such as
`A STATUS`/`A BAUD ...` for configuration and diagnostics. Registering A
alone would let it access an ACIA independently; it would not redirect the
monitor's existing console calls.

For a usable console driver, define service contracts for initialization,
transmit, nonblocking receive, and any buffering/cancellation integration.
Have the existing public RAM console entries route to the selected provider
while keeping their addresses and caller conventions stable. Driver private
state, callbacks, and any interrupt vectors need explicit ownership and a
reset fallback when the module or hardware is absent. A first polled driver
fits the current foreground execution model; an IRQ-driven buffered driver
needs a separate interrupt policy and qualification.

Driver integration now has the following status:

- The new candidate implements `SERVICE.REGISTER` v1 with eight dynamic
  entries alongside the static directory. It is installed and tested on 2205.
  A dynamically loaded driver can publish its services through that contract;
  monitor-console backend selection still needs a binding mechanism. See the
  [service-provider contract](STR8N_V2_SERVICE_PROVIDER_PROPOSAL.md).
- The b2 RAM console implementation currently uses FT245, without an active
  ACIA backend. `CONSOLE.PUTC` already resolves a stable RAM facade; changing
  that facade's routing is necessary to use an optional ACIA provider as the
  monitor console.

Console I/O is also needed while flash banks are switched and while flash
is being programmed. The parts of a replacement driver used in those paths
must be pinned in suitable RAM, together with any interrupt handler that must
run across bank changes. H's three-byte RAM JMP to C flash is suitable for a
foreground help command; that alone is insufficient for such a console
driver. Chip-specific register setup, clock/baud selection, and hardware
behavior need implementation and testing against the installed ACIA model.

The manager can therefore come first and support an ACIA provider later,
while preserving the fixed public ABI and leaving AP runtime linking as a
separate consumer. The X example proves command initialization, registration,
pinning and dispatch; it does not claim that driver binding or ACIA support
has already been implemented.
