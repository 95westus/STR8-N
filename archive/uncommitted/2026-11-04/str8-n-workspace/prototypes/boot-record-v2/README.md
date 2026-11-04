# Read-only F boot record: offline component prototype

## Operator walkthrough: build the system from F alone

Subsequent 2609 USB hardware step: the exact 4096-byte F was installed via
the qualified RAM migrator, device-verified, physically reset and stopped
at the first REC> with no later command. B0 and all non-F sectors were outside
the write target. ACIA remains model-tested only, with no board-test claim.
[Hardware receipt](../../output/qualification/2609-b15-onboarding-20261027T212009Z/step03-F-only-install/receipt.md).

The [b15 F-up operator guide](../../docs/STR8N_B15_FROM_F_GUIDE.md) starts
with only F, then journals, MON A/B, configuration, opaque images and the
other b15 features. The 2609 F-only RAM migrator and direct 4096-byte BIN
passed 44 offline groups and reproducibility checks. Every non-F byte is
preserved; the board was not accessed or flashed. The planner is
`wdc_b15_2609.py`; its only flash transfer is B3:F000-FFFF.
[Prepared artifacts and receipt](../../output/qualification/2609-b15-onboarding-20261027T212009Z/step02-F-only-ready/receipt.md).

In F-only mode RAM tools return through RESET at $7E64. HOLD at $7E67
resumes an active MON. Journal, MON and image setup are separate later steps.

## Current FLASH LED fix (October 27)

The installed B0:8 FLASH page now clears the F0 busy LEDs and restores 01
before every prompt. The original stuck-F0 erase case was reproduced; 69
regression groups and 34 LED groups pass. The live update/program/erase/Q
paths passed with the owner's erased B0:9, settings and owner RAM preserved.
[Audited update](../../output/qualification/FLASH-LED-2512-20261027/audited-results.json).
Build: `BUILD/b15-bank-monitor-led-r1`. F/MON are unchanged; FLASH remains
installed and the named launcher remains deferred.

## Current 2512 FLASH setup: left installed (October 27)

The owner-requested B0:8 FLASH example is now left installed at $8000.
Live boot/help/Q and full-flash readbacks passed; fresh owner RAM/ZP were
restored and independently verified. Default MON B and boot policy remain
unchanged. A full original B0 backup plus the overwritten sector are kept
with the [audited installation](../../output/qualification/FLASH-2512-keep-20261027-r3/audited-results.json).
See [start/return instructions](../../output/qualification/FLASH-2512-keep-20261027-r3/START_HERE.txt).
The named FLASH/IO/FILE/PROGRAM launcher remains deferred.

## Opaque FLASH page example and named bank applications

