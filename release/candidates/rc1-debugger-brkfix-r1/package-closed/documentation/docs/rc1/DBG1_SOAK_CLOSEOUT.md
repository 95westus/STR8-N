# v1g R6 soak closeout and scope

Promotion remains held. This candidate supports RAM debugging on 65C02 and
65C816 E=1; native applications/debugging remain excluded. Firmware generation
50, public title 2.0rc1, ASM 0.5, BRK ABI 1, firmware and installer bytes are unchanged.

The owner requested cooperative STOP on October 20, 2026 at 22:12:41 UTC.
The runner completed the current unit, restored both boards and collected final
preserving drift. It finished at 22:17:31.860576 UTC; actual process exit was
independently verified at 22:17:58 UTC. No worker or periodic RTC sampler was
restarted. There were no actual workload failures, restoration failures or
snapshot retries in R6.

| Board | CPU / selected slot | Passed cycles | LED frames | Completed patterns | Persistent breakpoint hits |
| --- | --- | ---: | ---: | ---: | ---: |
| 2604 | 65C02 / MON B | 61 | 38,430 | 610 | 976 |
| 2609 | 65C816 E=1 / MON A | 60 | 37,800 | 600 | 960 |

Monitored and active workload were both **12,803.703 seconds (3 h 33 min
23.703 s)**. Final safe closure took **216.041609 seconds** separately; total
worker wall span was **13,019.862814 seconds**. There were zero periodic
checkpoints in R6, only its final checkpoint. Its owner stop preceded the next
22:16:03 UTC boundary on the original R4 four-hour campaign phase. This is an
owner-stopped result in its actual scope, not a fixed four/eight-hour pass.

Both full original **25,344-byte** application RAM images were host-verified
restored and reread after final drift. All four flash banks, configuration,
monitor preference/wear observations and RTC control/trim settings matched.
2609 remained E=1 before and after every unit. Each board covered all 40 rotating
ASM sources, every built-in BRK `$80-$84` per unit, rotating system/user
registration and `$82/$84` edge cases, preserving base/utility commands and
full debugger smoke with all eight persistent breakpoints hit twice per cycle.

Each cycle assembled/exported and byte-verified one of four seeded LED sources
before execution. All ten patterns ran each cycle: wigwag 8, Gray code 256,
binary counter 256, walking one 16, walking zero 16, bouncing dot 14, checkerboard 8,
fill/drain 16, expanding/contracting pairs 8 and seeded LFSR sparkle 32: **630 frames**.
Every physical pin readback matched. Entry LED state was restored before BRK;
CRA/DDRA were not written. HOLD invalidated lifecycle/registration state.
The exact sources and CPU-qualified images are in
[LED cases](../../diagnostics/led10/cases.json).

## New tests and inherited scope

R6 newly passed **93 pure checks**: 22 LED protocol/oracle, 26 worker-policy and
45 CPU trace/write guards. Actual CPU models performed **16 onboard-ASM
assemblies and four complete 630-frame executions** across both CPUs and MON
A/B. All four source images were identical across the four CPU/slot scenarios;
each seed executed once. All delay instructions ran without acceleration.
Fresh both-board hardware preflight ran all four seeds plus one complete new
cycle: five LED executions, 3,150 frames and 50 patterns per board. Hardware
execution took 12.625-12.641 seconds per program. Full RAM/flash/settings,
preserving drift and post-drift RAM rereads passed before launch.

The earlier **48 broader checks, four full-utility CPU units, 16 built-in RAM
program executions and 160 isolated ASM model executions** are inherited,
not newly rerun R6 tests. The earlier three-pattern LED qualification is also
inherited and does not qualify the new ten-pattern images. Utility coverage
remains preserving: no CLOCK BATTERY policy append, SRAM reclaim/format/mode
writes, WORK repair/resize or EDU mode mutation. A qualified resident SRAM
query may only probe/restore the exact reserved `$1FFFF` XOR-FF byte; full
array contents and mode are unchanged.

## Final preserving drift

| Board | Reference UTC, October 20 | Offset seconds | Offset interval seconds | Rate interval ppm |
| --- | --- | ---: | --- | --- |
| 2604 | 22:16:28.739642 | +1.221858 | +0.797302 to +1.646414 | -0.362950 to +4.743935 |
| 2609 | 22:17:06.292456 | +0.660544 | +0.281434 to +1.039653 | -1.523459 to +3.540781 |

Snapshot SHA-256 is `50a87a5aeaa358dd37edcb7ae9057a21250caa7222e742055f06951b572fdc15`.
The immutable original RTC baseline index remains
`5db3f89e0bcdd1ec1bd9d1958c6abbc8530977783a2f1bb195bc80220af4913e`.
2604 compares with its original baseline; 2609 compares only within the
separate `2609-post-RTC-recovery-2026-10-18-r1` segment and its preserved recovery
anchor. The original baseline was not replaced. This passed preserving
collection does not establish the separate 168-hour RTC endurance/rate gate.

## Separate history and honest failure classification

The fixed three-hour v1g run was owner-stopped after 6,006.453 seconds with
74/73 cycles, restored RAM and final drift passed; it was not a three-hour pass.
R1 stopped after two cycles per board on the harness's incorrect assertion
that invalidated physical registry IDs must be zero. R2 rejected normalized
fixture bytes before its first workload cycle. R3 corrected the lifecycle
assertion/copy admission and closed after 3,387.5 seconds with 42/41 cycles,
672/656 hits and passed restoration/drift. These are separate run scopes.

R4 closed with 156/154 cycles, 2,496/2,464 hits over 26,678.906 monitored seconds
(26,462.828 active, 216.078 periodic). R5 closed with 7/6 cycles,
3,640/3,120 LED frames and 112/96 hits over 1,516.938 monitored seconds
(1,292.703 active, 224.235 periodic). R4 and R5 each completed one original-phase
periodic checkpoint and a final checkpoint; R5's short workload is not a
four-hour workload claim. Both restored full RAM and passed drift/flash/settings.

Earlier model-harness import/export fixes and the R6 synthetic fake-clock test
fixture correction are recorded separately from actual hardware failures.
The typed-timestamp comparison and preflight/running marker reconciliation
were host metadata corrections; the R6 worker was not restarted or repinned.
Earlier v1f's owner-stopped six-hour plan ran 2 h 33 min 11.859 s and passed
restoration/drift, not its planned duration. The v1e eight-hour results remain
historical and do not substitute for corrected v1g qualification.

See [summary](../../qualification/soak/summary.json),
[separate history](../../qualification/soak/history.json),
[periodic/final drift](../../qualification/soak/drift-checkpoints.json),
[offline versus inherited evidence](../../qualification/soak/offline.json) and
[source receipt hashes](../../qualification/soak/source-evidence.json).
Private original RAM/flash captures, serial logs, secrets and board-specific
plans are excluded. An explicit owner promotion/release decision remains required.

## Distribution timing-wording correction

Distribution r7 corrects one operator-summary sentence in the prior staged
r6 archive: final drift followed owner STOP during safe closure. The detailed
timeline, workload counts, firmware/installer bytes and underlying receipts
are unchanged. The prior archive remains immutable; this was a documentation
wording issue, not a hardware or workload failure.
