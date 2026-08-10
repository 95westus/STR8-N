# STR8-N v1.1 Technical Guide

This document is the current STR8-N integration and image-format contract.
Numeric address ranges are inclusive unless an end is explicitly called
"exclusive."

## Scope and command ownership

STR8-N is a reset supervisor, flash installer, recovery RAM loader, and bank
handoff guard. `I` remains flash-only. The separate `L` command is a compact
load-and-execute path, not a general monitor loader.

```text
Operation                 Owner              Result
flash S19 installation    STR8-N I           erases/programs selected flash
recovery RAM execution    STR8-N L           copies $2000-$7AFF, jumps to S9
S19 syntax validation     STR8-N $F009       parses one record; does not apply it
monitor RAM loading       HIMON L / L G      load-only or load-and-start
bank selection            STR8-N $F010       changes the visible flash bank
guest launch              STR8-N J0-J3       jumps through selected RESET vector
```

The STR8-N form stays small by omitting load-only, fallback-entry, reporting,
and arbitrary destination policy.

## Board address contract

The CPU sees 31.75 KiB of RAM, a 256-byte I/O page, and one selected 32K flash
bank:

```text
$0000-$7EFF  RAM                         32,512 bytes
$7F00-$7FFF  memory-mapped I/O              256 bytes
$8000-$FFFF  selected flash window       32,768 bytes
```

The SST39SF010A contains four physical 32K banks:

```text
Bank 0  physical $00000-$07FFF  -> CPU $8000-$FFFF
Bank 1  physical $08000-$0FFFF  -> CPU $8000-$FFFF
Bank 2  physical $10000-$17FFF  -> CPU $8000-$FFFF
Bank 3  physical $18000-$1FFFF  -> CPU $8000-$FFFF
```

Physical RESET forces Bank 3. Its physical top sector
`$1F000-$1FFFF` appears at CPU `$F000-$FFFF` and contains all persistent
STR8-N code and data.

## Protected 4K top-sector budget

The complete protected sector is exactly 4096 bytes:

```text
$F000-$FD53  resident supervisor, installer, loader   3412 bytes
$FD54-$FD5B  enforced unused margin                     8 bytes
$FD5C-$FFAF  stored unified worker                    596 bytes
$FFB0-$FFEF  four 16-byte bank-directory records       64 bytes
$FFF0-$FFF9  configuration pocket                      10 bytes
$FFFA-$FFFF  NMI, RESET, IRQ/BRK vectors                 6 bytes
                                                       ----------
                                                       4096 bytes
```

The 8-byte gap is the only build-certified growth room inside the protected
sector. The layout checker requires at least 8 bytes. `$FF` bytes found
inside linked code are not automatically free space.

The stored worker is copied to `$0200-$0453` before an install or bank handoff.
Each copied byte is immediately read back and compared before the next byte.
No worker bytes are transported in an `I` or `L` S19.

Hardware vectors are:

```text
$FFFA-$FFFB  NMI      -> $F09C
$FFFC-$FFFD  RESET    -> $F000
$FFFE-$FFFF  IRQ/BRK  -> $F0B0
```

NMI and IRQ/BRK enter STR8-N IVI stubs and dispatch through RAM vectors after
normal initialization. NMI must not be pressed during flash mutation: while a
different bank is selected or flash is busy, a hardware interrupt cannot be
made safe by a small top-sector stub.

## S19 install-file contract

The operator's `B0-3` and `RANGE` answers define the exact destination extent.
The S19 must describe that entire extent as one dense byte stream.

### Record grammar

An accepted install stream contains, in order:

1. Zero or one S0 metadata record.
2. One or more nonempty, strictly ascending S1 data records.
3. Exactly one S9 termination record, with nothing except normal line ending
   characters after it.

S2-S8 are not accepted. Every record needs a valid byte count and checksum.
S1 data records may contain 1 through 252 bytes; the supplied converter uses
32 bytes per record by default.

