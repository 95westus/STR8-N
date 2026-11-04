# BANK MAINT installation and acceptance scope: 2512 / 2609

October31,2026. **Approved and completed:** both boards passed the reviewed
installation and positive tests. See [acceptance](BANK_MAINT_ACCEPTANCE.md).
The exact pre-approval document is retained privately as approved-scope.md
beside the pinned review/approval JSON. The remaining text is the scope
as prepared, including its pre-install qualification status.

At review time:
Both boards passed the same RAM-only candidate. No flash, metadata, journal,
RTC-setting or SRAM-data writes were made during that qualification. Owner
RAM/ZP was restored and read back; COM4 and COM8 are released at B3>.

## Result to install

`R MAINT` will open `STR8-N BANK MAINT 2.4 / BASE1 g1` at `BM>` rather than
the CONFIG-led FLASH panel. The port retains copy/compare (including overlapping
RAM copy), board NAME/CLEAR, TABLE/T, the independent 4 KB sector editor,
guarded erase, maps/wear, VERSION, BOOT settings access, deliberate J and Q.
`R FLASH`, `R CLOCK`, bare MAINT/workbench, EDU/SRAM/WORK and PROGRAM remain.
MON A/B gC, CLOCK, FLASH, STATUS, PROGRAM and Foundation F images stay exact.

MAINT is 8,957 linked bytes, sealed into 12,288 bytes with 3,297 free bytes.
Code uses $2000-$42FC; its editor is $5000-$5FFF, state $6000-$63FF,
return escrow/trampoline $6400-$66FF and separate sector staging $6800-$77FF.
User C/V RAM is $0200-$1FFF. Q restores ZP and the monitor session; the host
trial also restores and verifies all borrowed owner RAM $0200-$66FF.

## Exact image replacement

On **each** board, seven sector erases/replacements, in this order:

| Sector | New content | Existing content affected |
| --- | --- | --- |
| B1:8/9/A | BANK MAINT g1, native RP/PR05 kind2 | Entire old $8000-$AFFF stored-record arena |
| B2:8/9 | WB2 gC and matching bundle header | WB2 gB; STATUS padding is copied unchanged |
| B3:E | Services gB | Services g9 |
| B3:8 | Native loader revision3 and BM-aware BATCH reader | Previous loader/reader; RTC provider and gateway stay exact |

**This is an occupied allocation, requiring approval:** B1:8000 currently
contains HELLO0200 on2512 and UCHESS on2609. Their original records and every
byte of B1:8-A are archived on the host before replacement; they will no
longer occupy those on-board addresses. Unlabelled old bytes in that extent
are also replaced. B1:B-F, including the legacy CLOCK record, stays exact.
No other owner image is an installation target.

The prepared files preserve B2:A-F, all STATUS sidecars, B3:9 provider/history
code and metadata, MON A/B, C/D old rows and F. They are composed from each
board's own captures, not from another board's settings.

## Positive flash and naming acceptance

Use only **B0:9**, with its exact 4 KB preimage retained privately. On2512 it
is verified blank FF. On2609 it is occupied WDC fallback data and must be
restored byte-for-byte before closeout. The test does not boot or replace WDC.

- Save the original sector in the editor, then copy it into RAM $0200-$11FF.
- On2609, confirm E 0 9 once to erase the occupied fixture. On2512, begin
  with its already-blank sector; no initial erase is needed.
- Create a short pattern in RAM $1300, use C to copy it into fresh flash,
  compare RAM/flash, read the full 4 KB sector, patch a fresh FF byte, and W
  the full editor image. Verify the bytes and buffer CRC. Neither operation
  reprograms an already-programmed byte with a different value.
- On2512, confirm E 0 9 once and verify all FF. On2609, R the saved original
  RAM image and W it back: one accounted erase, then full verification.
- Confirm NAME CLEAR, inspect unnamed status, then confirm NAME 2512 or
  NAME 2609. This adds exactly two committed BN rows per board. Every old
  metadata row stays intact; final names and -05:00 offsets are unchanged.
