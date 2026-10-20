# v1g DBG1 offline and hardware requalification results

This staged snapshot describes `v1g-BRK82-84-edge-fix`, firmware SHA-256
`6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b`.
It is generation 50, BRK ABI 1, for 65C02 and 65C816 E=1 only.
Native applications/debugging are excluded. Promotion remains held.
**Both boards passed physical requalification and the owner-stopped expanded R6 workload with final restoration/drift verified. Promotion remains held.**

## Offline release review

Both earlier edge findings are resolved in this image:

| Service | Fix | Regression |
| --- | --- | --- |
| `$82` | Reject every ID outside `$C0-$FE` before lookup | All 256 IDs in five table states, both slots/CPUs |
| `$84` | Finish counted output before incrementing beyond its last byte | All 256 counts at both RAM limits, zero/invalid/wrapping ranges, output/context/flag preservation and memory-bus overread checks |

The original 88 edge checks all pass. The expanded suite passes 7,256 cases,
with zero failures. Existing registration scenarios pass 36 executions per
CPU, for 72 total. Four system entries and sixteen user entries remain separate,
using 16 and 64 existing reserved bytes; no application RAM is reserved.

| Model | Full suite groups including manuals | Original edge checks | Expanded cases | Registration scenarios |
| --- | --- | --- | --- | --- |
| 65C02 | 23 | 44 | 3,628 | 36 |
| 65C816 E=1 | 26 | 44 | 3,628 | 36 |

Both slots are covered on each model. Full suites include strict MAINT marker
acceptance and each-byte/legacy mismatch refusal, automatic BRK entry, shared
D/M/U, C/S/N, all eight persistent breakpoints and cleanup, decoder/instruction
checks, full monitor boot and 16 documented ASM example executions. Hidden B
and E=1 are checked on the 816. The inherited reset detector retains its exact
existing exception; no native application/debugger tests were added.

All 21 installer-model groups pass, including actual instruction-model
install/rollback on both CPUs with eleven transfers, source and transfer
refusals, preservation of owner data and advancing wear history. These are
simulated transactions, not physical-board transfer receipts. Hash loops and
flash busy timing retain the model's recorded acceleration.

A fresh second build is byte-identical. Compared with the MAINT-corrected v1f
image, only B1:A000-AFFF changes; the MAINT fix and all other firmware bytes
are retained. The debugger uses 3,975 bytes plus two CRC bytes, leaving 119
bytes free. Application RAM limits and ASM buffers remain unchanged.

## Hardware and soak status

The exact v1g image passed on both physical boards in MON A and MON B before and after rollback/reinstall.

| Board | CPU | Registration scenarios | BRK $82/$84 checks | Breakpoint hits | Device-verified transfers |
| --- | --- | ---: | ---: | ---: | ---: |
| 2604 | 65C02 | 72 | 84 | 64 | 44 |
| 2609 | 65C816 E=1 | 72 | 84 | 64 | 44 |
| Total | | 144 | 168 | 128 | 88 |

Both slots passed MAINT, ASM, UCHESS, SRAM, WORK, EDU and CLOCK checks, system/user registration capacity and refusal cases, callback arguments/results, nested-BRK protection, BRK/C/S/N, shared D/M/U, all eight persistent breakpoints, ninth refusal and cleanup. The 816 remained E=1 before/after each slot. Focused $82/$84 hardware cases used each board's actual $64FF limit without changing optional-service ownership; released $66FF remains offline coverage.

Four transactions per board followed v1f -> generation 49 -> v1g -> generation 49 -> v1g. Every transaction verified eleven transfers, a fresh boot, all four flash banks and original RAM restoration. Both original full 25,344-byte application RAM archives and monitor preferences were restored at hardware closeout. Flash/settings guards, erase accounting and RTC controls/trims passed. No hardware-test failures occurred. Two waits for physical RESET expired harmlessly and were resumed after the operator acted; those waits are not firmware-test failures.

Actual [hardware receipts](../../qualification/hardware/summary.json), their [source binding](../../qualification/hardware/source-evidence.json) and the [ASM/BRK results supplement](ASM_DBG1_REQUALIFICATION.md) accompany this archive. Private board RAM/flash captures, serial logs and board-specific plans are excluded.

The owner stopped the expanded v1g R6 continuation cleanly after **12,803.703 seconds (3 h 33 min 23.703 s) of monitored/active workload**. 2604 passed **61 cycles, 38,430 LED frames, 610 completed patterns and 976 breakpoint hits**; 2609 passed **60 cycles, 37,800 frames, 600 patterns and 960 hits**. Both original full 25,344-byte RAM images were restored and reread after final preserving drift; all four flash banks/settings were unchanged. No actual workload failure or snapshot retry occurred. The verified worker exited; no workload or RTC sampler was restarted. **Promotion remains held; native applications/debugging remain excluded.**

The exact duration, separate run scopes, all ten patterns, inherited/new tests, drift intervals and baseline/recovery anchors are in [soak closeout](DBG1_SOAK_CLOSEOUT.md), [workload summary](../../qualification/soak/summary.json), [history](../../qualification/soak/history.json) and [drift receipts](../../qualification/soak/drift-checkpoints.json). Private original RAM/flash bytes and serial logs are excluded. Staging opens no port and changes no firmware, clocks, trims or settings.

## Offline scope and limits

These checks do not qualify electrical timing, interrupted writes/programmer
recovery, full endurance/RTC accuracy, arbitrary occupied-bank upgrades or
native applications/debugging. The reference BIN is not a preserving updater.

See the [debugger guide](DEBUGGER_GUIDE.md),
[candidate status](V1G_STAGING_STATUS.md),
[machine-readable offline summary](../../qualification/offline/summary.json)
and [current qualification](../../qualification/summary.json).
