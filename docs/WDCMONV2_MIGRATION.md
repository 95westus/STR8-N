# Stock WDCMONv2 to STR8-N Migration

This is the short onboarding rail for a stock WDC W65C02SXB, either alone or
with the W65C02EDU expansion board installed. W65C02EDU is an add-on for the
SXB, not a standalone CPU board. The v1.29 already-preserved-B0 path is
accepted on a physical W65C02SXB/EDU. The erased-B0 copy branch remains
pending for v1.29. The accepted v1.28 run remains historical hardware evidence;
the longer archive path remains available as optional owner-local evidence.

Current status:

```text
board-accepted                read-only four-bank inventory and selected-bank export
board-accepted                local BIN/S19/receipt extraction and validation
board-accepted                binary WDCMONv2 load/readback/execute host bridge
v1.28 accepted; v1.29 pending guarded B3 -> erased B0 copy and exact verify
board-accepted                external 4096-byte v1.29 BIN receive and B3:F install
board-accepted                v1.29 first boot and RESET return
board-accepted                explicit D0 65/WDCV2 adoption, selector 0, J0, and RESET return
separate optional procedure   load HIMON C-E and ASM-F2 8-B component slices
```

The archive artifact remains an optional read-only map/dump tool. It has no
flash unlock, erase, or byte-program sequence. A factory board does not have
to run that extended evidence path before using the minimal migrator: the
write-capable RAM program itself requires erased B0, copies all of B3 into B0,
and proves the complete copy before changing B3:F.

## Factory-board minimal path

Extract and optionally verify the migration kit, connect the board, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\STR8-iN65-LOADER.ps1
```

This is the compact default presentation. Add `-Details` to show the BIN hash,
T48 offset, bank policy, and evidence paths before the port is opened. Both
modes retain the same complete raw transcript and timestamped host event log.
The extracted package's `QUICKSTART.txt` is the short operator card.

The wrapper enumerates serial ports and asks for the COM port when `-Port` is
omitted. It opens and holds that port, then asks for a physical RESET. Reset
the board and press Enter in PowerShell. After board identity, flash identity,
B3 hashing, and the B0 policy check, an erased B0 requires this exact
confirmation:

```text
COPY B3 TO B0
```

It then copies and exactly verifies all eight B3 sectors in B0. When the board
prints `SEND STR8-N TOP BIN; 4096 BYTES; START $F000`, press Ctrl+U once. The
host sends the packaged `STR8-N-v1-29.bin`; the RAM loader requires exactly
4096 bytes and verifies its full build-time FNV. It then requires the separate
exact confirmation `INSTALL STR8-N 1.29` before replacing only B3:F.
That same BIN can be programmed by a T48 at device offset `$1F000`, used as a
logical `$F000` STR8-N top image, or supplied to the guarded top updater.

The canonical image deliberately starts with an empty Bank-3 directory. After
the first verified STR8-N 1.29 boot, select `S`, enter `L`, and press Ctrl+D to
send `STR8-iN65-BANK-MAINT-2000.s19`. In Bank Maintenance enter `D`, then enter
Bank `0`, type `65`, and description `WDCV2`. Inspect the exact proposed D0
record and type `ADOPT B0`.
The resulting Bank-3 directory record must read:

```text
D0 65 WDCV2 FFFF FCFFFFFF
```

Only then test reset selector `0`, shell `J0`, and physical RESET return to
STR8-N. Bank 0 remains an opaque 32K guest; its directory entry is physically
in Bank 3 at `$FFB0-$FFBF`. B1 and B2 are never selected as migration
destinations.

The PowerShell bridge remains the terminal while the two Ctrl-key transfers
run. After the adoption proof, enter Ctrl+] to leave it and connect minicom,
Tera Term, PuTTY, or another serial terminal at 115200 8N1 if desired.

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
BUILD/v1.29/s19/str8n-v1.29-wdcmonv2-archive-2000.s19
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
BUILD/v1.29/s19/str8n-v1.29-wdcmonv2-install-2000.s19
```

