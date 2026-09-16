# STR8-N v1.34 size candidate

This candidate saves 120 bytes while preserving the resident service entries,
RAM contracts, commands, and flash validation. The product and its displayed
version advance to 1.34; other messages retain their behavior. It is a new
binary with partial COM4 qualification recorded in the
[v1.34 board report](STR8N_V1_34_BOARD_TEST_2026-09-15.md). The board
acceptance of the preceding v1.33 image does not apply to untested paths.

## Measured layout

| Region | Preceding v1.33 | v1.34 candidate |
| --- | ---: | ---: |
| Resident | 3,394 bytes | 3,314 bytes |
| Last resident byte | `$FD41` | `$FCF1` |
| Erased margin | 14 bytes | 134 bytes, `$FCF2-$FD77` |
| Stored worker | 608 bytes at `$FD50` | 568 bytes at `$FD78` |
| Worker RAM extent | `$0200-$045F` | `$0200-$0437` |
| Selector prefix | 41 bytes | 39 bytes, `$0200-$0226` |
| NMI / IRQ-BRK targets | `$F0D2` / `$F0E6` | `$F0CF` / `$F0E3` |

The 4,096-byte image size, directory `$FFB0-$FFEF`, configuration
`$FFF0-$FFF9`, and hardware-vector locations `$FFFA-$FFFF` stay fixed.
The vector contents are generated from the new linked handlers. The public
reset/console/parser/bank-selection entries and `$0203` selector are unchanged.
The entire `$0200-$09FF` worker tray retains its existing phase ownership.

Preceding canonical top SHA-256:
`C9DA23B8ADFE78A401DD7CE5865F52B6E0F9A884BB17A6413678CEF63822BEF3`

Candidate canonical top SHA-256:
`9538D97854BA9D5D76143CBA0FEDB3B2E7CE18F977CE89557406E63404026CB7`

Candidate worker S19 SHA-256:
`485BA4C3ADCD622EAE90D74DE6FEB5BA8EBE0EAD6FC764CB9DBE6133B51324CC`

## Changes

| Resident change | Bytes saved |
| --- | ---: |
| Share enrollment/recovery input setup | 17 |
| Shorten metadata and directory-pointer setup | 7 |
| Generate journal mask instead of storing its table | 4 |
| Startup, console, line editor, printing, and shared HIMON handoff | 27 |
| Parser carry/status cleanup and shared nibble reader | 11 |
| Shared complete-page/partial-page worker copy and verification loop | 10 |
| One message-page helper | 4 |
| Total resident reduction | 80 |

All 26 emitted compact-message calls now use `STR8_PRINT_MESSAGE_X`.
The previous private page-helper names remain aliases. Both reset-source
messages, prompt fallthrough, and complete message output are checked. All
message starts fit on `$FC`; a regression also enforces termination within
256 bytes, the bound required by the smaller printer.

The worker saves 40 bytes through direct zero-page indirect addressing,
shared failure reporting, removal of a duplicate same-byte shortcut, and
shorter branches/return handling. Full record preflight, per-byte one-to-zero
validation, erase verification, and programmed-byte verification remain.
The flash polling instructions and counter values are unchanged; linked
branch-page checks protect their timing. The parser nibble helper adds one
nested return address (two stack bytes). Worker copying performs additional
loop-control work; it is verified for the new 568-byte size.

## Host validation

The frozen fixture `tools/fixtures/resident-v133-before-size.json` contains
the verified preceding host image and resident/worker symbols. It is not a
board flash dump. The differential suites execute actual linked 65C02 code.

```text
make all led-worker-test
make size-optimization-check
make release-package
```

`make all led-worker-test` passed for v1.34 on 2026-09-15. All four Python
suites described below also passed when run directly, covering the checks
exposed by `make size-optimization-check`. The console and LED worker probes
were rebuilt and subsequently passed on COM4. The worker probe targets the
verified erased B2:9 sector, preserving the AP image in B2:8. `make release-package` passed,
including migration-kit allowlist and extracted-package verification. The
combined R-YORS image and STR8-iN/65 top updater, RAM installer, and factory
restore tools also built and passed their host checks.

The v1.34 canonical BIN differs from the optimized interim v1.33 BIN at only
CPU address `$FC45`: the displayed version's ASCII `3` changes to `4`.

The deeper tests require `py65==1.2.0` from `tools/requirements-test.txt`.
They accept an installed copy or the repository's local test-dependency folder.

`test_resident_reclaim.py` verifies the exact resident data, all 26 compiled
message calls, fixed ABI, relocated interrupt opcodes/vector contents, erased
margin, worker extent, calibrated delay, and 1,560 range-parser cases.

`test_conservative_resident.py` compares the preceding and candidate resident:
1,354 record-parser cases, 2,144 directory cases, 31 loader cases, 512 journal
cases, 18 staging cases, invariants, and bank-jump output. Its flash calls are
stubbed and therefore do not qualify the worker.

`test_size_optimization.py` adds messages, every-byte worker-copy readback
failures at both old and new sizes, console-ready values, line editing,
reset/selector paths, warm/cold HIMON handoffs, installer preflight,
directory arithmetic, journal masks, and actual NMI/IRQ/BRK dispatch.

`test_worker_optimization.py` executes the worker with modeled bank switching
and flash commands: 1,304 differential cases passed, plus six polling-cycle
comparisons. Timeout exits check the production counter initialization, then
accelerate the failure by shortening the RAM counters. The model provides
deterministic failure injection and does not establish electrical behavior
or real flash timing.

## Integration and remaining hardware work

R-YORS consumes new image/public-contract hashes and layout values through
its refreshed integration lock. Its external-artifact, HIMON record-client,
and banked-AP checks passed against v1.34. The banked-AP check stubs the
selector; actual selector instructions are covered by the
worker suite. HIMON and ASM-F2 source changes are not required:
HIMON installs its handlers through the unchanged IVI RAM vectors and uses
the fixed parser/selector entries. ASM-F2 uses HIMON's service table.
HIMON's active bank helper is `$0300-$0335`, clear of the shorter selector;
it shares the tray with the full worker by phase.

Rebuild probes that copy the stored worker; old compiled probes contain the
preceding ROM address and size. Rebuild top updaters, migration images, and
combined images so that they contain this candidate's exact bytes.

The [2026-09-15 COM4 session](STR8N_V1_34_BOARD_TEST_2026-09-15.md) installed
v1.34 and verified exact live readback with the directory preserved,
physical/software reset, console ABI and BRK, HIMON C/W and timeout,
ASM-F2 entry/return, RAM loading, and J3. The
[follow-up session](STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md) also passed
power-cycle startup, physical NMI, actual VIA1 timer IRQ, and optimized-worker
program/verify/erase/verify on B2:9, including invalid-write rejection.
The [factory migration session](STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md)
also passed the erased-B0 migration, D0 adoption, both B0 boot paths, and
complete four-bank readback. Bank 1-2 guest boots, resident installation,
and injected recovery paths remain separate gates. The board reports state
the scope and retained hashes.
All historical reports remain tied to their original hashes.
