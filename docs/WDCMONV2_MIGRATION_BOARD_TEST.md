# WDCMONv2 Migration Board Test

Status: pending physical W65C02SXB acceptance; W65C02EDU may be installed.

This card proves the stock-monitor-to-STR8-N path one hazard at a time. Do not
combine the read-only acceptance and first destructive run merely to save a
reset.

## Exact host-built candidates

```text
BUILD/v1.23/s19/str8n-v1.23-wdcmonv2-archive-2000.s19
SHA-256 5E0811701830821022EDE13B7B8E5FA26392F0CAF42D3FB8993C7CDFA5698F5C
RAM $2000-$250E; S9 $2000; read-only

BUILD/v1.23/s19/str8n-v1.23-wdcmonv2-install-2000.s19
SHA-256 FF3F95DF40D87146384BDAB54DC61E07A09DFF30BEA95A07D47BA0888DF81206
RAM $2000-$4FFF; S9 $2000; flash-writing

BUILD/v1.23/bin/str8n-v1.23-bank3-f000-ffff.bin
SHA-256 0BB457D7BD17E3AC084B19C0F23DCE546F0A49CDB8E44842F0FB3F832C660DF1
canonical top source

BUILD/v1.23/bin/str8n-v1.23-wdcmonv2-bank3-f000-ffff.bin
SHA-256 3C162EDA001FB9EC6C4E5E1FCD1E1C5238DC4D5A36715B1876BD96728265139A
exact carried migration top; roles patched to FF/FF

../R-YORS/SRC/BUILD/s19/ryors-v1.2-himon-asm-bank3-8-e.s19
SHA-256 3212469D695EFC7228EB2DBABAF05E09234AB58B2925AA7D6DA8896323E8278A
Bank 3 $8000-$EFFF; S9 $C000

tools/wdcmonv2/start_wdcmonv2_ram.ps1
SHA-256 7881B2C685636B74481FD3F88C012120EB5A14280F4EBAABEBA5CEB67618DFF6
binary WDCMONv2 load/readback/execute plus retained terminal handle
```

Recalculate and update this card if any artifact changes. Do not accept a
transcript produced with a different hash under these labels.

When using the published migration ZIP, first record its separately published
SHA-256, extract it, and require `VERIFY-PACKAGE.ps1` to report `VERIFIED`.
The package manifest and allowlist must both state that WDCMONv2 firmware and
local bank archives are absent.

## Equipment and recovery prerequisites

```text
WDC W65C02SXB, optionally carrying W65C02EDU, with stock WDCMONv2 in Bank 3
stable board power and FTDI connection
terminal/front end capable of saving the complete byte stream
Windows PowerShell host bridge from the verified migration kit
T48 or equivalent external programmer ready
known-good complete 128K device readback saved before destructive testing
NMI button protected from accidental use
```

W65C02EDU alone is not a target; it is an expansion board plugged onto the
SXB. Record whether EDU is installed and what external modules are attached.
The migration does not exercise EDU peripherals, and a passing migration is
not evidence that optional RTC/SPI SRAM/ADC/buzzer/LED functions work.

Record board revision, flash part marking, selected COM port, baud/transport
settings, host-bridge hash, and exact command line in the retained transcript.
The reference bridge defaults to 115200 8N1, RTS/CTS and the WDC reset/DTR
sequence. It keeps the port open when WDCMONv2 command `$06` hands control to
the RAM application's ASCII terminal.

## Phase A: read-only archive acceptance

1. Read the complete 128K device with the external programmer. Save its
   SHA-256 as `PRE_DEVICE_SHA256`.
2. Extract the migration ZIP and require `VERIFY-PACKAGE.ps1` to pass. List
   available ports, then identify the candidate without loading RAM:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 -ListPorts

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 -Port COM5 -ProbeOnly
```

   Require `WDCMONV2 PROBE = PASS; NO RAM OR FLASH COMMAND ISSUED`. If the
   strict 12-byte identity is not `SXB2`, retain the hexadecimal refusal and
   stop; do not bypass the board-family gate merely because the device is FTDI.
   A timeout may be followed by one receive-only diagnostic:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 `
  -Port COM5 -ListenOnlySeconds 5 `
  -TranscriptPath .\LOCAL\wdcmon-listen.bin
```

   Require `TX=0 BYTES`. Whether RX is zero or contains another firmware's
   banner, do not continue Phase A until the operator presents a target that
   passes strict `-ProbeOnly` identity.

