# WDCMONv2 Migration Board Test

> [!NOTE]
> Historical v1.28 acceptance record. Retain the transcript and hashes for
> provenance; use the v1.29 migration guide and artifacts for a current board.

Status: the operator-authorized Phase A programmer-hash waiver remains
recorded below. The STR8-iN/65 v1.28 cold-start image, physical RESET,
cold-power start, retained-stock B0 enrollment, and repeated `J0` launch are
board-accepted. The one-command factory WDCMONv2-to-STR8-N 1.28 consumer
migration is also board-accepted from an erased-B0 factory baseline, including
the operator-observed CS0-CS3 chase, retained WDCMONv2 launch, and final
physical-RESET return to STR8-N. Canonical v1.28 is byte-identical to the
accepted top except for the documented migration-role policy. W65C02EDU may
be installed. The first 2026-08-29 v1.29 already-preserved-B0 run below accepts
the install and launch mechanics while retaining its entered type `65` as
historical evidence. The following factory-baseline rerun accepts the complete
v1.29 path with erased-B0 `COPY B3 TO B0`, exact D0 `FF WDCV2`, reset selector
`0`, shell `J0`, and physical-RESET return after both launches. A 2026-08-30
board #3 run repeats the factory WDCMONv2-to-STR8-N 1.29 path on COM3 with D0
`FF WDCV2`; it is retained as cross-board migration success evidence.

## 2026-08-28 first stock-board run: cold-reset failure retained

The first physical W65C02SXB/EDU run used board identity
`SXB2; HW=3.00; WDCMON=2.00`.  The original complete-device readback was
`131072` bytes with SHA-256
`E22F0D0279797EB6DEC175CA634E692A8EAA61974E93DC3C7EA2E4F6E51C86C7`.
The operator explicitly waived Phase A's final same-hash programmer readback;
that waiver prevents full Phase A acceptance but does not change the captured
read-only results below.

The archive application loaded and read back byte-exact, inventoried B0-B2 as
erased, and inventoried B3 as `FNV1A=1249E1F3 RESET=F818`.  Bank 0 and Bank 3
exports both passed the host extractor.  The wrong-token Phase B run returned
`REFUSE: LOCAL ARCHIVE TOKEN MISMATCH`; the correct-token/cancel run returned
`CANCELLED; NOTHING FURTHER WRITTEN`.

The host/FTDI reset path was not reliable on this board.  The bridge therefore
gained a same-open-handle `-NoReset -PhysicalResetGate` path.  That path passed
strict board identity and byte-exact installer RAM loading before Phase C.
Phase C printed:

```text
COPY/VERIFY B3 -> B0 ........
B0 == ORIGINAL B3 VERIFIED
ERASING/PROGRAMMING B3:F
STR8-N VERIFIED; RESET
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.23
0-2 C W S: ......
NO
I L C W J
STR8-N>
```

The first face above followed the installer's software `JMP ($FFFC)`, not a
hardware reset.  Subsequent physical RESET and power-cycle attempts produced
no STR8-N bytes, including with COM4 already open and DTR disabled.

The complete post-install programmer readback was
`06A8B688A01B18A8C50EAB868AA10B94B782C7A2C71DA897DC11C3F6309191F5`.
Byte comparison proved B0 equal to the original stock B3, B1/B2 erased,
B3:8-E unchanged, and B3:F equal to the carried STR8-N candidate.  B3 config
was `FF FF FF`; vectors were `D2 F0 00 F0 E6 F0`, including RESET `$F000`.

For the control, XGpro write/readback file `X.bin` was byte-exact with the
original complete-device backup and the same SHA-256.  Physical RESET then
printed the complete `W65C02SXB + EDU Kit Rev 1.0` startup face and reported
OLED, RTC, SPI SRAM, ADC, and CardKB `OK`.  This proves the board, flash socket,
physical reset, clock/power, and ASCII console path on the restored stock
image.  The migration remains unaccepted: the failure is isolated to true
cold-reset entry of the STR8-N candidate, before its first visible `RESET`.
The software-jump pass must not be cited as physical-reset proof.

## 2026-08-28 STR8-iN/65 cold-reset candidates

The W65C22S reset contract makes its peripheral pins inputs; their initial
bus-held level is not initialized by the chip.  Board pull-ups expose Bank 3
while the second VIA remains in that reset/input state.  A reset path must not
rewrite PCR `$7FEC` merely to make the selected bank explicit while it is
executing from the selected flash window.

The first separately gated STR8-iN/65 candidate wrote Bank-3 PCR value `$EE`
before IVY or console initialization.  Its top SHA-256 was
`E52D7AF7AF40272A5F6E0B57AAD599D52F70FEE1100F3B098EA879D4978B6979`.
The guarded RAM installer loaded/read back byte-exact, copied stock B3 to B0
and verified it, programmed/verified B3:F, and produced the complete v1.23
face after its software jump.  A subsequent physical reset emitted only byte
`$FF`; no later bytes arrived.  A separate receive-only power-cycle window
captured zero bytes.  That candidate is rejected.

