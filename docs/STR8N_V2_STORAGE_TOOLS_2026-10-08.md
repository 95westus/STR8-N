# Beta17 storage tools

This build combines the approved beta16 boot display with WORK 1.2,
SRAM 1.2, MAINT 1.8 and EDU 1.2. Files are generated under `BUILD/v2-storage`.
Beta17, WORK 1.2, SRAM 1.2, MAINT 1.8 and EDU 1.2 are installed on all three
boards; CLOCK remains 1.5. [Installation results and the 2609 SPI startup
limitation](STR8N_V2_STORAGE_HARDWARE_2026-10-08.md). Builders/model tests do not
open COM ports. No commit or push accompanies the installation.

## RAM and WORK

### SPI playground map candidate (2026-10-09; unflashed)

`python tools/build_v2_spi_map.py` builds a separate MAINT 1.9 candidate under
`BUILD/v2-spi-map`, using the beta22 firmware/service addresses. The monitor's
`M`, `M1`, `M2`, `M3` and MAINT's map commands share this display. It labels
the external 128 KiB SRAM separately from CPU RAM and flash, and reports the
saved program payload and SPI playground (WORK workspace) address ranges.
It distinguishes EDU OFF, absent/incompatible services, failed hardware reads,
uninitialized allocation, invalid metadata and layouts requiring repair.
OFF also displays the reclaimed CPU program RAM through $66FF.
MAINT 1.9 occupies $2000-$4A40 (10,817 bytes), fitting the existing three-sector
B1:8000-AFFF storage extent. Loading MAINT owns this larger RAM range.

The map reuses the boot formatter's layout validation and exact READ completion
checks. It reads metadata only, preserves its temporary user-RAM window and
does not PROBE, initialize, format, repair, claim workspace or acknowledge VIA
flags. Invalid/uninitialized layouts do not advertise a playground allocation.
`python tools/test_v2_spi_map.py` exercises the linked candidate. This candidate
has not been installed on a board.

WORK is linked at **$5000–$648A**, with its API at **$5003** and signature
`WK`,1,2 at $5006. It remains 5,259 bytes: relocation adds no library bytes.
The console and request layout are unchanged from WORK 1.1.

Programs can begin at **$0200**. While WORK is loaded, the contiguous lower
application range is **$0200–$4FFF (19,968 bytes)**. WORK owns its code,
buffers and state at $5000–$648A; callers must reserve that range. Load the
library before starting the application, validate its signature, and call
$5003 using the existing 32-byte request ABI. The rebuilt cache example and
hardware client use this address. A separately packaged linkable library
remains deferred.

The monitor's RAM line still describes the active application RAM ceiling,
independent of which utility is loaded. EDU ON reserves $6500–$66FF, giving
$0200–$64FF. Explicit saved EDU OFF activates only at RESET and releases that
reservation, giving $0200–$66FF. Merely lacking an EDU board does not release
RAM while the optional software is enabled. Without the optional service
software, application RAM can also extend through $66FF.

## Preserving R SRAM

`R SRAM` and `R 2 SRAM` use a sealed loader. It checks the fixed B2:A000 SRAM
record and the CRC of its complete transport image before copying its pieces
directly into monitor staging RAM. It never stages the image at $4000.
The full enabled-service application range, $0200–$64FF, remains intact on
entry and exit. WORK's own loaded range still belongs to that library when
WORK is in use.

The manager's core is $6C00–$77E1, its private data is $6700–$67F6, and its
layout helper is $6800–$68EF. Streaming hooks occupy $7B90–$7BC6, beyond the
worker ending at $7B80. Directory/buffers reuse $6900–$6AFF. A short loader
finalizer temporarily borrows journal scratch at $6B00; it makes no bus calls.
There is no additional permanent application RAM reservation.

The manager preserves the CPU transfer window at $6400–$643F except when an
explicit restore intentionally targets those bytes. Saving reads the named
application range; restoring/running deliberately replaces its saved range.
Normal monitor return, status display and flash operations can overwrite
staging code. Reload the manager for another session.

Load-only syntax such as `R SRAM L` is refused. The preserving path is the
named command for the fixed B2 record. Loading a transport S19, using an
explicit numeric record address, or deliberately executing its $4000 bootstrap
is an ordinary RAM load and can overwrite $4000–$4EE1; it does not gain the
named command's preservation contract.

Missing EDU services or a corrupt/missing manager fail before execution.
The loader never formats retained SRAM or changes RTC time, trim or EEPROM.

## Automatic flash placement

```text
B3> S 2 AUTO 0200 021F TINY
SAVE B02:8000
Done.
```

This is model output from an erased test bank. Real placement depends on the
bank's contents. Addresses and bank numbers retain hexadecimal monitor
notation. The chosen header address is printed before the standard SAVE
operation writes. This command uses SAVE's existing immediate-write behavior.

