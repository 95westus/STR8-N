# SPI Phase 5: adjustable allocation and workspace

Recorded 2026-10-08. The unflashed beta14 SPI candidate now pairs **SRAM 1.1**
with **WORK 1.0** and a runnable metadata-cache example. Linked-model checks
cover allocation, lifecycle, interrupted writes and actual resident bit-level
SPI integration. No serial ports were opened, boards changed, commits made or
files pushed. Boards 2512/2205/2609 still run beta13/CLOCK 1.5.

Phase 6 prerelease review subsequently corrected WORK's explicit FORMAT path
and repeated its model qualification before board installation. The footprint
and cycle figures below reflect that corrected candidate; the original Phase 5
image was 4,586 bytes. This follow-up changes utility code only, with no new
resident reservation or sector.

## Behavior

Program storage can occupy 16, 32, 48 or 64 KiB in 16 KiB steps; the first
2 KiB remains management space. Workspace uses the remainder through `$1FFDF`,
with the final 32 SRAM bytes reserved for the existing probe. The default
split retains 63,488 program payload bytes and 65,504 workspace bytes.
The smallest program region leaves 14,336 payload bytes and 114,656 workspace
bytes. No automatic relocation or compaction occurs.

WORK refuses shrinking past a committed saved extent, including retained old
versions, and refuses growing across a live workspace claim. Claims keep their
absolute location when a resize is accepted. SRAM 1.1's table/free-space/save
checks honor the selected boundary. Existing named program record bytes and
flash storage formats are unchanged.

Four workspace slots provide claim, release, read, verified write and capacity
query. A handle includes slot, epoch and ticket, with a separate owner check.
Offsets are relative to the claim and use checked 24-bit arithmetic. Buffers
must stay within application RAM and outside the loaded library; READ also
refuses overlap with its request/result. Writes use bounded staging/readback.
An error can leave partial/unverified data and does not imply rollback.

Claims survive normal monitor return and library reload. Actual RESET clears
the already-reserved `$66AF` latch; the next handle operation publishes a new
epoch, invalidating old handles. Query alone remains a capacity operation.
Each allocation commits its ticket before publishing the claim, so interrupted
replacements cannot reuse a published handle. Exhausted counters refuse wrap.

The paired layout is version 2. Explicit WORK `U` upgrades a valid version-1
layout without moving/deleting saved programs. `P n` changes the split, `V`
repairs an interrupted primary layout, and `F` initializes/clears management
references. Upgrade/resize/repair require YES; format requires FORMAT SRAM.
Invalid retained contents never trigger implicit formatting. Detailed commands,
the 32-byte application ABI and exact layouts are in
[WORKSPACE_API.md](../tools/v2-spi/WORKSPACE_API.md).

## Layout safety

The secondary layout is written and verified while the old primary remains
authoritative. Verified invalidation of the primary publishes the new boundary
through the secondary; the primary is then rewritten and committed. A cut
before that invalidation leaves the old split; a cut afterward exposes only
the verified new split to WORK. SRAM 1.1 refuses an invalid primary until repair,
preventing a saved-program write into the wrong region.

The existing directory stays at `$00040-$0023F`. New metadata uses previously
reserved management bytes: secondary layout `$00240-$0027F`, two session
packets `$00280-$002FF`, four claim records `$00300-$0037F`. Version/CRC and
commit-last markers protect each packet; an old marker is invalidated and
verified before reusing a slot. Stale-epoch claims are inactive. Committed bad
headers, overlapping claims and ambiguous session revisions fail closed.

The prerelease FORMAT fix invalidates and verifies all four claim markers
before publishing a fresh layout, including corrupt committed packets when an
existing session is valid. Previously that path advanced the epoch but could
leave corrupt old claim packets that later validation still refused. Explicit
FORMAT now permits recovery while leaving payload/workspace bytes intact. It
advances a valid retained epoch rather than resetting its counter history; an
invalid session establishes a fresh context. Clients must discard all old
handles after formatting. Invalid contents still never trigger automatic
formatting.

Use the paired utilities. Old SRAM 1.0 does not implement v2 ownership; its
administrative code is not a valid v2 client. SRAM 1.1 blocks legacy format
over a committed v2 layout and delegates administration to WORK. Direct memory
access can bypass cooperative ownership; crypto/security enforcement remains
outside this work.

## Footprint and cache example