Comparison with the known-good stock B3 reset path at `$F818` showed that
stock performs a long PIA/peripheral sweep before its first VIA/FT245 access.
The second candidate added a calibrated delay after IVY RAM initialization
and before any I/O, then wrote PCR `$EE` and initialized the FT245-facing VIA.
Its carried top SHA-256 was
`ACE1465280066DE93B35A11E7022CC7068DE94E17464CCC454F5CF5A263F28A5`.
It passed installation, software-jump boot, and a true physical RESET:

```text
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.23
0-2 C W S: ......
NO
I L C W J
STR8-N>
```

Its cold power-up nevertheless emitted zero bytes while COM4 remained open.
A physical RESET after that silent cold start immediately printed the same
complete face.  This isolates the failure to first-power PCR/bank-latch state,
not the ROM body, FT245 console, or reset switch.  Candidate 2 is rejected.

Candidate 3 retains the calibrated pre-I/O delay but removes every reset-time
PCR write.  Software bank selection remains unchanged.  Host checks retain
all fixed resident ABI addresses and vectors.  The special resident occupies
`$F000-$FD55`, leaving six bytes before the fixed worker at `$FD5C`; RESET
remains `$F000`.  The canonical v1.23 image remains byte-identical at SHA-256
`0BB457D7BD17E3AC084B19C0F23DCE546F0A49CDB8E44842F0FB3F832C660DF1`.

```text
BUILD/v1.23/bin/str8n-v1.23-str8-in65-wdcmonv2-bank3-f000-ffff.bin
SHA-256 F22AF53374F2D92F832C44DFC27B223FD824F1714F9BCEB0077FB8EB88B89DBF
roles FF/FF; FNV1A F46D7581; RESET $F000; host layout check PASS

BUILD/v1.23/s19/str8n-v1.23-str8-in65-wdcmonv2-install-2000.s19
SHA-256 1B44E32A447CF8FA8334085A6CB1502897F1533A4A4110587E73A05B3B88CCE2
RAM $2000-$4FFF; S9 $2000; carries candidate 3 only

BUILD/v1.23/s19/str8n-v1.23-str8-in65-top-update-2000.s19
SHA-256 EE6FC15B5C23F4E116D1D646E09BFE441AC25EDA2D4596E48D51DFEC9429768C
RAM $2000-$4FFF; S9 $2000; candidate-3 B3:F updater only

BUILD/v1.23/local/str8n-v1.23-str8-in65-cold-reset-test-128k.bin
SHA-256 E511ECF25608EDDB047696D608BE920563ECD549AD1382C44351C30B4F0579A0
base X.bin SHA-256 E22F0D0279797EB6DEC175CA634E692A8EAA61974E93DC3C7EA2E4F6E51C86C7
only file offsets $1F000-$1FFFF replaced; owner-local, never package/publish
```

The candidate-3 seed installer was first loaded through the running STR8 `L`
service.  It saw the already-installed candidate in B3 rather than stock and
was deliberately stopped by its archive-token gate before any flash write.
The variant-only top updater was then loaded instead.  It verified the current
B3:F rollback copy in B1:F (`SUM=$14B1`), erased/programmed only B3:F, verified
candidate 3, and printed the full face after its own reset.

An independent physical RESET printed the complete face.  A subsequent
receive-only cold-power test used automatic COM4 reconnection with TX=0,
DTR=0, and RTS=0 and captured the same complete face.  The exact 111-byte raw
power-cycle capture has SHA-256
`2F4F9308CFF491047A3C797860A71DA6044E2758ECDE75EAEC6B92BB3A27DB3B`.
Candidate 3 therefore passes both required hardware gates.

Candidate 4 changes presentation only.  In the STR8-iN/65 build, the first
six quarantine ticks and six live-key ticks retain their exact delays and key
policy, but the `WAIT...` and dot pulse messages and their dispatch code are
omitted.  Canonical v1.23 remains unchanged.  The special resident shrank by
21 bytes to `$F000-$FD40`, increasing the fixed-worker margin to 27 bytes.

```text
BUILD/v1.23/bin/str8n-v1.23-str8-in65-wdcmonv2-bank3-f000-ffff.bin
SHA-256 8A2F12DB6CB53B95F07BB5DDA0BB2FA8E227456DDFF92532D921521D1E40611F
roles FF/FF; FNV1A A212288B; RESET $F000; host layout check PASS

BUILD/v1.23/s19/str8n-v1.23-str8-in65-wdcmonv2-install-2000.s19
SHA-256 4AE8ED686D4CACB6AC104FD9B9E139218D2ACE1665C1DC564AF093C7B7EA9F42
RAM $2000-$4FFF; S9 $2000; carries candidate 4 only

BUILD/v1.23/s19/str8n-v1.23-str8-in65-top-update-2000.s19
SHA-256 565CCCE644B5184098E40982D99ECAD2A44B7595AF3EDC97299CFB8C67A1CBA1
RAM $2000-$4FFF; S9 $2000; candidate-4 B3:F updater only

BUILD/v1.23/local/str8n-v1.23-str8-in65-cold-reset-test-128k.bin
SHA-256 72ABF24A90525851737429D0094F71F901757964BE6F218C880E99C0B03CA44F
base X.bin SHA-256 E22F0D0279797EB6DEC175CA634E692A8EAA61974E93DC3C7EA2E4F6E51C86C7
only file offsets $1F000-$1FFFF replaced; owner-local, never package/publish
```

