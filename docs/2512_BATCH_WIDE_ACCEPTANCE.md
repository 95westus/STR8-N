# 2512 BATCH and large PROGRAM acceptance

October 30, 2026. Installed: MON A/B g0000000B, WB2 gA, PROGRAM SP/01 g2
(cancel repair r5), services g8 and native apps g1/r16. Frozen Foundation
**N-F 0.3.0 g00000001 / BASE1 / PR05** remains exactly 4096 bytes.
This is a development acceptance above Foundation, not full-b35 release
closeout. [Sanitized machine receipt](../monitors/validation/2512-batch-wide.json).

## Accepted operator workflows

- BATCH core Dump/Modify/bank commands; maps, wear and APPS; empty-segment
  refusal before changes, per-command errors, nesting/raw-handoff refusal.
- Live-confirmed STORE, TABLE and small PROGRAM load/run/HOLD followed by
  the remaining queue. The queue never provides YES.
- Native CLOCK STATUS/VERSION/TIME/Q; invalid SET and live NO stop the
  remaining queue. FLASH READ/editor/VIEW/Q retains queue outside its 4 KB
  buffer; protected-target refusal and live NO stop it.
- MON and WORKBENCH origin/return context, both A/B slots, native VERSION
  followed by TIME, stale-provider/cache admission and queued reload refusal.
- Registered PR05 PROGRAM spanning `$3000–$66FF`: all 14,080 loaded bytes
  read back exactly, including overwritten workbench/profile/request RAM.
  Run/public HOLD resumes the queue; final load-only preserves the payload
  without reloading WB. Payload CRC failure refuses before owner copying.
- Ctrl-C after a partial wide copy prints `Partial; not run`, returns from
  the resident tail, leaves later bytes uncopied and does not execute it.
- AP/02 bad CRC stops before the next command; a registered valid image
  waits for live Q, returns via HOLD and resumes queued VERSION.
- Physical saved-default B startup, volatile queue cancellation on RESET,
  VERSION/fresh TIME and unchanged full B3 after startup.

The [operator manual](NATIVE_UTILITIES_MANUAL.md) defines the 34-byte grammar,
BT/1/2 PR05 PROGRAM registration, AP/02's distinct BT/1/1 marker, live
confirmations and deliberate raw/protocol exclusions.

## Preservation and actual writes

Temporary SRAM slots3/4 and `$A000–$D73F` were restored: **14,272 exact bytes**.
Existing CLK, CLOCK and NFCOPY records, primary formatting and WORKSPACE were
not changed. B0:9 was first read completely FF, programmed only 1-to-0 and
restored completely FF using **one** cleanup erase. Owner RAM `$0200–$66FF`
and ZP `$00–$DF` were restored and read back exactly. EDU is ON for the session;
2512 finishes at `B3>` with COM4 released. No new whole-board capture campaign.

| Item | Actual result |
| --- | --- |
| Utility image replacements | 19 erases: initial13, return-context repair4, PROGRAM cancel-message repair2 |
| Native C/D rotation | One D erase; zero C erases |
| Temporary B0:9 | One cleanup erase; installation used guarded 1-to-0 byte writes |
| Total erases | 21 |
| Final journal | seq1087, 26 valid on-chip records |
| B0:9 tracked count | 19 |
| C / D / E / F tracked counts | 54 / 35 / 31 / 24 |
| Default | B retained, bound to new generation0000000B; enable/entry/delay policy retained |
| F / power cuts / RTC SET / trim / PF ACK / WORKSPACE writes | Zero |

Original C records remain on chip. The original D records were archived raw
on the host before native rotation; the latest boot/wear state was retained
and extended. All other boards and existing published downloads were untouched.

## Corrections and limits

A stale workbench-origin flag and native UI scratch overlap required the
four-sector repair. A three-byte cancellation acknowledgment was needed
because Foundation mutes text until its cancel flag is cleared. The initial
RAM cancellation sentinel accidentally invalidated the WB cache, causing an
older flash provider to reload; the corrected RAM harness passed. The first
AP host assertion expected a RAM-only write message after successful flash
readback; the known eight-byte partial target was admitted and resumed.
All affected temporary data and owner RAM were subsequently restored.

Automatic review rejected a proposed two-erase AP trial against the prior
one-erase 2512 allowance. The safer blank-program/one-cleanup-erase path
passed within that allowance. No erase was blindly retried.

| Component | Measured remaining bytes |
| --- | ---: |
| MON A / B (excluding128-byte reservation and2-byte CRC) | 21 each |
| WB2 code/module | 22 |
| PROGRAM code plus separate2-byte CRC | 0 |
| Services E | 38 |
| Native CLOCK payload | 9 |
| Native FLASH/MAINT payload | 1461 |

F was reused, not optimized or rebuilt. This increment used no CPU simulation.
The final PROGRAM repair was rebuilt once; unchanged support/native bytes were
reused. Earlier corrective size/build attempts remain in private build logs.

Large STORE-source staging across `$4800`, remaining storage/management parity,
positive CLOCK SET/ACK/trim/policy and new CONFIG OFF/DELAY/RUN cases, factory
restoration and targeted 65C816 checks remain open. ASM/DBG are deferred.
RTC/NTP re-admission passed using nine concise TIME reads and a NIST reference;
one audited 2512 point was appended. Prior baseline, trim, historical points
and the existing hourly cadence were retained. No other board was accessed.
