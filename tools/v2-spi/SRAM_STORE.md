# Named SPI SRAM storage candidate

Current checkpoint: SRAM 1.2 and the preserving named `R SRAM` path are installed
and qualified with frozen beta23 on all four boards. The $6C03 development entry
is private/version-paired, not a public resident ABI. Earlier candidate and
SRAM 1.1 descriptions below retain their historical context. See the
[beta23 technical guide](../../docs/STR8N_V2_BETA23_TECHNICAL_GUIDE.md).

The [installed beta17 build](../../docs/STR8N_V2_STORAGE_TOOLS_2026-10-08.md)
uses SRAM 1.2 and a preserving **named `R SRAM` loader**, copying the sealed
fixed B2:A000 image directly into monitor staging. It preserves $0200–$64FF;
ordinary S19/numeric-address loads and `G 4000` still overwrite the transport
range. `R SRAM L` is refused. The application request ABI and console commands
below are unchanged. MAINT 1.8 adds verified flash/SRAM copies and AUTO flash
placement. All three boards now have SRAM 1.2; the older transport details
below describe SRAM 1.1.

SRAM 1.1 is a standalone W65C02S utility, previously installed with beta15
on the three qualified boards. The same
instructions are usable in 816 emulation with DBR/PBR zero. Native mode and
interrupt callers remain deferred.

Build with `python tools/build_v2_sram_store.py`. Load the generated
`BUILD/v2-spi-resident/store/sram.s19`, then `G 4000`. Loading the utility
overwrites `$4000-$4E3F`, just as loading another RAM program would. Preserve
any existing program in that range first. The bootstrap moves the manager out
of user RAM before displaying `SRAM>`.

It can subsequently be saved as an ordinary flash record named `SRAM`, using
the existing monitor `S` command and a deliberately chosen free flash extent.
Then `R SRAM` opens the utility. Provisioning that record is a later deployment
step; this phase assigns no new resident service sector and writes no boards.
Each saved utility record consumes 3,672 bytes, including the existing 24-byte
flash record header. Default monitor `R`, `S` and `T` continue to use flash.

## Console

All commands at **`SRAM>` select SPI SRAM explicitly**. Identical names in
flash do not provide a fallback when SRAM is missing, corrupt or full.

| Command | Meaning |
| --- | --- |
| `T` | List latest live names, original load address and length; show free payload bytes in hex |
| `S name start end entry` | Save the inclusive CPU RAM range, with its original load address and entry |
| `R name` | Validate and restore only |
| `G name` | Validate, restore, then jump to its saved entry |
| `D name` | Publish a deletion tombstone; old versions cannot reappear |
| `C` | Reclaim superseded versions and completed deletion tombstones; never move a live image |
| `F` | Initialize/clear legacy v1 directory with exact `FORMAT SRAM`; v2 administration uses WORK |
| `?` | Repeat help |
| `Q` | Return to the monitor |

Addresses are four hexadecimal digits, without `$`. Names are 1-16 uppercase
letters, digits, `_` or `-`; console input converts lowercase to uppercase.
Entry `0000` marks an image for restore only. Any other entry must be inside
the saved image. For example:

```text
SRAM> S DEMO 2000 205F 2000
SRAM: 00
SRAM> T
DEMO 2000 0060
Free bytes: $F700
SRAM> R DEMO
SRAM: 00
SRAM> G DEMO
```

`F` removes directory references, not the payload bytes or workspace. Neither
boot nor a failed mount formats storage. Initialization is not secure erasure.
`D` and replacement require a free metadata slot. `C` is explicit, and may
release space committed by earlier versions. There is no automatic compaction.

Eight directory slots count **versions and tombstones**, not just distinct
visible names. A replacement needs a free slot among those eight and is
refused when all are occupied until explicit reclaim frees a slot. Replacement also
needs a fresh contiguous extent; the old image remains allocated until `C`.
The free-byte display counts all unused pages, so fragmentation can still
prevent a sufficiently large contiguous save. Capacity is checked separately
from metadata-slot availability.

## Region and record layout

| SPI address | Bytes | Ownership |
| --- | ---: | --- |
| `$00000-$0003F` | 64 | Versioned layout header |
| `$00040-$0023F` | 512 | Eight 64-byte directory records |
| `$00240-$007FF` | 1,472 | Reserved management space |
| `$00800-$0FFFF` | 63,488 | Program payload, allocated in 256-byte contiguous pages |
| `$10000-$1FFDF` | 65,504 | Default workspace; [WORK](WORKSPACE_API.md) provides allocation |
| `$1FFE0-$1FFFF` | 32 | Resident probe reservation |

The initial gross program region is 65,536 bytes. Its layout header starts
`53 53 01 08 08 00 01 00` (`SS`, version 1, eight slots, first payload page 8,
program boundary `$010000`); remaining bytes through 59 are zero. Bytes 60/61
seal bytes 0-59 using CRC-16/CCITT, initial `$FFFF`, polynomial `$1021`, high
byte first. CRC over bytes 0-61 is zero. Byte 62 is reserved; byte 63 is `$A5`
only after verified publication. The current reader accepts exactly this split.
SRAM 1.1 also accepts the primary v2 layout with a 16/32/48/64 KiB program
region. [WORK](WORKSPACE_API.md) performs explicit upgrade, resize, repair and
format administration. Its secondary header, session packets and claim records
occupy reserved management bytes without moving the eight program records.
SRAM refuses an invalid primary until WORK repairs it, and refuses its legacy
`F` command over a committed v2 layout. Use the paired utilities.

