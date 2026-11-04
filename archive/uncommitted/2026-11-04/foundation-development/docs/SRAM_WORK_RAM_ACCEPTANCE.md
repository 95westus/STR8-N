# SRAM/WORK RAM checkpoint

November 1, 2026. **Read-only qualification passed on 2512 and 2609;
positive RAM qualification passed on 2512.** The subsequent g2 native
installation also [passed on both boards](STORAGE_NATIVE_ACCEPTANCE.md).
Collection has priority; no RAM-trial receiver remains active.

The remaining release work is grouped in
`UNIFIED_ENVIRONMENT_REMAINING.md`. The positive trial scope is
`SRAM_WORK_POSITIVE_RAM_SCOPE.md`; native placement and loader constraints
are recorded in `SRAM_WORK_NATIVE_INTEGRATION.md`.

The combined candidate contains the b35 SRAM manager and WORK allocator/API,
adapted to BASE1/PR05. The library occupies $2000–$47F6: 10,231 bytes, with
4,873 bytes before the reserved $5B00 context. The loadable RAM BIN is
`BUILD/sram-work-g1-ram-r2/STR8N-SRAM-WORK-g00000001-RAM.bin`.
The build manifest retains its original build-only status; these later live
receipts supply execution evidence for that exact artifact.

Both physical CPU paths ran the same candidate: 2512/65C02 and
2609/65C816 emulation. Each passed:

- Fresh owner RAM/ZP capture, current MON gD and golden-F admission.
- Actual SRAM Table and WORK capacity queries through the new RAM code.
- Cancellation of both format dialogs and quiet return to MON.
- SRAM API query; bad request pointer, source overlap and missing format-key
  refusal; deletion of an existing CLK record refused with $4C while locked.
- WORK API capacity query, invalid operation/pointer refusal, SS1
  upgrade-required handling, and correctly keyed FORMAT refused with $4C
  before any write. No automatic epoch or layout creation occurred.
- Exact before/after comparison of the 2 KB storage metadata area and all B3
  bytes, including F, boot/wear history and saved settings.
- Fresh owner RAM $0200–$66FF and ZP $00–$DF restored and read back; incoming
  EDU session selection preserved; serial port released.

There were zero flash, journal, SRAM-data/WORKSPACE or RTC-setting writes,
resets or power cuts. This work did not access 2205/2604 or change collection
scheduling. The first 2512 attempt deferred before opening its port because
collection held the shared lease; the successful trials respected that lease
and checked for collection requests between commands.

## Use and limits

The RAM BIN starts at `STORAGE>` in read-only mode. `S` opens `SRAM>` and
`W` opens `WORK>`. Submenu Q returns to STORAGE; top-level Q restores ZP and
the MON session. A normal tool return does not restore borrowed application
RAM; the host trials perform that complete restoration separately.

Actual CPU save/restore and API request/data buffers are restricted to
$0200–$1FFF while this prototype occupies RAM. Mount/Table can inspect larger
existing records; the existing independent wide PROGRAM loader is unchanged.
`UNLOCK` with separate live YES enables writes for this RAM instance. The
later 2512 positive trial exercised UNLOCK/YES/LOCK. Read-only is a cooperative
tool guard, not isolation from arbitrary owner machine code or force Modify.

The descriptor at $2000 has jump entries at $2003 for SRAM requests and
$2006 for WORK requests. Both take A/X as the low/high address of a 32-byte
request and return A=status, C=set on success. They are private, resident-RAM
interfaces for this candidate; they do not expand frozen Foundation's ABI.
The WORK request retains the b35 owner/slot/epoch/ticket and bounded I/O fields.
A new RAM instance begins a WORK epoch lazily on its first mutating service;
querying storage does not create a session or invalidate existing metadata.

## Positive RAM checkpoint on 2512

The same g1 candidate passed two named Store versions, latest-version
Restore with byte comparison, reclaim, delete/tombstone and not-found
handling, and explicit SS1 format. WORK passed SS1 upgrade; claim and
inspection of the committed allocation; 64-byte write/read with byte
comparison; wrong-owner, allocation-bound and request/data-overlap refusal;
release/stale-handle refusal; 48/64 KiB resize and live-claim conflict;
fallback-header selection, primary repair and WORK format. Legacy SRAM
format correctly refused an SS2 layout with $49.

The harness granted the volatile write capability immediately before
mutating API calls. UNLOCK/YES/LOCK was also exercised normally. These API
results do not establish every console spelling or positive 2609 write
path. Its read-only RAM acceptance remains the earlier receipt.

Temporary mutations were confined to backed-up metadata $00000–$007FF,
PROGRAM pages $00800–$00BFF and WORK data $10000–$103FF. Every admitted test
block was restored and read back. The independent CRC-framed reader then
compared all 131,072 SRAM bytes with the complete original snapshot: exact
match. The read-only snapshot continued across priority collection windows;
all mutation-eligible blocks were freshly re-admitted before continuation.
B3, including F/settings/history, also matched exactly. Fresh owner RAM/ZP
was restored and read back, incoming EDU selection retained and COM4 released.
No flash/journal/RTC-setting writes, resets or power cuts occurred. This task
did not access 2205/2604 or alter collection scheduling.

Original host failures remain in the receipts. An obsolete private reader
correctly refused the newer PROGRAM provider; its fresh owner escrow was
restored without reset. A claim-cache assertion inspected the pre-publication
cache; the continuation inspected the committed SPI record instead. Finally,
the host expected $4A for SS2 SRAM-format refusal; both the preserved b35
source and the port define $49. The live call returned $49/C=0. The composite
receipt checks that actual API matrix and retains the original failed
assertion. No firmware repair or repetition of the passed SRAM write cases
was needed for either expectation correction.

Private positive evidence:

```text
output/qualification/2512-SRAM-WORK-positive-RAM-20261101-r5/report.json
output/qualification/2512-SRAM-WORK-positive-RAM-20261101-r6/report.json
output/qualification/SRAM-WORK-positive-checkpoint-20261101/report.json
```

These original g1 trials changed no installed route. The subsequent approved
g2 installation adds R SRAM/R WORK on both boards; its separate acceptance
records the occupied-image replacement and native journal rotation.

Private evidence, excluded from published kits:

```text
output/qualification/2512-SRAM-WORK-g1-RAM-20261101-r2/report.json
output/qualification/2609-SRAM-WORK-g1-RAM-20261101-r1/report.json
output/qualification/SRAM-WORK-RAM-checkpoint-20261101/report.json
```

See [the RAM trial scope](SRAM_WORK_RAM_SCOPE.md) for memory ownership and
collection-priority rules. Full b35 parity remains open.
