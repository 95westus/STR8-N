# STR8-N v1.2 Technical Guide

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
resident ABI discovery    STR8-N $F006       reports version and capabilities
console initialization    STR8-N $F003       restores the FT245R-facing VIA
raw console input         STR8-N $F013       waits for and returns one byte
raw console output        STR8-N $F019       waits until one byte is accepted
raw input readiness       STR8-N $F03E       reports without consuming a byte
guest launch              STR8-N J0-J3       jumps through selected RESET vector
```

The STR8-N form stays small by omitting load-only, fallback-entry, reporting,
and arbitrary destination policy.

For terminal-level examples, see [Worked Examples](EXAMPLES.md). For the same
contracts as pictures, see [Maps and Diagrams](MAPS.md).

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

### Power-up visibility and selector timing

After console initialization, STR8-N emits six `WAIT...` pulses approximately
one second apart. This unpolled phase gives the FT245R and host terminal time
to attach while showing continuing board activity. STR8-N then flushes queued
input and prints its identity and selector:

```text
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.2
0-2 H S: ......
```

The six selector dots are also approximately one second apart. Only this
second phase polls `0`, `1`, `2`, `H`, or `S`; timeout cold-starts compatible
HIMON. Total automatic startup time remains approximately twelve seconds.

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

The 23-byte gap is the only build-certified growth room inside the protected
sector. The layout checker requires at least 8 bytes. `$FF` bytes found
inside linked code are not automatically free space.

The stored worker is copied to `$0200-$0453` before an install or bank handoff.
Each copied byte is immediately read back and compared before the next byte.
No worker bytes are transported in an `I` or `L` S19.

Hardware vectors are:

```text
$FFFA-$FFFB  NMI      -> $F0D2
$FFFC-$FFFD  RESET    -> $F000
$FFFE-$FFFF  IRQ/BRK  -> $F0E6
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

### Transport contract

The S19 transport is terminal-independent and requires no artificial character
or line delay. After the operator confirms `WRITE? Y`, STR8-N copies and
verifies the RAM worker, journals START, and writes any first-enrollment
metadata and seal. Only after that preparation succeeds does it print `S19`.
The sender may then stream the complete text file continuously.

This ordering deliberately makes `Y` the persistent transaction boundary. If
the sender is cancelled, malformed, or never started after `S19` appears, the
directory remains incomplete and the documented full-range recovery rule
applies. It avoids placing a first-enrollment flash pause immediately after the
first S1 line, while retaining S9 validation, final-sector holdback, explicit
COMMIT, read-back verification, and COMPLETE-last ordering.

On 2026-08-10, board sessions at zero terminal pacing completed a first
Bank-3 enrollment and later ASM update, reached `OK`, and successfully entered
HIMON and ASM. The full 28K `$8000-$EFFF` stream showed six receive-time dots
and a seventh after `COMMIT? Y`, as expected. This is retained point evidence;
it does not replace the full qualification matrix listed below.

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

The R-YORS v1.2 streams are dense, payload-only examples:

```text
ryors-v1.2-asm-himon-bank3-8-e.s19  $8000-$EFFF  28K  S9 $C000
ryors-v1.2-himon-bank3-c-e.s19      $C000-$EFFF  12K  S9 $C000
ryors-v1.2-asm-bank3-8-b.s19        $8000-$BFFF  16K  S9 $FFFF
```

The combined stream is the simplest first Bank-3 install. For separate
streams, HIMON must establish entry `$C000` before the ASM-only `$FFFF` stream.
The stored Bank-3 entry constrains future S9 records; `H` still checks the
fixed HIMON identity and enters `$C000`, while `J3` uses Bank 3's RESET vector.

### Payload-only means no worker records

Historical combined streams that start with S1 records at `$0200` are invalid.
The first S1 for `I` must be the selected flash start, normally `$8000`,
`$9000`, and so on. The worker component in
`BUILD/v1.2/s19/str8n-v1.2-worker-0200.s19` is build and integration evidence, not a file
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
  -S19Path BUILD/v1.2/s19/guest-bank0-8000-ffff.s19
```

For a first Bank-3 HIMON image:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/convert_guest_bin_to_s19.ps1 `
  -BinPath C:\IMAGES\himon-c000-efff.bin `
  -BaseAddress 49152 `
  -EntryAddress 49152 `
  -Bank 3 `
  -S19Path BUILD/v1.2/s19/himon-bank3-c000-efff.s19
