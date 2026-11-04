# 2512 named transfers and persistent EDU acceptance

November1,2026. Installed and accepted on2512 only: MON A/B gE,
BANK MAINT g3 and SRAM/WORK g3, above unchanged Foundation0.3.0 g1
BASE1/PR05. Published downloads and the other boards are unchanged.

## Implemented and verified

`R MAINT` provides source-retaining named copies in both directions:

```text
BM> X 0 APP P APP
BM> X P APP 0 APPBACK
```

These are usage examples; APP must exist at the specified source. P selects
PROGRAM, with S as an alias. A live Y confirms a copy. The source remains;
there is no implicit erase or delete. Flash AUTO chooses whole blank sectors
in B0:8-D or B1:E-F and skips occupied/opaque sectors. X is refused in BATCH.
PROGRAM CRC admission precedes streaming; the flash SR/01 commit marker is last.
SR/01 has no payload CRC and cannot represent a distinct/restore-only entry.

The actual XSRC→XCOPY→XBACK trial passed TABLE, exact payload/CRC checks,
execution and public HOLD return. Its temporary records were removed afterward:
B0:9 is all FF again, and the original320 PROGRAM bytes are restored exactly.
CLK, CLOCK and NFCOPY remain intact. Installed ROM decompression and the
MAINT→SRAM→MAINT handoff passed; no host-supplied app body substituted for them.

Persistent EDU is explicit and separate from session selection:

```text
BM> EDU
BM> EDU OFF
BM> EDU SAVE OFF
Save EDU mode? Type YES:
BM> EDU SAVE ON
```

SAVE appends a32-byte ED/1 metadata record after exact YES. It never erases or
writes the C/D boot journal. Repeating the current saved mode adds no record.
No saved record defaults ON. Warm returns retain the session choice; cold entry
reads the saved choice before status probes.

OFF/seq1 atB3:9D80 and ON/seq2 at9DA0 were independently read back; all12 old
metadata rows remain exact. OFF was verified in MON B gE after the owner's
reported physical reset. Its first receiver expired, so that startup banner
was not captured. The second physical reset was captured in full: saved
default MON B gE, board2512, EDU ON. Final mode is saved ON/default B.

## Preservation and exact allowance

All12 approved erases were used: nine image sectors, one native D rotation,
and two B0:9 fixture-cleanup erases. There were no extra erases, F writes,
power cuts, RTC setting/trim writes or PF acknowledgements. All old history
was archived before writing; eight old C rows remain exact on chip, while16
old D rows were replaced by the explicitly approved rotation. Every latest
count and setting was carried forward.

Final journal: seq1146,21 valid rows; C/D/E/F counts56/37/36/24.
Saved default remains B, rebound to gE; bank enables, entries and delay remain.
All owner images outside the reviewed replacements remain; B0 is restored.
Owner RAM0200-66FF and ZP00-DF were restored and read back after each borrow.
2512 finishes at REC>, COM4 released. The approved write scope is exhausted.

Private closeout receipt:
`output/qualification/2512-named-EDU-closeout-20261101-r1/report.json`.
The [sealed write review](NAMED_EDU_2512_SCOPE.md) remains unchanged.

## Limits still open

The TIME and cold-start PREP limitations recorded below are historical to gE.
They are now closed on2512 by the installed, qualified gF
[TIME/PREP acceptance](TIME_PREP_2512_ACCEPTANCE.md). Other release gaps listed
at the end remain outside that repair.

Cold startup reported `SSRAM: --*`, and SRAM TABLE refused with guard01 until
the existing PREP control acknowledged disabled VIA flags:

```text
B3> R SRAM
SRAM> !
STORAGE> PREP
STORAGE> S
SRAM> T
SRAM> Q
```

PREP returned success; TABLE then showed CLK/CLOCK/NFCOPY and VERSION again
showed PROGRAM/WORKSPACE capacity. No SPI data or mode register was written.
Automatic cold-start preparation remains open. A host reply-case assertion
interrupted the first PREP follow-up; that failure and its owner restoration
receipt were retained, and the corrected continuation passed.

The unchanged794-byte LED/NIST sampler passed gE qualification and a real
scheduled gE collection, with exact RAM/LED restoration and unchanged clock,
trim, history and baselines. Physical CPU resets are logged separately from
power events. Native TIME's strict qualification remains open: two bursts
encountered intermittent RTCC decode error04; subsequent diagnostic reads
passed. Failure receipts remain intact; no validity guard was relaxed.

This acceptance does not close full b35 parity, factory restoration, new-manager
BATCH return, ASM/DBG, Classic presentation, physical Shift-key tests or
extracted-kit acceptance. New flash changes need a new reviewed allowance.
