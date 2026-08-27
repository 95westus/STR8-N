# Stock WDCMONv2 to STR8-N Migration

This is the short onboarding rail for a stock WDC W65C02SXB, either alone or
with the W65C02EDU expansion board installed. W65C02EDU is an add-on for the
SXB, not a standalone CPU board. The first implemented stage preserves flash
through the terminal before any erase or program operation is introduced.

Current status:

```text
implemented and host-checked   read-only four-bank inventory
implemented and host-checked   selected-bank dense S19 export
implemented and host-checked   local BIN/S19/receipt extraction and validation
implemented and host-checked   binary WDCMONv2 load/readback/execute host bridge
awaiting board transcript      stock WDCMONv2 load, inventory, and Bank-0/3 dump
implemented, host-checked      guarded B3 -> erased B0 copy and exact verify
implemented, host-checked      guarded STR8-N seed install into Bank-3 sector F
awaiting board transcript      copy, recovery, RESET into STR8-N, and J0 stock
existing STR8-N path           install R-YORS Bank-3 sectors 8-E with I
awaiting board transcript      first-use C/?/config/STR8/cold/J0 sequence
```

The archive artifact is intentionally not an installer. It has no flash
unlock, erase, or byte-program sequence. The separate seed installer is
write-capable and must not be used until the archive stage has passed.

## Supported first-stage profile

`SXB2` is the required WDCMONv2 board identity in both supported physical
configurations. Installing the EDU expansion does not create a different host
monitor or memory map. The bridge does not initialize, probe, or use EDU RTC,
SPI SRAM, ADC, buzzer, LED, or expansion-bus devices.

The read-only program currently assumes the established STR8-N hardware map:

```text
CPU                    W65C02S
RAM                    $0000-$7EFF
I/O                    $7F00-$7FFF
selected flash         $8000-$FFFF
physical flash shape   four 32K banks / 128K total
FT245R VIA             $7FE0-$7FE3
bank-select PCR        $7FEC, STR8-N patterns CC/CE/EC/EE
```

Both migration programs execute below `$8000`. Every bank-select subroutine
call therefore has its caller and return address in RAM; no call returns
through a bank switch that unmapped its caller. STR8-N's later `J0` launch is
performed by its copied RAM worker.

The read-only archive intentionally does not enter flash product-ID mode.
Successful inventory is not write authorization. The separate installer
enters and exits product-ID mode and accepts only the supported `$BF/$B5`
SST39SF010A before it offers a destructive gate.

## Build

From the standalone STR8-N repository:

```text
make wdcmonv2-archive
```

The board artifact is:

```text
BUILD/v1.23/s19/str8n-v1.23-wdcmonv2-archive-2000.s19
```

It occupies `$2000-$250E` in the current build and has S9 entry `$2000`.
The build check requires the complete image to remain inside
`$2000-$7AFF`, rejects flash-space writes and SST39 unlock addresses in the
source, and exercises the host extractor with a deterministic 32K image and a
corrupt-record rejection case.

The separately gated seed installer is built with:

```text
make wdcmonv2-install
```

Its artifact is:

```text
BUILD/v1.23/s19/str8n-v1.23-wdcmonv2-install-2000.s19
```

It is a dense `$2000-$4FFF` RAM image with S9 `$2000`. The code and state are
below `$2900`, `$0A00-$19FF` is its sector staging area, and the migration-
configured STR8-N top candidate is carried at `$4000-$4FFF`.

For publication from adjacent STR8-N and R-YORS checkouts, build the explicit
allowlisted kit:

```text
make wdcmonv2-package
```

This produces
`BUILD/v1.23/str8n-v1.23-wdcmonv2-ryors-migration-kit.zip`. It contains the
two bootstrap S19 files, the exact 4K STR8-N candidate, the R-YORS `8-E`
payload, source, binary-monitor host bridge, extractor, operator documents,
license, and a self-verifier.
It contains neither WDCMONv2 firmware nor locally extracted bank archives.
After extracting it, run `VERIFY-PACKAGE.ps1` before using any artifact. The
outer ZIP hash is printed by the build and should be published beside the ZIP;
it is intentionally not embedded in a document inside that same ZIP.