```

`tools/compose_str8n_install_s19.ps1` validates an existing payload and writes
a normalized payload-only stream. It reports the exact extent, S1 count, S9,
per-sector CRC-16, and whole-file SHA-256. For an existing Bank-3 row, pass
`-ExistingBank3Entry` so `$FFFF` or an exact match is checked correctly.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/compose_str8n_install_s19.ps1 `
  -PayloadS19Path BUILD/v1.2/s19/guest-bank0-8000-ffff.s19 `
  -PayloadStart 32768 `
  -PayloadEndExclusive 65536 `
  -Bank 0 `
  -S19Path BUILD/v1.2/s19/str8n-i-guest.s19
```

## Transaction timing and recovery

`I` is a streaming flash installer, not a RAM loader and not a
receive-everything-first loader:

1. It validates the bank, range, directory, and embedded worker.
2. `WRITE? Y` accepts the persistent transaction boundary.
3. STR8-N copies and verifies the worker, writes START, and writes any
   first-enrollment type, description, and seal that can be known before S9.
4. Only after that preparation succeeds does STR8-N print `S19`.
5. Each complete non-final 4K sector is erased, programmed, and read back as
   the dense stream arrives.
6. The final selected sector remains in the `$0A00-$19FF` tray.
7. A valid S9 and `COMMIT? Y` allow that final sector to be programmed and
   verified.
8. The Bank-3 entry, when first needed, is written; COMPLETE is always the
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

Ctrl-C (`$03`) is the record-parser abort status. During `L`, the on-board
STR8-N 1.2 presentation reports `BAD`, drains queued receive input, returns to
the STR8-N prompt, and does not jump to S9. S1 records already copied into RAM
remain present.

### STR8-N 1.2 bank-maintenance RAM image

`make bank-maint` builds and validates
`BUILD/v1.2/s19/str8n-v1.2-bank-maint-2000.s19`. Its S9 entry is `$2000`; the S1
address span is `$2000-$362A`, wholly inside the `L` contract. The WDC linker
fills the unused space before the embedded worker, so the stream contains
5,675 RAM data bytes even though the executable regions are smaller.

The utility is self-contained. It has direct FT245R input/output, local hex
formatting, and local 32-bit FNV-1a support. It does not use HIMON's IVI or
RAM service table. `Q` jumps to Bank-3 `$F000`; it does not use `RTS`, because
STR8-N `L` deliberately supplies no return address.

Enter by itself at the Bank Maintenance main menu follows the same `$F000`
quit path as `Q`. At an operation subprompt, an empty line cancels only that
operation and returns to the maintenance menu.

```text
$0200-$042A  runtime copy of the private mutation worker
$0A00-$19FF  one staged 4K flash sector
$7C00-$7C1F  operation result/state and directory entry
$7C20-$7C2F  bounded command input
$7C40-$7C7F  staged Bank-3 directory
$7C80-$7D1A  first-valid-AP inventory
$2000-...    bank-maintenance program and text
$3400-$362A  stored private mutation worker
```

The carried worker privately implements the staging/programming operations
needed by the maintenance tool. It calls the worker at `$0200` directly and
does not depend on resident console or ABI-query gates. Every programmed
sector is verified, Bank 3 sector `$F000-$FFFF` is protected, and the copy
guard recognizes the v1.2 resident signature at `$F00C` (`53 52 02 03`).

The `C` path requires an all-`$FF` destination directory row before changing
the destination. After the eight copied sectors verify, it collects TYPE and
the five-byte description, then uses the carried worker's private mode `$07`
to enroll the Bank-3 row without erasing the protected sector. The persistent
order is journal START, bytes `+0..+11` including seal `$FE` and Bank-0/1/2
entry `$FFFF`, then journal COMPLETE. Each request is preflighted for legal
one-to-zero transitions and independently read back. COMPLETE is therefore
never visible before the full-bank copy and immutable identity are verified.
Nonempty rows are refused; updating or recovering an existing identity remains
the responsibility of STR8-N `I`.

The `D` path adopts an existing payload without rewriting it. It requires an
all-`$FF` destination row, stages sector F, and validates a RESET vector in
`$8000-$FFFE`. Banks 0-2 receive entry `$FFFF`. Bank 3 additionally requires
the `SR 02 03` resident signature, an explicit entry in `$8000-$FFFE`, and at
least one non-`$FF` byte at that entry. After exact `ADOPT Bn` confirmation,
`D` uses the same START/identity/COMPLETE record writer as `C`. It cannot edit,
repair, or replace a nonempty row.

`tools/check_bank_maint_s19.ps1` rejects malformed checksums, unsupported
record types, duplicate destination bytes, RAM addresses outside
`$2000-$7AFF`, a missing private worker, or any S9 other than `$2000`.

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
the guarded RAM directory-refresh tool or an external programmer must refresh
the protected sector before another install to that bank.

The programmer BIN and the candidate embedded by
`str8n-v1.2-directory-refresh-2000.s19` contain an all-`$FF`
directory/configuration pocket. Refreshing it erases every bank's journal and
Bank-3 install identity. The onboard tool first verifies an exact live-sector
backup in Bank 1 sector F and retains retry/restore control in RAM while the
Bank-3 reset sector is unavailable.

The Top Update and Directory Refresh artifacts share the same guarded RAM
driver. Enter by itself at either pre-erase confirmation is a cancellation:
the tool selects Bank 3, prints its `ABORT - NO ACTIVE ...` message, and jumps
to resident STR8-N at `$F000`. It cannot use `RTS` because STR8-N `L` enters
the S9 address with a fresh stack and no return address. After active erase,
failure remains in the RAM `R` retry / `O` restore recovery prompt instead.
Top Update is the maintained replacement for the older ASM-generated
TopWriter workflow.

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
$1A00-$1FFF  user-free low RAM                   1536 bytes
$7C00-$7DBF  foreground High Tool Overlay         448 bytes
$7DC0-$7DC7  HIMON AP-link scratch                  8 bytes
$7DC8-$7DE8  reserved                              33 bytes
$7DE9-$7DFF  recovery/worker/jump state            23 bytes
$7B00-$7BFB  decoded S-record payload tray       252 bytes
$7E95-$7EA8  record request/result card           20 bytes
$7EDE-$7EDF  delay helper fixed cells              2 bytes
$7EED-$7EEF  IVI signature                         3 bytes
$7EF8-$7EFF  IVI RAM vectors                       8 bytes
$0100-$01FF  hardware stack, dynamic              256 bytes maximum
```

