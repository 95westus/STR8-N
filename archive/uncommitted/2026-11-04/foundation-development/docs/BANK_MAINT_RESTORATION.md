# BANK MAINT 2.4 is the operator reference

For current installed features and remaining full-b35 gaps, use the
[November 1 comparison](REFERENCE_FEATURE_PARITY_2026-11-01.md).
The target/front-door defect descriptions below retain their original context.

October31 update: the BASE1 BANK MAINT port passed RAM-only qualification on
2512 and2609. Copy/compare, board naming inspection/cancel, TABLE, the4 KiB
editor and quiet return were exercised; owner RAM/ZP was restored. The
[exact installation and positive-write scope](BANK_MAINT_2512_2609_SCOPE.md)
was approved and completed on both boards, including positive flash and
naming tests. See the [operator manual](BANK_MAINT_BASE1.md). The historical target below
must not be read as a claim that every legacy command has been ported: old
X named flash/PROGRAM transfer remains excluded, and NAME is board naming.

Owner transcript, October 30, 2026. This refines the familiar-workflow requirement:
R MAINT must open the actual BANK MAINT application at BM>, with working
operations, rather than opening the current CONFIG-led board-tool panel.
The preserved b35/rc1 source is the behavior reference; exact old binaries
remain unqualified under BASE1. No reference-board access is needed.

## Required user experience

| Front door | Required behavior | Current gap |
| --- | --- | --- |
| T / TABLE | Automatic admitted flash/PROGRAM discovery, location, load-end, size, completion and name | Current bare Table starts from selected flash scope plus mounted PROGRAM; output lacks end and familiar C flag placement |
| R name / RESTORE name | Unique-name resolution, explicit location/backend override, checked load/run/Q | Native routes work, but full catalogue/storage parity remains open |
| APPS | Familiar named modules and locations, installed/available state, checked launch | Routes are listed; full native availability/catalogue semantics remain |
| R MAINT | Full BANK MAINT 2.4 menu and functions, BM> | Current FT_START jumps into CONFIG_START and prints CONFIG branding/help |
| Startup/status | Board ID, owner RAM, EDU, PROGRAM/WORKSPACE sizes, local RTC/offset/day, tracked wear and battery policy | Current MON status is incomplete and UTC sample-oriented |

Use the supplied Table shape, for example:

```text
B1:8000 2000-499A 299B C MAINT
B1:B000 2000-4FC6 2FC7 C CLOCK
```

These are the owner's reference rows, not a claim those records are on2512.
C means complete/committed; legacy SR01 has no payload CRC. Pending/corrupt
records and unsupported ABIs must not be presented as validated runnable apps.

## Full BM command set

- NAME / CLEAR and existing per-bank/sector naming forms.
- M1/M2/M3: grid, ranges and tracked wear.
- E bank sector range: guarded journaled erase.
- C source range destination start: RAM/flash copy.
- V source range destination start: compare.
- R source range: read into the 4 KiB editor buffer.
- D offset/range, P bytes, F range/value, N length/value, K CRC16.
- W destination/start: write the buffer and verify.
- T bank/range: stored records; J bank: deliberate boot; Q: monitor.
- VERSION and explicit BOOT/CONFIG access retain the new environment's identity
  and boot policy. BOOT settings remain visibly separate from BM's copy C.

A help menu alone does not satisfy this list. Preserve source/destination
ownership, overlap handling, cancellation, write confirmation, verification
and coherent return. Keep F golden and C/D journal guards. Factory restoration
remains a separate deliberate workflow. Historical `Flash fail; Y retry/reset`
output is failure evidence, not an acceptance behavior or permission to retry
an erase automatically. ASM/DBG remain deferred.

## Front-door defect and prepared source repair

The shown `Tools invalid; use MAINT LOAD` after J3 or bare 3 is misleading.
The dispatcher reached its cache-missing message for an unrecognized command.
The prepared services gA candidate returns ordinary syntax for unknown input,
implements J3/J 3 through Foundation's existing public RESET, refuses that
reset inside BATCH, and adds cold AREA autoload. No F ABI changes. J0-2 remain
part of the boot/opaque workflow port; this candidate does not claim them.

It was built once with unchanged loader, WB2 gB and PROGRAM g2 reused.
Retaining bundle generation9 avoids a cosmetic B2:8 rewrite; only B3:E differs.
The candidate has 6 free bytes, is **not installed or live-qualified**, and
does not contain the full MAINT port. Existing downloads/board state remain
unchanged. At the current tool prompt, Q returns to B3>; another Q reaches REC>.

## Layout decision before the full port

The current FLASH/MAINT slot is 8 KiB. The preserved maintenance reference
body measured10,979 bytes before BASE1 adaptation; the owner's example stores
10,651 bytes. A full port cannot be assumed to fit the smaller wrapper slot.

One bounded literal/match packing experiment measured current CLOCK 12,245 to
9,908 bytes and the maintenance reference 10,979 to9,641 bytes. Both still
need three 4 KiB sectors; this encoding is not selected. No decoder, new RP
format, firmware rebuild, CPU model or device operation was involved in
that measurement. [Exact feasibility record](../monitors/review/classic-maint-packing-feasibility.json).

Next implementation order:

1. Port the full maintenance source to current PR05 console/banking/journal
   bindings. Replace legacy fixed addresses and preserve ZP/session on return.
   Measure the actual RAM body and dependencies, not a renamed help screen.
2. Fit it by factoring/reusing the current tools, or prepare a reviewed
   stored-app allocation as in the reference system. B0/B1 contents are not
   assumed disposable; no new allocation is authorized by this document.
3. Restore cross-bank Table/name resolution and the compact rows; reuse that
   implementation in BM T and the monitor front door.
4. Add the richer dynamic status above F. Board ID/profile and health-policy
   caveats must be truthful; prior wear and battery condition remain unmeasured.
5. Qualify complete operator success/cancel/failure workflows, then update a
   fresh local kit. Keep reference branches, boards and published artifacts.

This document is a corrected release acceptance target, not full-tool closure.