The variant-only updater replaced B1:F with a verified candidate-3 rollback
copy (`SUM=$1746`), programmed/verified candidate 4 in B3:F, and automatically
booted this expected shortened face:

```text
RESET

STR8-N 1.23
0-2 C W S:
NO
I L C W J
STR8-N>
```

An independent physical RESET reproduced that face.  A receive-only cold
power-up then reproduced it with TX=0, DTR=0, and RTS=0.  The exact 58-byte
raw capture begins with one transient `$FF` byte followed by `RESET`; its
SHA-256 is
`F1DE5368B8A804F21FC1AC6E1956D494BFDDB370BC297F522823EB30D5F9DE39`.
Candidate 4 passes both hardware gates and supersedes candidate 3 as the
active STR8-iN/65 test image.

The operator also reports that a third board of the same stated revisions,
but with no date-code information, did not show the early `WAIT...` text.
Retain that as cross-board timing evidence until that board receives this
accepted candidate.  The active console path is FT245R through a W65C22, not
the W65C51, and no W65C21/W65C22/W65C51 erratum is required to explain the
tested failure.

This card proves the stock-monitor-to-STR8-N path one hazard at a time. Do not
combine the read-only acceptance and first destructive run merely to save a
reset.

## Exact host-built candidates

```text
BUILD/v1.28/s19/str8n-v1.28-wdcmonv2-archive-2000.s19
SHA-256 5E0811701830821022EDE13B7B8E5FA26392F0CAF42D3FB8993C7CDFA5698F5C
RAM $2000-$250E; S9 $2000; read-only

BUILD/v1.28/s19/str8n-v1.28-wdcmonv2-install-2000.s19
SHA-256 21B1E39EA57F4C2DC1D20ACDC9ADECEC1CEE3FF150D10E87200A9D843D15B758
RAM $2000-$4FFF; S9 $2000; flash-writing

BUILD/v1.28/bin/str8n-v1.28-bank3-f000-ffff.bin
SHA-256 9B6720DABCDDB4373FB19A7CEA26D34218F466784C5E54DB687AE2BBFF160058
canonical top; roles 1E/1F; byte-identical to accepted STR8-iN/65 top

BUILD/v1.28/bin/str8n-v1.28-wdcmonv2-bank3-f000-ffff.bin
SHA-256 BDE8414B4BF76E69E33422662D6BD228ADF6775553B50A2955CD813A8CAC922A
exact carried migration top; D0 WDCM2 COMPLETE; roles FF/FF

tools/wdcmonv2/start_wdcmonv2_ram.ps1
SHA-256 4B20AE116D0E3E9A818B9D11D1718C7DC98F553B6C3E82D13EBC03B2ECC1A458
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
  -ImagePath .\ARTIFACTS\str8n-v1.28-wdcmonv2-archive-2000.s19 `
  -TranscriptPath .\LOCAL\stock-b0-b3-capture.log
```

4. Require `BOARD = SXB2`, the expected image SHA-256/range/S9, one progress
   dot per verified chunk, `RAM READBACK = BYTE-EXACT`, and `EXECUTE = $2000`.
   Any binary sync, identity, write acknowledgement, or readback failure stops
   this phase; do not fall through to a guessed command or address. Require the
   automatic `stock-b0-b3-capture.log.events.txt` companion to record the same
   image, board, readback, execute, and completed TX-line facts without
   inserting host events into the raw extractor input.
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
  -TranscriptPath .\LOCAL\stock-b0-b3-capture.log `
  -OutputDirectory .\LOCAL\stock-board `
  -Bank 0

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\extract_wdcmonv2_archive.ps1 `
  -TranscriptPath .\LOCAL\stock-b0-b3-capture.log `
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

## Phase B: minimal installer refusal gate

Keep the external programmer image ready. These tests must not reach an active
flash operation.

1. Load/start the seed installer with the same host bridge and a new transcript:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\TOOLS\start_wdcmonv2_ram.ps1 `
  -Port COM5 `
  -ImagePath .\ARTIFACTS\str8n-v1.28-wdcmonv2-install-2000.s19 `
  -TranscriptPath .\LOCAL\refusal-capture.log
