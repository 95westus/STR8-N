# STR8-N MON feature preview

This is the partial preview checkpoint. The
[unified shipping contract](UNIFIED_SHIPPING_RELEASE.md) requires all b35
capabilities except ASM/DBG, including functional CONFIG and CLOCK SET.
The preview's read-only pages and historical acceptance do not complete it.

Requires frozen **STR8N-F v0.3.0 g00000001 / BASE1 / PR05**.
Runtime components: MON A/B 0.1.0-dev g8, services g4, WB2 g5 and PROGRAM/SP1 g1.
MON B and installed tools passed the documented 2609/65C816 emulation checks.
This preview does not claim complete b35/rc1 replacement.

Subsequent [2512/65C02 installed acceptance](2512_SERVICES_G4_INSTALL_ACCEPTANCE.md)
passed on the same services g4/WB5/SP1 bytes: physical saved-default B boot,
native maps/wear/TIME, matching flash reload, CLOCK, PROGRAM query/Table,
BATCH and AUTO/NO. Positive PROGRAM write/run remains a separately named
CPU/backend scope. These later source receipts leave preview 1's published
archive and Foundation downloads unchanged.

Current positive Store/Restore/run now passed on
[2512/65C02](2512_PROGRAM_POSITIVE_ACCEPTANCE.md) and
[2609/65C816 emulation](2609_PROGRAM_POSITIVE_ACCEPTANCE.md). The 2512
composite receipt discloses its host directory-slot planning error and exact
restoring continuation; it does not claim the original narrow scope passed.
Current-g4 [AP/02 flash launch on 2609](2609_AP02_ACCEPTANCE.md) also passed,
with the original retained WDC bank restored and RTC sampling readmitted.

## Package and terminal

The candidate contains an unchanged copy of the published N-F operator kit in
`foundation/`, including its exact4KB F.bin, migration/recovery tools and Python
Serial Console0.1.0. New optional monitor/tool payloads are in `monitor/payload/`.
The foundation's own manifest remains unchanged and separately verifiable.

```text
python -m pip install -r foundation/requirements-console.txt
python verify_candidate.py
python foundation/tools/verify_release_kit.py foundation
python foundation/tools/nf_console.py
```

F10 connects, F2 chooses a BIN, F4 loads from an observed REC>, F3 sends at
SEND BIN, F9 controls logging and F12/Ctrl-C cancels before a transfer starts.
Disconnect the terminal before a CLI owns its port. A transfer borrows RAM;
use the preservation procedure when existing owner RAM must survive.
Use F3/F4 for matching foundation RAM tools and OPAQUE for flash images from
`monitor/payload/`.

For one host-side current-time sample, leave the board idle at B3>, disconnect
the terminal, and run:

```text
python monitor/host/time_samples.py --port COM8 --idle-monitor --output time-samples.jsonl
```

Add `--interval 300` to repeat every five minutes until Ctrl-C. This logs the
board calendar and host UTC; it does not set the RTC or obtain an NTP reference.
Use one serial owner at a time; the separate lab RTC/NTP campaign defers while
the port is occupied.

## Installation boundary

F stays unchanged. The tool bundle occupies B2:8/9/A, the dispatcher B3:E,
and optional MON A/B occupy B3:A/B. These are owner sectors under minimal N-F;
they are not automatically free or reserved for this preview. Preserve their
existing images before admitting replacement. No whole-chip clone is supplied.

Use the existing foundation OPAQUE installer and its verified preimage/wear
procedure for explicitly admitted 4KB targets; the split B2 files are supplied
for that protocol. Keep recovery as the saved default during installation.
Install the bundle and dispatcher before selecting a new monitor. In the
qualified 2609 installation, only MON B was replaced; A remains retained
legacy firmware whose execution is unqualified. Do not select that old A.

After installation, reset and select **B** at N-F's chooser to enter MON B.
`Q` returns to REC>. Installing an image does not save a new default. To make
an admitted monitor B the default, matching RAM CONFIG uses `C B`; that is a
separate persistent journal operation and was not included in the preserving 2609
preserving-install scope. Check journal capacity/rotation before adding it.

Do not load development workbench RAM packets directly from F-only recovery:
their Q expects an active compatible ROM monitor. The bounded2609 RAM trial
used a private temporary return hook, restored afterward. That fixture is not
an operator installation procedure or an included feature payload.