See `WDCMONV2_MIGRATION_PROVENANCE.md` for the source trail and the release
boundary. In short, generating an owner-local S19 does not relicense the
captured WDCMONv2 bytes. The project does not redistribute that S19 without an
express WDC grant.

## Stock-monitor launch

Stock WDCMONv2 is not an ASCII S19-paste monitor. Before the RAM application
starts, the USB channel carries WDCMONv2's framed binary host protocol. The
kit therefore includes `TOOLS/start_wdcmonv2_ram.ps1`; do not paste either
bootstrap S19 into a terminal.

List the COM ports, then launch the read-only archive application with the
actual board port (COM5 is only an example):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 -ListPorts

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 -Port COM5 -ProbeOnly

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 `
  -Port COM5 `
  -ImagePath .\ARTIFACTS\str8n-v1.23-wdcmonv2-archive-2000.s19 `
  -TranscriptPath .\LOCAL\stock-b0-b3-capture.log
```

`-ProbeOnly` performs reset/synchronization and `$0C` identity only, then
closes the port. It issues no RAM or flash command. Use it to distinguish the
board from another FTDI COM device before naming an image. The full bridge
then performs this fixed sequence:

```text
validate every S-record checksum, density, $2000-$7AFF range, and S9 entry
pulse DTR using the stock WDC reset sequence unless -NoReset is explicit
$55 $AA -> require $CC before every WDCMONv2 command
$0C       require the 12-byte board identity to begin SXB2
$02       write 256-byte RAM chunks; require status $00 for every chunk
$03       read each chunk back and require every byte to match
$06       execute the three-byte little-endian S9 address
same open COM handle becomes the raw ASCII terminal and capture stream
```

The command, address, and length fields are binary. Addresses and lengths are
24-bit little-endian values. The RAM bridge never sends WDCMONv2 flash-write,
flash-erase, or firmware-update commands. After `$06`, the RAM application
owns the VIA/FT245 path directly and makes no calls into private WDCMONv2 ROM
entry points.

The default terminal sends CR for Enter and exits on `Ctrl+]`. `Ctrl+B` sends
one WDCMONv2 `$0C` identity probe; use it only after `J0` has entered the
preserved monitor, because it is binary traffic rather than an ASCII command.
The transcript contains raw received bytes, including a successful probe's
12-byte binary reply. Keep the terminal open while the RAM program runs;
`-NoTerminal` is diagnostic because closing/reopening the COM port may toggle
DTR and reset the board. `-NoReset` is for a deliberately synchronized
already-running monitor, not the normal first attempt.

When `-TranscriptPath` is present, the bridge keeps two evidence streams:

```text
archive-capture.log             exact raw board RX; extractor input
archive-capture.log.events.txt  timestamped host actions and checks
```

The companion event log is created automatically unless `-EventLogPath`
names another file. It records the selected image range/hash, transfer
name/length/hash, board identity, byte-exact RAM readback, execute address,
completed TX lines, `Ctrl+U`, `Ctrl+B`, errors, and terminal exit. Host events
are never inserted into the raw RX transcript, so dense S-record extraction
remains byte-clean. Existing raw or event logs are refused unless `-Force` is
explicit. If `-EventLogPath` is supplied, it must differ from
`-TranscriptPath`.

Before resetting the board, the full path also requires an interactive console,
checks that requested raw and event logs do not already exist unless `-Force`
is explicit, creates their parent directories, and reads/hashes the optional
transfer file. These host-side failures therefore occur before command `$06`
hands control to RAM.

If probe synchronization times out, stop binary traffic. A diagnostic
`-ListenOnlySeconds 5` run may use the same `-Port` and optional
`-TranscriptPath`. It applies the selected DTR reset policy and captures RX,
but reports `TX=0 BYTES` and cannot query, load, execute, or alter flash. Zero
received bytes still does not identify the target; the operator must check the
physical board, power, cable, reset behavior, and COM assignment.

For the write-capable installer, name the R-YORS payload as the optional
terminal transfer file:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 `
  -Port COM5 `
  -ImagePath .\ARTIFACTS\str8n-v1.23-wdcmonv2-install-2000.s19 `
  -TransferPath .\ARTIFACTS\ryors-v1.2-himon-asm-bank3-8-e.s19 `
  -TranscriptPath .\LOCAL\install-capture.log
