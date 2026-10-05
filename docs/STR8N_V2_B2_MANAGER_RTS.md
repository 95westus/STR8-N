# 2.0b2 manager, RTS and persistent configuration candidate

**Latest installed source:** selective configuration autoload is implemented,
with independent R/S/T/H/X selection and startup messages. Matched B/C/E/F
and persistent configuration in B3:D are **installed and checked on 2205**. F is
4,039 bytes (9 free), including named-command registration v2. Startup dots
precede registration, and user/overlay
RAM and public ABI are unchanged. See
[autoload commands and contract](STR8N_V2_B2_AUTOLOAD.md). The installation
history below includes earlier service revisions; the latest autoload results
are in the [board record](STR8N_V2_B2_2205_BOARD_TEST_2026-10-04.md).

The latest source/build also implements `SERVICE.REGISTER` v1, with eight
dynamic services and existing lookup compatibility. This newer candidate
requires B3:B backing plus E and is now installed and checked on 2205. Its copied
manager is 516 bytes, with 48 service-record bytes and one count byte; core F
and application limits remain unchanged. See the
[service-provider contract](STR8N_V2_SERVICE_PROVIDER_PROPOSAL.md) for measured
cost, allocation, validation and example. The later service update changed
only B/E, preserving the command-catalog F core and H+X/configuration sectors.

Updated October 4, 2026. The current command-catalog revision is host-tested
and installed on 2205. Its F core is 3,984 bytes, with 64 bytes free. The
matched E/F update, core catalog, H+X in B3:C, software-reset autostart,
all selected banks, RTS listing/duplicate-save/restore, full bank readbacks,
and restoration of application/overlay RAM passed on 65C02/FT245. See the
[board qualification record](STR8N_V2_B2_2205_BOARD_TEST_2026-10-04.md) for exact
installed images and retained settings. Native 65C816, ACIA, physical RESET/
power-cycle qualification and release packaging remain pending.

## Build and verification

For an independent command provider, see
[Writing a command extension](STR8N_V2_COMMAND_EXTENSIONS.md). It includes a
complete H+X flash example and explains command-name and driver-service limits.

With Python 3 and the WDC assembler/linker on PATH:

```text
python tools/build_v2_b2.py
python tools/test_v2_b2.py
python tools/test_v2_b2_config.py
```

Equivalent targets are `make v2-b2` and `make v2-b2-check`.

The opcode tests also require py65, using the repository's existing test
dependency setup. Outputs are under `BUILD/v2-b2`. `build.json` records symbols,
sizes, source/artifact hashes and the selected memory allocations;
`manager-rts-tests.json` and `extended-config-tests.json` record the tested
image hash and passed checks. Rebuilding invalidates both receipts.

The suite executes named save/restore, exact lookup and independent command
registration, contiguous/fragmented placement, bank exclusions, duplicate and
ambiguous names, pending records, missing/corrupt extensions, reset lifetime,
application boundaries and configuration staging. It also exercises modeled
flash timeout/readback failures, cancellation, full-pool refusal, low-level
policy enforcement, complete-marker-last writes and the established public
ROM/RAM ABI. Native 65C816 execution and physical flash timing remain outside
these 65C02 model checks.

Configuration checks cover creation, reset persistence, movement, opaque-sector
refusal, exclusion of the reserved sector, corrupt/missing configuration,
boot-setting preservation, cancellation, disabling the locator, same-sector
updates, direct RTS service callers, destination failures and F-sector locator
failure/retry entirely through RAM.

The combined `str8n-v2-b2-e000-ffff.s19` contains the E extension sector and F
core sector. Component manager/RTS images are build products, not ordinary
application `L` inputs. Existing beta 1 installers, migrator and Bank
Maintenance have not been qualified against this changed RAM layout. Do not
use them as a b2 installation procedure.