```

   Require the installer S19 hash/range/S9 and byte-exact RAM readback before
   accepting any installer output.
2. Require `FLASH ID=BF/B5`. Any other ID is an accepted refusal, not a reason
   to bypass the gate.
3. At the migration prompt, enter anything except the exact
   `MIGRATE WDC TO STR8-N 1.28` text.
4. Require `CANCELLED: MIGRATION TEXT DID NOT MATCH` and a RAM halt.
5. Enter `Ctrl+]` to close the terminal, then press physical RESET and prove
   stock WDCMONv2 returns.
6. Never use `-Force` to overwrite the refusal transcript merely to reuse the
   example command.
7. If B0 is used and different, require
   `REFUSE: B0 USED AND DIFFERENT; NOTHING WRITTEN`, then stop this board test.
8. Programmer-read the device again and require `PRE_DEVICE_SHA256`.

## Phase C: stock preservation and STR8-N seed

Run when B0 is erased or already identical to B3. Phase A remains the optional
extended map/dump/archive evidence path; it is not a factory-minimal gate.

1. From an extracted kit, run
   `MIGRATE-WDC-TO-STR8N.ps1 -Port COMx`. Require byte-exact RAM readback; no
   earlier RAM load is carried across RESET.
2. Require flash ID `BF/B5` and the same B3 FNV as the verified local receipt.
3. Type exact `MIGRATE WDC TO STR8-N 1.28` once.
4. For an erased B0, require eight progress dots followed by
   `B0 == ORIGINAL B3 VERIFIED`.
5. For an already-identical B0, require the same verified line with no copy
   prompt and no copy dots. In both paths this line means both the FNV prefilter
   and the complete byte-for-byte B0/B3 comparison passed.
6. Do not touch RESET, NMI, or power while B3:F is active.
7. Require `MIGRATION VERIFIED; STARTING STR8-N`, followed by the STR8-N reset banner and
   selector. This first banner follows the installer's software jump through
   the newly written B3 RESET vector; it is not yet the physical-reset proof.
8. Enter Ctrl+] and connect minicom, Tera Term, PuTTY, or another 115200-8N1
   serial terminal.
9. Press physical RESET. Require the STR8-N banner and selector, then choose
   `0`; require the CS0-CS3 chase and working WDCMONv2. Reset again, select `S`,
   enter `J0`, and require the same retained-monitor behavior.
10. Press physical RESET. Require the STR8-N banner and selector again, select
   `S`, and return to `STR8-N>`. Do not accept a DTR transition or software
   jump as this proof.

If the active top write reports failure, retain the complete transcript. Use
`R` to retry the carried candidate or `O` to restore B0:F while the RAM
installer is still alive. Do not press RESET with a failed B3:F.

Phase C seed acceptance:

```text
B0 full-bank FNV equals the original stock B3 receipt
B1 and B2 have not been written
B3:F reads as STR8-N v1.28
B3 $FFF0/$FFF1 read FF/FF
physical RESET enters STR8-N
```

## Phase D: prove the stock guest

At `STR8-N>`, enter `J0`. WDCMONv2 is a binary host monitor, not an ASCII
command prompt, so an absent banner is not a failure. Press `Ctrl+B` once in
the still-open reference terminal. Require:

`J0` is a complete handoff to the preserved Bank-0 system. The expected return
path is the board's physical RESET button, which selects Bank 3 and starts
STR8-N again. Requiring physical RESET here is intentional and by design; it
is not a product defect or migration failure.

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
reserved and keep the local archive; final migration acceptance remains
pending.

Press physical RESET. Require STR8-N again, then select `S`.

## Migration endpoint and optional component loading

Migration ends after Phase D and the persistent D0/`J0` proof below. No
R-YORS payload is an input, acceptance gate, or packaged artifact.

HIMON and ASM-F2 may be added afterward as separate Bank-3 component loads.
Use [HIMON_ASMF2_AFTER_STR8N.md](HIMON_ASMF2_AFTER_STR8N.md); do not merge that
optional procedure into this migration transcript.

## 2026-08-28 Phase G: enroll retained B0 and prove J0 persistence

Phase G used the isolated STR8-iN/65 v1.28 RAM Bank Maintenance image. It did
not assign `$FFF0/$FFF1`, write `$FFF2`, initialize a VTOC, erase a payload
sector, or alter B1/B2.

The first RAM build, SHA-256
`12EFF250F5840EDC8AEB717363534B697FEF1143A1B3726868980C180EFCCD47`,
exposed a host layout defect before any flash command: expanded menu text had
crossed the fixed `$3400` worker origin, so worker bytes followed `Q=QUI` on
the console. The operator entered `Q`; the program returned to STR8-N and no
mutation command had run. This rejected build is retained as failure evidence.

The corrected build shortened only the STR8-iN/65 menu, added a host check for
the complete `Q=QUIT>` terminator, and measured 42 free bytes before `$3400`.
Its identity was:

```text
file     BUILD/v1.28/s19/str8n-v1.28-str8-in65-bank-maint-2000.s19
SHA-256 EE7715238646CDA1BDC4EF943986C1B2AED1A36EB22A7E5D682CE3061DFD5963
range    $2000-$3B15; 6934 bytes; S9 $2000
worker   FFCDB4201C913FC9B3E3F3D438A98940F76967C5E62F843A2DC32CFF1D1AD1B2
```

The complete corrected menu rendered and stopped normally:

```text
STR8-N 1.28 BANK MAINT
D=ADOPT N=NAME R=CLEAR E=ERASE M=MAP F=FLAG C=COPY P=AP Q=QUIT>
```

The operator selected `D` and accepted all migration defaults before typing
the exact commit confirmation:

```text
BANK 0-3 [0]> <Enter>
TYPE 00-FF [FF]> <Enter>
DESC 5 CHARS [AUTO]> <Enter>
TYPE ADOPT B0> ADOPT B0
 OK