Each directory record uses the same metadata seal and final marker:

| Offset | Bytes | Meaning |
| --- | ---: | --- |
| 0 | 2 | `SP` |
| 2 | 1 | Format version 1 |
| 3 | 1 | Reserved zero |
| 4 | 2 | Original CPU load address, little endian |
| 6 | 2 | Payload length, little endian; zero for deletion |
| 8 | 2 | Entry address, little endian; zero disables run |
| 10 | 2 | Sequence, little endian, nonzero |
| 12 | 2 | Payload CRC-16/CCITT, little endian |
| 14 | 1 | First 256-byte payload page; zero for deletion |
| 15 | 1 | 1 live image, 2 deletion tombstone |
| 16 | 16 | Name, zero padded |
| 32 | 28 | Reserved zero |
| 60 | 2 | Metadata seal, high byte first |
| 62 | 1 | Reserved zero |
| 63 | 1 | `$A5` committed; other values unpublished/free |

Mount rereads layout and every record each time. A committed bad header,
invalid range, overlapping allocation or ambiguous highest sequence is refused.
Latest committed sequence wins for a name. Sequence exhaustion refuses further
publication; automatic wraparound is unsupported. This is a storage ordering
field, not a persistent event identifier.

Save allocates a fresh extent and free record, computes the source CRC, writes
the payload and verifies its complete CRC, then writes/verifies the metadata.
It publishes the single final marker last and verifies that marker. It does
not invalidate the old version. A cut after verified commit can leave both
versions; lookup selects the new one. A failed final-marker read can leave a
valid new version whose publication was not confirmed to the caller. Recheck
the directory rather than assume the save had no effect.

Reclaim verifies the selected newer live payload before clearing superseded
records. Deletion uses a committed higher-sequence tombstone first; reclaim
clears all older references before removing that tombstone. It preserves other
names and payload bytes. No data relocation is performed.

Restore checks the entire SPI payload CRC and current destination range before
copying. It checks completed counts and computes another CRC while copying.
A failure after copying starts reports partial completion and **never executes
the saved entry**. CPU RAM may then contain a partial image; rollback is not
promised. No program executes directly from SPI SRAM.

## Ownership and results

With EDU mode ON, resident software reserves `$6500-$66FF`, so application RAM
ends at **`$64FF`, inclusive, even without EDU**. Hardware absence alone does
not release the reservation. Beta15's explicit saved EDU OFF mode disables
these services at RESET and returns RAM through `$66FF` to programs; SRAM
commands then report unavailable software without touching that RAM. See
[EDU mode](../../docs/STR8N_V2_EDU_MODE_2026-10-08.md).

The utility borrows the current monitor's sector-staging area: tables/state at
`$6700-$6AFF`, code at `$6C00-$77FF`. It preserves the journal/SPI scratch at
`$6B00-$6BFF` and the monitor worker at `$7800-$7B80`. `$6400-$643F` is a
temporary 64-byte service transfer window: original bytes are preserved through
save and pre-copy checks, including when they lie inside a saved image. Restore
copies directly to the destination after validation. Zero page `$D0-$D7` is
clobbered. Foreground stack, IRQ-disabled and decimal-clear calling rules apply.

The staging area is a temporary foreground lease, not additional public user
RAM. Do not invoke other storage/maintenance operations while the manager is
active. Reload `R SRAM` after returning to the monitor, RESET or any operation
that could reuse staging. Its development entry at `$6C03` is not a resident
or frozen API. A restore API caller must execute outside its destination.

Public SRAM WRITE is blocked from boot, including after RESET; READ and PROBE
remain available. The privileged manager temporarily enables writes for its
bounded foreground transaction, then restores protection on every return. This
cooperative convention is not isolation against a program with direct RAM
access. IRQ/NMI service callers and concurrent managers are unsupported.

| Hex result | Meaning |
| --- | --- |
| `00` | Completed |
| `40` | Unformatted/interrupted layout; explicit `F` required to initialize |
| `41` | Committed metadata/layout invalid or ambiguous |
| `42` | Name absent/deleted |
| `43` | Directory full, or no contiguous payload extent |
| `44` | Invalid command, range, entry, name or confirmation |
| `45` | CRC/readback verification failed before restore copy |
| `46` | Restore copy incomplete/unverified; entry was not executed |
| `47` | Saved image has no run entry |
| `48` | Sequence exhausted |
| `49` | Use WORK administration for the v2 layout |
| Other | Resident SRAM status; see [SPI API](SPI_API.md) |

The development request at `$6C03` is a copied 32-byte block addressed by A/X:
operation 0 query, 1 save, 2 restore, 3 run, 4 delete, 5 reclaim, 6 format;
byte 1 zero; start/end/entry LE16 at 2/4/6; name at 8-23; format key `FORMAT!!`
at 24-31. A=status, carry set only for success; registers and private staging
are clobbered. Query refreshes the internal directory/used-page state. A run
success jumps to the entry instead of returning to the caller.

SRAM retention depends on supplies and contents passing validation. These
checks establish neither remaining battery life nor authenticity. Losing both
supplies can lose every saved SPI image; flash storage remains available.