```

`Ctrl+U` sends that file only when the operator requests it. Use it later at
STR8-N's `S19` prompt; it is not sent automatically. A C terminal/front end
may implement the same state machine: binary sync/identity/write/read/execute,
then change its parser to terminal/screen-scrape/file-transfer mode without
closing the device. The PowerShell bridge is the publishable reference and
immediate path, not a requirement that the future host remain PowerShell.

The protocol details above follow WDC's public
[WDCMON v2 user manual](https://www.westerndesigncenter.com/wdc/documentation/WDCMON_User_Manual_v20.pdf).
WDC's public
[W65C02SXB getting-started procedure](https://wdc65xx.com/gettingstarted/02-sxb-getting-started/)
likewise describes host-side program loading and execution through WDCDB.
The packaged verifier also runs an in-process monitor emulator through the
actual bridge functions and requires the exact `$0C/$02/$03/$06` wire frames,
write acknowledgement, RAM readback, and execute address. This is host
evidence only; it does not replace the physical transcript.

On entry the program disables IRQ, clears decimal mode, resets the stack, and
initializes the FT245R-facing VIA. It then inventories all four banks:

```text
WDCMONV2 -> STR8-N ARCHIVE 0.1
READ ONLY; NO FLASH WRITE CODE
DO NOT PRESS NMI/RESET DURING DUMP

BANK INVENTORY
B0 USED FNV1A=........ NMI=.... RESET=.... IRQ=....
B1 ERASED FNV1A=........ NMI=FFFF RESET=FFFF IRQ=FFFF
B2 ...
B3 USED FNV1A=........ NMI=.... RESET=.... IRQ=....
B0_EQ_B3=YES (HASH ONLY)

0-3=DUMP M=MAP Q=HALT>
```

`M` repeats the inventory. `0` through `3` export that bank. `Q` selects
Bank 3 and halts in RAM; physical RESET returns to the stock Bank-3 image.
The program explicitly returns to Bank 3 after every completed dump.

Do not assert NMI or RESET while another bank is selected. IRQ is masked;
NMI cannot be masked and would vector through the selected bank.

## Capture a local archive

The terminal/front end may capture the complete session. An export is framed
as:

```text
W2R-BEGIN B=0 BYTES=8000 FNV1A=........ RESET=....
S1238000...checksum
...1024 dense S1 records total...
S903....checksum
W2R-END B=0 BYTES=8000 FNV1A=........
```

The S1 address range is exactly `$8000-$FFFF`, with 32 data bytes per record.
S9 equals the selected image's RESET vector. The FNV-1a value covers all
32,768 bank bytes in ascending address order.

Convert a captured transcript into local artifacts with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\extract_wdcmonv2_archive.ps1 `
  -TranscriptPath .\capture.log `
  -OutputDirectory .\LOCAL\board-archive `
  -Bank 0
