# Flash components, optional applications and reclaiming space

This map describes **rc1 DBG1 v1g, generation50**. A valid application is not
necessarily an independent erase unit. Flash erases affect a complete **4 KiB
sector**, including any shared tables, vectors, CRCs, records or user bytes.
There is no qualified general `uninstall ASM` / `uninstall DBG1` command in r9.
This guide does not erase or program either board.

## Direct answer: can I erase ASM or DBG1?

- **UCHESS** is an independently stored application record in B1:`$8000–$8FFF`.
  It can be omitted from a fresh layout without removing the monitor, ASM or
  debugger. On an installed board, first prove that the entire sector contains
  only the application and erased space; preserve any other owner bytes.
- **ASM occupies two sectors**, B1:`$E000–$EFFF` and `$F000–$FFFF`. The latter
  also supplies opcode/length tables used by DBG1. Erasing both does not retain
  a working full debugger. Erasing only E can remove the ASM entry while
  retaining those tables, but it changes the admitted exact core image. It is
  a reduced model layout, not a qualified general uninstall workflow.
- **DBG1**, B1:`$A000–$AFFF`, is coupled to both v1g monitor headers and RAM
  BRK/HOLD hooks. Do not just erase its sector: ordinary program return or BRK
  can still enter it. The normal mutation paths protect this sector. A usable
  no-debugger configuration needs matching monitor/core code, not a bypass of
  that protection.
- **CLOCK and the utility providers** have their own and shared regions below.
  An application name does not establish an independent reclaimable sector.
  Erase-only removal of those resident providers has not been qualified here.

Removing firmware components also removes features; the result is a reduced
system, not the unchanged full-system configuration. To retain all full-system
capabilities, retain all their component sectors. No application RAM is
reserved by DBG1, so removing it does not recover an application RAM allocation.

## Sector map

Bank numbers here are flash banks, not the internal MON A0/B0 page names.

| Bank / CPU range | Contents | Reclaim rule |
|---|---|---|
| B0 `$8000–$FFFF` | Owner/vendor bank, absent from STR8-N BINs | Preserve it. It is not automatically free. |
| B1 `$8000–$8FFF` | UCHESS stored record and remaining sector space | Optional record; remove only after whole-sector ownership inspection. |
| B1 `$9000–$9FFF` | Erased in the fresh reference image | 4 KiB already free in that image; inspect a real board for owner data. |
| B1:A `$A000–$AFFF` | DEBUG (DBG1) | Keep with v1g monitor/BRK/HOLD hooks. |
| B1 `$B000–$DFFF` | CLOCK storage image | Three sectors; not a proven generic erase-only uninstall. |
| B1 `$E000–$EFFF` | ASM header/editor/parser/assembler part 1 | E-only removal disables ASM; reduced layout / updater admission limit applies. |
| B1 `$F000–$FFFF` | ASM continuation, opcode/length tables and vectors | Shared with DBG1 decoding/stepping; keep for DBG1. |
| B2 `$8000–$CFFF` | MAINT/SRAM/WORK/EDU utility image | Shared utility and integrity domain; do not erase by command name. |
| B2 `$D000–$DFFF` | Utilities through `$D7FF`, boot-status provider from `$D800` | Shared sector; not independently reclaimable. |
| B2 `$E000–$EFFF` | Boot-status through `$E1FF`, battery provider `$E200–$EBFF` | Shared sector; padding does not make the sector free. |
| B2 `$F000–$FFFF` | Local display `$F000–$F6FF`, VERSION `$F800–$FFFF`, small gap | Shared sector; not a whole free sector. |
| B3 `$8000–$9FFF` | RTC/journal services and protected mutable holes | System/persistent services; retain. |
| B3 `$A000–$AFFF` | MON A | Keep valid matching slots and fallback; not an app uninstall target. |
| B3 `$B000–$BFFF` | MON B | Same rule; preference changes do not reclaim a safe app sector. |
| B3 `$C000–$DFFF` | Configuration/wear journal pair | Never reclaim as application space. An erased inactive journal is still reserved. |
| B3 `$E000–$EFFF` | Named-app dispatcher, services, S/R/T, initialization/loaders | Required shared core. |
| B3 `$F000–$FFFF` | Fixed reset/recovery core and vectors | Required bootstrap; not a replaceable application. |

The utility image is `$5800` bytes starting at B2:`$8000`; its last sector is
shared with another provider. Likewise ASM is not confined to its entry sector.
Unused bytes inside an occupied sector cannot be reclaimed by erasing that
sector while keeping its other occupants.

DBG1's linked shared-table addresses are B1:`$F17E` (lengths) and
`$F49C–$F993` (opcode table). `U`, `S` and `N` depend on correct decoding.
The model checks accompanying the package exercise MON A on both CPUs and
distinguish a deliberately reduced fixture from an independent removable
application. They are not physical
erase/uninstall qualification and do not authorize board changes.

## Upgrade and wear consequences

Use a fresh repeated four-bank capture, not this clean-image map alone, to
determine what a particular board owns. Back up a complete sector before any
reviewed mutation. Use the supported wear-accounted flash path and exact
restoration/readback plan; do not bypass debugger/system protection or erase a
sector with an external programmer and then pretend the wear journal is current.

The uniform updater admits exact registered core/provider bytes. Removing ASM,
DBG1 or another registered core sector can make the source **unknown**, even if
some monitor commands still work. R9 does not promise to reconstruct arbitrary
stripped layouts. An exact same-generation component restoration may be needed
under a reviewed preserving plan; this is not a rollback through generation49.
Owner data outside the admitted firmware profile remains data to preserve.

## F-only, opaque banks and the full-system BIN

The package includes the **exact 4,096-byte B3 `$F000–$FFFF` component** and the
**full 98,304-byte B1/B2/B3 system**. They are different artifacts with different
purposes. See [image choices and offsets](RELEASE_PATHS.md).

The F component alone provides fixed recovery, not the normal B3 monitor, ASM,
debugger or `J0/J1/J2` command parser. Its recovery menu is `A/B`, `U A|B`, `W`.
The B3 bank slice also is not a standalone DBG1 system with arbitrary B1/B2:
v1g has cross-bank dependencies. Do not label either slice as a separately
qualified minimal bank launcher.

From the complete running monitor, `Jn` selects bank n and follows its reset
vector at `$FFFC/$FFFD`; it does not require a STR8-N application record or
relocate the target. A target program must supply valid vectors and its own
runtime assumptions. B0 is left available to its owner; the full system already
occupies substantial B1/B2 ranges. Keeping all B0/B1/B2 opaque while retaining
the v1g full system is not this layout. That requires a different compact
monitor/boot build and separate qualification.

Native applications/debugging remain excluded. The RTC issue is deferred, and
RTC drift is outside release qualification. No clocks, preferences, RAM or
flash on 2604/2609 are changed by this documentation or its CPU model checks.
