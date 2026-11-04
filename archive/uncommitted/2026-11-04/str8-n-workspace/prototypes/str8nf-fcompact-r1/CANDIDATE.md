# F compaction r1: b15c1 / PR05

Status: built once; static checks only; not execution-qualified, installed or
published. Source base: STR8N-F v0.2.0, source commit
`06a58a29c318b0a8093c267eaf30cc3d80c7d626`.

## What changed

Removed 88 bytes of legacy FF/NOP patch filler after the fixed F facade. Two
old receiver patch reservations contributed 14 and 7 bytes; the remaining
holes/NOP runs contributed 67 bytes. No instructions in the raw receiver,
timed drain loops or worker/vector implementations were changed. The XCE/NOP
CPU-detection pairs are retained. All holes now join the tail after BOOT_END.
Reserved F03C-F03F and FFE0-FFFF remain fixed.

The public F tables, service stubs, RAM descriptor and calls, interrupt pointer
slots and hardware vectors retain their addresses. The worker remains
7800-7BE7 (1000 bytes), and the vectors remain 7E20-7EE3 (196 bytes); both are
byte-identical to the release. The ROM copy locations of those blobs move.

Private callers are relinked against regenerated boot symbols. The system
builder derives F CRC and SHA identity data from its actual F output and uses
the generated V2W_SELECT address in the monitor header. The legacy monitor CRC
aliases now refer to generated symbols. The stale F038 promote-entry comment
is corrected to the actual F039 entry.

## Matching components

CONFIG, OPAQUE and READBACK bind moved private F routines. Both BASE and VX1
monitor pairs carry PR05 and rebuilt private references. FLASH 8000/9000 ROM
images and RAM bodies carry the new F CRC. MAINT, EDU client, ES1 and VX1 bind
the new F CRC; VX1 also carries the new F SHA/release identity. Worker/vector
guard tables and the ES1 header layout are unchanged. DEMO and the VERSION RAM
client use public interfaces and retain their release bytes.

The same 8000000F generation and SNBT boot-record layout are retained. No boot
settings, C/D records, wear history, bank allocation or user data are changed
by building this candidate. No new program/WORK SRAM use is introduced. The
message journal, menus and additional ABI proposals remain separate work.

## Installation boundary

Do not mix this F with PR04 monitors or private-ABI RAM utilities. Raw L has no
image-version admission step, so it cannot protect against sending an old
CONFIG/OPAQUE/READBACK BIN. Existing FLASH/MAINT/EDU components with exact-image
guards refuse a changed F. A private-ABI opaque application also needs its own
compatibility review; a public-ABI-only image does not need relinking here.

For a later authorized board trial, use fresh flash/boot-settings/owner-RAM
backups, matching PR05 monitor sectors and utilities, and refresh any installed
FLASH example or provider that binds the old F. Preserve opaque user images,
C/D settings/history, SPI program/WORK contents and restore borrowed owner RAM.
Test reset/default/monitor admission, recovery and SEND BIN Ctrl-C followed by
a normal load, CONFIG display, and FLASH Q back to MON where applicable.
Board 2205 remains a read-only reference and is excluded from installation.

Those hardware checks have not been performed for this checkpoint. No device
installer is provided or invoked. Existing v0.2.0 release assets remain the
rollback source; this candidate is not an upgrade through ordinary OPAQUE,
which deliberately protects F and monitor sectors.
