# DBG1 board and offline test results

The local **rc1 DBG1 generation-50 candidate** passed the bounded tests below
on October 18, 2026 (America/Chicago; receipt directory timestamps are UTC).
The published generation-49 rc1 tag, ZIP and source tree remain unchanged.
This is debugger installation/smoke evidence for **65C02 and 65C816 E=1**;
native applications and native debugging are outside scope.

## Hardware results

| Board | CPU/runtime | MON A | MON B | Verified breakpoint hits | Restored preference |
| --- | --- | --- | --- | --- | --- |
| 2604 | 65C02 | Pass | Pass | 16 per slot, 32 total | B |
| 2609 | 65C816 E=1 | Pass | Pass | 16 per slot, 32 total | A |

Each slot ran the same four packaged scenarios:

1. Automatic `BRK 01` entry, shared D/M/U, S into/through JSR/RTS, N over
   ordinary instructions and JSR, C through another explicit BRK, then HOLD.
2. All eight persistent breakpoints in order twice, with saved-register
   checks; automatic rearming, original bytes visible while paused, ninth-slot
   refusal, individual/all clear, and final HOLD.
3. All eight set again, followed by X abort and cleanup verification.
4. `BRK 80` query returning without a stop until `BRK 03`, with A=`01`,
   X=`10`, Y=`04`, then C to HOLD.

All four combinations passed: **64 breakpoint hits across both boards**.
Loaded program bytes were checked after each HOLD/X for leftover patches.
2609 also passed six E=1 observations, including before/after each slot's
smoke: DBR, PBR and direct page zero, IRQ disabled and decimal clear. The RAM
observer records prior E with SEC/XCE while forcing E=1; it cannot enter
native mode. The unchanged startup CPU detector retains its existing behavior.

Each installation used fresh repeated reads of all four 32 KiB flash banks
and an application-RAM archive. All nine transfers were device-verified;
the owner then confirmed physical RESET. All four flash banks matched the
installation targets before preference changes. Slot changes used the
existing P/J3 software restart path.

After testing, all **25,344 original application RAM bytes per board** were
restored and checked byte for byte, and original preferences were restored.
Final repeated captures reverified all seven firmware sectors, preserved
other flash data/settings, and accounted for exactly nine erases per board.
Application RAM capacity and ASM buffers were unchanged. RTC controls, trim,
oscillator-start and backup-enable state were preserved; no clock/trim setter
was issued. Soaks and periodic RTC sampling remain stopped.

Rollback plans were derived from each final fresh capture and verified
offline. They were not executed on hardware. If the board changes, capture
again and rederive a plan; old C/D journal images must not reset wear history.

## Offline scope and limits

The matching build passed 21 65C02 groups and 24 independent 65C816 E=1 groups,
including full boots and packaged smoke in both slots, 512 decoder cases per
CPU, and 177 direct instruction comparisons on the 816. Dynamic user/system
registrations, capacity/bounds, unregister and nested-BRK refusal were tested
offline. The board smoke exercised query `$80`; it did not qualify callback
registration or all BRK services on hardware.

The documentation audit additionally assembled and executed the four marked
examples (C/S/N, eight breakpoints, user register/unregister, system registration)
in both slots on both models: **16 example executions**. Those runs passed
22 65C02 groups and 25 816 E=1 groups, including the existing complete suites.
They produced separate `debugger-test-manuals.json` and
`debugger-test-65c816-e-manuals.json` reports; historical board/model receipts
were retained. The firmware bytes were unchanged. Reproduce after building
the candidate and its board package as described in the candidate README:

```text
python tools/test_rc1_debugger.py --build BUILD/rc1-debugger-v1e --smoke-package BUILD/rc1-debugger-boardtest-r1 --manuals docs/rc1
python tools/test_rc1_debugger.py --build BUILD/rc1-debugger-v1e --cpu 65c816-e --smoke-package BUILD/rc1-debugger-boardtest-r1 --manuals docs/rc1
```

A separate 21-check package model exercised actual RAM installer/rollback
instructions on both CPUs, stale-source and corrupt-transfer refusal, and
host smoke/restoration guards. Model hash ranges were accelerated. This does
not establish electrical timing, interrupted-write recovery, general occupied-
bank upgrades, native-mode behavior, or full endurance/RTC qualification.

## Reproducible identity and local evidence

| Artifact | SHA-256 |
| --- | --- |
| `BUILD/rc1-debugger-v1e/firmware.bin` | `e3c7ae6247f23e579a2ffc31ea72986eb62611d22fc862da321371139ae6727a` |
| `BUILD/rc1-debugger-boardtest-r1/board-test-manifest.json` | `3287d719b703b1ae87300c05ffba9fe803594995e4a9156781c03c86d4fb0e9c` |
| `BUILD/rc1-debugger-boardtest-r1.zip` | `8543c8718479df6e6db4a90bfdc6b30f5cf931e3739c42d446654ac6bbc212e2` |

Local receipt roots, relative to the repository:

- `output/qualification/rc1-debugger-2604-boardtest-2026-10-19-024408Z`
- `output/qualification/rc1-debugger-2609-boardtest-2026-10-19-030225Z`

Each contains the combined `report.json`, `before`/`after` captures,
`install-receipt`, `flash-check`, `smoke-A`, `smoke-B`, `RAM-restored`, and
an unexecuted `rollback` plan. Private board captures/logs remain local and
are not part of the public manuals or published rc1 ZIP.

Candidate source/build and exact experimental install/rollback procedure:
[DBG1 candidate](../../release/candidates/rc1-debugger/README.md) and
[board-test procedure](../../release/candidates/rc1-debugger/BOARD_TEST.md).