```

The immediate `M` readback proved the retained payload and COMPLETE D0 row:

```text
B0 U U U U U U U U
B1 E E E E E E E U
B2 E E E E E E E E
B3 U U U U U U U P

DIR B T DESC ENTRY JOURNAL
D0 FF WDCM2 FFFF FCFFFFFF
D1 FF ..... FFFF FFFFFFFF
D2 FF ..... FFFF FFFFFFFF
D3 FF ..... FFFF FFFFFFFF
 OK
```

After `Q`, resident STR8 accepted `J0`, printed `J B0` without `J FAIL`, and
B0 produced the complete W65C02SXB + EDU initialization and ASCII menu. A
physical RESET then returned through Bank-3 pull-ups to `STR8-N 1.28`. A
second `J0` after that reset again printed `J B0` without `J FAIL`, proving the
directory record persisted independently of the RAM program.

Raw RX and host-action evidence is retained at:

```text
BUILD/v1.28/str8-in65-bank-maint-board-test.raw
BUILD/v1.28/str8-in65-bank-maint-board-test.events.log
BUILD/v1.28/str8-in65-bank-maint-board-test-retry.raw
BUILD/v1.28/str8-in65-bank-maint-board-test-retry.events.log
```

## 2026-08-28 canonical v1.28 promotion

Canonical STR8-N now builds the accepted silent-pulse cold-start sequence as
v1.28. `make str8-in65-promotion-check` proves the canonical and accepted
configured top sectors are byte-identical:

```text
canonical/accepted SHA-256  9B6720DABCDDB4373FB19A7CEA26D34218F466784C5E54DB687AE2BBFF160058
migration top SHA-256       BDE8414B4BF76E69E33422662D6BD228ADF6775553B50A2955CD813A8CAC922A
allowed difference          D0 WDCM2 COMPLETE plus $FFF0/$FFF1
canonical policy            1E/1F (B1:E WORK, B1:F top backup)
migration policy            D0=WDCM2; FF/FF roles (unassigned)
resident                    $F000-$FD40; 3393 bytes; 27-byte worker margin
```

The board transcript proves the promoted resident behavior and the migration
policy image. The host comparison proves canonical uses those same resident
bytes while retaining canonical role defaults. No additional board flash write
was performed for the repository promotion.

## 2026-08-28 factory-baseline reconstruction and consumer migration

To exercise the same preservation prompts as a first-time consumer, merely
copying retained stock B0 back over B3 is insufficient: that leaves B0 used and
byte-identical, so the installer follows its already-preserved path. The
board-lab-only factory restore instead performs this guarded sequence entirely
from RAM:

```text
B0 whole-bank hash/reset validation
B0 -> B3 sectors 8-E, with erase/program/exact readback per sector
B0 -> B3 reset-bearing sector F last
B0 == B3 whole-bank hash and byte-exact verification
erase/verify all eight B0 sectors
re-hash B3 against the retained source hash
boot stock B3
```

The host-proven artifact is deliberately excluded from `all`, the manifest,
and the consumer migration package:

```text
file     BUILD/v1.28/s19/str8n-v1.28-str8-in65-factory-restore-2000.s19
SHA-256 A933ECAF454E7C74133B5560553A77EF9EECB70C2DE6CCE16067F5EE5CF3F7C7
range    $2000-$2C18; 3097 bytes; S9 $2000
source   observed B0 FNV1A 1249E1F3; RESET $F818
```

The board-lab restore was used to recreate stock WDCMONv2 in B3 with B0
erased. From that factory baseline, the operator ran the extracted kit's
single consumer command from Windows PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "C:\SRC\STR8-N\BUILD\v1.28\wdcmonv2-str8n-migration-kit\MIGRATE-WDC-TO-STR8N.ps1" `
  -Port COM4
```

The manual physical-reset gate avoided the previously captured DTR/reset-arm
transport pollution. The bridge identified `SXB2; HW=3.00; WDCMON=2.00`,
loaded `$2000-$4FFF` byte-exact, and executed the installer at `$2000`. The
accepted serial evidence is:

```text
FLASH ID=BF/B5
STOCK B3 FNV1A=1249E1F3
TYPE MIGRATE WDC TO STR8-N 1.28> MIGRATE WDC TO STR8-N 1.28
COPY/VERIFY B3 -> B0 ........
B0 == ORIGINAL B3 VERIFIED
ERASING/PROGRAMMING B3:F
MIGRATION VERIFIED; STARTING STR8-N
RESET