Board 2205 used `tools/build_v2_b2_board_update.py`, an exact-source beta 1 to
b2 RAM updater builder. It requires a full B3 readback of the original published
core and an exact B2:F backup, verifies the candidate E/F binding, preserves
valid local boot settings, and produces separate E-first/F-last updaters below
5800. Each embedded source/guard sector is checked again after confirmation;
F also checks the live backup. `tools/test_v2_b2_board_update.py` executes its
success, refusal and RAM recovery paths against the original published worker.
The builder does no serial I/O. It is not an updater for an already installed
b2 core; the broader installer/migrator integration remains pending.

The separate `tools/build_v2_b2_revision_update.py` handles the exact preceding
3,993-byte b2 revision on 2205. It uses `$6100` staging and monitor scratch,
guards exact old/other sectors, preserves the boot/config pocket, and uses a
host readback backup while retaining the original B2:F recovery image.
`tools/test_v2_b2_revision_update.py` verifies both phases' success,
cancellation, changed-guard refusal and timeout rollback. It is not a general
updater for other source revisions.

For the installed service revision, `tools/build_v2_b2_service_update.py`
requires the exact catalog E and unchanged F, an initial full readback with
erased/excluded B3:B, and matching service qualification receipts. It produces
an E-only RAM updater with complete F/B guards and rollback, to run after
installing and verifying B. `tools/test_v2_b2_service_update.py` verifies its
success, cancellation, old-E refusal, post-confirmation F/B payload/B tail
refusals, and timeout rollback. It does no device I/O and is not a general
installer for other revisions.

## Commands

`?` retains the existing built-in compact syntax summary, available without E.
The preferred permanent H extension stores code and text in **B3:C flash**.
It shows syntax and short explanations for all core commands and K/S/R/T.
Its `Registered:` line lists live extension keys without executing their
handlers. The registry has no per-command help metadata, so future commands
appear by letter only.

Build and check the permanent provider independently after building b2:

```text
python tools/build_v2_b2_help_flash.py
python tools/test_v2_b2_help_flash.py
```

Or use `make v2-b2-help-flash-check`. The builder does not rebuild core/E or
access a board. `BUILD/v2-b2-help-flash/str8n-v2-b2-help-c000-cfff.s19` contains
exactly one full 4 KiB sector, with entry C000. It is an **I input, not an L
application**. Installation requires an independently verified, erased B3:C
sector, preserved core/configuration, and a storage mask excluding B3:C:

```text
B3
I C000 CFFF
Y
<send str8n-v2-b2-help-c000-cfff.s19>
<verify the entire C sector against its binary>
```

Reset first to withdraw any earlier RAM-loaded H. `G C000` initializes the
manager through E008, discovers `COMMAND.REGISTER` version 1, installs a
three-byte `JMP C300` stub at **7400-7402**, registers H at that RAM stub, and
returns to the monitor. H's 809-byte handler/text image stays at **C300-C628**;
the initializer uses 369 bytes at **C000-C170**. H accepts no arguments
(trailing spaces are allowed). The existing `?` command is unchanged.

For registration after reset, use the existing boot setting:

```text
C 1 3 C000 40
Y
```

This selects the H initializer as the automatic boot application, preserving
its hexadecimal 40 delay (64 tenths, nominally 6.4 seconds). C retains the
extended configuration locator. The existing S/Ctrl-C startup hold bypasses
the initializer; `G C000` can register H manually afterward. Returning to the
monitor uses HOLD rather than RESET, so registration is retained. This is an
explicit one-provider startup arrangement, not automatic discovery, a new
manager, or a general persistent module catalog. Future resident-bank commands
can use the same pattern with distinct reserved RAM stubs and a shared startup
initializer. Another flash bank requires a bank-switch/return wrapper.

The initializer is idempotent for an existing matching H/stub. It refuses a
conflicting H key, a registered target inside 7400-7402, a full/damaged registry,
or a missing/incompatible manager. Providers must respect the declared stub
reservation; registered entry addresses cannot describe every other module's
private code/data extent. K/S/R/T remain optional. Missing/invalid storage
configuration does not prevent H from showing help.