It is a compact RAM image with S9 `$2000`; the current build ends below
`$2A00`. The loader receives the canonical 4 KiB top into `$4000-$4FFF` only
after the B3-to-B0 copy has passed its whole-bank and byte-exact proofs. The
candidate is not embedded in the loader S19.

For publication from the standalone STR8-N checkout, build the explicit
allowlisted kit:

```text
make wdcmonv2-package
```

This produces
`BUILD/v1.29/str8n-v1.29-wdcmonv2-str8n-migration-kit.zip`. It contains the
archive and loader S19 files, the production Bank Maintenance S19, the exact
4K STR8-N BIN and matching S19, source, binary-monitor
host bridge, extractor, operator documents, license, and a self-verifier.
It contains no R-YORS, HIMON, or ASM-F2 payload.
It contains neither WDCMONv2 firmware nor locally extracted bank archives.
After extracting it, `VERIFY-PACKAGE.ps1` is available for package verification. The
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
  -ImagePath .\ARTIFACTS\STR8-iN65-ARCHIVE-2000.s19 `
  -TranscriptPath .\LOCAL\stock-b0-b3-capture.log
```

`-ProbeOnly` performs reset/synchronization and `$0C` identity only, then
closes the port. It issues no RAM or flash command. Use it to distinguish the
board from another FTDI COM device before naming an image. The full bridge
then performs this fixed sequence:

```text
validate every S-record checksum, density, $2000-$7AFF range, and S9 entry
pulse DTR using the stock WDC reset sequence unless -NoReset is explicit
settle for 1000 ms and discard reset-startup RX before binary synchronization
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

If the host/FTDI path changes reset state when the COM handle opens or closes,
use `-NoReset -PhysicalResetGate`. The bridge opens and holds the port, asks
the operator to perform physical RESET, waits for ENTER, discards startup RX,
and only then begins binary synchronization on the same open handle.

Some stock images expose their binary synchronization window too briefly for
that manual gate. In that case use `-NoReset -PhysicalResetArmSeconds 30` (up
to 120 seconds). The already-open bridge repeatedly attempts `$55 $AA` in
short bounded windows while the operator presses physical RESET, stops at the
first `$CC`, and then requires the exact `$0C` board identity. The arm mode and
manual gate are mutually exclusive; neither toggles DTR.

`-NoReset -TerminalOnly` opens the same raw terminal without a WDCMON probe,
RAM image, or reset operation. It is intended for an already-running ASCII
STR8 session. `-TransferPath` and `Ctrl+U` remain available, so an installed
STR8 `L` command can receive a host-verified S19 without reopening the port.
The mode cannot be combined with probe, listener, physical-reset, or
`-NoTerminal` options.

For a power-cycle transcript when Windows may remove and recreate the COM
device, `capture_wdc_serial_reconnect.ps1` is receive-only. It retries the
named port until its deadline, keeps TX/DTR/RTS disabled, writes an optional
raw capture, and reopens after a disconnect. It does not identify the board or
alter RAM/flash; use it only as the final boot-output evidence rail.

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
is explicit, creates their parent directories, reads/hashes the optional
transfer file, and opens both evidence files with live handles. Without
`-Force`, exclusive create semantics also reject a file that appears after the
initial check. Evidence-path and permissions failures therefore occur before
the serial reset/synchronization, and necessarily before command `$06` hands
control to RAM.

If probe synchronization times out, stop binary traffic. A diagnostic
`-ListenOnlySeconds 5` run may use the same `-Port` and optional
`-TranscriptPath`. It applies the selected DTR reset policy and captures RX,
but reports `TX=0 BYTES` and cannot query, load, execute, or alter flash. Zero
received bytes still does not identify the target; the operator must check the
physical board, power, cable, reset behavior, and COM assignment.

For the write-capable installer, load only the STR8-N migration program:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 `
  -Port COM5 `
  -ImagePath .\ARTIFACTS\STR8-iN65-LOADER-2000.s19 `
  -TransferPath .\ARTIFACTS\STR8-N-v1-29.bin `
  -Transfer2Path .\ARTIFACTS\STR8-iN65-BANK-MAINT-2000.s19 `
  -TranscriptPath .\LOCAL\install-capture.log