AUTO finds the first erased contiguous extent large enough for the 24-byte
header and inclusive RAM payload. It scans $8000–$DFFF in the selected bank,
skips full valid or pending SR record extents (including FF-filled payloads),
excludes the raw B2:C800–CFFF status/storage asset, refuses B3, and refuses a
bank with a valid-looking boot vector. It never erases occupied space.
The original SAVE range checks, erased-space preflight, verified sector writes
and final commit marker remain in force. An explicit address is still accepted
by the original SAVE path.

## MAINT program copies

MAINT remains a **flash-only** utility. Its existing raw bank, sector and RAM
commands remain available. The additional `X` command copies named R programs
directly between flash and SPI SRAM:

```text
BM> X 2 ORIGIN S COPIED
Copy program; source retained. Y to confirm: Y
Copied and verified; source retained.

BM> X S COPIED 2 RETURNED
Destination B02:8000
Copy program; source retained. Y to confirm: Y
Copied and verified; source retained.
```

`0`–`2` select a flash bank; `S` selects SPI SRAM. Names use the SRAM rule:
1–16 uppercase letters, digits, underscores or hyphens. Confirmation must be
a single Y; Enter, N, Escape or Ctrl-C cancels. The source remains available
after success. Delete it separately only when the copy is satisfactory; the
transfer never erases the original automatically.

Flash-to-SRAM preserves the original load address, uses that address as entry,
and allows a new name. Ambiguous duplicate flash labels refuse. Pending flash
records do not count as sources and their payloads are skipped while searching.
SRAM's manager calculates/verifies payload CRC and publishes its committed
directory entry last. The application is not restored over MAINT as an
intermediate step.

SRAM-to-flash verifies the source metadata and payload, finds/displays an AUTO
destination, asks for confirmation, reloads the manager, and rechecks the
source's load/length/entry/sequence before writing. Fresh flash bytes are
programmed and read back individually, without sector erases or a sector-sized
staging buffer. The pending SR header is committed only after the complete
restore CRC succeeds. A failed destination may remain pending; it is never
reported as a successful copy.

SR v1 runs at its load address and has no independent entry field. Therefore
SRAM images with entry 0000 or an entry different from their load address
refuse this direction instead of losing that information. B3 destinations
and transfers of MAINT to SRAM are refused. UTC, trim, EEPROM, saved outage
events, the SPI workspace region and its live handles are not transfer targets.
The streaming hooks are a private, version-paired interface; application authors
continue to use the documented WORK and SRAM request ABIs.

## Installed footprint

| Item | CPU placement / bytes | Flash placement |
| --- | --- | --- |
| WORK 1.2 | $5000–$648A; 5,259 bytes | B2:B000–C4A2, ordinary record |
| SRAM 1.2 transport | $4000 bootstrap transport; 3,810 bytes | B2:A000–AEF9, ordinary record |
| MAINT 1.8 | $2000–$44E3; 9,444 bytes | B1:8000–AFFF, three sectors |
| EDU 1.2 | $2000–$2266; 615 bytes | B2:C580–C7FE, ordinary record |
| Shared status/storage asset | $7000–$77FF temporarily; 2,048 sealed bytes | B2:C800–CFFF, existing sector C |

MAINT has grown by 1,747 bytes and now needs three sectors rather than two.
The shared asset stays within existing B2 sector C. Recovery F remains
byte-identical, both monitor slots fit their existing limits, and service RAM
remains the existing 512-byte ON reservation. The private executive signature
is `ED`,1,3; MAINT refuses a mismatched executive before calling it. The sealed
asset signature is `BS`,1,2. EDU 1.2 is built for this pairing.

The authorized installer used fresh, independently matching four-bank backups,
verified every preimage, retained other records/EUI slots, moved EDU from C600
and preserved SDEMO at AF80 because the longer SRAM record overlaps AE80.
DEMO/DEMO2 were omitted as requested. Four utility headers were committed only
after their complete images verified. Both monitors were replaced with A last;
recovery F was retained. No board-specific backup bytes belong in Git.

## Local reproduction and limits

```text
python tools/build_v2_storage.py
python tools/qualify_v2_edu_models.py --suite storage --build BUILD/v2-storage --clock BUILD/v2-storage/clock
python tools/qualify_v2_edu_models.py --suite workspace --build BUILD/v2-storage --clock BUILD/v2-storage/clock
python tools/qualify_v2_edu_models.py --suite core --build BUILD/v2-storage --clock BUILD/v2-storage/clock
python tools/qualify_v2_edu_models.py --suite remaining --build BUILD/v2-storage --clock BUILD/v2-storage/clock
python tools/audit_v2_storage.py
```

The models execute the linked W65C02S code and real resident SPI interface;
fault-heavy cases also use the existing ABI-level transfer model. They verify
lower-RAM preservation, flash allocation exclusions, round-trip copies,
cancellation, missing/ambiguous/pending sources, short writes, flash timeout,
commit-last publication and buffer/hook cleanup. Existing WORK interrupted-write,
SPI, RTC, EUI, journal, TIME and CLOCK models are rerun against the candidate.
Model coverage remains separate from the subsequent physical installation and
smoke checks linked above. Hardware transfer-fault/power-loss injection was not
performed. Generated artifacts, transcripts and receipts remain ignored.