- Check TABLE, BOOT inspect, VERSION/Q, a read-only BATCH through BM and
  back, APPS and existing CLOCK/FLASH/PROGRAM routes.

No boot-policy change, EEPROM-history write, RTC SET/trim/PF acknowledgement,
SRAM-data write, WORKSPACE write, power cut or retry erase is included.

## Erase and history budget

| Board | Image erases | B0:9 acceptance/restoration erases | Total | Journal appends | Naming appends |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2512 / COM4 | 7 | 1 | 8 | 8 | 2 |
| 2609 / COM8 | 7 | 2 | 9 | 9 | 2 |
| Total | 14 | 3 | **17** | **17** | **4** |

**Zero C/D erases and zero F writes.** All 20 old2512 and22 old2609
boot/wear records remain byte-for-byte on chip. New wear reservations are
append-only, before erasing each target. Saved default B/gC, enabled masks,
entries and unknown-prior-wear masks stay unchanged.

| Board | Reserved wear pages | Sequence | Valid rows | Final C / D / F counts | BN append addresses |
| --- | --- | --- | --- | --- | --- |
| 2512 | C400-CB00 | 1097 -> 1105 | 20 -> 28 | 55 / 35 / 24 | 9D20, 9D40 |
| 2609 | C600-CE00 | 1052 -> 1061 | 22 -> 31 | 79 / 48 / 31 | 9C40, 9C60 |

Other changed tracked counts, decimal:

| Target | 2512 before -> after | 2609 before -> after |
| --- | --- | --- |
| B0:9 | 19 -> 20 | 4 -> 6 |
| B1:8 / 9 / A | 5/6/5 -> 6/7/6 | 13/7/21 -> 14/8/22 |
| B2:8 / 9 | 601/270 -> 602/271 | 605/263 -> 606/264 |
| B3:8 | 24 -> 25 | 28 -> 29 |
| B3:E | 32 -> 33 | 46 -> 47 |

2609 will have no ordinary append slot left in active C after this scope;
its next mutating operation would need a separately reviewed native rotation.
Read-only tools remain usable. No rotation is included here.

## Evidence, limits and boundaries

Both RAM trials passed real menu operation, NAME query/cancel, BOOT inspection,
compact TABLE rows, 4096-byte editor/CRC, independent-buffer survival across
maps/VERSION/TABLE, overlapping RAM copy, compare success/mismatch, cancellation,
protected-flash refusal, quiet Q, exact ZP return and owner-RAM restoration.
Positive writes and the new cold native-loader route remain installation
acceptance, not completed claims.

NAME is board naming. The old X named flash/PROGRAM transfer is not ported;
existing S/T/R PROGRAM workflows remain separate. Old SR01 rows have no
payload CRC and do not certify old execution-ABI compatibility. No new
per-sector naming format or legacy binary-compatibility claim is made.

Frozen Foundation: STR8N-F0.3.0 g1 / BASE1 / PR05, 4096 bytes,
SHA256 `8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
Its exact worker mutation preamble is checked before using the existing
accounted erase/program/verify body; no F or worker source was changed.
2205 and2604 are excluded from all access. Published downloads are unchanged.
No simulator, CPU model, repeat firmware build or full-board backup campaign
was used for this work.

Private, exact prepared plans and sector hashes:
`C:\SRC\STR8-N\output\qualification\BANK-MAINT-scope-20261031-r1\review.json`.
Per-board plan files are in its2512 and2609 subdirectories. RAM evidence:
`2512-BANK-MAINT-RAM-20261031-r2/report.json` and
`2609-BANK-MAINT-RAM-20261031-r1/report.json` under output/qualification.

Execution must re-admit the reviewed preimages and fresh owner RAM; a changed
preimage or exhausted append room stops before the affected write. Any scope
increase or failed erase requires a new decision, not an automatic retry.
