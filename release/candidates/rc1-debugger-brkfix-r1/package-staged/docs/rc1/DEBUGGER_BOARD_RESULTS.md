# v1g DBG1 offline results and pending board qualification

This staged snapshot describes `v1g-BRK82-84-edge-fix`, firmware SHA-256
`6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b`.
It is generation 50, BRK ABI 1, for 65C02 and 65C816 E=1 only.
Native applications/debugging are excluded. Promotion remains held.
**This image has offline results only; physical-board results are pending.**

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

No v1g installation, MAINT/app regression, registration/debugger smoke,
rollback/reinstall, soak or drift snapshot has run on a real board. All remain
pending and must be tied to the v1g image hash. Historical v1e and v1f hardware
receipts are separate evidence. The ongoing six-hour v1f soak cannot qualify
v1g. No parent result is reused as a passing v1g hardware result.

Promotion requires physical requalification on 2604 and 2609 in both slots,
a separately authorized soak and final drift review, and an explicit release
decision. Staging does not install firmware, open board ports, reset a board,
change settings or stop the active soak.

## Offline scope and limits

These checks do not qualify electrical timing, interrupted writes/programmer
recovery, full endurance/RTC accuracy, arbitrary occupied-bank upgrades or
native applications/debugging. The reference BIN is not a preserving updater.

See the [debugger guide](DEBUGGER_GUIDE.md),
[candidate status](V1G_STAGING_STATUS.md),
[machine-readable offline summary](../../qualification/offline/summary.json)
and [pending qualification](../../qualification/summary.json).