| Component | Measured size / RAM |
| --- | --- |
| WORK image | 4,602 bytes at `$4000-$51F9` |
| WORK code/constant tables | 4,060 bytes |
| WORK private buffers/state | 542 bytes, within that application image |
| SRAM 1.1 main code | 3,044 bytes at `$6C00-$77E3` |
| SRAM layout adapter | 240 bytes at `$6800-$68EF` |
| SRAM tables/state | 241 bytes at `$6700-$67F0` |
| SRAM saved image / flash record | 3,648 / 3,672 bytes |
| Metadata client image | 293 bytes, including 64-byte immutable fixture |
| Client mutable cache / request / index | 16 / 32 / 1 bytes |
| Maximum modeled workspace foreground stack | 28 bytes including caller/resident service, excluding an NMI handler |
| Extra permanent service RAM / resident sectors | 0 / 0 |

WORK is ordinary application software; loading it overwrites its documented
range and programs must reserve it while calling its API. SRAM borrows the
monitor's staging/cache RAM only while active, avoiding `$6B00-$6BFF` and the
worker at `$7800`. Reload SRAM after monitor return or another staging user.
The resident reservation remains `$6500-$66FF`, and **user RAM ends at `$64FF`,
inclusive, even without EDU**. Hardware absence does not free installed code's
reservation. `$66AF` was already part of that reservation and initialized zero
in the qualified gateway template; the resident executable bytes did not change.

The client stores eight 8-byte rows in a 64-byte workspace claim while caching
only two rows in 16 bytes of board RAM. It writes/verifies four cache lines,
reads/checks them and releases the claim. It prints `W: 00` and returns through
HOLD. It does not format or resize storage and does not implement an assembler.

With the actual SPI model, a 16-byte read takes 627,759 modeled CPU cycles,
38 SPI frames and 971 clocked bytes; a verified write takes 641,975 cycles,
40 frames and 993 bytes. Each call revalidates layout, session, claims and
program headers, so metadata dominates these small requests. At illustrative
8 MHz, these are about 78/80 ms; they are not measured board timings. The
example's full run, including claim/release and HOLD, takes 12,244,252 modeled
cycles and 10,040 clocked bytes. Later caching may reduce this cost after
hardware qualification. The first implementation favors small shared loops
and explicit validation over a persistent CPU metadata cache.

## Qualification and delivery state

The assembled-code ABI model passes owner/ticket/epoch checks, release/reuse,
four-slot and byte-capacity exhaustion, exact tail access through `$1FFDF`,
protected CPU buffers, request overlap, sealed overlapping claims, live-claim
resize conflicts, program-extent shrink refusal, legacy upgrade preservation,
SRAM 1.1 capacity enforcement, actual RESET invalidation and HOLD preservation.
Every one of 133 resize-write and 100 claim/session-write cut points passes.
Interrupted layouts recover through explicit primary repair and leave program
payload/workspace bytes intact. No old handle is published without its ticket.

The Phase 6 prerelease focused checks also pass all 213 existing-session FORMAT
write cuts and all 205 UPGRADE write cuts. Explicit FORMAT retry clears every
claim and program reference, including corrupt committed claims, and preserves
all payload/workspace bytes. Upgrade retry or primary repair preserves named
images. Epoch, session revision, ticket and layout revision exhaustion each
refuse wrap without changing retained bytes. These additions are model checks,
not physical-board results.

The real resident SPI model passes claim, verified WRITE, READ, release, all
four caller banks, the runnable cache client and canceled console changes.
Flash, RTC registers and EEPROM remain byte-identical, locks are released and
public write denial is restored. Optional missing hardware/software fails
boundedly. The complete named-storage suite passes against SRAM 1.1, including
its bootstrap and normal saved `R SRAM` launch.

The resident image is unchanged from Phase 4, so its passed RTC/CLOCK/SPI
regressions and three exact-source offline installation rehearsals remain bound
to identical artifact hashes. Phase 5 adds utility/client qualification rather
than another firmware deployment. Utilities are not provisioned in any board's
flash; layout upgrade/initialization has occurred only in models.

Build and qualification entry points:

```text
python tools/build_v2_sram_store.py
python tools/build_v2_workspace.py
python tools/build_v2_workspace_example.py
python tools/test_v2_sram_store.py
python tools/test_v2_workspace.py
python tools/test_v2_workspace_guards.py
python tools/test_v2_workspace_format.py
python tools/test_v2_workspace_integration.py
python tools/audit_v2_sram_store.py
python tools/audit_v2_workspace.py
python tools/check_no_board_backups.py --history
```

Ignored reports under `BUILD/v2-spi-resident/workspace` bind source/image hashes,
paired utility tests, interruption cases, client and transfer measurements to
the qualified resident artifacts. Raw backups remain untracked. **Phase 6
physical qualification and installation is next**; native calls, crypto,
assembler integration, automatic compaction and session recovery remain deferred.
