# 2512 named copies and persistent EDU: write review

November 1, 2026. **Review ready, not approved. No persistent writes have been
made for this increment.** 2512 is at REC>, COM4 released, with owner RAM/ZP
restored and read back. Other boards and published downloads are excluded.

## What this installs

The candidate restores the familiar source-retaining copy commands:

```text
B3> R MAINT
BM> X 0 XSRC P XCOPY
BM> X P XCOPY 0 XBACK
```

P selects PROGRAM; S is retained as an alias. The copy requires live Y.
The source stays intact. Flash destinations must be wholly erased; there is
no implicit erase, override or automatic source deletion. AUTO uses complete
erased sectors, skipping occupied/opaque sectors. Eligible destinations are
B0:8-D and B1:E-F; installed utilities remain protected. Duplicate source names
are refused. PROGRAM metadata/payload CRC is checked before copying to flash
and again during streaming; the SR/01 commit marker is written last. SR/01
cannot express a distinct or restore-only entry, so those conversions refuse.
Flash SR/01 still has no payload CRC of its own.

Persistent EDU is deliberately explicit:

```text
BM> EDU
BM> EDU OFF
BM> EDU SAVE OFF
Save EDU mode? Type YES:
BM> EDU SAVE ON
```

EDU ON/OFF changes the session. EDU SAVE requires exact YES and appends one
32-byte ED/1 record in the existing B3:9C00-9FFF metadata arena. It never
erases metadata or writes C/D. Repeating an already saved mode adds nothing.
Full/incompatible arenas, conflicting newest records and exhausted sequences
refuse. The slot is verified before its commit byte is programmed last.
MON gE reads the saved mode on cold entry; warm returns retain session overrides.
No saved record retains the existing default ON behavior.

These commands are **not yet installed**. The present MON remains gD and
installed EDU remains session-only until this review is approved and accepted.

## Placement and bounds

Shared BANK MAINT g3 and SRAM/WORK g3 use their existing three sectors each.
Copies run through the SRAM manager's existing trusted streaming hooks, rather
than loading the source into RAM occupied by the utilities. Native-to-native
handoff returns to BM after the copy/cancel. X is refused in BATCH.

The packed applications are admitted by the unchanged native loader's complete
RP CRC. A bounded RAM decoder checks output length, back references and the
expanded code CRC before entry. It reads compressed input directly from ROM;
ordinary app loading does not borrow owner RAM0200-1FFF for decompression.

| Component | Expanded code | Packed end | Reserved data starts |
|---|---|---|---|
| BANK MAINT | 2000-4712, 10,003 bytes | B1:A08E | B1:A31D |
| SRAM/WORK with X | 2000-515D, 12,638 bytes | B1:D8F2 | B1:D900 |

Existing FLASH gate/record/dense fragments at A31D-AFFD and STORE frontend at
D900-DFFD remain exact. Only each complete RP's outer CRC is resealed. The
editor and each app's return/context areas remain separate from its code.
Named copies restore the original LED latch and volatile SRAM write permission.
This is a tight development layout: the SRAM packed body has14 bytes before
the next reserved allocation. It does not expand Foundation or claim a new ABI.

## RAM evidence

Nine live2512 checks passed, with earlier successful checks carried forward:

- Expanded-code CRC/admission, EDU query and save cancellation.
- Exact OFF/ON ED/1 records, repeated-save no-op and session return.
- Flash-to-PROGRAM parsing, P/S aliases, missing/syntax refusals and NO.
- Real retained NFCOPY PROGRAM CRC and real blank-flash AUTO preview/NO.
- Incompatible/full metadata refusal and a bounded RAM-byte backend failure
  after two bytes, leaving the record uncommitted and the session unchanged.
- Final candidate identity/help, EDU save NO and transfer NO with LED cleanup.

EDU writes were confined to CPU-RAM fixtures, not flash metadata. One flash
source was a bounded CPU-RAM read fixture. The real PROGRAM reverse preview
used the actual SPI source and flash reads. No SPI data was written.
Initial parser/private-request failures and their verified restoration receipts
remain preserved. The final report is:
`output/qualification/2512-named-EDU-RAM-20261101-r5/report.json`.