The main `I` transaction regions through the record card total 5,015 named
bytes when the `L`-only flag at `$00A0` is excluded. The fixed delay and IVI
cells add 13 bytes. The hardware stack can consume up to 256 more bytes.

```text
Quantity                                      Bytes
board RAM below I/O                          32,512
named I transaction areas                     5,015
fixed delay and IVI cells                         13
outside those named/fixed STR8-N areas        27,484
outside them with full stack reserved         27,228
STR8-N L accepted window                      23,296
R-YORS normal application convention          18,694
```

These are ownership counts, not a claim that all remaining bytes are safe for
an application. HIMON, ASM, a loaded program, and active stack frames define
additional ownership. The R-YORS figure is its own monitor-aware convention,
not simple subtraction from the STR8-N figure.

The worker, tray, record buffers, and state are volatile. A program that needs
their contents after STR8-N service must rebuild them. HIMON's Banked-AP RAM
helper begins at `$0500`, above the worker's fixed `$0453` last byte.

### `$1A00-$1FFF`: user-free low RAM

STR8-N v1.2, HIMON v1.2, ASM-F2, Bank Maintenance, and the maintained RAM
tools make no fixed runtime allocation in `$1A00-$1FFF`. The complete 1536
bytes are free for user code and data. As with all RAM, a HIMON cold start
clears it, and an application must still avoid colliding with another user
program that it loaded itself.

The v1.2 capsule and optional-tool allocations in this range are obsolete.
Do not use a v1.2 RAM tool with the v1.2 firmware set.

### STR8-N v1.2 high-RAM ABI

```text
$7C00-$7DBF  foreground High Tool Overlay
$7DC0-$7DC7  HIMON AP-link scratch
$7DC8-$7DE8  reserved
$7DE9-$7DFF  STR8-N Recovery State Capsule
```

The High Tool Overlay is volatile and single-owner. Only one foreground RAM
tool or ASM output session may use it at a time. ASM's exclusive output limit
is `$7D00`, so `$7D00-$7DFF` is protected from assembled output.

The 23-byte Recovery State Capsule contains these defined slots:

```text
$7DE9        current/failing sector high byte
$7DEA-$7DEB first failing flash address
$7DEC-$7DED reserved/unassigned
$7DEE        source bank for worker operations
$7DEF        destination bank
$7DF0        worker operation mode
$7DF1        boot-input / CR-LF parser state
$7DF2        requested jump bank
$7DF3-$7DF4 validated RESET vector
$7DF5        jump validation status
$7DF6        staged-sector buffer high byte
$7DF7-$7DFC reserved legacy update fields
$7DFD-$7DFF published Bank Jump Record: "BJ" plus last validated bank
```

