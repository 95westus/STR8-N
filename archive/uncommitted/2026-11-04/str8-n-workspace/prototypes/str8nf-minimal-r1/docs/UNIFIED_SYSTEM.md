# Unified STR8N-F codebase

The 2512 FLASH work and the 2609 F-up work now use this single source tree and
build command. The shared baseline remains b15 / PR04 / generation 8000000F.
The F bytes and boot-record format are unchanged. Board profiles describe
installed components and preservation requirements; they do not contain saved
defaults, owner images, journal pages, erase counts or USB identities.

## Build and verify

From the STR8N-F project directory, with Python and the WDC assembler/linker:

```text
python tools/build_system.py --out build/system
python tools/verify_system.py --build build/system
```

A requested source build produces 18 payloads from local source. The operator
release reuses existing payloads and does not execute this rebuild. There are no imports from the parent
STR8-N project, private captures, or old build directories. The original
four-component `tools/build.py` remains the small F-only toolkit build. The
system build calls that same builder and adds the optional components.

| Shared component | Use |
|---|---|
| BOOT | B3:F bootstrap, recovery, first-byte Ctrl-C and raw RAM loader |
| CONFIG RAM | The same BIN on either board; enable/entry/default and wear inspection |
| OPAQUE RAM | OIP1 sector read/replace, preimage checks and durable wear reservation |
| DEMO RAM | F console and capability demonstration |
| MAINT RO RAM | The same BIN on either board; map, buffer read/display, CRC and compare |
| READBACK RAM | Binary flash/RAM export and fixed-range RAM restoration with CRC |
| MON BASE A/B | Existing b15 monitor layout used on 2512 |
| MON VX1 A/B and VX1 E | Same monitor template with the optional VERSION/CAPS hooks |
| ES1 8 and EDU/SRAM RAM | Optional read-only provider and client; fitted hardware required |
| FLASH 8000 or 9000 | Same commented application, alternate allocations; RAM/flash edits and Q |

Both MON flavors are generated from one monitor template. FLASH placements are
generated from one application and entry stub. All components share F constants,
RAM services and the existing guarded journal engine. Legacy board-bound
builders remain historical qualification evidence and are not the active build.

## Board layouts remain independent

The [profiles](../profiles.json) represent these existing installations:

| Item | 2512 | 2609 |
|---|---|---|
| CPU | 65C02 | 65C816 emulation |
| F | Same b15 BIN | Same b15 BIN |
| MON | BASE A/B | VX1 A/B |
| B0 | FLASH at $8000; original backup retained privately | Entire WDC backup preserved |
| Optional B3 components | Existing owner contents preserved | VX1 at E; ES1 at 8 |
| Saved boot policy | Preserve current settings | Preserve current settings |

These are component inventories, not full-flash images or installation scripts.
Unification does not copy one board's journal, image allocation, saved default or
wear into the other. A component already matching the common build needs no
erase. A new optional component needs its own selected target, backup, current
preimage admission, durable wear reservation and verification.

The FLASH example remains installed at B0:8 on 2512. It is available from the
same build for a future assigned location on 2609. Do not use 2609 B0 as that
location. FLASH's application-local protections are not a board inventory:
its editor must not be used to overwrite optional services or owner backups.
MAINT is read-only; its generic B0/E labels avoid claiming those regions contain
a particular image on every board. Consult the board inventory for their use.

## Default boot uses the same CONFIG

At `REC>`, enter `C1`, then `L`. At `SEND BIN`, send
`firmware/payload/STR8N-F-CONFIG-RAM.bin` as binary and wait for its prompt.
Inspect with bare `B` before changing anything. Each accepted setting command
saves immediately; `W` displays wear and is not a Save command.

For the existing 2512 FLASH image, with its enabled B0:$8000 entry:

```text
C 0
B
Q
```

To choose MON B later, reload the same CONFIG and use `C B`, then `Q`.
For a separately installed and verified image in B1 at $9000, the sequence
would be `B 1 9000`, then `C 1`, then `Q`. This example does not assign that
space or install an image. The 2609 BASIC/Forth selector remains future work.

CONFIG and the other RAM tools borrow application RAM starting at $0200.
Live maintenance must escrow and restore owner RAM when preservation is
required. Q returns/restarts; it does not automatically undo borrowed RAM.

## Verification and remaining work

The unified qualification runs both CPU models against both board layouts.
It checks common CONFIG inspection, MAINT reads/CRC/compare, binary export and
RAM restore, FLASH editing/LED cleanup/Q, and both VX1 MON query paths. The
existing 26 core boot/config/OIP groups also run. The existing independent reproduction covers
all 18 payloads. Rebuild/reproduce only when a concrete source change requires it. Byte-identical optional components retain their earlier
component evidence; generic text changes and CRC updates are declared separately.

The [system qualification](../validation/system-qualification.json) is offline.
Live board receipts are separate and must name the exact build. Neither a
profile nor model results prove that a board was updated or tested physically.

Still planned: menu-based CONFIG, the named FLASH/IO/FILE/PROGRAM launcher,
2609 BASIC/Forth selector, general owner-history import, the proposed LED/piezo
ABI, and physical ACIA qualification. This merge does not implement those ideas.