STR8-N 1.28
0-2 C W S: S
I L C W J
STR8-N>J0
J B0
```

Retained B0 then printed the complete W65C02SXB + EDU startup, detected OLED,
RTC, SPI SRAM, ADC, and CardKB as `OK`, and reached its application prompt.
The operator visually verified the expected CS0-CS3 chase. A final physical
RESET at that prompt was captured returning to:

```text
RESET

STR8-N 1.28
0-2 C W S:
NO
I L C W J
STR8-N>
```

The raw RX transcript and companion event log were copied byte-exact from the
kit's `LOCAL` directory into retained evidence at
`BUILD/v1.28/hardware-evidence/factory-migration-20260828-211427/`. Their
SHA-256 values are `ED20AD34B7786C9DAC82EE65503577F1CFB16F4A63C3294DA1FED6582A9AC67D`
and `FF0DF0A0F6C3C45418A0EE984515F021D563A4A1B9F368CC7503393F12C3713B`,
respectively. The event log records the physical reset gate, board identity,
byte-exact RAM readback, `$2000` execution, and transmitted confirmation
input. This accepts the minimal erased-B0 factory migration, complete
B3-to-B0 preservation, D0 `WDCM2` publication, `J0` guest launch, visual bank
chase, and physical-RESET recovery to STR8-N 1.28.

## Final readback and retained evidence

Use the external programmer to save a post-migration 128K readback. Verify:

```text
physical $00000-$07FFF   equals the original stock B3 BIN
physical $10000-$17FFF   equals PRE device Bank 2
physical $08000-$0FFFF   equals PRE device Bank 1
physical $18000-$1EFFF   equals PRE device Bank 3 sectors 8-E
physical $1F000-$1FFFF   equals migration-configured STR8-N top candidate
```

Retain:

```text
pre/post 128K hashes
archive BIN/S19/receipt
raw RX transcripts and companion `.events.txt` host-action logs
exact artifact hashes
complete Phase A-F terminal transcript
observed bank inventory and FNV values
stock J0 WDCMON binary identity proof
any failure/retry/restore transcript
operator acceptance statement
```

Do not mark the migration path hardware-accepted until every applicable row
above has direct evidence.

## 2026-08-29 v1.29 external-BIN factory migration acceptance

The production v1.29 consumer path is accepted on the same physical
W65C02SXB/EDU. The first connection attempt discarded 553 startup bytes and
timed out while synchronizing command `$0C`; it obtained no board identity,
did not execute the RAM adapter, and made no flash write. A clean retry
identified `SXB2; HW=3.00; WDCMON=2.00`, loaded and read back the muted-entry
RAM adapter byte-exact, and executed it at `$2000`.

The retry used these exact transferred artifacts:

```text
RAM adapter SHA-256  16D18D44970704D7BF16F0C572264584C43DBBE4B0654B87587B1327CE72AF0B
RAM adapter range    $2000-$296F; 2416 bytes; S9 $2000
RAM adapter FNV1A    4BAD81BA
STR8-N top SHA-256   C52CBE162B23147657406AC4709D8908639351FBEF97FDCD016EE77FF32B0682
Bank Maint SHA-256   642ABDF643E8726BDEE0634B9227192223F9231F2DDE3B4F759636841A89EF9B
raw RX SHA-256       146B70213CD95B87892157F16D0BE28410210AC4ADAD5073F6AABBDFFAEA5B1B
event log SHA-256    F7F40F1DF4AFD49E146650BEF780BB6E11E225DE985F292FE2840F78E1C665D4
```

Bank 0 was already byte-identical to original stock Bank 3, so the adapter
correctly skipped a redundant copy while retaining the whole-bank exact gate.
It received the external 4096-byte canonical top, required the exact
`INSTALL STR8-N 1.29` confirmation, programmed and verified B3:F, and started
STR8-N 1.29. Before D0 existed, `J0` failed closed as required.

The operator entered type `65` and description `WDCV2`; the intended consumer
type was subsequently corrected to `FF`. The production Bank Maintenance image
displayed the exact bytes it actually wrote, retained here as evidence rather
than rewritten as the desired result:

```text
PROPOSED D0 B3:$FFB0: 65 FF FF FF 57 44 43 56 32 FE FF FF FC FF FF FF
TYPE ADOPT B0> ADOPT B0
 OK

DIR B T DESC ENTRY JOURNAL
D0 65 WDCV2 FFFF FCFFFFFF
D1 FF ..... FFFF FFFFFFFF
D2 FF ..... FFFF FFFFFFFF
D3 FF ..... FFFF FFFFFFFF
```

The optional `P` and `F` explorations both aborted before confirmation and
made no change. Reset selector `0` then launched retained WDCMONv2 and its EDU
application from B0. Physical RESET returned to STR8-N 1.29. Shell `J0`
launched the same retained application, and a final physical RESET again
returned to STR8-N 1.29:

```text
STR8-N 1.29
0-2 C W S: 0
J B0
3S