Not every operation writes every capsule byte. The flash worker consumes the
sector, bank, mode, and staging fields. Bank handoff consumes the jump fields
and commits the three-byte Bank Jump Record only after bank selection and
RESET-vector validation.

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
4. records the validated bank at `$7DFD-$7DFF`;
5. disables IRQ, clears decimal mode, sets X and SP to `$FF`; and
6. jumps through the RESET vector without restoring Bank 3.

RAM and peripherals are otherwise preserved. This is a warm handoff, not an
electrical reset. A guest initializes its own RAM, IVI vectors, VIA, ACIA, and
other required state. It must preserve the PCR bits that select its flash bank.

On any validation failure the RAM worker restores Bank 3 and STR8-N prints a
jump failure. Physical RESET always forces Bank 3.

## Resident callable ABI

All resident calls require Bank 3 to be visible because another selected bank
replaces the complete `$8000-$FFFF` CPU window. Call with `JSR` unless the
individual contract says otherwise. Only the documented entry addresses are
stable; other labels and addresses in the linker map are implementation
details.

```text
$F003  FT245R-facing VIA initialization (CONSOLE_INIT)
$F006  resident ABI version/capability query (ABI_QUERY)
$F009  SR/02 validated-record parse service
$F00C  signature/capability bytes: $53 $52 $02 $03
$F010  bank-selection service
$F013  blocking raw character input (CHARIN)
$F019  blocking raw character output (CHAROUT)
$F03E  non-consuming raw input-ready poll (CHAR_READY)
$0203  RAM return-capable selector entry after relocation
```

### `$F003` CONSOLE_INIT

`JSR $F003` restores the FT245R-facing VIA output/control state used by the
raw console services: control and control-direction bytes become `$0C`, and
the data-direction byte becomes `$00`. It returns A=`$0C`, preserves X, Y,
and carry, and does not select Bank 3. A caller must establish Bank 3 before
calling it.

In the preceding v1.2 image, `$F003` was a fail-closed `CLC / RTS / NOP`
tombstone. Call `$F006` first when compatibility with that image matters.

### `$F006` ABI_QUERY

`JSR $F006` returns carry set, A=`$01` resident ABI version, X=`$3F`
capabilities, and Y preserved. The capability bits are:

```text
$01  $F009 record parser
$02  $F010 bank selector
$04  $F013 CHARIN
$08  $F019 CHAROUT
$10  $F03E CHAR_READY
$20  $F003 CONSOLE_INIT
```

The preceding v1.2 image safely returns carry clear from its `$F006`
tombstone, so software must test carry before interpreting A or X. This query
is the required feature test before calling an entry absent from that image.

### `$F009` record parser

The parser accepts one complete S0, S1, or S9 record from a RAM buffer or the
console. It validates and decodes the record but does not apply its data to RAM
or flash. Signature `SR`, ABI version `$02`, and capabilities `$03` advertise
both buffer (`$01`) and console (`$02`) input.

Set these request fields before `JSR $F009`:

```text
$7E95  operation       $01 = parse
$7E96  format          $01 = Motorola S19
$7E97  source          $00 = buffer, $01 = console
$7E99-$7E9A            buffer address, little endian; ignored for console
$7E9B                  8-bit exact buffer byte count; ignored for console
```

A buffer contains exactly one record from `S` through its checksum, without a
line ending. Its one-byte length limits a buffered S1 to 122 data bytes; the
console form can decode the S-record maximum of 252. The buffer must not
overlap the result card or `$7B00-$7BFB` decode tray. Console input skips
leading CR/LF, requires CR or LF after the checksum, and treats Ctrl-C (`$03`)
as abort. Console reads are raw and are not echoed.

The result card is:

```text
$7E98  status
$7E9C  kind            $00 none, $01 S0 metadata, $02 S1 data, $03 S9 end
$7E9D  flags           bit 0 = entry valid
$7E9E-$7E9F            record address, little endian
$7EA0                  decoded data length
$7EA1-$7EA2            S9 entry address, little endian
$7EA3-$7EA4            decoded-data pointer; always $7B00 on success
$7EA5-$7EA8            legacy failure-detail fields; cleared for parse
$7B00-$7BFB            decoded data; up to 122 buffer or 252 console bytes
```