```

The extractor accepts only a complete matching receipt pair, 1024 sequential
checksum-valid S1 records, one checksum-valid S9, an S9/reset-vector match,
and a whole-image FNV match. It then writes:

```text
wdcmonv2-bankN.bin           canonical exact 32768-byte bank image
wdcmonv2-bankN.s19           checked transport/install representation
wdcmonv2-bankN.receipt.txt   bank, range, FNV-1a, RESET, and SHA-256
```

Existing outputs are not replaced unless `-Force` is explicit. These are the
owner's local WDCMONv2 artifacts; they are not STR8-N release files and must
not be bundled into a public release.

One transcript may contain several completed dumps. Use `-Bank 0` and
`-Bank 3` in separate extractor runs to retain both; without `-Bank`, the
extractor selects the last complete transaction for compatibility.

## Which bank should be archived?

Do not encode one answer before inventory. For this migration, always export
and retain B0 and B3 before running the installer:

- On an untouched stock board, the executing WDCMONv2/SPI image is expected
  in Bank 3. Export Bank 3 before any migration work.
- On an established R-YORS layout, WDCMONv2 may already be retained in Bank
  0. Export Bank 0 before releasing or repurposing it.
- If B0 and B3 have equal full-bank hashes, report the fact but do not treat a
  hash comparison as erase authorization.
- If they differ, retain both archives until their roles are understood.

This resolves the apparent B0/B3 policy conflict: the bridge observes the
actual board first. A later copy step may establish stock Bank 3 as the
onboard Bank-0 guest when Bank 0 is proven disposable, but the local archive
exists independently of that choice.

A byte-exact B3-to-B0 copy proves preservation, not relocatability. Stock
WDCMONv2 may contain startup behavior that assumes or reselects its factory
bank. The Phase-D `J0` plus `$0C` identity exchange is therefore a separate
hardware acceptance gate. If it fails, keep B0 reserved, retain the local
archive, and use the external programmer to restore B3 if stock operation is
needed; do not relabel the copy as a working guest merely because its bytes
and FNV match.

## Seed STR8-N after the archive passes

The seed installer makes one deliberately narrow bank-policy decision:

```text
B0 erased                 copy B3 -> B0; verify each sector, FNV, and all bytes
B0 byte-identical to B3   keep B0 without rewriting
B0 used and different     refuse; write nothing
B1/B2                     do not select as destinations and do not write
```

This is intentionally stricter than a general bank manager. A later tool may
support replacing a locally archived, explicitly released B0, but the stock
onboarding installer does not.

The carried top sector is derived from the verified STR8-N v1.23 top BIN, but
its optional configuration bytes begin as:

```text
$FFF0 WORK sector        $FF  unassigned
$FFF1 top-backup sector  $FF  unassigned
$FFF2 FNV bank policy    $FF  automatic external search disabled
$FFF3-$FFF9              $FF  unassigned
```

The canonical development image defaults these roles to B1:E and B1:F. The
stock migration candidate cannot make those claims because neither B1 nor B2
has been inventoried or released for that use. Bank Maintenance should own the
first assignment after migration; later SYSgen may request policy, but must use
the same guarded service rather than patching `$FFF0/$FFF1` itself.

The first-assignment transaction is deliberately separate from installation:

```text
1  map B0-B3 and decode current roles; FF means unconfigured
2  select and qualify a top-backup sector explicitly
3  copy and verify the complete live B3:F there before changing B3:F
4  select a distinct erased/discardable WORK sector, or leave WORK FF
5  patch only the requested role byte(s) in a staged full B3:F image
6  rewrite and verify B3:F through the RAM worker
7  retain the verified backup according to the selected recovery policy
8  offer directory/VTOC initialization as a later, separate command
```

Assigning a role does not enroll a bank, create a directory record, initialize
a VTOC, or authorize backup rotation. Those are opt-in transitions after the
operator sees the inventory. This preserves the installer's B1/B2 promise:
B1/B2 remain byte-for-byte untouched until an explicit post-migration Bank
Maintenance command names a destination.

The later `$FFF2=$A6` proposal is another separate policy transaction. It
enrolls B1/B2 for automatic FNV/AP search while continuing to exclude retained
WDCMONv2 in B0. Until that transaction is implemented and accepted, `$FFF2=FF`
means no automatic external-bank search.

The ordinary `I` transaction used below does not require either optional role.
Operations that need WORK or top-backup storage remain unavailable until Bank
Maintenance completes and verifies their assignments.

After loading and starting the installer at `$2000`, expect:

```text
WDCMONV2 -> STR8-N SEED INSTALL 0.1
B0 PRESERVES STOCK; B3:F BECOMES STR8-N
NO RESET/NMI/POWER DURING ACTIVE WRITE
FLASH ID=BF/B5
STOCK B3 FNV1A=xxxxxxxx
AFTER LOCAL EXTRACTOR PASS TYPE ARCHIVE xxxxxxxx>
```

The software-product-ID gate accepts only Microchip/SST manufacturer `$BF`
and SST39SF010A device `$B5`. The installer exits product-ID mode before
continuing. An unknown device halts without erase/program activity.

Enter the exact displayed archive token only after the extractor has written
and verified the local BIN/S19/receipt. If B0 is erased, the next destructive
gate is exact:

```text
COPY B3 TO B0
```

Eight dots mean eight B0 sectors were erased, programmed, and compared. The
installer then recomputes B0's whole-bank FNV and requires it to equal the
original B3 hash, followed by an independent byte-for-byte comparison of all
32K. A matching FNV is only a prefilter; it never proves identity by itself.
If B0 was already byte-identical, the copy and its confirmation are skipped.

The final top-sector gate is exact:

```text
INSTALL STR8-N 1.23
```

Before offering that gate, the RAM installer checks the complete carried
4K candidate with 32-bit FNV-1a against its build-time value. Only then is
B3:F erased and replaced. If program/verify fails while RAM is
still executing, `R` retries the carried STR8-N candidate and `O` restores the
old top sector from proven B0:F. A success selects B3 and jumps through its
new RESET vector.

Power loss during B3:F erase/program remains an external-programmer recovery
case. The board has no alternate boot jumper and cannot execute the B0 copy
after an invalid B3 RESET vector prevents startup.

Version 0.1 does not drive an EDU add-on status LED. Doing so safely requires a
board-profile decision about which VIA/PIA bit is free and must not disturb
the FT245 or bank latch. For now, the terminal's active-write message and the
test-card power exclusion are the authoritative do-not-power-off indication.

At the STR8-N reset selector, choose `S`. Install the ordinary R-YORS payload:

If the selector times out before `S`, STR8-N first checks the complete HIMON
image marker. The still-stock lower B3 does not qualify, so control returns to
the STR8-N menu instead of jumping into it.

```text
STR8-N> I
B0-3: 3
RANGE: 8-E
TYPE: 5A
DESC: RYORS
I B3 8-E WRITE? Y: Y
S19
```

Send `ryors-v1.2-himon-asm-bank3-8-e.s19`. After six programmed-sector dots
and S9, accept `COMMIT? Y` to complete the new B3 directory row. Physical
RESET should then enter STR8-N; `C` enters R-YORS/HIMON. `J0` enters the
preserved stock image as an opaque guest; because WDCMONv2 is a binary monitor,
prove that handoff with the host terminal's `Ctrl+B` identity probe rather
than by waiting for an ASCII banner.

## Migration transaction and acceptance state

The implemented and remaining migration gates are:

```text
1  identify supported board and flash geometry
2  inventory B0-B3 without writing
3  export the stock image and validate the local BIN/S19/receipt
4  require B0 erased or already byte-identical; otherwise refuse
5  copy and whole-bank-compare stock B3 into B0 when required
6  validate the carried STR8-N top candidate with full 32-bit FNV before erase
7  install and verify Bank-3 sector F from RAM
8  physical RESET into STR8-N and remain with S
9  let STR8-N I install and verify R-YORS Bank-3 sectors 8-E
10 prove C enters R-YORS and J0 enters the preserved stock guest
11 prove first use with help, FF/FF/FF config, STR8 return, cold C, and J0
```

Archive, onboard copy, erase, installation, directory enrollment, backup
rotation, and FNV/AP search enrollment are separate state transitions. No
successful earlier transition silently authorizes the next one.

Stages 4-11 are host-built or procedurally specified but not yet accepted on a
stock board. Keep an
external programmer and a known-good full-device image available. A failed
Bank-3 top sector has no onboard software recovery path after RESET or power
loss.

## Hardware references

- [WDC W65C02SXB product page](https://wdc65xx.com/single-board-computers/w65c02sxb/)
  describes the 32K SRAM, 128K flash, upper-32K mapping, and VIA-controlled
  bank overlays.
- [WDC W65C02EDU product page](https://wdc65xx.com/single-board-computers/w65c02edu/)
  defines EDU as an expansion board for W65C02SXB. Its optional/unpopulated
  devices are outside this migration profile.
- [Microchip SST39SF010A data sheet](https://ww1.microchip.com/downloads/aemDocuments/documents/MPD/ProductDocuments/DataSheets/SST39SF010A-SST39SF020A-SST39SF040-Data-Sheet-DS20005022.pdf)
  is authoritative for the `$BF/$B5` product ID, ID entry/exit, 4K sector
  erase, byte-program, and polling command sequences.
