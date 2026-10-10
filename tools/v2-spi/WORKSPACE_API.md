# WORK 1.2 allocation and workspace

Current checkpoint: WORK 1.2 remains at $5000–$648A with API $5003 in frozen
beta23. Four-board qualification passed, with EDU ON on all four. Earlier
beta15/beta17 installation statements below are historical. See the
[beta23 technical guide](../../docs/STR8N_V2_BETA23_TECHNICAL_GUIDE.md).

The [installed beta17 build](../../docs/STR8N_V2_STORAGE_TOOLS_2026-10-08.md)
relocates **WORK 1.2 to $5000–$648A**, with API **$5003** and `WK`,1,2 signature
at $5006. Reserve that library range; programs may start at $0200 and use the
contiguous $0200–$4FFF range while it is loaded. The request ABI below remains
unchanged. Build the paired candidate with `python tools/build_v2_storage.py`.
All three boards now have WORK 1.2. WORK 1.1 used $4003 and occupied
$4000–$548A; those addresses remain historical.

WORK is a W65C02S application library/utility for the beta14 SPI services
and paired SRAM 1.1 utility. WORK 1.1 was installed with beta15 on all three
qualified boards. Its API requires EDU mode ON and responding SRAM; 2512
uses OFF and reports unavailable software. See
[EDU mode](../../docs/STR8N_V2_EDU_MODE_2026-10-08.md).
It also uses ordinary 816 emulation instructions with DBR/PBR zero.
Native and interrupt callers are unsupported.
It adds no resident sector or permanent user-RAM reservation.

Build with `python tools/build_v2_workspace.py --build BUILD/v2-storage --base 0x5000`, load
`BUILD/v2-storage/workspace/workspace.s19`, then `G 5000` for the console.
The loaded WORK 1.2 library owns `$5000-$648A`, including its private buffers/state.
Loading it overwrites that range. A saved ordinary flash record named `WORK`
provides `R WORK`; no board provisioning is performed by these builders/tests.
User programs must reserve the library range or link a suitably placed variant.
The current build and ABI have fixed addresses; relocation is not automatic.

## Console and allocation

Help is printed once on entry and again on `HELP`; subsequent commands use
a plain `WORK>` prompt. `?` reports the gross program allocation in decimal
KiB and exact workspace capacity in decimal bytes. `P 16`, `P 32`, `P 48`,
or `P 64` selects the program allocation directly in KiB, previews the new
split, and asks `Apply? [y/N]:`. Only a single `Y` (case insensitive) confirms
the resize. Enter, `N`, any other answer, Escape or Ctrl-C cancels it.
Selecting the existing allocation reports `No change.` without confirmation
or metadata writes. The old console syntax `P 1` through `P 4` is rejected.
The remaining SRAM is workspace, excluding the last 32 bytes.

The [unflashed beta16 status candidate](../../docs/STR8N_V2_STATUS_DISPLAY_2026-10-08.md)
also reports saved program payload/workspace capacities at monitor entry and
inside EDU 1.1. Its query validates layout metadata without initializing a
session, claiming memory, resizing or changing SRAM bytes. WORK remains the
explicit administrator. This display is now installed in beta17 with EDU 1.2.

```text
WORK> ?
Programs: 64 KiB; workspace: 65504 bytes
WORK> P 32
Programs: 32 KiB; workspace: 98272 bytes
Apply? [y/N]: Y
Resized.
WORK> P 32
No change.
WORK>
```

Older WORK 1.0 uses `P 1`-`P 4` and hexadecimal capacity output. The three
qualified boards use the same interface in WORK 1.2.

`U` explicitly upgrades the Phase 4 layout without deleting saved programs.
`V` repairs an interrupted primary layout from its verified secondary.
Both require exact `YES`. `F` clears program references and workspace ownership
metadata with exact **`FORMAT SRAM`** confirmation. It does not erase payload
or workspace bytes. FORMAT invalidates and verifies all four claim markers,
including corrupt committed claims, before publishing the new layout. With a
valid retained session it advances the epoch and preserves counter history;
an invalid session establishes a fresh context. Discard all previous handles
after formatting. `Q` returns to the monitor. No formatting or upgrading
occurs merely because retained contents are invalid.

Normal results are `Resized.`, `Formatted.`, `Upgraded.`, `Repaired.`,
`No change.` or `Canceled.`. Common refusals have readable explanations,
including `Resize refused: workspace overlaps.` and
`Storage invalid or program exceeds boundary.`. Other service failures retain
the diagnostic form `WORK error: $xx`. Changing this console does not change
the application ABI: request byte 21 still uses 1-4 units of 16 KiB.

| Gross program region | Program payload | Workspace capacity |
| ---: | ---: | ---: |
| 16,384 | 14,336 | 114,656 |
| 32,768 | 30,720 | 98,272 |
| 49,152 | 47,104 | 81,888 |
| 65,536 | 63,488 | 65,504 |