The commented `bank-monitor.asm` and `bank-monitor-entry.asm` build a FLASH
page at B0:8, with RAM/flash editing, sector erase, protected journal wear
reservation and Q to validated MON B/A. An alternate B0:9-A allocation
demonstrates a multi-sector image. The B0:8 install/RAM-edit/flash-edit/Q
trial passed on 2512; original B0:8/9 images, boot settings and fresh owner
RAM/ZP were restored. Four real erase reservations remain in the journal;
F/MON are unchanged. The B0:9-A variant remains model-tested only.
Build with `build_bank_monitor.py`, then run `test_bank_monitor.py`.
[Hardware audit](../../output/qualification/FLASH-2512-install-edit-restore-20261027-r2/audited-results.json).
See the [consolidated guide](../../docs/STR8N_B14_BOOT_AND_RECOVERY_GUIDE.md#bank-applications-and-the-flash-page-example)
for commands, memory use, artifacts and the planned FLASH/IO/FILE/PROGRAM
launcher. Named dispatch is planned; SNBT still holds one entry per bank.

## b15 installed on 2512: Ctrl-C at SEND BIN

Ctrl-C (03) as the first input at SEND BIN now returns to recovery without
writing or executing RAM; later 03 bytes remain literal payload. The b15
update is installed and audited on 2512. USB-mode and BOTH/CRLF cancellation
passed, as did a normal 2602-byte CONFIG load/execution with independent RAM
readback. Original boot policy, opaque images and fresh owner RAM/ZP were
preserved. One A/F/B erase each was reserved; no C/D erase. Final BOTH MON B,
pending flags clear and serial released. No physical reset or RTC write.

Builder: `build_b15.py`; [512-group offline qualification](../../BUILD/pr04-b15-cancel-r3/b15-qualification.json);
[hardware audit](../../output/qualification/b15-2512-install-20261026/audited-results.json).
Exact-F-CRC-bound b14 MON/recovery kits still require b15 rebuilds.

## Consolidated current b14 guide

Use the [boot, recovery and configuration guide](../../docs/STR8N_B14_BOOT_AND_RECOVERY_GUIDE.md)
for the current boot-sector function, SNBT records, recovery, RAM CONFIG,
worked examples, related improvements and implemented/planned status.
The dated sections below retain earlier protocols and qualification history.

## Extended b14 RAM CONFIG (October 26)

Enable an opaque-image bank, set its entry, and save the default with the
[extended RAM CONFIG](RAM_CONFIG_B14.md). This standalone b14 RAM app keeps
F/MON and the SNBT record format unchanged. Build, commands and offline
qualification are documented there.

## Deferred workflow: cross-platform terminal

For later: investigate a Windows/Linux Python/pyserial terminal with an
option to send BIN files. The deferred scope is recorded in the
[board development workflow](../../docs/BOARD_DEVELOPMENT_WORKFLOW.md#deferred-host-terminal-investigation-october-24-2026).
No terminal implementation or board work is started by this item.

## Offline combined RAM recovery kit, revision 1 (October 24)

The combined `recovery-kit.bin` is an offline RAM app, not new firmware.
All three physical boards are unchanged; no serial port was opened. It uses
the unchanged PR04 b14 F services and works in CPU models with MON A/B absent.
Do not load this app on RC1 g0034 or WDCMONv2: their private services differ.

| Component | Actual size/location |
|---|---|
| Combined raw BIN | 11,985 bytes, 0200-30D0; entry 0200 |
| Embedded original b14 MON images | 8,192 bytes total |
| Single shared RAM journal writer | 983 bytes at 0CF8-10CE |
| Reduction versus the two separate tools | 329 bytes (12,314 to 11,985) |
| Application RAM beyond the loaded app | 13,359 bytes at 30D1-64FF, unborrowed |
| F, unchanged | 3,572 active bytes; 3,669-byte body span; 395 contiguous free; 97 internal spare; 32 vector bytes |
| MON A/B, unchanged | 3,830-byte body + 128-byte header, 138 free each |

The app reuses the fixed-target MON routines and OIP1 protocol, with only one
copy of the journal writer. The 6700 journal frame, 6800-77FF staging buffer,
existing RAM worker/vector areas and reserved service state remain reserved.
The loaded app span is disposable; the tests preserve owner ZP and RAM beyond
it. A future live operation still needs fresh capture/escrow and serial ownership.

Prompt: `RAM KIT ? T I X Q> `. These are echoed **text commands followed by
Enter**, accepting lowercase, CR, LF or CRLF. Unlike the old standalone MON
kit, a single T/X/Q without Enter does not dispatch immediately.

| Command | Meaning |
|---|---|
| `?` | Complete help; uses the page-aware RAM printer |
| `T` | Restore embedded original b14 MON A/B, read back, commit last, restart through F |
| `I` | Existing OIP1 host read/write transfer, one complete 4096-byte sector plus CRC |
| `X` | Erase both MON slots after entering `ERASE`; checks both preimages first |
| `Q` | Software restart through F, using the current boot record |

F L still receives the app as a regular raw BIN at 0200 and starts it after
three seconds idle. The later I operation retains OIP1's separate 20-byte
header, exact 4096-byte payload, current-preimage CRC and payload CRC. It is
a host-driven transfer, rather than an arbitrary BIN pasted at the app menu.
I permits B0/B1/B2:8-F and B3:8/9/E; normal I requests cannot read or overwrite
B3:A/B/C/D/F. Only T/X own the MON sectors; C/D writes are managed journal
transactions. F remains read-only. T and I skip identical content without
an erase or wear increment. Writes require a valid journal and durable erase
reservation; a missing/corrupt journal is never initialized by this app.

The app checks its own CRC and matching F CRC at entry and before I/T/confirmed-X.
The known mutable OIP1 header/CRC/page bytes are normalized first. This is an
integrity check after raw execution begins, not verified F loading or authenticity.
Framing/TX failures still quarantine all late bytes, including T/X/ERASE/?/Q.

Final offline result: **162 groups passed, zero final failures**, across
65C02 and 65C816 emulation: 18 combined integration groups, 14 MON/integrity/
quarantine guards, 120 OIP1 groups and 10 CRC-summary differential comparisons.
All 17,256 opaque mutation prefixes in append/rollover were retried, with
618 safe reservation refusals rather than unsafe continuation. Separately,
18 selected MON interruption prefixes reloaded through F and completed T.
These are CPU/NOR models, with differentially checked bulk/CRC summaries;
no physical power-cut, NMI or new console electrical timing proof is claimed.
The initial long-help page-wrap and harness corrections are retained in the
results' prior-attempt records. A second build reproduces the BIN byte-for-byte.

Evidence and artifact:
[results](../../BUILD/pr04-b14-recovery-kit-r3/recovery-kit-offline-results.json),
[BIN](../../BUILD/pr04-b14-recovery-kit-r3/payload/recovery-kit.bin),
[help text](../../BUILD/pr04-b14-recovery-kit-r3/recovery-kit-help.txt).
Builder: `build_recovery_kit.py`; integration: `test_recovery_kit.py`;
exhaustive OIP1 driver: `test_recovery_kit_accelerated.py`; additional guards:
`test_recovery_kit_guards.py`; audited receipt: `qualify_recovery_kit.py`.

### WDCMONv2 conversion assessment

Its MON restoration and write logic can be reused in a **WDC bootstrap build**,
but the present app is not that converter. It calls matching STR8-N RAM services
and F APIs before its integrity checks; T owns only A/B, and I protects F/C/D.
Putting these MON images into WDC B3 alone does not establish a coherent system.

A conversion build must load through the WDC debugger/S19 route, initialize
its own console/bank/flash/vector services in RAM, admit an exact supported
WDC image and CPU, and bind changes to preservation captures/device preimages.
It must establish compatible F plus MON A/B and initialize or migrate the
SNBT C/D journal with explicit unknown prior wear where history is absent.
Owner programs/retained RAM/settings and RTC time/trim remain preservation
requirements. Vendor-occupied C/D are not the same as a blank journal.
Normal opaque-command protections should remain intact; a separate migration
operation should own the admitted F/journal transition.

The existing exact-profile WDC factory planner/transport and documented
[WDC-to-RC1 route](../../docs/rc1/UNIFORM_UPGRADE.md) are useful foundations,
including source/CPU admission and transfer/readback ordering. Their historical
hardware results do not qualify WDC-to-this-b14-layout. New offline interruption
coverage is needed before any authorized board trial; before a valid F exists,
some interrupted factory states can still require the original programmer backup.
No WDC conversion command or board change was added here.


## Current 2512: b14 MON A/B restored through F (October 24)

The owner requested restoration after the F-only opaque-image test. F raw L
loaded the unchanged 9902-byte MON kit at 0200; after the idle start, a single
T restored the original b14 A/B images, generation 8000000E. The shared RAM
writer reserved wear before each A/B erase, verified each uncommitted image,
then programmed its commit byte last. F, boot settings, prior journal pages,
B0/B1/B2 and unrelated B3 sectors are unchanged. A/B each gained one erase
attempt. Both slots match the original twice-captured backups byte-for-byte.

The complete software default-B boot and both MON selections passed. J3 with
CRLF followed by S reached recovery from both A and B, without physical reset.
Four full-flash comparisons matched the two CPU models. Six current-source
CPU/NOR groups and six host groups pass, retaining the prior 16 kit groups and
selected interruption coverage. Three raw-service full-RAM comparisons plus
an independent final MON full-RAM readback and two owner-ZP reads passed. The
first disposable L prefix was restored from the latest verified owner image;
fresh remaining RAM/ZP values were preserved. The board is idle at BOTH MON B;
all restoration/lease flags are clear. 2604/2609 were not accessed or changed.
RTC sampling remains stopped. No physical reset or power-cut test was added.

Evidence: output/qualification/mon-restore-2512-through-F/test-results.json.
The following MON-absent/opaque accounts describe earlier completed states.


## 2512 F-only opaque install/run qualification (October 24)

A subsequent owner-authorized test loaded the unchanged 2412-byte OIP1 RAM
installer through b14 F with both MON slots erased. A headerless 4096-byte
opaque probe was installed at B0:8000, read back byte-for-byte with CRC, and
executed using F bank choice 0. Its public RAM reset entry returned through
the full countdown to REC without a physical reset. Identical retry and
wrong-preimage refusal caused no mutations. Independent full-flash readbacks
matched both CPU models. The original B0:8 sector was restored, MON A/B remain
erased, and F is unchanged. Only B0:8 gained two erase attempts; boot settings
and previous counts were preserved. 2604/2609 were not accessed or changed.

Ten new CPU/NOR groups and ten host groups pass; the unchanged OIP1 binary
retains its prior 120 protection/fault groups and 17256 interrupted prefixes.
Six complete flash comparisons and three independently audited full-RAM log
comparisons passed on hardware. An earlier pre-flash RAM guard found 4D7F=20
versus older escrow 10; no flash was written then, and the current value 20
was preserved. The first disposable L prefix comes from the last verified
owner escrow; all remaining RAM and owner ZP were freshly captured/preserved.
The board is idle at BOTH REC, with RAM and sector restoration flags clear.

Evidence: output/qualification/opaque-absent-2512-install-run-restore-r2/
test-results.json. No physical power-interruption qualification is claimed.


## Current 2512 MON-absent bench state (October 24)

The owner subsequently requested removal of both MON slots on 2512. B3:A/B
are now erased (8192 bytes). F remains exact b14. Software reset-vector timeout
boot reaches REC, selecting absent A/B stays in recovery, and F raw-loads the
qualified MON restore kit with both slots absent. The restore T command was not
sent on hardware. Four full-flash comparisons match the CPU-predicted postimage;
only the two MON erase counters increased, with settings/history preserved.
Original full application RAM and owner ZP were restored and verified. The board
was left at BOTH REC; 2604/2609 were not opened or changed. A physical reset was
not requested or tested after this removal; normal MON J3 is now unavailable.

Evidence: output/qualification/mon-absent-2512-remove/test-results.json.
Backup: output/qualification/mon-absent-2512-backup-r2/capture.
Restore kit/instructions: BUILD/pr04-b14-mon-absent-r5/payload/mon-kit.bin
and BUILD/pr04-b14-mon-absent-r5/RESTORE-INSTRUCTIONS.txt.
The following b14 deployment account describes the earlier intact MON state.


## b14: raw BIN at $0200, three-second idle autorun

`2.0proto b14`, generation `8000000E`, changes recovery L to accept an ordinary
raw binary file at $0200. After SEND BIN, the first byte can arrive at any time.
Every received byte restarts a nominal three-second idle timer; when it expires,
F restores text console state and jumps directly to $0200. R, the RLP1 header,
transfer length and transfer CRC are removed. D/V remain removed. All byte
values, including first-byte Ctrl-C, CR and LF, are literal data; there is no
in-band cancel. No binary bytes are echoed. The first enabled console providing
data owns the transfer, regardless of which console typed L. The other console
is not consumed during reception. Send the file in binary mode after SEND BIN.
An optional command CRLF's LF is normalized before that ready message.

Writable load RAM is $0200-$64FF (25,344 bytes). Binary writes cannot reach zero
page, stack, $6500-$77FF journal/staging workspace or reserved console/ABI RAM.
Overflow and detected serial receive errors refuse without executing the loaded
program. A three-second pause runs the received prefix; without CRC or length,
corruption and truncation are intentionally undetectable. This raw transfer is
not verified. CRC/header/range/preimage/readback checks remain in the separate
OIP1 opaque flash installer, MON slot validation and journal reader/writer.

| F budget | b13 | b14 |
|---|---:|---:|
| Body span, including internal gaps | 3,868 | 3,669 |
| Active code/data | 3,824 | 3,572 |
| Reserved hardware vectors | 32 | 32 |
| Contiguous free bytes | 196 | 395 |
| Internal reusable gaps | 44 | 97 |
| Total available bytes | 240 | 492 |

The contiguous reserve is $FE55-$FFDF. The copied 196-byte console/vector ROM
image now occupies part of the removed framed-loader region. The private startup
trampoline moves too; PR04 shared API/SR/parser/console/CRC/journal call addresses
remain fixed. Copied RAM console/vector bytes, the countdown and balanced drain
loop are unchanged. Each MON still has 3,830 body +128 header bytes and 138 free.
The 983-byte writer remains in each MON and standalone CONFIG. CONFIG (1,176
bytes) and the OIP1 installer (2,412 bytes) are rebuilt to enter at $0200. No
.rlp1 artifact is emitted. Old tools linked at $2000 must be rebuilt for $0200;
an old RLP1 transfer is now just ordinary bytes, not a recognized format.

Build: `BUILD/pr04-b14-raw-r4/`; bound results: `b14-qualification.json`.
618 passing offline groups, zero final failures: 350 core/selection (276 retained
core groups +74 selection), 66 raw-loader groups, four full idle instruction
measurements, 14 CONFIG/program/ACIA execution groups, 120 opaque installer
protection/readback/interruption groups, 60 startup/drain/key/J3 groups and four
CPU/MON bench cases. Obsolete RLP1/R/D/V tests are explicitly replaced rather
than counted as passing. Both CPUs and console ports are covered. Each complete
idle measurement executes every opcode and agrees exactly with the fast empty
poll model in CPU state and RAM. At nominal 8MHz the idle-entry-to-$0200 interval
is 24,000,097 cycles on FT245 and 24,000,091 on ACIA (about 3.000012 seconds).
The paced ACIA transfer lasts over three seconds without premature execution.
Exact-capacity and overflow cases, all byte values, timer reload, indefinite
first-byte wait, blocked FT output, no-MON CONFIG/OIP execution and detected ACIA
errors are covered. Interrupted OIP writes retain its existing wear/protected
sector rules. A second clean build reproduces every component binary.

Earlier build EQU placement and test-harness issues (old reference builds lacking
b14 symbols, and blank CONFIG correctly refusing a disabled opaque bank) are
recorded in logs and qualification notes. ACIA electrical timing is unmeasured.
The initial prototype qualification accessed no serial ports or boards. A separate,
fresh-preimage-bound b12-to-b14 update is now complete on 2512; 2604/2609 remain
RC1 g0034 and were not opened or flashed. The generic image still has installation
permission disabled; only the board-specific admitted plan authorized this update.

2512 evidence: `output/qualification/pr04-b14-2512-install/test-results.json`.
The complete physical-reset boot was captured before first host TX, followed by
software J3 -> S without another physical reset. Recovery help and removed R/D/V
refusals passed. L waited 5.047 seconds for data, accepted the literal 2,412-byte
installer BIN at $0200 with a 2.031-second gap between chunks, and reached its
program prompt 3.016 seconds after the last host write. No header, transfer
length, transfer CRC or R command was sent. These are host FT245 timestamps,
not a physical byte-arrival measurement. OIP read B0:8 without writing flash;
independent MON readback checked every loaded tool byte against its expected
executed image, including the 23-byte mutable request/CRC/page workspace.

All four flash banks matched the exact expected image after the probes. Native
journal records, B0/B1/B2 and RTC/history/E sectors were preserved; C/D had no
erases. Original application RAM was restored with three full comparisons and
reread after the final full-countdown BOTH/MON-B software boot. Owner ZP00-DF
passed two final comparisons. Restoration/reset flags are clear and the serial
lease is released. All 678 final offline groups passed (618 firmware, 17 buffered
probes, two CPU independent-readback cases, six host/reset-watcher cases, ten
native installer fault models, 14 admission cases and 11 source-backup cases).
The earlier CPU test-adaptation address correction is recorded in the report;
there were no final hardware failures. Live ACIA electrical behavior was not
measured. Only the planned three F/MON erases occurred.

Build with build_b14.py, then run test_b14.py --suite regression and --suite
bench, test_b14_raw.py, test_b14_config.py, and test_b14_raw.py --timing --cpu
for each CPU (65c02 and 65c816-e). Run test_b14_startup.py and test_b14_tools.py
with each CPU. All accept --build BUILD/pr04-b14-raw-r4. Build a fresh comparison
at BUILD/pr04-b14-raw-repro, then run qualify_b14.py against the tested build.

## b13: contiguous F reserve, offline only

`2.0proto b13`, generation `8000000D`, keeps the PR04 shared entry
addresses and creates **196 contiguous free bytes at $FF1C-$FFDF**.
The hardware vectors at $FFE0-$FFFF are unchanged. This is an offline
prototype: 2512 stays on b12; 2604/2609 stay on RC1 g0034.

| F budget | b12 | b13 |
|---|---:|---:|
| Body span, including internal padding | 3,969 | 3,868 |
| Active code/data | 3,875 | 3,824 |
| Reserved hardware vectors | 32 | 32 |
| Contiguous free bytes | 95 | 196 |
| Internal reusable padding | 94 | 44 |
| Total available bytes | 189 | 240 |

Twenty-one validator branches use short encodings instead of expanded
conditional/JMP pairs, saving 63 bytes without removing checks. The 104-byte
startup implementation moves into existing gaps and reclaimed validator
space. Three phase jumps and the entry trampoline cost 12 bytes: net saving
51 bytes. BOOT_STARTUP stays at $FF19 as a JMP, immediately before the free
block. The remaining 44 spare bytes are scattered; all 240 are not contiguous.

| Relocated startup part | Address | Bytes, including bridge |
|---|---|---:|
| Silent USB wait | $F6B1 | 11 |
| WAIT message / drain setup | $F45B | 26 |
| Balanced drain loop / exit JMP | $F89F | 62 |
| Drain cleanup / chooser handoff | $F78D | 14 |
| Preserved startup entry JMP | $FF19 | 3 |


Public BOOT_API entries, SR routes, line/hex/console entries, shared CRC,
journal scanner, BOOT_SLOT_CHECK and actual RAM-tool call targets keep their
addresses. Internal validator/startup labels move. Standalone RAM CONFIG and
opaque installer artifacts and copied console/vector images are byte-identical
to b12. Each MON stays 3,830 body +128 header bytes, with 138 free; only the
banner, generation and header CRC differ. The 983-byte journal writer remains
independently in each MON and RAM CONFIG. F only reads the journal.

Build: `BUILD/pr04-b13-packed-r1/`; bound results: `b13-qualification.json`.
562 passing offline groups, zero final failures: 426 core/selection, 32
wait/cancel/binary, 36 recovery commands, four CPU/MON bench cases, two
MON-absent F load/run installer cases, two full countdown measurements and
60 startup/drain/key/software-J3 groups. A separate clean build reproduces
all component binaries. Earlier harness-only errors (fixture byte count and
an inherited three-second assertion) are recorded in the receipt and logs;
firmware did not change to correct them.

The relocated 59-byte drain loop is identical and remains within one page.
Linked instruction models at nominal 8MHz measure 15,998,787 cycles for the
silent USB phase including entry/phase jumps, and 8,000,498 cycles for drain
including its new exit JMP. Both CPUs/consoles measure 5.9980545 seconds from
6 to 0. The startup matrix covers excess/continuous input, paced ACIA, blocked
FT245 output, both ports' boot keys and actual MON B software J3 then fresh S.
ACIA electrical behaviour is not measured. No hardware or serial access was
performed, and this candidate has no installation permission or deployment kit.

Reproduce with `build_b13.py --out BUILD/pr04-b13-packed-r1` and a second
build at `BUILD/pr04-b13-packed-repro`. Run `test_b13.py --build <directory>
--suite <regression|commands|wait|installer|bench|countdown>` (countdown takes
`--cpu 65c02` and `--cpu 65c816-e` separately). Run `test_b13_startup.py` with
the same build and each CPU, then `qualify_b13.py --build <directory>`.

## b12: D/V removed; recovery load RAM is disposable

`2.0proto b12`, generation `8000000C`, removes recovery `D` and `V`, their
binary-output loop and its F-local TX-error handler. Both commands, including
lowercase forms, now report `REFUSED: command`. The banner and `?` help list
only L/R, A/B, banks 0�3 and C1/C2/C3. The completion text is `LOADED; R runs`.
MON's D command remains its ordinary hex dump.

The owner permits recovery to overwrite the RLP1 destination; no recovery
backup or loaded-image readback command remains. RLP1 still admits only
`$2000�$5FFF`, checks header/payload CRC, length and entry/range, and enables R
only after a valid completed load. RAM outside the loaded span, reserved ABI
RAM, bank protections and the read-only F journal policy are retained. The
initial wait/Ctrl-C behaviour and both consoles are unchanged.

| F budget | b11 | b12 |
|---|---:|---:|
| Body span, including internal padding | 4,063 | 3,969 |
| Reserved hardware vectors | 32 | 32 |
| Contiguous free bytes at end | 1 | 95 |
| Known internal reusable padding | 7 | 94 |
| Total available bytes, split across regions | 8 | 189 |

The net gain is **181 bytes**, including **94 additional contiguous bytes**.
The 98-byte removed output region now holds 94 bytes of former trailing boot
text/helpers. Other vacated text/dispatch/error areas remain explicit padding
so existing shared PR04 entry addresses stay fixed. Internal padding is not
one contiguous allocation. Each MON remains 3,830 body +128 header bytes,
with 138 free. MON changes are identity/generation/header CRC only; CONFIG,
the opaque RAM installer and copied console/vector binaries are byte-identical
to b11. Use `prototype-report.json` for the named padding regions and symbols.

Build: `BUILD/pr04-b12-no-readback-r4/`. `b12-qualification.json` binds 500
passing offline groups: 426 regression/selection (352 core +74 selection),
32 wait/cancel/raw input, 36 command/help/removed-DV/load-run, two complete USB
wait instruction measurements and four bench CPU/MON cases. The frozen b06
checker remains unchanged; `test_b12_core.py` explicitly replaces the obsolete
D/V tests with removed-command refusal checks, retaining CRC/range/console,
CONFIG writer and journal interruption coverage. Both CPU and console models
are exercised. Final qualification has zero failures; preliminary build-wrapper
and receipt-checker errors were corrected before qualification.

The initial b12 build and 500 firmware groups were offline. A separate,
preimage-bound b11-to-b12 deployment is now complete on 2512. 2604/2609 remain
RC1 g0034 and were not opened or flashed. Deployment evidence is in
`output/qualification/pr04-b12-2512-install/test-results.json`.

Physical-reset capture received the complete WAIT/chooser/six-to-zero/b12
banner before any host TX. Live software J3 -> S reached the reduced recovery
menu; ? help, R without an image, and D/V/d/v refusal passed before load and
after Ctrl-C. L waited over 12 seconds and cancelled cleanly; a delayed RLP1
load ran the opaque installer, which read B0:8 with a verified raw sector CRC.
After return to MON B, all 2,412 RAM-tool bytes matched the predicted executed
image, including the exact 23-byte request/CRC/page workspace. This independent
check uses MON D; it does not restore recovery D/V commands.

Full flash readback matched the expected target; recovery probes changed no
flash. Existing C/D snapshots and RTC sectors were preserved with zero C/D
erases. Owner application RAM was restored with three complete comparisons,
then compared again after the final ordinary full-countdown software boot;
owner zero page passed two final comparisons. MON B/BOTH is the final state,
all pending restoration/reset flags are clear and the serial lease is idle.

All 561 qualified offline groups passed: 500 firmware groups plus 19 buffered
no-D/V probes, two CPU executions of F load/run and independent MON readback,
ten native installer fault models, six source/target host/reset-watcher cases,
13 admission/refusal cases and 11 source-backup cases. The first offline
post-execution comparison was corrected to account for the RAM installer's
embedded mutable workspace; the final comparison checks its predicted bytes
rather than excluding them. ACIA electrical qualification remains outside this
FT245 hardware test. The generic image remains non-deployable without a fresh
board-specific backup, admission and qualified installer plan.

```text
python prototypes/boot-record-v2/build_b12.py --out BUILD/<fresh-b12-directory>
python prototypes/boot-record-v2/test_b12.py --build BUILD/<fresh-b12-directory>
python prototypes/boot-record-v2/test_b12_wait.py --build BUILD/<fresh-b12-directory>
python prototypes/boot-record-v2/test_b12_commands.py --build BUILD/<fresh-b12-directory>
python prototypes/boot-record-v2/test_b12_usb_wait.py --build BUILD/<fresh-b12-directory> --cpu 65c02
python prototypes/boot-record-v2/test_b12_usb_wait.py --build BUILD/<fresh-b12-directory> --cpu 65c816-e
python prototypes/boot-record-v2/bench_b12.py --build BUILD/<fresh-b12-directory>
python prototypes/boot-record-v2/qualify_b12.py --build BUILD/<fresh-b12-directory>
```


## b11 recovery help and absent-image diagnostics

`2.0proto b11`, generation `8000000B`, adds `?` at `REC>` and makes `R`/`V`
without a verified image say `REFUSED: no valid RAM image`. No receive timer
runs in either command. A new `L`, its cancellation, and startup invalidate
run permission; successful framed load restores it.

The recovery help describes L/R/D/V, monitor A/B, configured banks 0�3 and
runtime console selection C1/C2/C3. `L` accepts RLP1, not a bare `.bin` or S19:
16-byte header followed by the payload. Header fields are `RLP1`, format 1,
ABI 1, load/length/entry as little-endian u16, payload CRC16, header CRC16.
Header CRC covers the first 14 bytes; both CRCs are CCITT-FALSE.

`D` retains its existing protocol: 16,384 raw bytes from `$2000�$5FFF`, then
CRC16 low byte/high byte. `V` sends only the verified loaded range plus its
CRC. Neither binary body is a readable hex dump. Full application RAM is
`$0200�$64FF` (25,344 bytes); the deployment backup captures that whole range,
as well as owner zero page, before borrowing any application RAM. The F RAM
loader deliberately admits only `$2000�$5FFF`.

F remains 4,063 body bytes plus 32 reserved hardware-vector bytes, leaving
one byte. The patch reclaims branch-trampoline bytes in the menu/loader and
read-only boot-record reader; all shared/public entry addresses, including
`BOOT_CHECK_FIELDS`, remain fixed. Startup timing, copied worker/vectors,
standalone CONFIG/opaque installer, and their journal writer binaries are
byte-identical to b10. Each MON remains 3,830 body +128 header, 138 bytes free;
MON changes are identity, generation and header CRC only.

Build and offline receipts: `BUILD/pr04-b11-help-r7/`. Checks cover 426 core/
selection groups, 32 wait/cancel/raw receive groups, 24 additional help/raw/
absent-image groups, two complete USB timing measurements and four bench
CPU/monitor cases. Hardware claims require the separate completed deployment
receipt; a prototype build alone does not authorize installation.


2512 hardware verification is complete. Both full target readbacks matched;
software `J3 -> S`, `?`, precise invalid `R`/`V` refusals, a 12.047-second idle
load wait followed by Ctrl-C, delayed RLP1 load/V CRC readback and read-only
OIP1 sector read all passed. Full application RAM was restored and compared
three times, then compared again after the ordinary complete software boot;
owner zero page passed two final comparisons. The final session is MON B,
BOTH console, with the shared serial lease released. 2604/2609 were untouched.

The two-hour physical-reset receiver expired before the owner reset; its log
and partial capture are empty. Physical-reset boot is **not** claimed as
captured. After owner reset confirmation, verification resumed on the exact
installed target without another physical reset, and captured the full
`WAIT...`, chooser, `Boot : 6 5 4 3 2 1 0` and b11 monitor banner via software
J3. The report records one capture timeout separately from the passing
functional tests. All 533 qualified offline groups passed.

Evidence: `output/qualification/pr04-b11-2512-install/test-results.json`,
`final-BOTH-software-boot.txt`, `software-boot-recovery.txt`,
`b11-help-fresh.txt` and raw `serial-post-reset-*.jsonl` in that directory.

## b10 indefinite initial binary wait

`2.0proto b10`, generation `8000000A`, keeps the b09 startup sequence: two
seconds silent USB wait, one-second `WAIT...` drain, then six-to-zero countdown.
After `L` prints `SEND HEADER+BIN`, it waits indefinitely for the first byte
from the initiating console. Ctrl-C at that point returns directly to `REC>`
without `REFUSED`. Repeated cancellations retain the ordinary prompt stack.

The first non-cancel byte starts the RLP1 frame. Remaining header and payload
bytes use the bounded 65,536-empty-poll receiver; `$03`, CR, LF and every other
byte remain raw data. CRC, signature, range, entry and receive-error checks
remain required before an image becomes runnable. `L` expects the RLP1 header
plus payload, rather than a bare `.bin`. A partial transfer still times out and
invalidates the image; RAM already received is not automatically restored.

Three unnecessary long branches in the timed reader were compacted. Six of
the nine reclaimed bytes dispatch header byte zero, and three NOPs remain on
the empty-poll path. The appended first-byte wait/cancel code uses 16 bytes.
F uses **4,063 bytes plus 32 reserved, one byte free**. Each MON remains
**3,830 body bytes plus 128 header bytes, 138 free**. Public ABI entries and
external private entries retain their addresses; only internal timed-reader
labels change. Worker, vectors, RAM CONFIG and OIP installer binaries remain
byte-identical to b09. Monitor changes are identity/generation and header CRC.

```text
python prototypes/boot-record-v2/build_b10.py --out BUILD/pr04-b10-wait
python prototypes/boot-record-v2/test_b10.py --build BUILD/pr04-b10-wait
python prototypes/boot-record-v2/test_b10_wait.py --build BUILD/pr04-b10-wait
python prototypes/boot-record-v2/test_b10_usb_wait.py --build BUILD/pr04-b10-wait --cpu 65c02
python prototypes/boot-record-v2/test_b10_usb_wait.py --build BUILD/pr04-b10-wait --cpu 65c816-e
python prototypes/boot-record-v2/bench_target.py --build BUILD/pr04-b10-wait
python prototypes/boot-record-v2/qualify_b10.py --build BUILD/pr04-b10-wait
```

The offline matrix covers 426 regression/selection groups, 32 receive groups,
two complete USB wait measurements and four CPU/monitor bench-image cases.
Receive tests exceed the former initial timeout on both consoles and CPUs,
cancel repeatedly, load 4 KiB containing all byte values, preserve `$03` in
the remaining header and payload, enforce initiating-port ownership, and
retain partial-header/payload timeouts. Evidence is bound in
`BUILD/pr04-b10-wait/b10-qualification.json`.

2512 was updated from its fresh b09 backup in
`output/qualification/pr04-b10-2512-backup-r3/`, after ten native transaction
models, six exact-runtime/reset-watcher checks and eleven admission cases
passed. Buffered backup and live-probe helpers passed eleven and three cases.
Only F and MON A/B were erased, after a committed native wear reservation;
original C/D snapshots, boot settings, B0/B1/B2 and RTC history were retained.

Captured hardware evidence confirms physical-reset b10 boot, full expected
flash readback, and software `J3 -> S` without another reset. `L` waited
12.016 seconds without output, then Ctrl-C returned to `REC>` without refusal.
A separate three-second initial wait preceded an RLP1 transfer and exact CRC
readback of the 2,412-byte OIP tool, including `$03` payload bytes. Its read-only
B0 sector check passed and subsequent full flash readback remained unchanged.
Original application RAM (25,344 bytes) and owner ZP (224 bytes) were verified
restored. The final no-selection six-to-zero boot selected MON B in BOTH mode;
the serial lease was released. 2604/2609 ports were not opened and their records
are unchanged. The full evidence audit, counts and limitations are in
`output/qualification/pr04-b10-2512-install/test-results.json`.

## b09 two-second USB wait (offline)

```text
python prototypes/boot-record-v2/build_b09.py --out BUILD/pr04-b09-usb2
python prototypes/boot-record-v2/test_b09.py --build BUILD/pr04-b09-usb2
python prototypes/boot-record-v2/test_b09_usb_wait.py --build BUILD/pr04-b09-usb2 --cpu 65c02
python prototypes/boot-record-v2/test_b09_usb_wait.py --build BUILD/pr04-b09-usb2 --cpu 65c816-e
python prototypes/boot-record-v2/bench_target.py --build BUILD/pr04-b09-usb2
```

`2.0proto b09`, generation `80000009`, reduces the silent USB wait to two
seconds. The one-second `WAIT...` input drain and six-second
`Boot : 6 5 4 3 2 1 0` countdown remain. Recovery selections start on a new
line, and `REC>` accepts guarded bank commands `0` through `3` as in b08.

The entire F sector differs from qualified b08 by exactly one instruction
operand: the silent wait loop count changes from 30 to 20 tenths. All other
F bytes, addresses, binary handlers, drain and countdown code remain identical.
The b08 countdown timing receipts therefore apply to those unchanged bytes;
b09 separately measures the complete two-second wait with actual instructions.
MON A/B receive the new build identity and generation. Sizes remain F 4,047
bytes plus 32 reserved (17 free), and each MON 3,958 bytes including its header
(138 free). No boards are changed by this offline build or qualification.

Qualification passed all 426 regression/selection groups, both complete USB
wait timing cases and four CPU/monitor-slot bench cases, with zero failures.
Both CPU models measured 15,998,781 cycles, or 1.999847625 seconds at 8 MHz,
with no input access or output during the wait. Evidence and artifact hashes
are bound in `BUILD/pr04-b09-usb2/b09-qualification.json`.

Board 2512 was subsequently updated using the exact b07 preimage from
`output/qualification/pr04-b09-2512-backup-r2/`. The native installer model
passed ten success/refusal cases, the exact source/target host checks passed
six cases, and eleven positive/negative admission cases passed before flashing.
Only F and MON A/B were erased; one native snapshot durably reserved all three
attempts, with no C/D erase. Original native records and boot settings were
retained, with the monitor generation updated to `80000009`.

The prearmed receiver captured the owner's physical reset boot through the
complete six-to-zero countdown into MON B. Subsequent software `J3` with CRLF
followed by `S` entered recovery on a new line without another physical reset.
All four flash banks matched the exact expected image; RLP1 binary load/readback
and a read-only OIP1 B0 sector read passed without changing flash. Full original
application RAM and owner ZP `$00-$DF` were verified restored, with a final
default MON B boot in BOTH console mode and the serial lease released.
2604 and 2609 were not opened or changed. Hardware receipts and captured boot
text are in `output/qualification/pr04-b09-2512-install/test-results.json`.

## b08 selection and six-second countdown (offline)

```text
python prototypes/boot-record-v2/build_b08.py --out BUILD/pr04-b08-six-second
python prototypes/boot-record-v2/test_b08.py --build BUILD/pr04-b08-six-second
python prototypes/boot-record-v2/test_b08_countdown.py --build BUILD/pr04-b08-six-second --cpu 65c02
python prototypes/boot-record-v2/test_b08_countdown.py --build BUILD/pr04-b08-six-second --cpu 65c816-e
python prototypes/boot-record-v2/bench_target.py --build BUILD/pr04-b08-six-second
```

`2.0proto b08`, generation `80000008`, retains the three-second silent USB
wait and one-second input drain. The countdown is now `Boot : 6 5 4 3 2 1 0`,
with six elapsed seconds from 6 to 0 at the nominal 8 MHz clock. A recovery
selection starts its heading on a new line, and opaque bank handoff emits CRLF
before entering the configured image. MON A/B already start their banners
with CRLF. Ignored keys still do not select or restart the countdown.

Recovery now shows `Recovery L/R/D/V A/B 0-3 C1/2/3`. At `REC>`, enter an exact
one-character `0`, `1`, `2` or `3` command followed by Enter to select that
opaque bank. This uses the existing validated entry page and enable mask, and
rereads the boot record before every recovery bank handoff. Disabled banks or
invalid records return to recovery; no default, journal, wear count or RTC
setting is written. MON A/B need not be present. `C1`, `C2`, `C3` still select
FT245, ACIA or BOTH consoles respectively; they are not bank commands.

`L` expects an RLP1 header plus payload, `R` runs only a valid loaded image,
`V` returns its binary payload plus CRC, and `D` returns the raw `$2000-$5FFF`
RAM escrow plus CRC. `D` is not a hexadecimal terminal dump. The RAM CONFIG
and opaque installer binaries and their binary-transfer handlers are unchanged.

F uses **4,047 bytes plus 32 reserved, 17 free**. Each MON uses a
**3,830-byte body plus 128-byte header, 138 free**. The new recovery digit
dispatcher reuses the unused 36-byte old chooser string; twelve appended bytes
provide the newlines. Every pre-existing private entry address, copied worker,
vectors and standalone RAM tool stays unchanged. This is an offline bench
prototype; it does not itself install or authorize a board update. The earlier
three-second b08 development folder is superseded by `pr04-b08-six-second`.

The six-second candidate passed 426 regression/selection groups (352 inherited
regression groups and 74 new selection groups), with zero failures. Complete
countdown execution on 65C02 and 65C816 emulation models measured 5.9980545
seconds from 6 to 0 on both FT245 and paced ACIA paths at 8 MHz. All four
CPU/monitor-slot bench-image cases passed. These are offline results; no board
was accessed or flashed. Receipts are in `BUILD/pr04-b08-six-second/`.

## b07 boot display

```text
python prototypes/boot-record-v2/build_b07.py --out BUILD/pr04-b07-startup
python prototypes/boot-record-v2/test_b07.py --build BUILD/pr04-b07-startup
```

`2.0proto b07`, MON generation `80000007`, retains `PR04` and the b06
three-second silent USB wait, one-second input drain, then three-second
countdown. Its display is:

```text

WAIT...
S=Recovery  A/B=Monitor  0-3=Bank
Boot : 3 2 1 0
```

F uses **4,035 bytes plus 32 reserved, 29 free**. Each MON still uses a
**3,830-byte body plus 128-byte header, 138 free**. The new strings and print
wrapper are appended; existing chooser operands select them without moving
any prior PR04 code entry. CONFIG, the opaque installer and RLP1 packet, the
copied worker and vectors are byte-identical to b06. The b06 builder and
qualification sources remain unchanged; separate b07 wrappers bind the new
text expectations and linked components. This is the same bench profile with
legacy auxiliary commands inactive. Board installation and boot evidence are
captured separately, using fresh preimage-bound backups and serial leases.

## b06 USB wait, input drain and countdown

```text
python prototypes/boot-record-v2/build.py --bench-core --startup-drain --out BUILD/pr04-b06-startup-r2
python prototypes/boot-record-v2/test.py --build BUILD/pr04-b06-startup-r2
python prototypes/boot-record-v2/test_boot_startup.py --build BUILD/pr04-b06-startup-r2
```

`2.0proto b06`, MON generation `80000006`, keeps the `PR04` private-call
contract. Startup and software `J3` wait silently for nominally three seconds
without reading input, then print `Consuming input` and actively discard both
FT245 and ACIA input for one second. They clear software receive state, errors,
line ownership, CRLF state and the old RAM run permission before the chooser.
The chooser then displays `3 2 1 0` over three seconds, accepting selection
keys throughout, and boots the saved default immediately after 0. Total time
is about seven seconds plus message and image-validation overhead.

The drain has a fixed budget of 32,256 polls per receiver; input cannot prolong
it. This clears normal buffered keyboard input and paced ACIA traffic. It is
not a promise to empty an arbitrary host backlog or stop a sender that keeps
transmitting after the deadline. Startup waits/draining are never entered
from a binary-transfer handler. F does not write the boot record or RTC.

Actual F size is **3,987 bytes plus 32 reserved, 77 free**. MON A/B remain
**3,830-byte bodies plus 128-byte headers, 138 free each**. Appending the new
wrapper and changing only the existing three-byte chooser entry keeps every
prior PR04 private-call address fixed. RAM CONFIG, the opaque installer and
its RLP1 packet, the copied RAM worker and vectors are byte-identical to b05
PR04. They must still be bound to this exact runtime when used.

The dedicated startup suite executes the complete timing paths and both
physical-receiver models, including input during the USB wait, buffered and
continuous traffic, blocked output and late selection keys. Its local timing
adapter documents corrections for the installed emulators' BRA and absolute
DEC cycle counts against the WDC data sheets; no vendored emulator is edited.
Timing is CPU/register-model evidence, not an electrical measurement.

The owner has authorized a preservation-bound b04-to-b06 update on 2512.
Physical installation, boot/recovery evidence and original RAM restoration
are recorded separately from this offline component build. Other boards are
outside that update scope; this remains the bench profile with legacy
auxiliary commands inactive.

## b05 startup countdown, PR04 compatibility (offline only)

```text
python prototypes/boot-record-v2/build.py --bench-core --boot-countdown --out BUILD/pr03-b05-countdown-r3
python prototypes/boot-record-v2/test.py --build BUILD/pr03-b05-countdown-r3
python prototypes/boot-record-v2/test_boot_countdown.py --build BUILD/pr03-b05-countdown-r3
```

The optional `--boot-countdown` build identifies itself as `2.0proto b05`,
MON generation `80000005`, with bootstrap contract `PR04`. It displays
`3 2 1 0`: 3 immediately, one second between numbers, then the saved default
immediately after 0. There is no fourth one-second wait. Both initial consoles
receive the display, and startup keys are polled in nominal 10 ms slices.
CR, LF and invalid keys do not select the default or restart the countdown.
This includes a late LF after a software `J3` restart. `S`/Ctrl-C, A/B and
0/1/2/3 retain their existing validated selection paths.

This UI uses a fixed nominal three seconds at 8 MHz. F continues to read the
saved target from C/D and never writes the journal. The stored timeout byte
is preserved but is not used by this optional UI. The b04 builder path and
its original timeout behavior remain available without `--boot-countdown`.

Actual b05 bench sizes are **F 3,865 bytes plus 32 reserved, 199 free**;
**MON A/B 3,830-byte bodies plus 128-byte headers, 138 free each**. The
RAM worker remains 1,000 bytes, RAM CONFIG 1,176 bytes, opaque installer
2,412 bytes and shared writer 983 bytes. CONFIG and the installer are relinked
to the moved private F addresses; their b04 receipts are not reused as b05
qualification. Countdown tests bind their results
to the linked components and measure complete instruction timing, including
both-console ACIA output pacing. They do not establish electrical timing.

PR04 prevents manually launching a b04 MON under b05 F or the reverse: private
F call addresses have moved. The preliminary PR03-tagged b05 r2 candidate is
superseded and must not be deployed. Generic RLP1 remains an arbitrary RAM
loader; it does not certify a downloaded tool's private F calls. Use only the
CONFIG/installer components linked and hash-bound to the exact F build.

This is an offline candidate; no board has been changed to b05. The qualified
2512 b04 installation and its captured evidence remain separate. A preserving
b04-to-b05 hardware update has not been prepared or qualified here.

## PR03 opaque-image RAM installer

```text
python prototypes/boot-record-v2/build.py --opaque-installer --out BUILD/pr03-opaque-final
python prototypes/boot-record-v2/test.py --build BUILD/pr03-opaque-final
python prototypes/boot-record-v2/test_journal_admission.py --build BUILD/pr03-opaque-final
python prototypes/boot-record-v2/test_opaque_installer.py --build BUILD/pr03-opaque-final
```

This iteration keeps bootstrap contract `PR03` and uses a new, experimental
identity: `2.0proto b04`, MON generation `80000004`. It is not an RC1 release.
F's bytes are unchanged from the dual-console baseline. The tool is downloaded
through F's verified `L` command and entered with `R`; neither MON is required.

| Component | Body bytes | Header/reserved | Free |
|---|---:|---:|---:|
| F | 3,823 | 32 vector bytes | 241 (`$00F1`) |
| MON A / MON B, component variant | 3,821 each | 128 each | 147 each |
| MON A / MON B, bench variant | 3,830 each | 128 each | 138 each |
| RAM CONFIG | 1,176 | none | loads at `$2000` |
| RAM opaque installer | 2,412 | 16-byte RLP1 transport header | `$2000–$296B` |

The same 983-byte journal writer is independently linked into each MON,
CONFIG and the installer. Its additional 67 bytes reject committed,
equal-sequence snapshots with divergent complete contents, even when the
boot fields agree. This prevents discarding conflicting configuration or
wear history. Uncommitted pages and older sequences retain their existing
handling. F remains a read-only boot-record consumer.

### Whole-sector transfer

At `INSTALLER I Q>`, enter `I` with CR, LF or CRLF. Wait for
`SEND OIP1 HEADER` before sending the 20-byte header:

```text
OIP1 | version=1:u8 | operation:u8 | bank:u8 | sector_page:u8 |
length:u16 | preimage_crc16:u16 | payload_crc16:u16 |
reserved_zero:4 | header_crc16:u16
```

Integers and CRC trailers are little-endian. CRC is CCITT-FALSE; the header
CRC covers its first 18 bytes. Operation 0 reads, operation 1 writes. Length
must be exactly 4096. The sector page must be one of `80/90/A0/B0/C0/D0/E0/F0`.
Operation 0 requires both preimage and payload CRC fields to be zero. Operation
1 requires the current target's preimage CRC even for an identical no-op.
Allowed targets are **B0/B1/B2:8–F and B3:8/9/E**. Both read and write reject
**B3:A/B/C/D/F**, noncanonical banks/pages, reserved fields and other lengths.
Journal mutation is only through the shared writer, never through a supplied
opaque payload. This tool does not install MON images or replace F.

A write waits at `SEND 4096` for the literal payload. It checks receive status,
payload CRC and the current target's preimage CRC before mutation. An exact
byte match returns success without reserving wear or erasing. Otherwise the
journal durably reserves an erase attempt, the RAM worker erases the target,
checks all erased bytes, programs it, and compares every byte plus CRC on
readback. A read returns `READ SECTOR+CRC`, 4096 literal bytes and a two-byte
CRC, then its text result. Binary transfers use only the initiating console;
raw `00/03/0A/0D/FF` are never interpreted as text commands.

`Q` returns to F after a complete operation. Malformed or incomplete binary
frames, receive errors, CRC failures and blocked binary output instead enter
`LOCKED: RESET required`, a raw drain loop. Delayed payload bytes cannot become
`Q`, `L`, `R` or boot commands. Reboot before retrying such failures. Known-boundary
preimage, journal and flash failures return specific refusal diagnostics.

### Preservation and interruption rules

Escrow application RAM before loading the tool. Only its loaded span is
borrowed from application RAM; `$6800–$77FF` is the existing reserved staging
buffer. The journal frame and documented service scratch remain reserved.
Preserve and restore the original application span after use, and verify it
twice. The tool has no RTC time, trim or timezone operations.
An explicit opaque write replaces its whole allowed target sector. In
particular, B3:8/9 can contain the old RTC provider or history; those sectors
are allowed image destinations, not automatically preserved contents. The
2512 firmware migration separately requires them to remain byte-identical.

Opaque target sectors can contain arbitrary bytes, including invalid interrupt
vectors. Target operations skip the optional debugger BRK tags and execute
from RAM with IRQ disabled. Protected B3 remains the journal's execution bank.
An external NMI during an opaque-bank operation is not qualified.

After interruption, the opaque target can be torn. F, MON A/B and a committed
journal remain available. Read the actual target and supply its fresh preimage
CRC before retrying. Interrupted journal rollover can leave a reservation
state that safely refuses another erase; automatic repair of that state is
not implemented. Never bypass that refusal or erase C/D to make progress.
CRC provides error detection, not authentication. Model mutation boundaries
do not qualify electrical brownouts or physical flash failure.

### Board installation profile

The component build retains old auxiliary code that has not been ported to
PR03's moved private services and RAM layout. It is not a deployable full RC1
image. `--bench-core` adds explicit gates and a default BRK handler so those
legacy providers cannot execute. `bench_target.py` composes only F and MON A/B
over the qualified g0034 image; all old auxiliary bytes remain stored intact.
The resulting build supports boot, recovery, dual consoles, basic MON memory
commands and C/P/W. Named apps, RTC/status tools, B2 utilities and DBG1 are
inactive. A full RC1 feature port is separate work.

`deployment_plan.py` prepares a plan bound to repeated 2512 source captures.
It preserves owner sectors, RTC/TZ and all settings except the MON generation
pin. It reserves all planned erase attempts before mutation and bridges the
old/new journal formats during F replacement. The CPU migration model checks
each NOR mutation prefix. A model-passing plan is not hardware admission;
the selected feature profile, lease, fresh preimage checks, device verification,
reset, boot, flash readback and application-RAM restoration must also pass.
Replacing F itself has an unavoidable interval with a torn root sector;
power loss in that interval requires external recovery. The journal migration
model proves durable history accounting, not bootability of a partially
programmed F. This differs from OIP1 operations, which cannot target F.

Test counts, hashes and any failures are recorded in each build directory's
`cpu-tests.json`, `journal-admission-cpu-tests.json` and
`opaque-installer-cpu-tests.json`. MON-absent loading and interrupted writes
are offline tests. Do not present them as live hardware results.

### Full RC1 compatibility

Restoring all RC1 tools requires source changes and regression qualification;
regenerating address includes alone is insufficient. The bench gates avoid
executing these incompatible paths while retaining their stored bytes.

- **Private bindings:** regenerate `src/current/core/app-fixed-symbols.inc`
  (including `AP_SLOT_ROUTE`), `banner/kernel-private.inc`, the `status-links.inc`
  copies in `status`, `loader` and `mode`, `version/version-links.inc`,
  `version/boot-symbols.inc`, `source-store/worker-equ.inc`, `xip/kernel.inc`
  and `debugger/generated.inc` against the new F, worker, MON and E links.
  `edu/edu.inc` also embeds CRC and private call addresses. The XIP entry,
  reader and provider tables in `status/storage-services.inc`,
  `xip/work-stub.asm`, `xip/dispatch.inc` and `batch/batch-gate.asm` must follow
  the rebuilt utilities rather than the g0034 addresses.
- **RAM ownership:** the 68-byte XIP gate at `$7B90–$7BD3` and 34-byte B29
  queue at `$7BD4–$7BF5` overlap the PR03 worker. These 102 bytes need a new
  allocation or a revised gate/worker design; the worker's 20 spare bytes do
  not accommodate them. `$7D90–$7DCA` is occupied by the SR request/header and
  state, not free scratch. Preserve application RAM, the RTC gateway, journal
  frame, full 4 KiB staging buffer and debugger state. The separate 92-byte
  B29 gate remains at `$7C90–$7CEB`; its `$7C90/94/98/9E/9F` entry references
  in MON, CLOCK and XIP utilities must remain consistent with any relocation.
- **Wear format:** `battery/battery.asm` and `maintenance/maint.inc`'s
  `MM_MAP_WEAR` read WC counters at `$6718`.
  SNBT counters begin at `$6740`; the display must also respect the
  unknown-history mask at `$67A0–$67A3` and preserve its lower-bound meaning.
- **EDU settings:** `edu/edu.inc` saves through the legacy promotion entry.
  PR03 promotion also changes the saved boot default to MON A/B. Add a
  configuration-only save operation that preserves the SNBT default, entry
  pages, generation pin, counters and history when EDU ON/OFF changes.
- **Initialization order:** publish the MON journal handler before
  `AP_CHECK`/`$E014` enters `mode/status-mode-init.asm`. Its early
  `BOOT_API_READ` currently precedes handler publication, so a restored E
  provider would fall back to EDU ON instead of honoring saved OFF.
- **Command semantics:** update `xip/dispatch.inc`'s embedded help and batch
  admission for PR03's C/default and recovery behavior; the old arbitrary
  autostart command contract is intentionally replaced.

Qualification must cover both CPUs and MON slots, EDU cold ON/OFF and saved
settings, both consoles and batch cancellation, named apps and all XIP entry
paths, WORK APIs, SRAM/SR/source-store writes, DBG1 guards/shared MON commands,
VERSION/status/BATTERY wear reporting, RTC/TZ and interrupted durable writes.
Existing starting points are `tools/test_resident_batch.py`,
`tools/test_rc1_source_store.py`, `tools/test_rc1_source_flash.py`,
`tools/test_rc1_source_flash_edges.py`, `tools/test_rc1_debugger.py`,
`tools/test_resident_version_full.py`, `tools/test_rc1_sample_walkthroughs.py`
and the prototype CPU suites. These checks must bind to the newly composed
image; the old g0034 reports do not qualify a PR03 full image. No hardware
qualification of this port has been performed.

## Dual-console iteration (PR03 baseline)

```text
python prototypes/boot-record-v2/build.py --dual-console --out BUILD/boot-record-v2-dual-console-final
python prototypes/boot-record-v2/test.py --build BUILD/boot-record-v2-dual-console-final
```

Identity: `2.0proto b03`, bootstrap `PR03`, experimental MON generation
`80000003`. Both FT245 and ACIA are initialized and enabled at every F reset.
This is an offline component experiment; all three boards, the selected
`src/current` tree and the qualified g0034 firmware remain unchanged.

| Component | Body bytes | Header/reserved | Free |
|---|---:|---:|---:|
| F | 3,823 | 32 vector bytes | 241 (`$00F1`) |
| MON A | 3,754 | 128 header bytes | 214 (`$00D6`) |
| MON B | 3,754 | 128 header bytes | 214 (`$00D6`) |
| RAM CONFIG | 1,109 | none | loads at `$2000` |

F spans `$F000–$FEEE`; `$FEEF–$FFDF` is free. This costs 273 more F bytes
than PR02. Each MON has the same body size as PR02, with updated service
addresses, header compatibility/generation and debugger trampoline initializer.
The shared editor is now 184 bytes; the parsers remain 71. Journal writers
are still independent 916-byte copies at `$AB96–$AF29`, `$BB96–$BF29` and
`$20C1–$2454` in RAM CONFIG.

The console has enable masks `1=FT245`, `2=ACIA`, `3=BOTH`; recovery commands
`C1/C2/C3` select these modes at runtime. Selection does not write C/D or the
RTC and is reset to BOTH on console initialization/F reset. Saved transport
preferences are not implemented. Initial banners, prompts and text echo go to
both enabled outputs. Input polling alternates fairly when both are ready.
The first input port owns a line; competing input is discarded through that
port's line terminator, including when its tail arrives after ownership ends.
Ctrl-C from either enabled port cancels text input. CRLF pairing is tracked
per port, avoiding a pending LF swallowing the other port's first line.

GETC, PUTC, RAW_POLL, CHECK_CANCEL and RX_RESET retain their fixed RAM entries.
PR03 adds `POLL` at `$7E58` and `CHKC` at `$7E5B`, with extension signature
`DC` at `$7E5E`. Both preserve X/Y and the selected bank. POLL consumes a
queued text byte with C=1, or returns C=0 empty. CHKC services one receive
byte and reports availability without consuming the queued byte. Ctrl-C is
reported as byte 03 by GETC/POLL. The existing capability query now executes
in the RAM worker, freeing its old alignment gap for these two JMP entries.
Text queue ownership is released at an empty-queue CR/LF boundary, so direct
GETC clients can also change ports. The editor and CRC/hex services remain in
F and require B3 visible; all console I/O executes in RAM.

FT245 text output checks readiness once. If blocked or absent, it skips the
byte, sets sticky bit 0 at `$7C2E`, and still sends to ACIA; it does not queue
skipped output for later replay. The ACIA transmitter retains its existing
fixed pacing at 19200 baud/8 MHz. It does not wait on TDRE. The register model
uses the receive flags and data-read clearing described in the
[WDC W65C51N datasheet](https://www.westerndesigncenter.com/wdc/documentation/w65c51n.pdf).
Tests cover TDRE held both low and high. A CTS/physical-wire block is not
software-detected: the driver continues paced writes, allowing FT245 to keep
working, but cannot promise ACIA delivery in that condition.

L, D and V pin binary input/output to the port that entered the command.
The other port is not read and receives no raw payload or CRC. Its buffered
input remains pending; hosts should leave that port quiet until transfer
completion. After completion/refusal the selected text mode resumes. Raw
00/03/0A/0D/FF bytes retain their values. A blocked FT245 binary output
aborts with `REFUSED: TX blocked`, clears binary ownership, and allows a
retry; a short failed transfer never pretends to have a valid trailer.
Receive parity/framing/overrun flags reject the load even when data CRCs
otherwise match. A failed receive leaves run permission invalid. The host
must wait for `SEND HEADER+BIN` before sending any header/payload bytes.

### RAM and preservation budget

- Worker: **1,000 bytes**, `$7800–$7BE7`, leaving 20 bytes before existing
  debugger metadata at `$7BFC–$7BFF`. Fixed bank selector `$7848` is retained.
- Console state: seven bytes at `$7C29–$7C2F`; TX reuses existing RX scratch.
  The debugger registry at `$7C30–$7C3F` remains separate.
- The 15-byte debugger trampoline moves from `$7B81` to `$7C50–$7C5E`,
  between writer input and handler state. Its existing fast-return area
  `$7EF5–$7EFF` and batch-provider scratch remain intact. The vector image
  remains 196 bytes and ends before `$7EE4`.
- No application RAM `$0200–$64FF`, service gateway `$6500–$66FF`, journal
  frame `$6700–$67FF`, or 4 KiB flash staging `$6800–$77FF` is borrowed for
  console code/state. Verified RAM downloads still require range escrow.
- The old worker's resident self-rewrite retry UI is removed. MON F/I already
  prohibit B3 writes, so this path was unreachable through supported MON
  commands; a nonzero SELF request now explicitly refuses before mutation.
  RAM CONFIG still writes C/D through the tested primitives. F remains a
  reader of boot records and does not gain a journal writer.

The final hash-bound test report covers both CPU models, the previous suite,
dual startup/output, either input, simultaneous lines, queue overflow,
cross-port cancellation, all runtime modes, bank-independent POLL/CHKC,
blocked/absent FT245, a blocked ACIA wire model, initial and mid-transfer
FT245 blockage/retry, 4 KiB transfers with every byte value on both ports and
all three text line endings, timed one-byte ACIA receive buffering, error
injection, real CRC/pacing instructions, and actual MON A/B J3→S through ACIA.
It also checks the relocated trampoline through real tagged-BRK journal
operations and every modeled interruption prefix. These are CPU/register/NOR
model results, not live board, electrical or full debugger/provider qualification.

The earlier prototype artifacts and limits below are retained for comparison.

## Shared-console iteration (PR02)

The follow-up prototype moves the line editor, whitespace scanner and hex
word/byte parsers into F. Build it separately; the original PR01 artifacts at
`BUILD/boot-record-v2-prototype-final` are retained:

```text
python prototypes/boot-record-v2/build.py --shared-console --out BUILD/boot-record-v2-shared-console-final
python prototypes/boot-record-v2/test.py --build BUILD/boot-record-v2-shared-console-final
```

Its identity is `2.0proto b02`, bootstrap contract `PR02`, experimental slot
generation `80000002`. None is an accepted RC1 release or a board update.

| Component | PR01 body | PR02 body | Header/reserved | PR02 free |
|---|---:|---:|---:|---:|
| F | 3,413 | 3,550 | 32 vector bytes | 514 (`$202`) |
| MON A | 3,955 | 3,754 | 128 header bytes | 214 (`$D6`) |
| MON B | 3,955 | 3,754 | 128 header bytes | 214 (`$D6`) |
| RAM CONFIG | 1,097 | 1,109 | none | loads at `$2000` |

F grows by 137 bytes, while each MON recovers 201. Its span is
`$F000–$FDDD`, with `$FDDE–$FFDF` free. The 144-byte editor echoes original
printable character case while storing uppercase command text; tab becomes a
space. The 71-byte parser block contains hex word/byte parsing and whitespace
skipping. MON keeps four three-byte JMP thunks, retaining the original call
labels/contracts. F reuses reserved facade slots at `$F01C/$F02E/$F031`, adds
one three-byte skip-spaces entry and replaces its old small line reader.
Recovery and CONFIG check invalid-line status before interpreting any prefix.

The journal/CONFIG engine is still **916 bytes per independent link**:
`$AB96–$AF29` in MON A, `$BB96–$BF29` in MON B, and `$20C1–$2454` in RAM
CONFIG. The whole RAM CONFIG now spans `$2000–$2454`. C/D ownership and all
preservation rules below remain the same. The extra 12 RAM CONFIG bytes reject
malformed text before blank-journal initialization or other commands.

GETC, PUTC, RAW_POLL, CHECK_CANCEL, RX_RESET and console initialization were
already stored in F as part of the **897-byte RAM worker**. They continue to
execute from RAM, which works with any flash bank selected and during flash
busy polling. The worker remains byte-identical to g0034. Copying these
routines to another ROM location would not reclaim their existing F storage;
executing returning console calls in F alone would lose bank independence.
The editor/parsers execute in F and require B3 visible, initialized RAM
services, IRQ disabled, decimal clear, and the existing 816 emulation contract.
They share `$7C00–$7C28` and existing ZP scratch; they are not reentrant and are
not added to the bank-independent RAM ABI.

ACIA implementation code is already counted in that worker: 16 bytes for the
timed transmitter, 12 for raw receive, 5 for its transmit call path, and 16 for
the conditional initialization block (13 register-write bytes plus a 3-byte
guard). These are existing dormant paths. CON_INIT forces FT245, RAW_POLL
returns empty for an ACIA selection, and PUTC suppresses it; there is no
end-to-end enabled ACIA console. This iteration leaves that dispatch unchanged.
Enabling ACIA needs receive/error/cancel and baud/pacing qualification on actual
hardware; FT245 model tests cannot establish that.

PR02's hash-bound `cpu-tests.json` includes the PR01 suite plus parser
differential tests against the original linked MON, line editing through F and
both MON thunks, malformed-prefix rejection in recovery/CONFIG, actual MON D
commands and console RAM calls with each of the four banks visible. Tests
exercise CR/LF/CRLF, original-case echo, BS/DEL/tab, length bounds, invalid bytes,
ESC/control-C and sticky receive errors. Raw binary bytes continue to bypass
text handling. Exact final counts and component hashes are in the report;
there are no serial/device operations. All three boards and `src/current`
remain unchanged. Existing feature-compatibility and deployment limits below
still apply.

## Original PR01 baseline

This prototype builds isolated F, MON A/B and RAM CONFIG components. It never
opens a device; the build and tests block serial/network imports. The selected
`src/current` tree and all three boards remain unchanged. These components are
not an installation kit or a complete firmware image.

Run from the repository root, using an unused output directory:

```text
python prototypes/boot-record-v2/build.py --out BUILD/boot-record-v2-prototype-final
python prototypes/boot-record-v2/test.py --build BUILD/boot-record-v2-prototype-final
```

The builder uses the existing qualified `BUILD/rc1-r10p2-g0034` baseline and WDC
assembler/linker. `prototype-report.json` records source hashes, compiler logs,
component sizes and the selected-source preservation check. `cpu-tests.json`
binds final tests to the component hashes. The experimental slot generation is
`80000001`, bootstrap contract `PR01`, and monitor banner `2.0proto b01`.
This is not a new accepted RC1 generation or distribution revision.

## Actual linked sizes

| Component | Code/body bytes | Other allocation | Free |
|---|---:|---:|---:|
| F | 3,413 | 32 bytes reserved for vectors | 651 |
| MON A | 3,955 | 128-byte image header | 13 |
| MON B | 3,955 | 128-byte image header | 13 |
| Standalone RAM CONFIG | 1,097 | Loads at `$2000` | Within the 16 KiB load window |

F's span is `$F000–$FD54`; `$FD55–$FFDF` is free. Its count includes the
897-byte copied RAM console/bank/flash worker and 196-byte vector image. Flash
primitive pruning has not been credited. F has no journal writer, wear display,
or direct MON flashing command; its legacy service stubs route explicitly to
the active MON/CONFIG handler, or refuse if no handler is installed.

The **916-byte shared journal implementation** has independent ROM copies at
`$AC5F–$AFF2` in MON A and `$BC5F–$BFF2` in MON B. Standalone CONFIG links the
same implementation at `$20B5–$2448`; the whole RAM program spans
`$2000–$2448`. The copies use one source, `engine.inc`, with separate link
addresses. There is no dependency on the other MON slot or an additional flash
sector for this engine. Normal MON journal control executes from its own ROM
copy; all flash busy polling/programming/erase code executes in RAM. Standalone
CONFIG executes entirely from RAM and uses the F-initialized RAM services.

Scratch is the 256-byte frame at `$6700–$67FF`, existing saved ZP/service RAM,
and otherwise unused console-line padding at `$7C40–$7C7F`. Normal journal
operations preserve application RAM `$0200–$64FF`, including when called from
the actual MON command path. CONFIG's downloaded range must be escrowed before
loading; F's `D` operation supports that.

## C/D record format and ownership

Both B3:C and D contain sixteen page-aligned 256-byte snapshots. Offsets:

| Range | Contents |
|---|---|
| `00–1F` | Boot record: `SNBT`, format/length, flags/default, sequence, timeout, bank mask, four entry pages, pinned MON generation, reserved, CRC16 |
| `20–3F` | System configuration, preserving legacy settings |
| `40–9F` | 32 little-endian saturating 24-bit wear counters |
| `A0–A3` | Unknown-history mask |
| `A4–A7` | History/policy flags |
| `A8–FB` | Reserved extension space |
| `FC–FD` | CRC16 of `00–FB` |
| `FE` | Reserved `FF` |
| `FF` | Commit byte: program `00` last |

F checks the boot CRC and final commit, fields, newest sequence and conflicting
equal-sequence records. It does not depend on the full snapshot CRC. MON and
CONFIG also require the full snapshot CRC; they refuse mutation if it fails.
Opaque bank 3 cannot select C/D as its entry. Missing settings select recovery.
Manual A/B selection still requires a valid, compatible monitor image.

The writer verifies before publishing commit. It skips torn pages, reserves
the last source page for an erase intent, increments the peer-sector counter
durably before erase, and retains a committed source while rotating. It can
resume into an already-erased peer. Exhausted reservation space refuses.
Initialization is allowed only when both sectors are entirely blank; it marks
history unknown rather than pretending zero lifetime wear. The W display makes
that unknown status visible. No RTC/TZ/time/trim operations are present.

## Transfer and prototype interface

Startup selects `S/A/B/0/1/2/3` or the saved default. The configured delay uses
nominal tenths at 8 MHz. CPU instruction tests measure the tick; no physical
timing measurement is claimed. Bank handoff uses the existing RAM switching
routine and an explicit entry in `$8000,$9000,…,$E000`.

Recovery commands are `L` (load), `R` (run), `D` (escrow all `$2000–$5FFF`),
`V` (read back the verified loaded range), and `A/B`. Text echoes and supports
CR, LF and CRLF. Binary data bypasses text handling, including `03/0A/0D`.
After `SEND HEADER+BIN`, send a 16-byte header followed by the payload:

```text
RLP1 | format=1 | ABI=1 | load:u16 | length:u16 | entry:u16 |
payload_crc16:u16 | header_crc16:u16
```

Both CRCs are CCITT-FALSE; header CRC covers the first 14 bytes. Load range is
bounded to `$2000–$5FFF`, entry must lie within the received range, and length
must be nonzero without overflow. A new load invalidates the old run permission;
only a complete, checked transfer enables `R`. D/V append a little-endian CRC16
to raw output before the next prompt. The host must wait for the binary-ready
prompt and preserve/reload borrowed RAM. RAM tool behavior itself remains the
responsibility of that tool; a transfer CRC is not code authentication.

MON's prototype `C target` updates the saved default after confirmation; P
promotes a monitor and W reports counts. RAM CONFIG offers `I` (blank-only
initialization), `C target`, `W` and `Q`. It uses the same journal engine.

## Limits

- Each MON has only **13 spare bytes**. Further settings UI and repair policy
  should go into RAM CONFIG or require more monitor space reduction.
- This replaces the old arbitrary-address C/autostart parser. Timeout and
  entry pages exist in the record but do not yet have editing UI commands.
- There is no legacy C/D migration or repair of nonblank corrupted sectors;
  such cases refuse. This prototype does not initialize existing boards.
- Existing auxiliary providers/debugger have not all been relinked to the new
  private ABI. Cold MON tests omit the unchanged E/B2 provider components.
  This is not full RC1 feature compatibility qualification.
- A general opaque-image flash installer is not included. The MON-free test
  proves verified RAM load/run and actual C/D programming through CONFIG.
- NOR interruption tests cover modeled mutation boundaries, not electrical
  brownouts or physical flash failure. Broader hardening is required before
  any deployment.

The test suite covers both CPU models, each MON writer link and the RAM link,
cold A/B boot, actual C/W commands and J3→S, all four opaque handoffs, frame/range
rejection, raw line-ending bytes, RAM escrow/readback, no-MON CONFIG startup,
corrupt/saturated journal refusal, and every observed mutation prefix in an
append and a rollover. Final counts are in the hash-bound CPU report.