```text
S1 cc aaaa dd... ss
   |  |    |     +-- ones-complement checksum
   |  |    +-------- data bytes
   |  +------------- 16-bit destination address, high byte first in text
   +---------------- count of address + data + checksum bytes

S9 03 aaaa ss
```

For every record, the low eight bits of the sum of `count`, address bytes,
data bytes, and checksum must equal `$FF`.

The first S1 address must equal the selected start. Each following S1 address
must equal the address immediately after the preceding data. The final data
byte must equal selected end-exclusive minus one. Gaps, overlaps, duplicate
addresses, backward records, empty S1 records, or omitted `$FF` padding fail.

### Bank 0-2 extent and S9

- Start and exclusive end must be 4K boundaries.
- Size may be 4K, 8K, 12K, 16K, 20K, 24K, 28K, or 32K.
- The extent must remain inside `$8000-$10000`.
- A full `$8000-$FFFF` image must contain a non-erased RESET vector at
  `$FFFC-$FFFD`, low byte first. S9 must equal that vector.
- A partial image uses S9 `$FFFF` or an address inside the selected extent.

The upper-aligned ranges that include the vector sector are:

```text
size  selected range  data extent
 4K   F               $F000-$FFFF
 8K   E-F             $E000-$FFFF
12K   D-F             $D000-$FFFF
16K   C-F             $C000-$FFFF
20K   B-F             $B000-$FFFF
24K   A-F             $A000-$FFFF
28K   9-F             $9000-$FFFF
32K   8-F             $8000-$FFFF
```

Upper alignment is not an install requirement. Any contiguous sector span
inside `8-F` is valid. Including F merely ensures that the S19 supplies the
hardware vectors. The RESET vector must still point to code that actually
exists in the installed bank.

Example: bytes `$34,$C2` at `$FFFC,$FFFD` form RESET address `$C234`, so a full
image must end with a correctly checksummed S9 for `$C234`.

S9 is not the `Jn` launch address. `J0`-`J2` always read the selected bank's
RESET vector. For that reason, a partial install that does not include sector
F preserves whatever vectors were already there. A completed first partial
install into an erased bank will not boot.

### Bank 3 extent and S9

- Start and exclusive end must be 4K boundaries.
- Size may be 4K through 28K in 4K steps.
- The extent must remain inside `$8000-$F000`; sector F is protected.
- The first Bank-3 install requires S9 to point inside the selected extent.
- Updating an existing immutable Bank-3 identity accepts S9 `$FFFF` or the
  exact existing directory entry.

The Bank-3 ranges ending immediately below STR8-N are `E`, `D-E`, `C-E`,
`B-E`, `A-E`, `9-E`, and `8-E`, for 4K through 28K respectively. Other
contiguous spans inside `8-E` are also legal.

The R-YORS v1.1 streams are dense, payload-only examples:

```text
ryors-v1.1-asm-himon-bank3-8-e.s19  $8000-$EFFF  28K  S9 $C000
ryors-v1.1-himon-bank3-c-e.s19      $C000-$EFFF  12K  S9 $C000
ryors-v1.1-asm-bank3-8-b.s19        $8000-$BFFF  16K  S9 $FFFF
```

The combined stream is the simplest first Bank-3 install. For separate
streams, HIMON must establish entry `$C000` before the ASM-only `$FFFF` stream.
The stored Bank-3 entry constrains future S9 records; `H` still checks the
fixed HIMON identity and enters `$C000`, while `J3` uses Bank 3's RESET vector.

### Payload-only means no worker records

Historical combined streams that start with S1 records at `$0200` are invalid.
The first S1 for `I` must be the selected flash start, normally `$8000`,
`$9000`, and so on. The worker component in
`BUILD/s19/str8n-worker-0200.s19` is build and integration evidence, not a file
to send to `I`.

## Creating and checking install files

