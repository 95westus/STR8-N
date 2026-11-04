# 2205/2604 features on 2512/2609

Verification date: November 1, 2026. **Full b35 parity is not closed.**
Subsequent work: the [SRAM/WORK RAM port](SRAM_WORK_RAM_ACCEPTANCE.md) is built
and passed read-only query/guard/return trials on both boards. Positive RAM
trials also passed on 2512 with full SRAM/owner-RAM restoration. The subsequent
[native SRAM/WORK installation](STORAGE_NATIVE_ACCEPTANCE.md) passed on both
boards. That approved write scope is separate from the original read-only
audit below; full b35 parity remains open.
The target is the [unified shipping contract](UNIFIED_SHIPPING_RELEASE.md):
the familiar 2205/b35 and 2604/rc1 workflows on both supported SXB profiles,
with ASM/DBG explicitly deferred. Retained legacy binaries are not proof of
BASE1 compatibility.

The references are the preserved b35 source/build, the owner's transcripts,
and the earlier [CLOCK comparison](CLOCK_2205_EQUIVALENCE.md). This verification
does not open COM3/2205 or COM5/2604. It does not build firmware, use a CPU
simulator, flash a board, change RTC settings or update published downloads.
Independent RTC campaign results, where cited, are attributed separately.

## Installed implementation and evidence

At the initial comparison checkpoint, both boards had golden STR8N-F 0.3.0 g1 / BASE1 / PR05, MON A/B gD,
STATUS g1, services gC, WB2 gD, SRAM/WORK g2, PROGRAM SP1 g2/wide-r5, CLOCK 1.10,
FLASH g1/r16 and BANK MAINT 2.4 / BASE1 g1. MON A and B provide the same
commands. Both saved defaults are B, bound to generation D.

The accepted complete B2 utility bank was identical on both boards at that checkpoint:
`54879c0fbe70ab0da018f8839ab4462c589be79cc016010cfbd9b575c28f979d`.
The local evidence audit binds its WB2 module, PROGRAM provider, complete
CLOCK image and FLASH body to their existing artifacts. Store, PROGRAM,
SRAM and BATCH source includes are unchanged from the accepted batch/wide
checkpoint; other adapters have changed and require current route checks.

Subsequently,2512 received services gD/PROGRAM g3 and the S19/STORE overlay
under the [transfer review](TRANSFER_2512_2609_SCOPE.md). Installed S19 and
actual8KiB PROGRAM Store/Table/load-only Restore passed, with exact source
and temporary SPI restoration.2609 still has the earlier transfer profile;
its newer owner hold prohibits COM8 access until explicit recovery instructions.
The old common B2 hash above is historical, not2512's current bank hash.

Positive write evidence is carried forward with its exact limits, rather
than repeating erases for a help/menu check:

| Evidence | What it establishes |
| --- | --- |
| [BANK MAINT acceptance](BANK_MAINT_ACCEPTANCE.md) | Actual R MAINT on both CPU profiles; copy/compare, editor/write/erase, naming and exact fixture restoration |
| [Native utilities acceptance](2512_NATIVE_UTILITIES_ACCEPTANCE.md) | Native FLASH byte programming, full-sector write/erase and checked restoration; flash/PROGRAM storage workflows |
| [BATCH and large PROGRAM acceptance](2512_BATCH_WIDE_ACCEPTANCE.md) | Positive Store/run, registered 14 KB PROGRAM handoff, load-only through $66FF, cancellation/CRC failure, native app queue return |
| [2512 AP/02 acceptance](2512_AP02_G4_ACCEPTANCE.md), [2609 AP/02 acceptance](2609_AP02_ACCEPTANCE.md) | Checked owner-app launch/return and CRC refusals |
| [Live trim update](MON_TIME_TRIM.md) | Both installed gD slots read current trim/control; saved B default and owner RAM restoration |

These are functional evidence, not a claim that every gate used the latest
MON/WB wrapper. The live route checks and exact unchanged-component binding
must be read with them. Original failed attempts and preservation continuations
remain in their private receipts.

## Workflow comparison

“Accepted” below includes the named prior positive receipt; “query/cancel”
does not mean a setting was successfully written.

