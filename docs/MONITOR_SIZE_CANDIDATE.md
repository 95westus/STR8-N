# Monitor A/B branch-size candidate

The offline candidate shortens 170 expanded conditional-branch/JMP pairs in the
common monitor source. Each monitor body falls from 3,967 to 3,457 bytes, leaving
511 free bytes in each existing 4 KiB slot. The sector and firmware file sizes
remain unchanged. No command, check, message, recovery path or ASM feature is removed.

The verified source patch is now selected in `src/current/target.json` and promoted
into the authoritative tree. A clean normal build reproduces the candidate exactly.
Installation on 2604 has separate fresh admission, escrow and verification evidence
in `output/qualification/monitor-size-install-2604-20261022-r1`; consult its closeout
for completion status. Board 2609 is outside this installation's authorization.

Successful candidate: `BUILD/ms4/firmware.bin`, SHA-256
`efb5f2c031be32d268aefb9bc14a16d0b8f7f4bef12974293664de517ec83dad`.
Its derived sources are in `BUILD/ms4/s/core`, with the dependent debugger binding
in `BUILD/ms4/debugger/generated.inc`. `BUILD/ms4/source.patch` records the edits.

## Scope and dependencies

Only eligible, reachable short branches replace inverted branches plus absolute
jumps. Labels are retained. Startup/prompt layout, G dispatch branch pairs,
receive-drain loops and autostart polling/delay code are excluded from shortening.
The checked timing regions retain instruction behavior and taken-branch page-crossing
costs. Fixed F, RAM worker/vectors, ASM and the source-store code are unchanged.

Two private dependencies must follow the monitor relocation:

- The batch provider's reader binding changes from ACF0/BCF0 to AAF2/BAF2.
  Only its reader address/page-delta operands and component CRC change.
- DBG1's shared monitor D/M offsets change from 02EB/03C0 to 02E8/0387.
  Only the two affected immediate bytes and sector CRC change; debugger entry
  points, code size and behavior remain the same.

Consequently the complete candidate changes B3:A/B, B2:D and B1:A. This is not a
standalone replacement for two monitor sectors with the old dependent bindings.

## Reproduction and verification

For the selected source, use `python -B tools/build_current.py --out BUILD/current-new`.
The historical preparation commands below require the preserved pre-optimization
asm-dev source tree as their control; they are not the current build chain.
Use fresh, short output paths. WDC02AS/WDCLN and the existing local CPU model
dependencies are required; no packages are fetched.

```text
python -B tools/build_current.py --out BUILD/ms-control-new
python -B tools/prepare_monitor_size.py --control BUILD/ms-control-new --out BUILD/ms-new
python -B tools/test_monitor_size.py --control BUILD/ms-control-new --candidate BUILD/ms-new --out tmp/ms-check-new
python -B tools/test_monitor_size.py --control BUILD/ms-control-new --candidate BUILD/ms-new --out tmp/ms-import-new --imports-only
python -B tools/test_rc1_debugger.py --build BUILD/ms-new --cpu 65c02
python -B tools/test_rc1_debugger.py --build BUILD/ms-new --cpu 65c816-e
```

Run `tools/test_rc1_asm_dev.py` with `STR8_SOURCE_BUILD` set to `BUILD/ms-new` as
well. It exercises EQU/LST/SYMS/diagnostics, storage and console editing on both
CPUs and both slots. The `prepare` tool produces a candidate report, never a
claim that optimized bytes match the old installed baseline.

Verification includes:

- Flattened independent links and an exhaustive audit of every emitted monitor
  byte: only branch deletion/inversion and required address relocation are allowed.
- 174,080 branch-condition CPU cases covering both slots and CPU models.
- 552 baseline/candidate command comparisons across both CPUs, both slots and
  EDU on/off: output, application RAM, SRAM, simulated NOR mutations and resulting
  flash changes must agree. Full-sector import includes cancellation, malformed
  addresses/streams, incomplete data and a successful 4 KiB upload.
- Existing full debugger and cold-boot regressions, including the debugger's D/M
  bridge and both slot selections, plus the ASM extension suite.
- A second build with identical image, payloads, symbols and source patch.

The differential model accelerates only an unchanged fixed-F helper after checking
3,072 complete CPU-state cases against its actual instructions. It does not alter
firmware. Electrical USB/flash timing is outside this offline verification.

Results and frozen evidence are recorded in
`output/qualification/monitor-size-offline-20261022-r1`.
