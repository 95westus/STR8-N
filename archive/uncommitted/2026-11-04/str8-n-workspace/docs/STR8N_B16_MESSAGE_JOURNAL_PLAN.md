# b16 message and metadata journal direction

Owner direction recorded October 28, 2026. Design checkpoint only: no journal
writer, format migration, partition allocation, firmware renumbering or flashing
is implemented by this document.

## Accepted storage boundary

Use optional EDU SPI SRAM, allocating journal space exclusively from the WORK
area. Keep the formatted program region, saved-program directory and every
saved payload byte unchanged. Keep the flash C/D SNBT boot/configuration/wear
journal separate. Do not allocate a flash message pool or silently fall back to
flash when EDU/SPI SRAM is absent, disabled, busy or unusable.

Program-store headers and allocation formatting are included in that preservation
boundary. Do not use FORMAT or a program-layout upgrade as a shortcut. Keep new
journal reservation/discovery metadata inside WORK itself, and teach the paired
WORK allocator to exclude it without reformatting program storage. Older WORK
writers that do not recognize the reservation must not be admitted to that pool.

Inventory each board before assigning addresses: CPU/firmware, active and saved
monitor, component availability, retained WDCMONv2 backup, external SRAM layout,
program/work boundaries and existing WORK claims. Capacity is not proof that a
range is free. Preserve existing WORK contents/claims before any allocation
change. Do not probe, format or repartition automatically during discovery.

An ordinary WORK claim is insufficient because its session handle expires on
RESET. The journal needs a persistent reservation excluded from subsequent WORK
claims and resizing, and an explicit administrative policy for formatting.
Preserve the existing reserved management and probe ranges. A future compatible
allocator/layout change must describe and protect that reservation.

A 16 KiB reservation is the current sizing proposal, not an assignment. For the
2205 layout shown by the owner (30,720 program payload bytes and 98,272 WORK
bytes), that would leave 81,888 general WORK bytes. The program allocation is
unchanged. Start/end addresses depend on the admitted retained layout and claims.
The existing final 32-byte probe area also remains excluded. A possible 16 KiB
WORK-only extent is external SRAM $1BFE0-$1FFDF, leaving $1FFE0-$1FFFF alone;
this is not proof that those bytes or claims are free on a particular board.

Retain append-only records for messages and metadata. Replacement, deletion,
acknowledgement and reply append related records instead of overwriting history.
Use bounded lengths, stable IDs, sequences, format/type, CRC and a final commit
marker. Scan only fully committed valid records after RESET. Reclamation must
retain current metadata and unresolved requests; no automatic destruction of
unknown retained bytes. Storage-full behavior remains to be specified.

SRAM can retain records across board RESET while powered. Retention after power
removal depends on the fitted backup supply and its condition; the current b15
ES1 evidence does not qualify battery retention. Report this distinction.

## Messages and normal console output

Keep the existing human-readable startup/status messages. Examples include
EDU ON/OFF, application RAM range, SSRAM PROGRAM/WORK capacity, provider/storage
availability, boot/monitor choice and failures. These become typed journal
messages with their displayed wording, rather than disappearing from the console.

Distinguish a boot/session observation from an actual state change. Record a
startup observation once for that boot/session; record a later change when it
occurs. Reprinting a status screen or scanning the journal does not append a
duplicate or initialize storage. Early startup text may need a bounded RAM queue
until a valid journal is mounted.

If EDU/SPI SRAM is unavailable, emit a plain-console message and return an
unavailable/not-saved status. Do not claim those messages survived RESET. Saved
EDU OFF continues to forbid implicit peripheral access; retaining a disable
request while storage is available is distinct from verifying the next disabled
boot. Failure of optional journaling must not prevent F recovery or MON startup.

WTO display and retained messages are the first layer. WTOR later adds correlated
request/reply IDs, timeout/cancel, stale reply rejection and operator routing.
Retained questions/history do not retain authority to resume destructive work
after RESET or automatically accept a reply.

## Inventory and future WDCMONv2 fixtures

Preserve a private WDCMONv2 backup for each board, identifying live bank captures
separately from historical originals and local installation candidates. Keep
CPU-specific 65C02 and 65C816 images distinct. Hash and retain locally found SPI
enhancements and their sources; locating them does not establish compatibility.

The owner intends to use WDCMONv2 with SPI enhancements for future cases. This
does not authorize flashing or booting those fixtures during the current
inventory. Review their initialization behavior before a later preserving
installation; SPI demos/tests are not implicitly safe for existing WORK/program
contents. Vendor binaries, source archives, owner SRAM and raw backups stay
outside the public STR8N-F package and Git.

## Working method

Checkpoint as work progresses. Do not run routine simulations/offline group
checks or second builds. Use a targeted check only when a concrete change or
unresolved issue requires it. The current task is inventory/backups and this
design record, not the implementation or installation of b16.