Status values are `$00` success, `$01` bad operation, `$02` bad format, `$03`
bad source, `$04` bad start, `$05` bad record type, `$06` bad hexadecimal,
`$07` bad count, `$08` bad checksum, `$09` bad end, and `$0E` console abort.
On return, A equals status; carry is set only for success. X and Y are
clobbered, and decimal mode is cleared. Interpret the other result fields only
when carry is set.

### `$F010` bank selector

A RAM caller passes A = bank 0-3. Bank 3 must be visible on entry, and the
caller and its JSR return address must be below `$8000`. STR8-N copies and
verifies the 41-byte selector prefix at `$0200-$0228`, then tail-calls its
`$0203` entry so RTS occurs from RAM after the flash window changes.

Carry set means the requested bank is selected and remains visible. Carry
clear means the request failed and the bank is unchanged. A, X, and Y are
clobbered. The copied selector overwrites `$0200-$0228`.

The selector controls bank-state byte `$7FEC` under mask `$EE` with explicit
PCR patterns Bank 0 `$CC`, Bank 1 `$CE`, Bank 2 `$EC`, and Bank 3 `$EE`.
Other raw PCR values, including reset/input state, are not bank identities.

### `$F013` CHARIN

`JSR $F013` waits until one raw FT245R console byte is available. It returns
the byte in A with carry set and preserves X and Y. It does not echo, translate
case, combine CR/LF, or recognize control characters. It has no timeout.

### `$F019` CHAROUT

Pass one raw console byte in A and `JSR $F019`. The call waits until the FT245R
accepts the byte, then returns with A, X, and Y preserved and carry set. It does
not add CR/LF and has no timeout.

### `$F03E` CHAR_READY

`JSR $F03E` tests the raw FT245R receiver and returns immediately without
consuming a byte. Carry set means at least one byte is ready; carry clear means
the receiver is empty. X and Y are preserved; A and flags other than carry are
clobbered. It does not echo, translate, wait, or time out.

The normal polling sequence is `JSR $F03E`, `BCC` for the empty path, then
`JSR $F013` to consume the byte. Console input has one owner; if an interrupt
handler or another context consumes the byte between those calls, CHARIN can
block.

Physical RESET initializes the console before the startup selector and all
normal STR8-N handoffs. A caller that has subsequently reconfigured the
FT245R-facing VIA must restore the STR8-N console state before using CHARIN,
CHAROUT, or CHAR_READY. It can do so with CONSOLE_INIT. None of the character
calls selects Bank 3 or reinitializes the interface.

Mode 6 and the former general worker doorway are not public interfaces. A user
program that needs to read a selected sector should run below `$8000`, call
`$F010`, copy the bytes itself, and select Bank 3 again if it intends to return
to Bank-3 ROM code.

## Build, artifacts, and qualification

The Makefile requires WDC `wdc02as` and `wdcln` on `PATH`. Its user-facing
targets are:

```text
make                         build and verify the release artifacts
make resident                build the resident supervisor
make workers                 build the unified RAM worker evidence image
make bank-maint              build and validate the RAM maintenance S19
make console-abi-test        build the resident ABI hardware probe
make top-update              build the guarded Bank-3 top updater
make onboard-directory-refresh
                             build the guarded directory-pocket refresh
make ryors-full-bank         compose the R-YORS plus STR8-N 32K image
make layout-check            enforce fixed addresses and the 8-byte reserve
make range-matrix-check      test documented flash install ranges
make ram-load-contract-check test STR8-N L address and S9 boundaries
make programmer-bin          create the exact 4096-byte top-sector BIN
make clean                   remove generated BUILD artifacts
```

`make layout-check` verifies fixed entry points, vectors, worker span, metadata
placement, exact image size, and at least 8 bytes of free resident margin.
`BUILD/str8n-manifest.json` publishes the resulting addresses and hashes.
`make range-matrix-check` generates and re-validates every top-aligned 4K-32K
Bank 0-2 range, every 4K-28K Bank-3 range, and representative middle spans.
These host fixtures are written below `BUILD/v1.2/test/range-matrix`; they do not
change the firmware image or consume protected-sector space.
`make ram-load-contract-check` verifies the linked `L` entry and every lower,
upper, crossing-record, empty-record, and S9 boundary case.
`make bank-maint` builds the self-contained RAM maintenance image and rejects
bad record counts/checksums, duplicate bytes, data outside `$2000-$7AFF`, an
incorrect S9, or a changed private-worker hash.
`make ryors-full-bank` validates the dense R-YORS `$8000-$EFFF` input, appends
the current verified STR8-N top-sector BIN, derives S9 from RESET, and emits a
dense 32K Bank-0/1/2 payload. It deliberately does not use the older STR8-N
copy embedded in R-YORS's previously combined BIN.