## Requested new allowance: 12 erases

| Target | Erases | Purpose |
|---|---:|---|
| B1:8/9/A | 3 | Packed BANK MAINT/EDU; preserve FLASH helpers |
| B1:B/C/D | 3 | Packed SRAM/WORK/X; preserve STORE frontend |
| B3:8 | 1 | Saved-EDU reader and shared help in loader padding; RTC code unchanged |
| B3:A/B | 2 | Identical MON gE slots |
| B3:D | 1 | Native journal rotation needed for the new reservations |
| B0:9 | 2 | Exact cleanup of the two temporary named-copy fixtures |
| **Total** | **12** | **Zero F writes, C erases or power cuts** |

The BOOT/wear journal presently has24 valid records, latest C700/seq1133.
Only seven ordinary C append pages remain; CF00 is reserved for erase intent.
The eighth image replacement causes native D rotation. All24 original records
will be archived on the host **before writing**. Rotation replaces16 old D
records on chip; all eight original C records stay exact. Every latest wear
count and boot field is carried forward. This is not preservation of all old
records on chip, and needs explicit owner approval.

The forecast finishes at seq1146 with21 valid records. B0:9 count22→24;
B1:8-D become7/8/9/15/15/16; B3:8/A/B become27/46/53.
Final **C/D/E/F = 56/37/36/24**. Unknown-prior-wear flags remain unchanged.
The saved choice stays B, rebound once at D400 to generation0000000E.
Bank enables, entries, countdown/delay and other boot settings remain unchanged.

Two ED/1 appends at **B3:9D80** (OFF/seq1) and **9DA0** (ON/seq2) qualify
cold persistence, ending ON as before. All12 old metadata records remain exact;
there is no B3:9 erase. Name, fixed offset, battery policy and RTC history stay.

The PROGRAM trial temporarily uses **slot4, SPI00140-0017F**, and payload
**00800-008FF**,320 bytes total. This page contains historical payload bytes;
it is backed up and restored exactly, not assumed blank. Original CLK, CLOCK
and NFCOPY records stay intact. The trial seeds XSRC at the verified-blank
B0:9, copies to PROGRAM, verifies/runs it, erases B0:9, copies back from PROGRAM,
then erases B0:9 to restore all FF. Temporary PROGRAM bytes are restored exactly.
There are no WORKSPACE writes or formatting, deletion/reclaim or mode changes.

Two physical CPU RESET checks are included, with USB power left connected:
saved OFF, then saved ON/default B. RTC time/control/trim/PF state is never set
or acknowledged. Fresh owner RAM0200-66FF and ZP00-DF are restored/read back.
Finish at REC> and release COM4.

## RTC compatibility is part of installation

The active LED/RTCC collector currently pins MON gD. The review includes
versioned2512-only gE LED and native-TIME readers and a small routing adapter.
They use the unchanged qualified LED RAM agent and preserve the original gD
readers/audits. New gE admission requires actual installed startup/TIME plus
preserving read-only qualification. Until qualified,2512 defers; other boards'
existing collection paths keep operating. Only2512's admission/profile changes.
Cadence, NIST reference, clock settings, baselines, points and history are not
rewritten. The candidate routing files are prepared privately and are **not
registered or active**. The live RTC sources/configuration have not changed.

Actual ROM decompression, BM↔SRAM handoff, positive copies, real ED/1 writes,
physical-reset persistence and RTC readmission remain acceptance checks after
the approved installation. A RAM fixture pass does not claim these are closed.

Private pinned targets, originals, raw journal archive, PROGRAM preimages and
forecast: `output/qualification/NAMED-EDU-2512-scope-20261101-r1/plan.json`.
Build: `BUILD/named-edu-g3-r8/manifest.json`. All target preimages and current
admission must still match before any write; stop on a mismatch.

Other boards, F, B2, B1:E/F and all owner images outside the explicitly restored
B0:9 fixture stay unchanged. Published ZIPs/downloads, factory restoration,
ASM/DBG, wide flash AUTO and storage-manager BATCH return are outside this scope.