================================
  W65C02SXB + EDU Kit  Rev 1.0
  W65C02S @ 8 MHz  |  5V System
  I2C/SPI bit-banged via W65C22
================================
Initializing...
Scanning devices...
  OLED (SSD1306)     $3C  OK
  RTC  (MCP79411)    $6F  OK
  SPI SRAM           OK
  ADC  (ADS1015)     $48  not found
  CardKB             $5F  not found
Init complete.

> RESET

STR8-N 1.29
0-2 C W S: S
I L C W J
STR8-N>J0
J B0

================================
  W65C02SXB + EDU Kit  Rev 1.0
  W65C02S @ 8 MHz  |  5V System
  I2C/SPI bit-banged via W65C22
================================
Initializing...
Scanning devices...
  OLED (SSD1306)     $3C  OK
  RTC  (MCP79411)    $6F  OK
  SPI SRAM           OK
  ADC  (ADS1015)     $48  not found
  CardKB             $5F  not found
Init complete.

> RESET

STR8-N 1.29
0-2 C W S:
NO
I L C W J
STR8-N>
```

This accepts the v1.29 external-BIN install from an already-preserved B0,
directory rewrite mechanics, reset selector `0`, shell `J0`, and physical-RESET
persistence. It does not accept the skipped erased-B0 copy branch or the
intended `D0 FF WDCV2` identity. The serial transcript cannot establish an
audible property. After the run, the operator explicitly confirmed that the
EDU buzzer was silent when the RAM adapter began; that observation is retained
separately from transcript-derived claims.

## 2026-08-29 v1.29 complete erased-B0 consumer acceptance

The canonical package rerun began with stock WDCMONv2 in B3 and erased B0.
The host identified `SXB2; HW=3.00; WDCMON=2.00`, read back the 2416-byte RAM
adapter byte-exact, and executed it at `$2000`. Unlike the preceding
already-preserved run, this one reached and completed the intended copy branch:

```text
FLASH ID=BF/B5
STOCK B3 FNV1A=1249E1F3
TYPE COPY B3 TO B0> COPY B3 TO B0
COPY/VERIFY B3 -> B0 ........
B0 == ORIGINAL B3 VERIFIED
SEND STR8-N TOP BIN; 4096 BYTES; START $F000

STR8-N TOP RECEIVED
TYPE INSTALL STR8-N 1.29> INSTALL STR8-N 1.29
ERASING/PROGRAMMING B3:F
MIGRATION VERIFIED; STARTING STR8-N
```

The production Bank Maintenance image then displayed and committed the exact
intended directory record:

```text
TYPE 00-FF [FF]> FF
DESC 5 CHARS [AUTO]> WDCV2

PROPOSED D0 B3:$FFB0: FF FF FF FF 57 44 43 56 32 FE FF FF FC FF FF FF
TYPE ADOPT B0> ADOPT B0
 OK

DIR B T DESC ENTRY JOURNAL
D0 FF WDCV2 FFFF FCFFFFFF
D1 FF ..... FFFF FFFFFFFF
D2 FF ..... FFFF FFFFFFFF
D3 FF ..... FFFF FFFFFFFF
```

Shell `J0` launched retained WDCMONv2 and the complete EDU application; a
physical RESET returned to STR8-N 1.29. Reset selector `0` launched the same
guest; the second physical RESET again returned to STR8-N 1.29. The final
extra `C`, `W`, and `S` keystrokes merely exercised missing optional component
paths at the STR8-N prompt and made no flash change.

The retained host evidence is:

```text
raw RX path       BUILD/v1.29/wdcmonv2-str8n-migration-kit/LOCAL/factory-migration-20260829-201332.raw
raw RX SHA-256    23F3650BDCBF7FDBB278B5954187C0C3DB12552FB89B89E4D282DD4C37782E67
event log path    BUILD/v1.29/wdcmonv2-str8n-migration-kit/LOCAL/factory-migration-20260829-201332.raw.events.txt
event SHA-256     1CB79649D27C69AC849D4B3F3AC23D9218DB53ECF30BF26578DD65CFB494BCA6
adapter SHA-256   16D18D44970704D7BF16F0C572264584C43DBBE4B0654B87587B1327CE72AF0B
top BIN SHA-256   C52CBE162B23147657406AC4709D8908639351FBEF97FDCD016EE77FF32B0682
bank maint SHA-256 642ABDF643E8726BDEE0634B9227192223F9231F2DDE3B4F759636841A89EF9B
```

This accepts the complete v1.29 factory migration transaction. Serial evidence
cannot prove an audible property, but the operator separately confirmed that
the EDU buzzer became silent immediately when the RAM adapter started. The
complete migration and quiet-start behavior are therefore board-accepted.

## 2026-08-30 board #3 v1.29 factory replication

The operator repeated the v1.29 factory WDCMONv2-to-STR8-N path on board #3.
This board is recorded as having no visible date stamp, in contrast with
operator board #1 marked `202205` and board #2 marked `202512`. The board used
COM3 and reported the same supported monitor identity:

```text
BOARD      = SXB2; HW=3.00; WDCMON=2.00
```

The run used the extracted v1.29 migration kit from Windows PowerShell 5.1.
The wrapper enumerated only COM3, loaded the RAM adapter byte-exact, and
executed it at `$2000`:

```text
S19 SHA256 = 16D18D44970704D7BF16F0C572264584C43DBBE4B0654B87587B1327CE72AF0B
RAM RANGE  = $2000-$296F (2416 bytes)
ENTRY      = $2000
RAM FNV1A  = 4BAD81BA
RAM READBACK = BYTE-EXACT
EXECUTE      = $2000
```

The migration followed the erased-B0 factory branch and completed the
destructive gates:

```text
FLASH ID=BF/B5
STOCK B3 FNV1A=1249E1F3
TYPE COPY B3 TO B0> COPY B3 TO B0
COPY/VERIFY B3 -> B0 ........
B0 == ORIGINAL B3 VERIFIED
SEND STR8-N TOP BIN; 4096 BYTES; START $F000