```

The first transfer is the exact production top BIN and the second is the
production Bank Maintenance S19 used after the first boot. No Bank-0 guest
payload is declared or transferred during migration. A C terminal/
front end may implement the same state machine: binary sync/identity/write/read/execute,
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

When taking the optional extended archive evidence, do not encode one answer
before inventory. Export and retain the banks relevant to the observed board:

- On an untouched stock board, the executing WDCMONv2/SPI image is expected
  in Bank 3. Export Bank 3 before any migration work.
- On an established multiboot layout, WDCMONv2 may already be retained in Bank
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

## Seed STR8-N from the factory board

The minimal path reaches this step directly through
`MIGRATE-WDC-TO-STR8N.ps1`; an optional archive run may precede it without
changing the installer policy.

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

The installer does not carry a modified migration top. It receives the exact
canonical STR8-N v1.29 BIN supplied in the release package. Its configuration
bytes are:

```text
$FFF0 WORK sector        $1E  Bank 1 sector E
$FFF1 top-backup sector  $1F  Bank 1 sector F
$FFF2 FNV bank policy    $FF  automatic external search disabled
$FFF3-$FFF9              $FF  unassigned
```

These configuration bytes do not write or initialize B1/B2 during migration;
they are only the resident's later maintenance defaults. The Bank-3 directory
at `$FFB0-$FFEF` is erased in the canonical BIN. Banks 0-2 remain opaque, and
Bank Maintenance owns the separate D0 enrollment transaction:

```text
1  boot and verify STR8-N 1.29 from Bank 3
2  load the packaged production Bank Maintenance S19 through `L`
3  enter `D` and inspect the proposed Bank-3 directory record for opaque B0
4  require `D0 65 WDCV2 FFFF FCFFFFFF`
5  type the exact `ADOPT B0` confirmation
6  verify D0, selector `0`, shell `J0`, and physical RESET return
```

Adopting D0 writes directory metadata only in protected Bank-3 sector F. It
does not modify or interpret Bank 0, and it does not authorize any B1/B2 write.

The production STR8-iN/65 v1.29 RAM menu, its B0 adoption defaults, and the exact
Bank Main `E` then `R` procedure for erasing B0 and clearing D0 are documented
in [STR8_IN65_BANK_MAINTENANCE.md](STR8_IN65_BANK_MAINTENANCE.md). That image
does not invent the still-undefined VTOC or combine role assignment with
directory enrollment.

The later `$FFF2=$A6` proposal is another separate policy transaction. It
enrolls B1/B2 for automatic FNV/AP search while continuing to exclude retained
WDCMONv2 in B0. Until that transaction is implemented and accepted, `$FFF2=FF`
means no automatic external-bank search.

The ordinary `I` transaction used below does not require either optional role.
Operations that need WORK or top-backup storage remain unavailable until Bank
Maintenance completes and verifies their assignments.

After loading and starting the installer at `$2000`, expect:

```text
WDCMONV2 -> STR8-N 1.29 MIGRATION
B3 STOCK -> B0; STR8-N 1.29 -> B3:F
NO RESET/NMI/POWER DURING ACTIVE WRITE
FLASH ID=BF/B5
STOCK B3 FNV1A=xxxxxxxx
TYPE COPY B3 TO B0>
```

The software-product-ID gate accepts only Microchip/SST manufacturer `$BF`
and SST39SF010A device `$B5`. The installer exits product-ID mode before
continuing. An unknown device halts without erase/program activity.

Enter the exact migration text once. If B0 is erased, the copy begins
automatically:

```text
COPY/VERIFY B3 -> B0 ........
```

Eight dots mean eight B0 sectors were erased, programmed, and compared. The
installer then recomputes B0's whole-bank FNV and requires it to equal the
original B3 hash, followed by an independent byte-for-byte comparison of all
32K. A matching FNV is only a prefilter; it never proves identity by itself.
If B0 was already byte-identical, the copy is skipped, making an interrupted
pre-top-write run safely resumable. Used, different B0 is refused.

Before the top write, the host validates an exact 4096-byte input and the RAM
loader receives those bytes into `$4000-$4FFF`. The board checks the complete
received candidate with 32-bit FNV-1a against its build-time value; a short or
mismatched transfer cannot authorize B3:F erase. The board then requires
`INSTALL STR8-N 1.29`; only that second exact confirmation permits B3:F erase
and replacement. If program/verify
fails while RAM is still executing, `R` retries the verified received candidate
and `O` restores the old top sector from proven B0:F. A success selects B3 and
jumps through its new RESET vector.

Power loss during B3:F erase/program remains an external-programmer recovery
case. The board has no alternate boot jumper and cannot execute the B0 copy
after an invalid B3 RESET vector prevents startup.

STR8-N v1.29 production startup includes the EDU quiet-start work: it forces
the buzzer control inactive and configures/clears the LED outputs before normal
console initialization. These startup changes do not turn the LEDs into a
write-progress indicator; the terminal's active-write message and the test-card
power exclusion remain the authoritative do-not-power-off indication.

At the first STR8-N reset selector choose `S`, load Bank Maintenance, and adopt
D0 as described above. The migration is complete only after the resulting D0
record, selector-0/`J0` retained-stock launch, and physical-reset return proof.
Do not install a combined R-YORS payload as part of this transaction.

If the user later wants HIMON and ASM-F2, follow
[HIMON_ASMF2_AFTER_STR8N.md](HIMON_ASMF2_AFTER_STR8N.md). That procedure loads
the two component slices separately and begins only after migration acceptance.

## Migration transaction and acceptance state

The retained v1.29 transcript accepts the already-preserved-B0 continuation of
these minimal gates:

```text
1  identify supported board and flash geometry
2  load and read back the complete RAM installer byte-exact
3  require B0 erased or already byte-identical; otherwise refuse
4  require COPY B3 TO B0, then whole-bank-compare the preserved copy
5  receive exactly 4096 canonical STR8-N bytes and validate full FNV before erase
6  require INSTALL STR8-N 1.29, install/verify B3:F, and start v1.29
7  load production Bank Maintenance and explicitly adopt D0 65/WDCV2 in Bank 3
8  prove selector 0 and J0 enter the preserved stock guest
9  prove physical RESET from the B0 guest returns to STR8-N 1.29
```

The run entered step 4 with B0 already byte-identical to B3, so it proved the
exact comparison and safe skip but did not execute the erased-B0 copy. A final
v1.29 factory-board transcript must still exercise `COPY B3 TO B0` before the
whole consumer path is called complete.

Optional extended evidence inventories B0-B3 without writing and exports the
stock image to checked owner-local BIN/S19/receipt files. Those archive steps
remain board-accepted but are not prerequisites for the erased-B0 factory
path.

The canonical migration top has an empty directory. The packaged production
STR8-iN/65 Bank Maintenance image performs the required, separately confirmed
D0 adoption and remains the owner of later rename, reclaim, erase, and
search-flag operations.

Archive, onboard copy, erase, installation, later directory maintenance,
backup rotation, and FNV/AP search enrollment are separate state transitions.
No successful earlier transition silently authorizes another destructive
operation.

The earlier v1.28 migration stages are accepted on the recorded board. The
changed v1.29 external-BIN receive, quiet-start, and postboot D0-adoption path
must not be called board-accepted until its new transcript is captured.
Keep an external programmer and a known-good full-device image available. A
failed Bank-3 top sector still has no onboard software recovery path after
RESET or power loss.

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
