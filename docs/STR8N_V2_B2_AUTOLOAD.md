# Selective command autoload candidate

**Installed and checked on 2205:** named-command registration v2 is implemented
in the same manager. The X module also publishes HELLO/ECHO; H lists names.
The core is now 4,039 bytes (9 free), 26 bytes above the earlier 4,013-byte
startup-order revision. Full readbacks and direct/legacy command checks passed.
See the
[named command contract](STR8N_V2_COMMAND_EXTENSIONS.md#named-commands-commandregister-v2).

October 4, 2026. **Installed and checked on 2205**, with matched B/C/E/F
images and persistent selection in B3:D. R/S/T/X/H are enabled and registration
messages are on. Application autostart remains disabled (`C 00 03 V 0A`).
See the [board record](STR8N_V2_B2_2205_BOARD_TEST_2026-10-04.md).
Earlier E-only and E/F-only updaters do not install this revision.

The current source includes a subsequent startup-order fix, **flashed and checked**:
the hold-window dots precede registration messages, then the monitor banner.
Selected extensions still initialize before application entry. This adds 12
core bytes over the previous revision (4,013 bytes, 35 free); public ABI and
RAM reservations are unchanged. The installation record includes both the
earlier 4,001/4,013-byte builds and the current 4,039-byte build. Software-reset output
and full readbacks passed on 2205; configuration and user RAM were preserved.

## Choosing commands

Keep the existing K configuration sector and storage masks (currently B3:D).
C controls application boot. Extension initialization runs before that decision,
including with `C 0`.

```text
K AUTO ?             Show persistent startup selection
K AUTO +X            Enable X; default returning entry C70A
K AUTO +H            Enable H; default returning entry C00A
K AUTO -X            Disable X at next reset
K AUTO -S            Disable S independently of R/T
K AUTO QUIET 1       Suppress successful startup messages
K AUTO QUIET 0       Show successful startup messages
K AUTO CLEAR         Select no optional commands; retain recovery K
K AUTO RESET         Replace the list with R/S/T on and H/X off
K AUTO +Y CA00       Add a future Y provider by returning entry
K AUTO -Y            Disable Y, retaining its address
K AUTO +Y            Reenable Y using that stored address
```

Every edit shows its proposed list and asks the existing flash-write
confirmation. It preserves the CF storage header and all bytes outside AL/1.
AUTO edits do not rewrite the core boot pocket. **Reset applies changes**;
editing does not unload live commands/services.

Installing a new Y image does not enable it. An absent AL block retains the
legacy R/S/T defaults with H/X off; the first edit makes those defaults explicit.
Use CLEAR to start with only K, then select exactly the desired commands. RESET
and CLEAR can explicitly repair malformed AL metadata when CF is valid.

Example startup with R/S/T/X/H selected and messages enabled:

```text
K registered
R registered
S registered
T registered
X registered
H registered
```

K cannot be deselected. Invalid AL metadata retains only K and reports
`Autoload invalid`. Missing/invalid CF loads no configured providers, retains
legacy wrappers, disables RTS writes, and leaves the monitor usable. A failed
provider reports `Y registration failed`; later selected entries are attempted.
Quiet suppresses successes, not errors. With FT245 absent, no startup output is
attempted, preserving headless application boot.

There are eight selection records and eight runtime command slots. K uses one
runtime slot, leaving seven active optional commands. Disabled records retain
addresses and occupy selection records; CLEAR/RESET reclaim them. Providers
initialize in displayed order, without discovery or dependency resolution.

R/S/T are individually selectable commands of the existing RTS provider. Its
code/service bindings remain resident; disabling a command does not reclaim
that provider's RAM. Providers in this milestone execute in resident bank 3;
storage and configuration still support optional bank selection. General
cross-bank provider execution remains future AP runtime work.

## Returning initializer contract

An entry is in resident B3 ROM B000–DFF9 and begins with a three-byte JMP,
then EX, format 1, and its uppercase key:

```asm
AUTO_ENTRY:    JMP INITIALIZE
               DB "EX",$01,'Y'
INITIALIZE:    ; Discover COMMAND.REGISTER / SERVICE.REGISTER via LOOKUP.
               ; Validate and initialize explicitly owned pinned storage.
               ; Register exactly one Y command; optional services may follow.
               ; Return C=1,A=0 on success, C=0 on failure.
               RTS
```

The manager checks the version/key header at configuration and startup. This
is not a checksum of the complete third-party provider image. SEI/CLD, 65C02 or
816 emulation, DBR/PBR=0 and resident bank 3 apply. AXY, flags and monitor scratch
are volatile. Keep the stack balanced and selected bank unchanged. Do not jump
to the monitor, chain another module, or call manager INIT. Discover/publish
services through LOOKUP/SERVICE.REGISTER; a later module may consume earlier
services. Providers must not use autoload-private RAM 7640–768E.

Success must add exactly one command with the requested key. On failure or an
incorrect registration, the manager restores command/service counts, withdrawing
new records. Providers own other memory side effects and must keep private state
safe on failure. No live unload, allocation, ownership tracking, console-driver
replacement or runtime linker is introduced.

H/X returning entries are C00A/C70A. Original `G C000` and `G C700` remain
compatible; C700 manually registers both X and H. Manual registration is separate
from automatic selection. Keep C from pointing at that combined legacy entry
when selective startup is wanted: it explicitly chains H regardless of AL.

## Persistent format and recovery

CF/1 at sector offsets 0–15 and its FFD0–FFDF locator remain compatible. The
previously reserved CF byte 10 becomes A1 when an AL block is assigned; it is
included in CF's checksum. This distinguishes a torn/erased list from an older
configuration that never had a list. AL/1
occupies offsets 10–4F hex in that same reserved sector. K mask changes and
configuration relocation preserve valid AL; opaque bytes outside it survive.

| AL offset | Meaning |
| --- | --- |
| 0–1 | ASCII AL |
| 2 | Format 1 |
| 3 | Completed 3F; staged 7F until data verification |
| 4 | Quiet flag 0/1 |
| 5–7 | Zero reserved |
| 8–39 | Eight records: key, enabled 0/1, initializer LE16 |
| 40–61 | Zero reserved |
| 62–63 | CF two-sum checksum over bytes 0–61 |

Empty records are all zero. R/S/T use initializer zero; others require EX/1
entries. Core keys/K and duplicate keys are rejected. A wholly FF block means
absent. Checksums, completion, flags, keys and addresses validate before any
selected initializer runs. Interrupted sector writes can invalidate CF itself;
the monitor remains bootable. RESET/CLEAR repair AL only when CF is valid;
otherwise repair/reselect the configuration sector first.

## Measured size

This table describes the earlier 4,013-byte startup-order revision. The installed
named-command revision and its measured increase are documented in the
[command extension guide](STR8N_V2_COMMAND_EXTENSIONS.md).

| Item | Candidate | Change from installed service revision |
| --- | ---: | ---: |
| F core including copied core RAM images | 4,013 bytes | +29; 35 free |
| Copied manager at 7100 | 516 bytes | unchanged |
| Autoload code/text in B | 2,194 bytes | +2,194 |
| Config editor at BB00–BEEE | 1,007 bytes | +16; moved from E |
| E carrier | 370 bytes | +62 |
| Service helper at E180 | 507 bytes | unchanged; relocated |
| RTS at E400 | 2,255 bytes | unchanged; relocated |
| H/X C code/text | 1,950 bytes | +159 |
| Autoload RAM 7640–768E | 79 bytes | existing manager reservation |
| Persistent AL metadata | 64 bytes | existing config reservation |

Total code/text increase: **2,460 bytes**, including **29 core bytes**. No new
flash sector or user RAM reservation. B contains manager backing, autoload and
config code; E contains the carrier, services and RTS. The copied manager,
autoload, config, service helper and RTS participate in the runtime CRC binding;
the carrier checks its expected F binding before using private core calls.
Public ROM/RAM entries and saved records
retain their ABI/formats. Application 0200–57FF remains **22,016 bytes (21.5 KiB)**;
5800–5FFF remains a separate **2 KiB overlay**. H/X retain six stub RAM bytes.

Build with `python tools/build_v2_b2.py` and
`python tools/build_v2_b2_command_example.py`. `make v2-b2-check` includes the
assembled-opcode autoload tests and existing manager/config/service tests.
Separate H/X suites check legacy manual startup. Physical serial checks passed:
full bank readbacks, independent software-reset autoload, X deselection,
H/X with all selected banks, RTS and dynamic services. Physical-button RESET
and power-cycle checks remain pending.

All **37 host check groups passed**: nine manager/RTS/ABI, eight configuration,
three dynamic-service, five selective-autoload, one headless, four flash-H,
three H/X and four RAM-H compatibility groups. `make v2-b2-autoload-check`
builds all these images and runs all 37 groups. These execute assembled code
in the banked 65C02 model, including failed writes, malformed metadata and
provider rollback. `python tools/qualify_v2_b2_autoload.py` verifies receipt
hashes against the current images and records `BUILD/v2-b2/autoload-qualification.json`.