3. Start capture and launch the archive app in one operation, substituting the
   actual port:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 `
  -Port COM5 `
  -ImagePath .\ARTIFACTS\str8n-v1.23-wdcmonv2-archive-2000.s19 `
  -TranscriptPath .\LOCAL\stock-b0-b3-capture.log
```

4. Require `BOARD = SXB2`, the expected image SHA-256/range/S9, one progress
   dot per verified chunk, `RAM READBACK = BYTE-EXACT`, and `EXECUTE = $2000`.
   Any binary sync, identity, write acknowledgement, or readback failure stops
   this phase; do not fall through to a guessed command or address.
5. Require the archive title and complete B0-B3 inventory in the same session.
6. At the prompt, enter `0` to export the user's present Bank 0, then enter
   `3` to export the executing stock bank.
7. Confirm that the raw receive transcript was saved as
   `stock-b0-b3-capture.log`.
8. Enter `Q`, then `Ctrl+]` to close the reference terminal. Press physical
   RESET and prove stock WDCMONv2 returns. A reset caused by closing the COM
   handle is not by itself accepted as the physical-RESET proof.
9. Extract the archive:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\extract_wdcmonv2_archive.ps1 `
  -TranscriptPath .\stock-b0-b3-capture.log `
  -OutputDirectory .\LOCAL\stock-board `
  -Bank 0

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\extract_wdcmonv2_archive.ps1 `
  -TranscriptPath .\stock-b0-b3-capture.log `
  -OutputDirectory .\LOCAL\stock-board `
  -Bank 3
```

10. Require `WDCMONV2 ARCHIVE = VERIFIED` twice. Retain both sets of BIN, S19,
    and receipt files, including an erased B0 image if that is its actual state.
11. Confirm each receipt FNV equals its inventory row and W2R-END FNV.
12. If B0 is used and differs from B3, do not proceed to Phase C with this
    first installer; its local archive is evidence, not erase authorization.
13. Read the complete device again with the programmer and require the same
    128K SHA-256 as `PRE_DEVICE_SHA256`.

Phase A acceptance:

```text
WDCMONv2 reports SXB2 through command $0C
archive S19 loaded with command $02 and read back byte-exact with command $03
S9 $2000 started with command $06 without closing the COM handle
all four bank rows printed without crash
selected bank export contains 1024 S1 plus one S9
host extractor verifies checksum, density, RESET, and FNV
physical RESET returns to WDCMONv2
complete device readback is byte-identical before/after
```

## Phase B: installer refusal gates

Keep the external programmer image ready. These tests must not reach an active
flash operation.

1. Load/start the seed installer with the same host bridge and a new transcript:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 `
  -Port COM5 `
  -ImagePath .\ARTIFACTS\str8n-v1.23-wdcmonv2-install-2000.s19 `
  -TransferPath .\ARTIFACTS\ryors-v1.2-himon-asm-bank3-8-e.s19 `
  -TranscriptPath .\LOCAL\refusal-capture.log
```

   Require the installer S19 hash/range/S9 and byte-exact RAM readback before
   accepting any installer output.
2. Require `FLASH ID=BF/B5`. Any other ID is an accepted refusal, not a reason
   to bypass the gate.
3. At the archive prompt, enter one wrong hexadecimal digit.
4. Require `REFUSE: LOCAL ARCHIVE TOKEN MISMATCH` and a RAM halt.
5. Enter `Ctrl+]` to close the terminal, then press physical RESET and prove
   stock WDCMONv2 returns.
6. Reload/start the installer with a new transcript filename and enter the
   exact archive token. Never use `-Force` to overwrite an earlier refusal
   transcript merely to reuse the example command.
7. If B0 is used and different, require
   `REFUSE: B0 USED AND DIFFERENT; NOTHING WRITTEN`, then stop this board test.
8. If B0 is erased, enter anything other than `COPY B3 TO B0`; require cancel
   and reset back to WDCMONv2.