| Reference feature | Current route and evidence | Remaining limit |
| --- | --- | --- |
| Rich startup/status | VERSION/V, board name, A/B generation/default, RAM, EDU, PROGRAM/WORKSPACE, local RTCC, wear and battery policy; installed on both | Each board keeps its own data; unavailable storage/health is labelled, not invented |
| Clock sample and trim | MON TIME reads current calendar, trim and control | Explicit sample, not a precision/drift or battery-health measurement |
| Dump/Modify/Go, bank selection | D, M, !M, G, B0–B3; deliberate force and return | Both b35 and current M use inline bytes. D defaults to 16 bytes instead of b35's one; ordinary low-memory edits use deliberate !M under the current guard policy |
| Loading/cancellation | L uses golden F's raw RAM BIN loader; RAM S19 passed on both; integrated S19 Ctrl-C and checked loading through66FF accepted on2512 | Integrated2609 update held. I start/end flash-stream intake remains missing; host BIN/OPAQUE operations are different workflows |
| Maps/wear | M1/M2/M3 and W, all 32 tracked counts; WDC recognition and reservations | Tracked attempts cannot establish prior wear or physical health |
| Familiar maintenance | R MAINT → BM>; copy/compare, Table, naming, 4 KB editor, CRC, write/erase, Q; accepted on both | NAME is board naming; named X transfer is a separate missing feature below |
| Flash edit/erase | R FLASH: READ/VIEW/EDIT/WRITE, BYTE, ERASE; prior positive tests | Golden F and C/D remain protected; utility/self regions also have guards |
| Boot policy/opaque images | BOOT/CONFIG plus qualified host CONFIG/OPAQUE; enabling, entry/default and real opaque default boot tested earlier | Native OFF/DELAY-field/RUN/HOLD positives now accepted on2512. Frozen BASE1 chooser stays3s; old C/P/J/U spellings are not all monitor aliases |
| Table and named restore | STORE/TABLE/RESTORE and S/T/R; explicit flash bank or P, load-only/run; BM TABLE bank/range | WB discovery is admitted/selected scope, not an unconditional four-bank search; SR01 has no payload CRC |
| Flash/PROGRAM AUTO Store | Calculates start in the admitted arena/allocation; preview, confirmation, commit-last and positive storage evidence; installed2512 explicit PROGRAM Store preserved4700-66FF | Not backend selection; large flash STORE remains open;2609 wide-Store update held |
| Large PROGRAM/run | Independent loader through $66FF; registered public-HOLD return and batch continuation; actual2512 large Store/Table/load-only Restore also accepted | Latest large Store receipt is2512-only; its8256-byte SPI fixture was restored exactly |
| APPS and named native tools | R CLOCK / R FLASH / R MAINT; APPS catalogue; APP name for checked owner AP/02 | Existing old binaries are not made compatible merely by listing their SR01 record |
| BATCH | Bounded 34-byte queue; core/native/storage/registered PROGRAM/AP02 return, validation and stop/cancel | Raw protocols, reset/jumps and unsafe handoffs have explicit exclusions |
| Detailed CLOCK | TIME/STATUS/TRIM/EUI/HISTORY/STATS/OFFSET/BATTERY, VERSION and Q; invalid/cancelled settings tested | Actual2512 EUI/offset/battery-limit writes and restoration accepted. Fourteen CPU-RAM cases passed ACK, trim ordering/guards and failures; physical changed trim and battery replacement/date tests are not claimed |
| Set clock | Independent November1 RTC fleet receipts show successful installed CLOCK SET on2512 and2609, preserving control/trim and history | Physical SET began with PWRFAIL clear. Latched SET/ACK archive-before-write and failure handling now pass2512 CPU-RAM fixtures; see CLOCK_FAULT_RAM_2512_ACCEPTANCE.md. Physical latched writes/816 fixture execution remain separate |
| EDU/PROGRAM access | Explicit EDU ON/OFF, SRAM status/PREP/READ, mounted PROGRAM Store/Table/Restore/run; proposed saved-mode reader passed RAM fixtures on2512 | Installed ON/OFF is session-only; confirmed saved mode and reset integration remain open. PREP acknowledges disabled CB flags, not SRAM format/repair |
| Full SRAM manager | R SRAM installed on both; Table, controls and selected-bank Q accepted; positive Store/latest Restore/delete/reclaim/format passed on 2512 with complete SRAM restoration | Resident copy window is 0200–1FFF; small-manager G positive acceptance and checked BATCH return remain open |
| WORK service | R WORK installed on both; capacity/admin menu and Q accepted; positive allocation/I/O/release/bounds/resize/fallback/repair/format passed on 2512 with complete restoration | Resident private API; interactive R WORK is refused in BATCH. No WORKSPACE message journal is claimed |
| Named flash↔SRAM transfer | Can perform reviewed staged copies using existing storage operations | Legacy BM X named transfer is missing; manual staging is not command parity |
| Factory firmware restoration | Host preparer now defaults to F-only preservation; explicit full-B3 requires a32KiB original; scope/rejection tests pass | Not a normal FLASH override; live unified-kit factory restoration remains unqualified and deliberately replaces F |
| Assembler-owned source editor / ASM/DBG | Historic assets/branches retained | ASM/DBG and their embedded source editor are deferred; ordinary source/data storage remains required. The rc1 source arena/debugger is not claimed by current MON |
| Host terminal and manual | Existing Foundation terminal, raw BIN/CONFIG/OPAQUE and migrator retained | A new full-environment extracted candidate must be tested before shipping it |