**H uses zero application RAM and zero overlay RAM.** Application RAM remains
0200-57FF: 22,016 bytes (21.5 KiB). The complete 5800-5FFF overlay reservation
(2,048 bytes) is available to other modules; 6000-60FF remains unassigned.
H adds only three bytes inside manager-reserved RAM and consumes one existing
registry slot, leaving three after K/S/R/T/H. Its initializer/handler use
monitor foreground scratch E0-E3, without any additional permanent zero-page
allocation or new ABI entry.

B3:C is a reserved provider sector. It contains 1,178 code/text bytes and
2,918 zero-filled gap/tail bytes. This fill prevents RTS from finding an erased
record extent there even if its mask is mistakenly enabled. K also refuses
the occupied sector as a configuration destination. Future commands can share
the sector through a rebuilt, verified sector image; there is no append loader.
The monitor's explicit F/I commands still allow deliberate replacement; this
reservation is not a hardware write lock or an unload/update protocol.

The permanent H provider itself adds no core/E bytes. The later command-
catalog revision reduces F to 3,984 bytes with 64 free and changes the E/F
binding; it requires a matched E/F update before using that revision on a
board. H's B3:C image and three-byte stub remain unchanged. The C boot setting
uses the existing F pocket.
`help-flash-tests.json` records model checks for I installation, exact RAM
preservation, idempotent/conflicting registrations, reset/cold-RAM startup,
startup hold, help from all selected banks, overlay commands, RTS coexistence,
and occupied provider-sector refusal.

On 2205, the exact permanent image passed full-sector readback, manual H,
and automatic H registration after a software RESET (`G F004`). Full 0200-
60FF readback matched the preceding application/overlay snapshot. Full bank
readbacks confirmed B0/B1/B2, B3:D/E, and core code unchanged; only B3:C and
the F boot pocket changed. K stayed `K 00 B3 D0 00 3F 00 00`, and T still
listed BETA2. H was left registered at the B3 prompt with `C 01 03 C000 40`.
Physical-button RESET and power-cycle qualification of this permanent provider
remain pending; cold RAM/startup hold/conflict paths are host-model checks.
See the board record for exact images and transmissions.

The earlier RAM-loaded diagnostic H remains available through
`tools/build_v2_b2_help.py` and `tools/test_v2_b2_help.py`. That version uses
809 overlay bytes at 5800-5B28 and requires reloading after reset; it must not
be installed alongside the permanent H key. Its recorded 2205 load check is
historical evidence, not the preferred permanent placement.

The optional RTS module registers S, R and T with one manager:

```text
S 2000 201F DEMO
R DEMO
T
S 2000 201F OTHER B1
R OTHER B1
T B1
```

S saves the inclusive application range with a name and finds the first
available erased extent automatically. R restores the range stored under that
name. T lists records, including their bank, flash address, application range,
length, pending/complete state and name. Names contain 1–16 printable,
non-space characters; monitor input normalizes letters to uppercase.

The optional B0–B3 argument restricts the configured search areas. It does not
enable a disabled bank. No external configuration is assigned in the factory
image, so RTS storage is disabled until K establishes a valid policy. Bank 2
is opaque unless explicitly enabled. E/F sectors and the selected configuration
sector are always excluded. The `STORAGE.POLICY` version-1 data service returns
four effective RAM masks, one per bank; bit 0 represents sector 8 and bit 5
sector D. Treat this data as read-only: it is refreshed from persistent
configuration before extension commands and low-level RTS save/restore calls.

## K: configuration location and storage masks

```text
K                          Show status, selected location and requested masks
K B3 D 00 3F 00 00          Reserve B3:D; allow storage in B1 sectors 8–D
K B2 A 00 00 3F 00          Move configuration to B2:A; allow B2 except A
K OFF                      Clear the locator and disable RTS storage
```