`tools/convert_guest_bin_to_s19.ps1` converts a 4K-aligned 4K-32K binary to a
dense install stream. Byte zero maps to `-BaseAddress`. Full Bank 0-2 images
derive S9 from RESET. Partial images default to `$FFFF`; `-EntryAddress`
publishes an in-range entry. A first Bank-3 image needs an explicit in-range
entry.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/convert_guest_bin_to_s19.ps1 `
  -BinPath C:\IMAGES\guest.bin `
  -BaseAddress 32768 `
  -Bank 0 `
  -S19Path BUILD/s19/guest-bank0-8000-ffff.s19
```

For a first Bank-3 HIMON image:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/convert_guest_bin_to_s19.ps1 `
  -BinPath C:\IMAGES\himon-c000-efff.bin `
  -BaseAddress 49152 `
  -EntryAddress 49152 `
  -Bank 3 `
  -S19Path BUILD/s19/himon-bank3-c000-efff.s19
```

`tools/compose_str8n_install_s19.ps1` validates an existing payload and writes
a normalized payload-only stream. It reports the exact extent, S1 count, S9,
per-sector CRC-16, and whole-file SHA-256. For an existing Bank-3 row, pass
`-ExistingBank3Entry` so `$FFFF` or an exact match is checked correctly.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/compose_str8n_install_s19.ps1 `
  -PayloadS19Path BUILD/s19/guest-bank0-8000-ffff.s19 `
  -PayloadStart 32768 `
  -PayloadEndExclusive 65536 `
  -Bank 0 `
  -S19Path BUILD/s19/str8n-i-guest.s19