9. If B0 already equals B3, enter anything other than
   `INSTALL STR8-N 1.23`; require cancel and reset back to WDCMONv2.
10. Programmer-read the device again and require `PRE_DEVICE_SHA256`.

## Phase C: stock preservation and STR8-N seed

Run only if Phase A passed and B0 is erased or already identical to B3.

1. Load/start the seed installer with the Phase-B command, changing the
   transcript name to `seed-install-capture.log`. Require byte-exact RAM
   readback again; no earlier RAM load is carried across RESET.
2. Require flash ID `BF/B5` and the same B3 FNV as the verified local receipt.
3. Type the exact `ARCHIVE xxxxxxxx` token.
4. If prompted, type exact `COPY B3 TO B0`.
5. For an erased B0, require eight progress dots followed by
   `B0 == ORIGINAL B3 VERIFIED`.
6. For an already-identical B0, require the same verified line with no copy
   prompt and no copy dots. In both paths this line means both the FNV prefilter
   and the complete byte-for-byte B0/B3 comparison passed.
7. Type exact `INSTALL STR8-N 1.23`.
8. Do not touch RESET, NMI, or power while B3:F is active.
9. Require `STR8-N VERIFIED; RESET`, followed by the STR8-N reset banner and
   selector.
10. Select `S` and remain at `STR8-N>`.

If the active top write reports failure, retain the complete transcript. Use
`R` to retry the carried candidate or `O` to restore B0:F while the RAM
installer is still alive. Do not press RESET with a failed B3:F.

Phase C seed acceptance:

```text
B0 full-bank FNV equals the original stock B3 receipt
B1 and B2 have not been written
B3:F reads as STR8-N v1.23
B3 $FFF0/$FFF1 read FF/FF
physical RESET enters STR8-N
```

## Phase D: prove the stock guest

At `STR8-N>`, enter `J0`. WDCMONv2 is a binary host monitor, not an ASCII
command prompt, so an absent banner is not a failure. Press `Ctrl+B` once in
the still-open reference terminal. Require:

```text
WDCMON PROBE = SXB2; HW=...; WDCMON=...
```

This sends the public `$55,$AA,$0C` board-info exchange and proves that Bank
0's RESET vector reached the preserved monitor. Do not press `Ctrl+B` while
STR8-N, HIMON, or a normal ASCII application owns the channel; those bytes
would be application input.

If the identity probe fails, record whether B0 remained selected and whether
the CPU halted or remapped. A byte-exact stock copy can still fail as an
in-place guest if WDCMONv2 reselects its factory bank during startup. Keep B0
reserved and keep the local archive; Phase D and final migration acceptance
remain pending even though preservation and the R-YORS install may be intact.

Press physical RESET. Require STR8-N again, then select `S`.

## Phase E: install R-YORS through STR8-N

At `STR8-N>`:

```text
I
B0-3: 3
RANGE: 8-E
TYPE: 5A
DESC: RYORS
I B3 8-E WRITE? Y: Y
S19
```

Press `Ctrl+U` once to send the exact predeclared R-YORS S19 listed above.
Require:

```text
......COMMIT? Y: Y.
OK
```

Press physical RESET, select `C`, and require the R-YORS/HIMON banner and
prompt. Reset once more and use `J0` to prove the stock guest remains intact.

## Final readback and retained evidence

Use the external programmer to save a post-migration 128K readback. Verify:

```text
physical $00000-$07FFF   equals the original stock B3 BIN
physical $10000-$17FFF   equals PRE device Bank 2
physical $08000-$0FFFF   equals PRE device Bank 1
physical $18000-$1EFFF   equals the accepted R-YORS 8-E payload
physical $1F000-$1FFFF   equals migration-configured STR8-N top candidate
```

Retain:

```text
pre/post 128K hashes
archive BIN/S19/receipt
exact artifact hashes
complete Phase A-E terminal transcript
observed bank inventory and FNV values
stock J0 WDCMON binary identity proof and R-YORS C banner
any failure/retry/restore transcript
operator acceptance statement
```

Do not mark the migration path hardware-accepted until every applicable row
above has direct evidence.