Set/move/OFF operations require the monitor's Y confirmation. No default sector
is silently reserved. A new destination must be entirely erased, or contain a
valid configuration header owned by that bank/sector. Opaque contents are
refused even if the first sixteen bytes are erased. E/F destinations are
refused in every bank. Updating a valid owned sector may erase it as required,
while preserving its tail through a full-sector snapshot. A damaged header is
not sufficient proof of ownership; select an erased destination to repair it,
or use an explicit maintenance procedure before reclaiming the damaged sector.

The display uses `K NN`: 00 means valid or unassigned (a valid selection also
prints its Bn/sector/masks), 01 means invalid bootstrap/locator, and 02 means
invalid/incomplete selected sector. Sector display is its address high byte
(D0 for sector D). Displayed masks are requested values; effective masks always
remove the selected configuration sector. An erased factory pocket reports 01
until initialized; it still boots to the monitor and enables no storage.

K writes the desired header as pending, verifies the sector, then programs the
complete marker. Only after that succeeds does it change the fixed locator.
A destination failure leaves the old locator intact. A move leaves the old
sector untouched; it does not automatically erase/reclaim it. No scan for
alternate configuration signatures occurs. K OFF leaves sector contents intact.

The fixed boot pocket remains format 1 at resident FFD0–FFDF. K preserves
validated boot settings, or initializes invalid settings to monitor-only.
Normal C edits now preserve a valid locator. External-sector failures do not
change the local boot settings: valid local autostart remains independent;
invalid/disabled local settings retain monitor fallback. Reset and built-in
recovery do not depend on the manager or external sector being present.

Changing the locator uses the existing F-sector snapshot/rewrite worker. If
that write fails, execution remains in RAM and offers Y retry/reset; it does
not return into damaged ROM. This is not an atomic power-loss-safe F update:
loss of power while F is erased may still require the existing hardware
recovery procedure, as with C. Invalid external configuration itself does not
erase or prevent booting the core.

### Byte format and discovery service

| Fixed pocket offset | Meaning |
| --- | --- |
| 0–6 | Existing boot settings |
| 7 | C1 locator tag; 00 with zero bank/sector means unassigned |
| 8 | Configuration bank 0–3 |
| 9 | Sector address high byte 80, 90, A0, B0, C0 or D0 |
| 10–13 | Reserved, zeroed by K |
| 14–15 | Existing two accumulated 8-bit sums of bytes 0–13 |

The selected sector begins with sixteen bytes: `CF`, format 01, complete
marker 3F (7F during write), masks for banks 0–3, owner bank, owner sector
high byte, four reserved bytes, and two accumulated 8-bit sums of bytes 0–13.
The remaining 4,080 bytes belong to the reserved configuration sector. Owner,
version, marker, mask bounds and sums must validate before policy is enabled.
Reserved header bytes are included in the sums and otherwise ignored in this
version; K writes them as zero.

`CONFIG.LOCATE` version 1 refreshes validation and effective policy. It returns
C=1, A=bank, X=sector high byte, Y=1 for a valid selection. On C=0, A=0 means
unassigned, A=1 invalid bootstrap/locator, and A=2 invalid/incomplete sector;
X/Y are unspecified. Scratch and A/X/Y are volatile; the selected target bank
and physically resident bank are preserved. Every failure clears effective
storage masks, including when an initialized manager previously cached them.

The shared host encoder/validator is `tools/v2_b2_config.py`. It performs no
device writes. The existing migrator and Bank Maintenance do not yet offer
this setup UI; K provides configuration creation/movement in this milestone.

S rejects an existing name within its search scope. R rejects ambiguous names
across enabled banks; an explicit bank can disambiguate. Existing valid
records, including pending records and payload bytes containing FF, reserve
their complete extent. Placement cannot cross an excluded sector or bank.
Saving never automatically erases, replaces or reclaims records.