## Preservation and current live checks

The verification driver admits only current gD and qualified RAM readers.
It borrows CPU RAM temporarily and restores/reads back owner RAM $0200–$66FF
and ZP $00–$DF. SRAM is read only. STORE, flash WRITE/ERASE and CLOCK setting
confirmations receive NO; only BANK MAINT destinations explicitly equal to
CPU RAM receive Y. Flash/journal/RTC-setting/PROGRAM/WORKSPACE writes are zero.

A pre-existing valid TZ append on 2512 selects −06:00. It is preserved as
current owner data; the older −05:00 capture must not be restored over it.
Its C/D and firmware bytes, including F, match the accepted installation.
The verifier initially rejected the valid TZ signature because of a host
schema assertion; it restored owner RAM before that assertion was corrected.
Serial-lease timeouts opened no port and ran no board commands.

The 2512 route run also exposed two host expectation errors, not firmware
failures. TABLE 1 selected bank1 and WB Q correctly returned to B1>; the
driver had waited for B3>. A preserving continuation restored/read back the
saved owner RAM and verified unchanged B3. The corrected driver accepts the
selected-bank prompt and explicitly normalizes its test context. The wide
PROGRAM load-only path on2609 also correctly returned directly to B1>, after
loading a CRC-verified CLK record across the WB region; this return needed
the same selected-bank handling rather than a B3>/WB-only expectation. Golden F
also cancels SEND BIN by redisplaying its minimal recovery menu, without a
separate cancellation sentence. The loader assertion was corrected to that
actual contract. Passed workflows were carried forward; only unfinished
checks were rerun. No firmware repair or rebuild was needed.

The independently authorized UTC synchronization campaign completed a successful
SET on both boards during this audit. Its private evidence is
`output/qualification/rtc-fleet-20261101T084352Z/{2512,2609}/report.json`.
Both receipts verify control/trim unchanged, history preserved and PWRFAIL
clear before/after. This verification did not send those SET commands or
access either reference board. Clock adjustment splits the RTC measurement
series; the campaign retains its own baseline/history accounting.

## Current live checkpoints

2512 completed the current implemented-workflow suite. Its final receipt is
`output/qualification/2512-reference-workflows-20261101-r9/report.json`,
carrying the successful r7/r8 checks and preserving their original host
expectation failures. It includes current PROGRAM load/run of NFCOPY, BATCH,
APPS, initial Ctrl-C at SEND BIN, a normal BIN load, unchanged B3 and restored,
read-back owner RAM/ZP. COM4 was released at B3>.

2609 completed the unfinished checks after the RTC alignment and follow-up
collection finished. Final receipt:
`output/qualification/2609-reference-workflows-20261101-r5/report.json`.
It carries the successful core, map/wear, BANK MAINT, CLOCK and FLASH
query/cancel checks from r1. The continuation passed:

- Mounted PROGRAM Table and EDU/SRAM/WORK query aliases; STORE AUTO
  allocation preview followed by live NO, with no storage write.
- Existing large CLK PROGRAM record load-only, CRC OK, returning correctly
  to the selected-bank monitor. The legacy executable was not run.
- Exact before/after comparison of the 576-byte PROGRAM layout/directory.
- BATCH through native MAINT, CLOCK and storage/workbench, with normal
  continuation, bad-separator refusal and error/unavailable-provider stops.
- APPS native catalogue and refusal of an absent owner app. Owner AP/02
  positive launch/return remains the prior acceptance evidence, not a new
  fixture or positive owner-app launch in this read-only continuation.
- First-byte Ctrl-C at SEND BIN, then a normal BIN load of the qualified
  RAM reader and successful operation of that loaded program.
- Exact full-B3 comparison, including both monitors, settings/metadata,
  all 19 boot/wear records and golden F. B2 matched the admitted utility
  image; B0/B1 were outside all write paths, without another whole-board
  backup/checksum campaign.

The boot/wear sequence remains 1065, saved default B/gD, mask00 and all four
$8000 entries unchanged. Every tracked count is unchanged, including
C=79, D=49 and F=31 (decimal). Fresh owner RAM $0200–$66FF (25,856 bytes) and ZP $00–$DF
were restored and read back. COM8 was released at B3>. There were zero
flash/journal, SRAM-data/WORKSPACE or RTC-setting writes, resets, power cuts,
firmware builds or simulations. This verification did not access 2205/2604.

The composite evidence report is
`output/qualification/reference-parity-audit-20261101-r1/report.json`.
Both boards' current implemented-workflow checks are now closed. The missing
features and unqualified write/packaging gates in the comparison above remain
open; this is not full-b35 parity or a new shipping release.

No new positive flash/PROGRAM write or administrative setting test is implied
by these read-only checks. This document does not authorize additional erases
or clock changes.
