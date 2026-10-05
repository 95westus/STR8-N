# Dynamic service providers: first registration contract

The latest installed [autoload candidate](STR8N_V2_B2_AUTOLOAD.md) preserves this
SERVICE.REGISTER ABI and adds ordered returning command initializers. Providers
may publish services during initialization for later selected providers. It is
installed and checked on 2205, including the dynamic-service probe and reset
cleanup. Current autoload-private RAM 7640–768E is unavailable to providers.

October 4, 2026. `SERVICE.REGISTER` v1 is implemented and installed on
board 2205, with physical callable/data/version/duplicate/copy/reset checks
passed. See the [qualification record](STR8N_V2_B2_2205_BOARD_TEST_2026-10-04.md).
Console-driver binding remains
proposed. This document specifies registration and the remaining driver work.

## Keep one manager and one lookup interface

Extend the existing manager rather than adding a driver manager. Keep
`STR8MGR_LOOKUP` and its versioned name lookup unchanged for callers. Its
search covers the existing immutable core service directory and a bounded
RAM directory populated by extensions. These are two storage regions behind
one logical service namespace, not two managers.

The first version rejects registrations that duplicate an existing
name/version pair, including built-in services. A provider can add
`ACIA.PUTC` without replacing the built-in `CONSOLE.PUTC`. Different versions
of the same name can coexist if there is capacity; lookup continues requesting
an exact version. A failed registration must leave the directory unchanged.

## SERVICE.REGISTER version 1

Discover the callable registration entry through the existing lookup. Pass
A/X as a low/high pointer to this six-byte descriptor; reserve input Y=0:

| Offset | Field | Size |
| --- | --- | ---: |
| 0 | Pointer to pinned NUL-terminated service name | 2 bytes |
| 2 | Interface version, nonzero | 1 byte |
| 3 | Kind: 0=data, 1=callable | 1 byte |
| 4 | Pinned data/entry pointer | 2 bytes |

This matches the existing service-directory record shape. The manager copies
the descriptor; the input descriptor can then be temporary. It retains the
name and target pointers, so their storage must remain pinned.
Names remain case-sensitive ASCII, with the existing 31-character limit.
The callable ABI of an individual service must also be documented: the record
identifies it but does not define its register, stack, cancellation, or IRQ
contract.

Use the familiar carry/A result convention: carry set/A=0 success; carry
clear/A=1 invalid, A=2 duplicate, A=3 full. A/X/Y/flags and monitor scratch
are otherwise volatile. Validate the whole descriptor and name, then append
one complete record. An unsupported target/storage region must fail, rather
than creating a dangling or bank-dependent entry accidentally.

For this first contract, providers remain pinned until reset. Reset clears
dynamic registrations, and boot initializers reconstruct them. There is no
unregister/unload promise yet. AP runtime linking can look up these services,
but an unloadable AP module cannot publish pointers to its movable code under
this pinned-provider contract. Later unloading needs ownership, withdrawal,
and protection for callers that already cached a result.

## ACIA provider versus console selection

An ACIA provider could register names such as `ACIA.INIT`, `ACIA.PUTC`, and
`ACIA.RAW_POLL`. An optional A command could configure the device and display
status. Other commands or a shell could discover and use those services
without changing the monitor console at all.

Selecting ACIA as the monitor console is an additional step. Define an
explicit console binding operation that validates a compatible group of
driver operations and updates the RAM facade's backend together. Preserve
the existing public ROM/RAM entry addresses and calling conventions.
`CONSOLE.PUTC` should continue naming that facade, so callers do not have to
know which physical driver is selected.

The proposed binding is not an implicit overwrite of `CONSOLE.PUTC` through
registration. It should cover transmit, nonblocking receive, receive reset,
and the existing buffering/cancellation behavior. Provider registration alone
must not change the console. Start with a polled driver and FT245 as the
recovery default; select the optional backend only after initialization and
validation succeed. Missing module or hardware leaves recovery usable.

Driver code/state needed during bank switching or flash programming must be
pinned in RAM. A foreground flash command can use a RAM JMP to its flash body;
a console callback that must work while another bank is mapped cannot rely
on that arrangement. Any later IRQ driver also needs explicit vector/buffer
ownership and interrupt policy.

## Cost and placement

Eight dynamic records need **48 RAM bytes**, plus count/bookkeeping. Names
kept in provider flash add no RAM copying cost; RAM-resident names would add
their character counts plus NUL terminators. An ACIA provider with three
services consumes three of those eight entries. Driver code, buffers, and
console dispatch vectors are additional allocations inside the reserved
module/monitor areas; they are not included in that 48-byte calculation.