Management consumes the first 2,048 bytes of the program region. Resize never
moves data. Shrinking refuses saved extents beyond the new boundary; growing
refuses a live workspace claim below it. Old committed program versions still
occupy space until SRAM's explicit reclaim command releases them. Existing
workspace claims keep their absolute placement when a change is permitted.

Workspace has four live claim slots. Claims start on 256-byte boundaries,
but lengths are exact, including the final 224 bytes ending at `$1FFDF`.
Allocation searches for a contiguous free interval; fragmentation can prevent
a request even when total free bytes would suffice. Claims receive existing,
uninitialized data; allocation does not clear the region.

Claims persist in SRAM across normal monitor return and library reload.
RESET clears a private resident latch at `$66AF`. Before the next claim/handle
operation, WORK commits a new epoch, so earlier handles become stale. Query
alone reports capacity without initializing a new epoch. Saved programs remain
eligible for validation after RESET. Session recovery after RESET is deferred.
Release invalidates its claim marker; a replacement receives a new ticket.
The private `$66AF` byte was already reserved/zeroed in the gateway template;
no new permanent RAM is allocated.

## Application calls

Validate `WK`,1,2 at `$5006-$5009`, then `JSR $5003` with A/X holding the
low/high address of a **32-byte request/result**. The block must be within
`$0200-$64FF`, outside the loaded library. Fields are copied before service
calls and results copied back on return. A=status, carry set only for success;
X/Y, zero page `$D0-$D5`, and private library buffers are clobbered. Calls are
foreground, IRQ disabled and decimal clear on return. Bank selection and stack
are preserved by the service. Caller must keep the library and source buffers
stable. A signature is version discovery, not an integrity/authenticity proof.

| Offset | Bytes | Meaning |
| --- | ---: | --- |
| 0 | 1 | 0 query, 1 claim, 2 release, 3 read, 4 verified write, 5 resize, 6 format, 7 upgrade, 8 repair |
| 1 | 1 | Flags; zero |
| 2 | 2 | Owner, LE16; nonzero for claim/release/read/write |
| 4 | 8 | Handle: slot, zero, epoch LE32, ticket LE16 |
| 12 | 3 | READ/WRITE offset relative to claim, LE24; QUERY returns absolute workspace boundary |
| 15 | 1 | READ/WRITE count, 1-64 |
| 16 | 2 | CPU buffer, LE16 |
| 18 | 3 | CLAIM length, LE24; QUERY returns workspace capacity |
| 21 | 1 | RESIZE program units, 1-4; QUERY returns current units |
| 22 | 1 | QUERY: legacy-layout flag; READ/WRITE: completed payload count from final transfer |
| 23 | 1 | QUERY: secondary-layout recovery flag; READ/WRITE: driver diagnostic transfer count |
| 24 | 8 | Administrative key: `RESIZE!!`, `FORMAT!!`, `UPGRADE!`, or `REPAIR!!` |

CLAIM returns the handle at 4-11 and a zero offset at 12-14. Keep the owner
and all handle bytes together; checks include slot, epoch, ticket and owner.
An application read/write cannot cross the claim, wrap a 24-bit offset, touch
the probe reservation or overlap the library. READ also refuses overlap with
its request/result block. WRITE stages at most 64 bytes and verifies readback;
an error can leave a partial or unverified write. Failed READ may already have
changed its CPU buffer. Counts do not override a failed status.

An unconfirmed allocation can leave a committed claim. The returned handle
fields, if available, can be checked/released, or RESET starts a new epoch.
Do not assume an error implies no effects. All epoch/revision/ticket counters
refuse exhaustion instead of wrapping. This is cooperative ownership, not
isolation from direct memory access. Losing retained management data invalidates
the storage context; explicit formatting establishes a new context, and clients
must discard previous handles. No authenticity or remaining-battery-life claim
is made.

Results `00`, `40`-`48` retain the SRAM utility meanings. Additional results:
`49` layout upgrade/WORK administration required; `4A` live-workspace resize
conflict; `4B` stale/wrong-owner handle. A saved extent outside a proposed
boundary is refused as `41`; it does not cause a layout write. Other results
are [resident SPI/SRAM statuses](SPI_API.md). Public raw SRAM WRITE stays denied;
WORK's bounded private write path restores that denial on return.

## Retained management layout

| Address | Bytes | Meaning |
| --- | ---: | --- |
| `$00000-$0003F` | 64 | Primary `SS` v2 layout |
| `$00040-$0023F` | 512 | Existing eight `SP` v1 program records; unchanged |
| `$00240-$0027F` | 64 | Secondary layout |
| `$00280-$002FF` | 128 | Two alternating `WS` v1 session packets |
| `$00300-$0037F` | 128 | Four `WC` v1 claim records |
| `$00380-$007FF` | 1,152 | Reserved management space |