The existing SR/01 record format is retained: a 24-byte header followed by
payload, with a complete marker programmed last. Structural validation and
flash readback checks are present; the format has no payload checksum.
Restores must fit the new application range.

Errors printed as `RTS error NN` are: 01 invalid low-level argument, 02 occupied
extent/duplicate name, 03 flash failure, 04 invalid or pending record, 05
ambiguous name, 06 missing name, and 07 no permitted space. Cancellation prints
`Canceled`; malformed command arguments print `Bad hex/name`.

## Manager contract

The resident Bank 3 E image has `EM`, format 1 at E000. Its initializer at
E008 validates its core binding and image CRC, installs the manager at 7100,
binds RTS imports, and registers S/R/T. Initialization happens on the first
extension command; boot and built-in recovery do not require a valid E image.
A missing or incompatible extension reports `RTS unavailable`. Repeated
initialization preserves registrations while the image identity is unchanged.
Reset clears manager state.

The version-1 manager has two operational interfaces:

| Interface | RAM entry | Contract |
| --- | --- | --- |
| DISPATCH | 710B | NUL command at 7C00, at most 40 bytes; A=0 unknown, A=1 handled |
| LOOKUP | 710E | A/X=name pointer low/high, Y=exact version; C=1 returns A/X pointer and Y=1 callable or Y=0 data; C=0 returns A=1 missing or A=2 incompatible |

Initialize before using these entries. ROM facades E00B/E00E forward to the
installed RAM entries; they do not initialize it themselves. Service names are
case-sensitive, NUL terminated and at most 31 bytes. Calls are foreground,
IRQ disabled and decimal clear; 65C816 callers use emulation mode with
DBR=PBR=0. Monitor scratch, A/X/Y and flags are volatile unless the individual
service says otherwise. Stack balance is required.

Services version 1: `CONSOLE.PUTC`, `CONSOLE.HEXOUT`, `CONSOLE.NEWLINE`,
`CONSOLE.CANCEL`, `PARSE.HEXWORD`, `PARSE.HEXBYTE`, `PARSE.SPACES`,
`FLASH.READ`, `FLASH.SNAPSHOT`, `FLASH.MUTATE`, `COMMAND.REGISTER`,
`COMMAND.CORE`, `RTS.SAVE`,
`RTS.RESTORE`, `STORAGE.POLICY`, and `CONFIG.LOCATE`. Console pointers use the established public
RAM entries. Low-level flash/parser services retain the calling conventions
in the worker/core sources; RTS low-level request contracts are in
`src/v2-b2/str8n-v2-rts.asm`. These services are trusted interfaces, not memory
isolation. FLASH.MUTATE does not apply the RTS storage policy for its callers.

`COMMAND.REGISTER` takes A=single uppercase command letter and X/Y=handler
pointer low/high. Handlers must be pinned in 5800–5FFF, 7100–78FF or resident
E000–EFFF. It returns C=1/A=0 on success; C=0/A=1 invalid, A=2 duplicate,
A=3 full. Capacity is eight commands, four initially occupied by K/S/R/T.
Built-ins retain precedence. Dispatch matches the complete one-letter token.
Handlers return A=1 via RTS after handling their command. An independently
registered X handler is exercised by the host test.

`COMMAND.CORE` version 1 is a **read-only data service**, not a callable
command gate. LOOKUP returns C=1, Y=0 and A/X pointing to its six-byte descriptor
in manager RAM:

| Offset | Field |
| --- | --- |
| 0 | Descriptor format, 1 |
| 1 | Built-in command count, currently 10 |
| 2-3 | Pointer to packed one-byte keys in resident F ROM |
| 4-5 | Pointer to the corresponding little-endian handler words in F ROM |