Exposing `SERVICE.REGISTER` adds a six-byte directory record and its 17-byte
name, **23 bytes**, included in the measured manager size. The preceding E
sector was full. The candidate therefore stores the manager's load image in
reserved **B3:B**, starting at B008 after an eight-byte informational header.
The B sector is zero-filled beyond that image, preventing RTS from treating
its tail as erased record space. Command dispatch still executes from pinned
manager RAM; lookup and registration execute in resident E ROM. Startup
validates the exact core binding and CRC over the manager payload, RTS,
configuration code and service code before enabling the manager. A missing
or corrupt B payload disables optional extensions while core boot/recovery
remains available. B's header and padding are informational; the trusted
payload extent and CRC come from E.

Measured against the preceding candidate: core F remains **3,984 bytes/64
free**; copied manager shrinks from 569 to **516 RAM bytes**; table/count use
**49 bytes**, so total occupied RAM decreases by four bytes. The E boot
carrier is **308 bytes**, and service lookup/registration code is **507
bytes**. Together with the manager load image and B header, this adds **490
flash code/data bytes**, plus reservation of the additional 4 KiB B sector.
Alignment padding is separate. Application remains **22,016 bytes**, and
the 2 KiB overlay reservation is unchanged.

This extension does not inherently require more application RAM or a new
core ABI entry. Keep the one-byte command registry intact, keep lookup's
existing interface, and explicitly allocate new internal storage without
moving H/X stubs or RTS/config state. Whether code fits the current reserved
space must be verified before choosing final addresses.

## Validation, example and limits

Build with `python tools/build_v2_b2.py`; run
`python tools/test_v2_b2_services.py`. `make v2-b2-check` includes the service
tests and existing manager/RTS/configuration checks. Model boot helpers install
the B backing sector alongside E/F. Output includes
`str8n-v2-b2-b000-bfff.bin/.s19` and the usual E/F component artifacts. An E/F
artifact alone is no longer a complete optional-manager installation. Existing
exact beta1/b2 E/F updaters are not a B/E installation procedure. The factory
full-bank image includes B; it is not a preservation installer for a populated
board. The subsequent owner-authorized 2205 installation used B first, then
`tools/build_v2_b2_service_update.py` for E. That exact-source RAM updater
guards unchanged F and every byte of new B before and after confirmation.
It preserves C/D/F, boot settings and the B2:F recovery backup. Seven updater
host checks, an assembled hardware-probe host check, physical service checks,
software-reset H/X autostart and full before/after readbacks passed.

The 48-byte table is at 7600-762F; its byte count is at 7DEB, which the core's
existing reset clearing already clears. Registration uses existing monitor
scratch and no additional persistent bookkeeping. The old three-byte command
records and eight-command limit are unchanged. H/X stubs at 7400-7405 and
RTS/config state at 7500-756A retain their allocations.

For a callable example, a provider owns and pins name `DEMO.VALUE` at 7700
and code `LDA #$42 / RTS` at 7800. Its temporary descriptor at 2400 contains:

```text
00 77 01 01 00 78
```

Discover `SERVICE.REGISTER` v1, verify carry set and Y=1, and save its entry
pointer. Invoke it through the existing JSR-to-indirect-JMP helper with
A=$00, X=$24, Y=0. On success, lookup of `DEMO.VALUE` v1 returns A=$00,
X=$78, Y=1. Calling that result returns A=$42. The descriptor can be
overwritten afterward; name and code must stay pinned. Service tests execute
this example and publish version-2 data to prove exact-version selection.

Descriptor storage must fit six bytes wholly within RAM 0200-78FF or ROM
8000-FFFF. Name and target pointers must be in overlay RAM 5800-5FFF,
reserved module RAM 7100-78FF, or resident B..F ROM B000-FFFF. Names must be
nonempty printable ASCII without spaces, at most 31 characters, and their
terminator must remain in a permitted pointer region. The public RAM console
facade is reached through its existing static service. These checks validate
ranges, not ownership or function semantics; providers must choose unoccupied
pinned storage and implement the documented callable contract.

There is no service withdrawal or provider unloading. Do not free a name,
data object or callable while its record or a cached lookup result remains
live. Revalidating the same runtime refreshes policy while retaining
registrations; reset/reinitialization withdraws them. Dynamic console binding
and an ACIA driver are the next separate changes.

All **27 host check groups** passed for this candidate: nine manager/RTS,
eight configuration, three service-registration, four permanent-H and three
H+X example groups. Receipts reference E/F SHA256
`ca62ff9b2a1a6476908a2d113c68892a9fd0ea500b2873540614adc4a291ecc3`;
the manager B-sector SHA256 is
`22dd20ef7b9f158a0aedf2e1db1cb6d8e98b16f97801fe4cb6896b9c24713ef8`.
Service checks include callable/data results, RAM and resident-ROM provider
descriptors, multiple versions, static and dynamic duplicates, malformed
counts, 31-character bounds, full capacity, copied-descriptor lifetime,
reset/revalidation, and missing/corrupt B or service code with core recovery.
These host checks do not cover native 65C816 execution. The later physical
run covers the scoped 2205 checks above; physical-button RESET, power cycle,
ACIA and fault injection remain unqualified.