## Commands after an admitted monitor/tools installation

```text
?                  help
V                  monitor / foundation identity
TIME               read current RTC calendar
D 3000 303F        hex/ASCII dump
M 3000 12 34       ordinary RAM modification
!M addr bytes      deliberate force; B3:C/D/F remain protected
M1                 bank/sector map
W                  tracked erase counts, with physical-wear caveat
APPS               compatible native/owner app inventory
APP name           launch a CRC-admitted AP/02 image
MAINT              open tools
MAINT LOAD         deliberately reload the current tools
Q                  return from MON to recovery
```

MON and workbench Q have different destinations: an installed workbench's Q
returns through HOLD to its active admitted monitor; MON's Q enters REC>.
Retained AP/01 programs and old private-provider apps are not made compatible
by appearing in a memory map. Earlier AP/02 launch/return passed on 2512 with
services g3; current services g4 now also passed positive launch on 2609/816E.
The example's CPU header must match 02 or 16 as appropriate, with valid header
and payload CRCs. The 2609 fixture reused the same executable body with its
CPU 16 header; its original WDC sector was restored afterward.

Inside WORKBENCH:

```text
EDU ON                         choose the volatile Rev D profile
SRAM                           query the existing mounted PROGRAM layout
SRAM PREP                      explicitly acknowledge disabled VIA CB flags
T                              selected flash bank plus PROGRAM if enabled
T P                            PROGRAM records and versions
S P AUTO 3000 3007 HELLO         preview/store RAM data in PROGRAM
NO                             cancel at the YES prompt
R P HELLO L                     load only, checking payload CRC and RAM bounds
R HELLO L                       search selected flash plus PROGRAM; refuse ambiguity
BATCH T;T                      bounded returning-command sequence
WORK                           existing workspace bounds; no message allocation
Q                              return to the active compatible monitor
```

`SRAM PREP` is needed only after disabled CB flags block a transfer. Its guard
refuses enabled interrupt/pin ownership. It acknowledges VIA edge flags, not
RTC power-fail flags; it performs no SPI clocks. Never use it to override a
peripheral owner. Missing hardware, incompatible format or busy pins must be
reported rather than formatted automatically.

AUTO determines an address inside the explicitly selected backend. It does
not select a backend or erase. Flash Store additionally requires an owner-
declared B0/B1 AREA; erased bytes alone do not grant allocation. NO writes no
record; YES commits a new record. PROGRAM and flash record formats differ.
PROGRAM has directory/payload CRCs; legacy flash SR01 has no payload CRC.

## Initial preview acceptance (historical)

The following paragraph records preview1's original qualification boundary.
The later qualification links above and below supersede its pending status;
the published archive itself remains unchanged.

2512/65C02 RAM evidence with services g3 covers positive PROGRAM Store/Restore/AUTO, refusal
cases, AP/02 launch/public return, exact test-byte restoration and the one
specifically approved older duplicate retirement. Those tools are not yet
installed on 2512. 2609/65C816 emulation adds RAM and installed acceptance for the monitor,
native TIME/maps/APPS inventory, guarded PROGRAM query/Table, BATCH and AUTO
preview canceled with NO. It adds no positive 816 PROGRAM-write/run claim.
Services g4's forced-reload fix passed on 2609; g4 on 65C02 has not been retested.

Full SOURCE/ASM/DEBUG, complete core/app BATCH parity, advanced CLOCK, the
4KB FLASH editor, CONFIG integration and persistent WORKSPACE messages remain
unfinished. Battery condition/prior physical flash wear remain unverified;
tracked counts and policy are not physical-health measurements.

## Later qualification and next release

The unchanged installed payloads subsequently passed
[positive PROGRAM Store/Restore/run on 2609](2609_PROGRAM_POSITIVE_ACCEPTANCE.md),
including exact full-SRAM/owner-RAM restoration and zero flash writes. That
later receipt adds evidence to the existing binaries; it does not replace the
published preview 1 ZIP or its original manual snapshot.

The owner has deferred [resident ASM and DBG](MON_ASM_DBG_RELEASE_GATE.md)
as follow-on work. Their BASE1 port and live qualification are open, without
blocking the current MON/tools release.