The current keys are `BDMGLFICJ?`. Read the descriptor after initialization and
read its ROM tables with resident Bank 3 mapped. Descriptor/pointers are valid
until reset, manager reinitialization or firmware replacement. The targets are
monitor control-flow entries: their handlers may jump to the prompt or hand
off execution, and **must not be JSR-called or registered as RTS providers**.
Built-in parsing and precedence remain owned by the independent recovery
dispatcher. B/J accept attached bank digits through their existing parsers.
The catalog consumes none of the eight extension slots and exposes only keys
and targets, not syntax/help text or an enable/disable mechanism. Format
constants are in `str8n-v2-manager-public.inc`; tests check every key/target,
version refusal, fixed public ABI, stack balance and missing-E recovery.

The service directory is compiled into this candidate; the command registry
accepts additional pinned handlers at runtime. Returned service pointers remain
valid only until reset, reinitialization or core replacement. CRC16 is a build
compatibility/error check, not a security mechanism. There is no AP relocation,
unload, live provider replacement, general bank-call gate or SPI SRAM backend
in this milestone. Those can extend this manager boundary. Indexed fast slots
and per-service interrupt policies remain deferred to a full decimal version.

## Memory and measured size

| Allocation | Range / size |
| --- | --- |
| Application RAM | 0200–57FF: 22,016 bytes |
| Overlay reservation | 5800-5FFF: 2 KiB, available; no general allocator |
| Unassigned reservation | 6000–60FF: 256 bytes |
| Sector staging | 6100–70FF: 4 KiB |
| Manager/module reservation | 7100–78FF: 2 KiB |
| Permanent H dispatch stub | 7400-7402: three bytes inside manager RAM |
| Installed manager code/directory/catalog | 7100-7338: 569 bytes |
| RTS state/import bindings | 7500–7537 allocation, with gaps |
| Configuration private state/header buffers | 7540–756A |
| Manager registry/state | 7DCB–7DEA, within monitor-private RAM |

The F core is 3,984 bytes, including the unchanged 741-byte worker and
180-byte vector images, leaving 64 bytes before FFD0. Removing S/R/T from
the core key/pointer tables saves nine bytes: three keys and three two-byte
pointers. These commands continue through the existing unmatched-command
manager path; all ten built-in recovery entries stay in F. Public entry
addresses and RAM allocations are unchanged.

The COMMAND.CORE directory entry/name and six-byte descriptor add 25 manager
bytes. Three equivalent implementation reductions save seven bytes: four by
using existing monitor zero-page scratch for REGISTER's temporary target,
one by returning LOOKUP's high pointer byte with PLX, and two by sharing
existing error-return paths. Monitor scratch was already volatile under these
contracts. Net growth is 18 bytes, all inside reserved manager RAM/E flash.

The manager image is 569 RAM bytes and its E carrier is 849 bytes. Configuration
remains 991 code bytes, now at E351; RTS remains 2,255 bytes, now at E730. The
E carrier consumes the old 17-byte alignment gap, and shifting the following
modules by one byte consumes one old tail byte. E contains 4,095 bytes of
code/data and has one trailing free byte. Services with moved private addresses
remain discoverable through the same version-1 names and calling conventions.
A new E/F CRC binding requires installation as a matched pair; previous board
receipts do not qualify this revised pair.

Permanent H uses B3:C and a three-byte manager-RAM stub, without application or
overlay RAM. Adding more E-resident code requires another placement or further
reductions. The startup/configuration autoload list is now implemented in
the separate [autoload candidate](STR8N_V2_B2_AUTOLOAD.md); COMMAND.CORE alone
does not implement it.

The established public ROM/RAM entry addresses are preserved. Reducing the
application ceiling from 68FF to 57FF is an explicit beta 2 memory-contract
change; applications needing the old range must be rebuilt or adjusted.
Zero-page and upper monitor allocations retain their existing boundaries.

See [the consolidated design](STR8N_V2_BETA2_DESIGN.md) for future configuration
and AP runtime work, and [the manager include](../src/v2-b2/str8n-v2-manager-public.inc)
for assembly constants.