```text
BUILD/v1.2/bin/str8n-v1.2-bank3-f000-ffff.bin
                                      exact 4096-byte programmer image
BUILD/v1.2/s19/str8n-v1.2-f000.s19         resident build component
BUILD/v1.2/s19/str8n-v1.2-worker-0200.s19  worker evidence/build component
BUILD/v1.2/s19/str8n-v1.2-bank-maint-2000.s19
                                      self-contained RAM maintenance program
BUILD/v1.2/s19/str8n-v1.2-console-abi-test-2000.s19
                                      raw console ABI hardware probe
BUILD/v1.2/s19/str8n-v1.2-top-update-2000.s19
                                      guarded Bank-3 sector-F updater
BUILD/v1.2/s19/str8n-v1.2-directory-refresh-2000.s19
                                      guarded directory-pocket refresh
BUILD/v1.2/s19/ryors-v1.2-asm-himon-str8n-bank0-2-8-f.s19
                                      32K ASM+HIMON+STR8-N Bank-0/1/2 payload
BUILD/str8n-manifest.json             sizes, addresses, ABI, and hashes
```

All BIN, S19, and generated S19 qualification fixtures live below the version
root `BUILD/v1.2/`. The compatibility manifest remains at
`BUILD/str8n-manifest.json` and records the versioned artifact paths.
Compiler/linker intermediates remain directly below `BUILD/obj`, `BUILD/lst`,
and `BUILD/sym`.

The BIN file maps as follows:

```text
file offset $000-$FFF -> CPU $F000-$FFFF -> physical $1F000-$1FFFF
```

### Qualification evidence and remaining board tests

The [2026-08-11 expanded resident ABI hardware proof](RESIDENT_ABI_HARDWARE_PROOF_2026-08-11.md)
accepts the current top-sector image for guarded onboard update, verified
backup, RESET/live selector, ABI_QUERY, CONSOLE_INIT, CHAROUT, both
non-consuming CHAR_READY paths, raw CHARIN, `$F0E6` BRK dispatch, warm and
cold HIMON entry, and `J3`. NMI remains unclaimed without an explicit operator
annotation.

The retained continuation accepts the guarded onboard directory refresh with
live-sector sum `$0BE5`, a newly verified Bank-1 sector-F backup, Bank-3
rewrite/verify/RESET, and a post-reset `M` showing D0-D3 completely erased.
It then accepts Bank Maintenance `C` from Bank 3 to Bank 2, all eight verified
sector writes, enrollment as `D2 FF TEST0 FFFF FCFFFFFF`, selector `2` launch
of the copied STR8-N, and its `J3` return through physical Bank 3.

The separate
[directory-maintenance proof](DIRECTORY_MAINT_HARDWARE_PROOF_2026-08-11.md)
accepts the current Bank Maintenance artifact's metadata-only `D` path:
nonempty-row refusal, low/erased ENTRY rejection, DESC-length rejection,
precommit cancellation, bad-RESET refusal, successful D1/D3 commits, and the
shared `C` commit-path regression.

Observed v1.2 board sessions have established:

- physical RESET selects Bank 3 and reaches STR8-N;
- the six `WAIT...` pulses and later identity/selector are visible;
- a full-speed, zero-pacing Bank-3 `8-E` install completes and starts HIMON;
- separate HIMON `C-E` and ASM `8-B` installs complete and ASM starts through
  HIMON;
- RAM Bank Maintenance starts through `L`, maps banks, copies/verifies all
  eight sectors, and enrolls the empty destination row COMPLETE;
- a raw copy without directory enrollment is correctly rejected by `J0`-`J2`,
  proving the launch gate is directory-based rather than a used-flash test.

The generated Bank-0/1/2 `8-F` image, every size/range boundary, interruption
at each sector, journal exhaustion, AP put, explicit command-path
`J0`/`J1`/`J2`, and all `L` boundary failures still require retained hardware
transcripts before claiming a complete release matrix. NMI/IRQ may be tested
only outside flash mutation; do not deliberately press NMI while flash is
busy.

Retain the exact BIN/S19 files, manifest, hashes, flash readback, and terminal
transcript for each board-proof run. A clean host build is necessary evidence,
not a substitute for board proof.

See [Maps and Diagrams](MAPS.md) for the same relationships visually.