SENDING STR8-N-v1-29.bin (4096 bytes)
FILE SENT
STR8-N TOP RECEIVED
TYPE INSTALL STR8-N 1.29> INSTALL STR8-N 1.29
ERASING/PROGRAMMING B3:F
MIGRATION VERIFIED; STARTING STR8-N
```

After the first STR8-N 1.29 boot, the operator loaded the production Bank
Maintenance S19 and recorded the D0 description as `WDCV2`. The observed and
retained directory state is:

```text
PROPOSED D0 B3:$FFB0: FF FF FF FF 57 44 43 56 32 FE FF FF FC FF FF FF
TYPE ADOPT B0> ADOPT B0
 OK

DIR B T DESC ENTRY JOURNAL
D0 FF WDCV2 FFFF FCFFFFFF
D1 FF ..... FFFF FFFFFFFF
D2 FF ..... FFFF FFFFFFFF
D3 FF ..... FFFF FFFFFFFF
```

This preserves the functioning board state exactly as tested and matches the
published v1.29 consumer label target `D0 FF WDCV2 FFFF FCFFFFFF`; the Bank-0
payload remains the byte-exact retained factory guest.

Two exploratory maintenance commands did not change the migration result. The
first Bank-2 erase confirmation used the spaced text `ERASE 2 ALL` and aborted
without mutation. The subsequent exact `ERASE 2ALL` did erase Bank 2. A later
`COPY 0 2` attempt used `COPY 0 2` instead of the required compact
confirmation and aborted without copying B0 into B2.

Reset selector `0` launched retained WDCMONv2 and the EDU application from B0.
Physical RESET returned to STR8-N 1.29. Shell `J0` launched the same retained
application, and the final physical RESET again returned to STR8-N 1.29:

```text
STR8-N 1.29
0-2 C W S: 0
J B0
3S

================================
  W65C02SXB + EDU Kit  Rev 1.0
  W65C02S @ 8 MHz  |  5V System
  I2C/SPI bit-banged via W65C22
================================
Initializing...
Scanning devices...
  OLED (SSD1306)     $3C  OK
  RTC  (MCP79411)    $6F  OK
  SPI SRAM           OK
  ADC  (ADS1015)     $48  not found
  CardKB             $5F  not found
Init complete.

> RESET

STR8-N 1.29
0-2 C W S: S
I L C W J
STR8-N>J0
J B0

================================
  W65C02SXB + EDU Kit  Rev 1.0
  W65C02S @ 8 MHz  |  5V System
  I2C/SPI bit-banged via W65C22
================================
Initializing...
Scanning devices...
  OLED (SSD1306)     $3C  OK
  RTC  (MCP79411)    $6F  OK
  SPI SRAM           OK
  ADC  (ADS1015)     $48  not found
  CardKB             $5F  not found
Init complete.

> RESET

STR8-N 1.29
0-2 C W S: S
I L C W J
STR8-N>
```

The local evidence files named by the wrapper were:

```text
C:\Users\walte\Music\str8n-v1.29-wdcmonv2-str8n-migration-kit\STR8-N-v1.29-Migration-Kit\LOCAL\factory-migration-20260830-103922.raw
C:\Users\walte\Music\str8n-v1.29-wdcmonv2-str8n-migration-kit\STR8-N-v1.29-Migration-Kit\LOCAL\factory-migration-20260830-103922.raw.events.txt
```

This board #3 transcript accepts factory migration, erased-B0 preservation,
external v1.29 top install, retained WDCMONv2 launch through selector `0` and
shell `J0`, and physical-RESET return to STR8-N 1.29 on a no-date-stamp board.
It records the D0 `WDCV2` description.