```

## Transaction timing and recovery

`I` is a streaming flash installer, not a RAM loader and not a
receive-everything-first loader:

1. It validates the bank, range, directory, and embedded worker.
2. `WRITE? Y` arms the operation.
3. The first valid S1 causes the START bit and any new identity bytes to be
   written.
4. Each complete non-final 4K sector is erased, programmed, and read back as
   the dense stream arrives.
5. The final selected sector remains in the `$0A00-$19FF` tray.
6. A valid S9 and `COMMIT? Y` allow that final sector to be programmed and
   verified.
7. The Bank-3 entry, when first needed, is written; COMPLETE is always the
   last persistent action.

Once START is present without COMPLETE, retry is limited to the whole writable
bank: `$8000-$FFFF` for Banks 0-2 or `$8000-$EFFF` for Bank 3. This prevents a
small retry from hiding unknown sectors changed before the interruption.

## STR8-N L RAM load-and-execute contract

`L` calls the same resident `$F009` parser used by `I`, but it applies valid S1
data directly to RAM and never copies or invokes the flash worker.

```text
accepted S1 destination bytes  $2000-$7AFF
exclusive upper boundary       $7B00, parser data buffer
accepted S9 execution address  $2000-$7AFF
record data length              1-252 bytes
flash mutation                  none
completion                      immediate indirect JMP through S9
```

The complete S1 span is checked by adding `length-1` to the record address. A
record beginning below `$7B00` is still rejected if its last byte would reach
`$7B00`. This prevents the destination from overwriting the record currently
being copied. `$7B00-$7BFB`, `$7E95-$7EA8`, IVI cells, I/O, zero page, stack,
worker, sector tray, and recovery state remain outside the accepted range.

The stream accepts individually valid S0, S1, and S9 records. It does not
require dense or ascending S1 addresses. At least one nonempty S1 must pass;
then S9 must be in range. On success STR8-N executes `SEI`, `CLD`, loads
`X=$FF`, sets `SP=$FF`, and jumps indirectly through the S9 address. Bank 3
remains selected. A/Y, RAM outside the received records, IVI targets, and
peripherals are inherited. No return address is prepared; the loaded program
must not use `RTS` as a return to STR8-N. The sender must stop after S9 because
queued console bytes are also inherited by the loaded program.

There is no confirmation or load-only state. On any parse, checksum, record
type, data-span, or S9 failure, control returns to the STR8-N prompt without a
jump. Already copied records are not rolled back. This is safe from flash
damage but means a failed recovery load may leave partial program bytes in
RAM; retrying or RESET is the normal cleanup.

## Directory and transaction journal

`$FFB0-$FFEF` holds one 16-byte record for each bank:

```text
+0       type byte
+1..+3  reserved; must remain $FF
+4..+8  five-character description
+9      identity seal ($FE)
+10..11 Bank-3 entry address, little endian; $FFFF for Banks 0-2
+12..15 32 one-way journal bits
```

Descriptions accept uppercase `A-Z`, digits, hyphen, underscore, and period.
Type, description, seal, and Bank-3 entry are immutable because STR8-N never
erases its own sector.

Each bank has its own 32-bit journal, arranged as 16 START/COMPLETE pairs.
Bits change only from 1 to 0. A failed install and full recovery finish the
same open pair; a successful later install consumes the next pair. A START
without COMPLETE prevents `J0`-`J2` launch. When a bank's 16 pairs are full,
an external programmer must refresh the protected sector before another
install to that bank.

The external-programmer BIN contains an all-`$FF` directory/configuration
pocket. Refreshing it erases every bank's journal and Bank-3 install identity.

## RAM ownership

The board has 32,512 RAM bytes below the I/O page. STR8-N has no persistent RAM
payload; it uses the following transient and service areas:

```text
$0090-$009C  I state                              13 bytes
$009D        free between I fields                 1 byte
$009E-$009F  I state                               2 bytes
$00A0        L nonempty-data flag                  1 byte
$00A1-$00A3  I range state                         3 bytes
$00CD-$00D6  record/directory/worker scratch      10 bytes
$0200-$0453  relocated unified worker            596 bytes
$0A00-$19FF  current 4K sector tray             4096 bytes
$1FE9-$1FFF  recovery/worker/jump state           23 bytes
$7B00-$7BFB  decoded S-record payload tray       252 bytes
$7E95-$7EA8  record request/result card           20 bytes
$7EDE-$7EDF  delay helper fixed cells              2 bytes
$7EED-$7EEF  IVI signature                         3 bytes
$7EF8-$7EFF  IVI RAM vectors                       8 bytes
$0100-$01FF  hardware stack, dynamic              256 bytes maximum
```

The main `I` transaction regions through the record card total 5015 named
bytes, plus dynamic stack use and the fixed IVI/delay cells. This is an
ownership count, not a claim that every other byte is safe application RAM;
the installed monitor, assembler, and user program define the rest of the RAM
map. An R-YORS v1.1 build reports 18,694 bytes as application-usable by its
normal convention.

The worker, tray, record buffers, and state are volatile. A program that needs
their contents after STR8-N service must rebuild them. HIMON's Banked-AP RAM
helper begins at `$0500`, above the worker's fixed `$0453` last byte.

## HIMON RAM S19 alternative

HIMON `L` and `L G` provide a richer alternative to STR8-N recovery `L`.
HIMON calls the
public `$F009` parser on each buffered S0/S1/S9 record and then applies its own
destination policy:

```text
accepted destination bytes  $0000-$7EFF RAM
rejected                    $7F00-$7FFF I/O
rejected                    $8000-$FFFF flash
simple R-YORS program area  $2000-$4FFF
```

This RAM stream need not be 4K-aligned or dense. The caller is responsible for
not overwriting loader state, monitor workspace, the hardware stack, or code
that still needs to run. Other R-YORS RAM ranges can be usable by phase; check
its current memory report. `L G` uses a nonzero S9 as its start address; a
zero S9 falls back to the first loaded address.

## Jn handoff contract

`J0`-`J2` require their Bank-3 directory record to be COMPLETE. `J3` is the
local exception and does not require a completed Bank-3 directory row. The RAM
worker then:

1. selects the requested bank;
2. reads that bank's little-endian RESET vector at `$FFFC-$FFFD`;
3. rejects a vector below `$8000` or erased `$FFFF`;
4. records the validated bank at `$1FFD-$1FFF`;
5. disables IRQ, clears decimal mode, sets X and SP to `$FF`; and
6. jumps through the RESET vector without restoring Bank 3.

RAM and peripherals are otherwise preserved. This is a warm handoff, not an
electrical reset. A guest initializes its own RAM, IVI vectors, VIA, ACIA, and
other required state. It must preserve the PCR bits that select its flash bank.

On any validation failure the RAM worker restores Bank 3 and STR8-N prints a
jump failure. Physical RESET always forces Bank 3.

## Public interface

```text
$F003  retired gate: CLC / RTS / NOP
$F006  retired gate: CLC / RTS / NOP
$F009  SR/02 validated-record parse service
$F00C  signature/capability bytes: $53 $52 $02 $03
$F010  bank-selection service
$0203  RAM return-capable selector entry after relocation
```

### `$F009` record parser

The parser accepts one record from a RAM buffer or the console. Request and
result fields are `$7E95-$7EA8`; decoded payload is `$7B00-$7BFB`, at most
252 bytes. Capability `$03` means both buffer and console input. The service
reports record kind, addresses, data, entry, and parse status. It does not
write RAM or flash for the caller.

### `$F010` bank selector

A RAM caller passes A = bank 0-3. The caller and its JSR return address must be
below `$8000`. STR8-N copies and verifies the 41-byte selector prefix at
`$0200-$0228`, then tail-calls its `$0203` entry so RTS occurs from RAM after
the flash window changes.

The selector controls bank-state byte `$7FEC` under mask `$EE` with explicit
PCR patterns Bank 0 `$CC`, Bank 1 `$CE`, Bank 2 `$EC`, and Bank 3 `$EE`.
Other raw PCR values, including reset/input state, are not bank identities.

`$F003` and `$F006` are fail-closed tombstones. Mode 6 and the former general
worker doorway are not public interfaces. A user program that needs to read a
selected sector should run below `$8000`, call `$F010`, copy the bytes itself,
and select Bank 3 again if it intends to return to Bank-3 ROM code.

## Build, artifacts, and qualification

`make layout-check` verifies fixed entry points, vectors, worker span, metadata
placement, exact image size, and at least 8 bytes of free resident margin.
`BUILD/str8n-manifest.json` publishes the resulting addresses and hashes.
`make range-matrix-check` generates and re-validates every top-aligned 4K-32K
Bank 0-2 range, every 4K-28K Bank-3 range, and representative middle spans.
These host fixtures are written below `BUILD/test/range-matrix`; they do not
change the firmware image or consume protected-sector space.
`make ram-load-contract-check` verifies the linked `L` entry and every lower,
upper, crossing-record, empty-record, and S9 boundary case.

```text
BUILD/bin/str8n-bank3-f000-ffff.bin  exact 4096-byte programmer image
BUILD/s19/str8n-f000.s19             resident build component
BUILD/s19/str8n-worker-0200.s19      worker evidence/build component
BUILD/str8n-manifest.json            sizes, addresses, ABI, and hashes
```

The BIN file maps as follows:

```text
file offset $000-$FFF -> CPU $F000-$FFFF -> physical $1F000-$1FFFF
```

Before qualifying a release on hardware, exercise `L` at `$2000`, `$7AFF`,
cross-page records, rejected `$1FFF`/`$7B00` spans, bad records, partial-load
failure, and automatic S9 execution. Also exercise every allowed Bank 0-2 and
Bank-3 size, malformed S19 rejection, interruption at each sector, full-range
recovery, directory exhaustion, readback, `H`, `J0`-`J3`, NMI/IRQ outside
flash mutation, and physical RESET. Retain the exact image, manifest, hashes,
and board transcript. A clean host build is necessary evidence, not a
substitute for board proof.

See [Maps and Diagrams](MAPS.md) for the same relationships visually.