The 64-byte packets have zero reserved fields, a CRC-16/CCITT seal at 60/61
(initial `$FFFF`, polynomial `$1021`, high byte first), zero at 62 and `$A5`
commit at 63. CRC over 0-61 is zero. Layout fields retain `SS`, version at 2,
eight slots at 3, first payload page 8 at 4, boundary in 256-byte pages LE16
at 5/6, and nonzero revision LE32 at 8-11. Units are 64/128/192/256 pages.
Session fields are `WS`,1; revision LE32 at 4-7; epoch LE32 at 8-11; latest
ticket LE16 at 12/13.

Claim packets are 32 bytes: `WC`,1 at 0-2; owner LE16 at 4/5; ticket LE16 at
6/7; epoch LE32 at 8-11; absolute start LE24 at 12-14; exact length LE24 at
16-18; other fields zero; seal at 28/29, zero at 30, commit `$A5` at 31.
CRC over 0-29 is zero. Committed corrupt or overlapping claims are refused.
Valid claims from older epochs are inactive and their slots may be reused.

Layout update writes/verifies the secondary first while the primary remains
authoritative. It then invalidates/verifies the primary marker: this publishes
the new boundary through the verified secondary. The primary is rewritten and
committed afterward. A cut before primary invalidation leaves the old boundary;
a cut afterward permits WORK to read the secondary and explicitly repair.
SRAM 1.1 refuses an invalid primary until repair, so it cannot write into the
wrong region. A committed corrupt primary is refused rather than silently
falling back. Use the paired utilities; SRAM 1.0 does not implement v2 ownership.

Session updates alternate packets by increasing revision. A ticket is committed
before its claim record can be published. Each reused packet/slot has its old
marker invalidated and verified before replacement. No partially written packet
becomes active merely because it previously held a committed record.

## Runnable metadata-cache example and costs

Build `python tools/build_v2_workspace_example.py`. With a v2 layout and the
WORK library loaded, load `workspace/example/example.s19` and use `G 2000`.
It claims 64 bytes for eight 8-byte metadata rows (id, length, load address,
flags), writes/verifies four cache lines, reads/checks them, releases the handle,
prints `W: 00`, then returns through HOLD. It never formats or resizes storage.

The client is **293 bytes**, including its 64-byte immutable test fixture. Its
mutable RAM is a **16-byte two-row cache**, **32-byte request**, and one-byte
line index. The WORK 1.1 image is **5,259 bytes**: 4,716 instruction/table bytes
and 543 bytes of private buffers/state, all within ordinary application RAM.
The previous WORK 1.0 image is 4,602 bytes. The new console adds 657 bytes
to the application image and no resident sector or permanent service RAM.
Four fixed decimal capacity strings and shared allocation digits avoid
a general 24-bit decimal formatter.

Measured by the 65C02/real bit-level SPI model after activation:

| Operation | CPU cycles | SPI frames | Clocked bytes |
| --- | ---: | ---: | ---: |
| Claim 64 bytes | 782,322 | 60 | 1,221 |
| Verified WRITE 16 bytes | 641,207 | 40 | 993 |
| READ 16 bytes | 627,027 | 38 | 971 |
| Release | 623,352 | 40 | 963 |

Each data operation currently revalidates layout, session, four claim records
and eight program headers. That metadata dominates small-transfer cost. At an
illustrative 8 MHz, the measured READ is about 78 ms and verified WRITE about
80 ms; these are model figures, not hardware timing measurements. Caching more
metadata to reduce transfers is deferred until measured board qualification.
The 16-byte client cache demonstrates bounded backing storage without starting
an assembler implementation.

The Phase 6 prerelease review corrected FORMAT's existing-session path so
corrupt old claim packets cannot survive an explicit format. Focused model
checks cover all 213 existing-session FORMAT write cuts, all 205 UPGRADE write
cuts, preservation of payload/workspace bytes, explicit retry/repair, and
refusal of exhausted epoch, session revision, ticket and layout revision
counters without wrapping. These are model qualifications; they do not claim
board testing.

WORK 1.1's assembled console model covers all four direct KiB selections,
help/prompt behavior, same-size no-write queries, canceled and malformed
commands, live-workspace resize refusal, explicit format/upgrade/repair,
uninitialized storage and unavailable optional services. The existing
allocation, guard, all 651 interrupted-write checkpoints and bit-level SPI/cache
integration suites also pass for this image. `tools/audit_v2_workspace.py`
binds those reports and the new console report to the image/source hashes.
The model transcript is generated at
`BUILD/v2-spi-resident/workspace/console-example.txt`; it is not a board capture.
WORK 1.1 was flashed with beta15. 2205/2609 passed actual format, direct
32/64 KiB resize, readable capacities and same-size no-change commands;
their original SRAM contents are restored afterward. On 2512 and during
temporary OFF-mode checks on both EDU boards, unavailable WORK calls leave
all 512 reclaimed RAM bytes untouched.
