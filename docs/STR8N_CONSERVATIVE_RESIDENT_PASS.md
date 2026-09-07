# STR8-N v1.30: conservative resident follow-up

> **Historical predecessor:** the current LED slices use 58 of the resident
> bytes reclaimed here and expand/re-pack the worker by 12 bytes.
> The current host-built layout is documented in `README.md`,
> `TECHNICAL_GUIDE.md`, and `LED_STATUS_PROPOSAL.md`. The board evidence below
> applies to this preceding conservative image, not to the LED candidate.

The accepted scope is resident-only size reduction. No worker optimization,
worker repacking, public ABI change, prompt deletion, or weakened validation
is included. Version stays 1.30. This candidate has its own board evidence
below; the original v1.30 transcript remains historical evidence for commit
`521fd0a` and its original binary.

## Measured result

| Region | Original v1.30 (`521fd0a`) | Conservative candidate |
| --- | ---: | ---: |
| Resident code | 3,172 bytes | 3,132 bytes |
| Resident data | 178 bytes | 178 bytes, identical |
| Resident total | 3,350 bytes | 3,310 bytes |
| Last resident byte | `$FD15` | `$FCED` |
| Erased margin before worker | 70 bytes | 110 bytes (`$FCEE-$FD5B`) |
| Worker | 596 bytes | 596 bytes, identical |

This saves 40 more bytes, or 104 resident bytes relative to v1.29. It releases
no additional RAM. Worker storage stays `$FD5C-$FFAF`; directory, configuration,
vectors, and public entry addresses stay fixed. Canonical bytes `$FD5C-$FFFF`
are identical to the original canonical v1.30 image, including its empty
directory. No live board directory was copied into the candidate.

| Change | Bytes saved |
| --- | ---: |
| Remove redundant journal register transfers; direct pointer read | 5 |
| Reuse receive constants; direct pointer store; unconditional phase-2 assignment | 14 |
| Direct pointer accesses in directory verification and failure capture | 4 |
| Remove three zero comparisons; publish zero with STZ; direct parser read | 10 |
| Initialize apply-buffer low pointer with STZ | 2 |
| Tail-call final jump-message print | 1 |
| Share the two private message-page helper names | 4 |
| Total | 40 |

## Opcode and safety review

The release uses the WDC 65C02 assembler target. Two `LDA #0 / STA` pairs
become `STZ`. Five sites use 65C02 `(zp)` addressing instead of loading Y=0
for `(zp),Y`; the instruction operand itself is not smaller, but removing the
unneeded Y load saves two bytes per site. Existing `BRA`, accumulator `INC`,
and other useful CMOS instructions remain in use. Ordinary 6502 instructions
remain where already compact; this is not an opcode-for-opcode conversion.

The removed zero comparisons have no live carry consumer before carry is
established again. The shared initialization depends on three ABI constants
being `$01`, and the STZ changes depend on the data-buffer low address being
zero; host checks enforce those assumptions. All messages now fit page `$FC`;
both private helper labels alias one routine, with every compiled call checked.

The full apply-pointer increment, including high-byte carry handling, remains
unchanged. Directory bounds, post-write byte verification, failure details,
record checksums, RAM-load bounds, and installer ordering remain intact.
The worker and its storage layout are untouched. Exact-byte regression guards
also cover the delay loop, NMI/IRQ entry code, and console hardware routines.
Non-delay instruction counts can change; no cycle-identical claim is made.

## Host validation

The ordinary `make all` suite includes `resident-reclaim-check`: frozen
protected-byte comparisons, exact data comparison, 110-byte erased-margin
check, 26 compiled message calls, and 1,560 linked range-parser executions,
alongside the existing layout, ABI, loader, updater, and migration host checks.
`make release-package` rebuilds and verifies the packaged deliverables.

The optional differential suite executes old and new linked 65C02 instructions
with py65 1.2.0, using the original canonical build and symbol map frozen in
`tools/fixtures/resident-521fd0a.json`. This fixture is not a board flash dump.

- 1,354 parser cases: records, malformed/truncated input, checksums, invalid
  requests, source-buffer boundaries, console line endings, and register seeds.
- 2,144 directory cases: bounds, lengths, worker failure, and verification
  mismatches, including expected/observed failure reporting.
- 512 journal cases: banks, sector pairs, start/complete transitions, and masks.
- 31 RAM-loader cases: legal spans, boundary violations, checksums, and entry
  address policy, including actual accepted RAM payload bytes.
- 18 dense staging cases: one/two sectors, three record sizes, invalid starts,
  and declined commits, comparing all staged sector bytes and worker requests.
- Four bank-jump preparation cases: identical text and handoff state.

Console transport and flash-worker calls are explicit host stubs. These tests
exercise resident logic but do not prove electrical behavior or actual flash
erase/program operations. Register comparisons respect private scratch use
and relocated message pointers rather than requiring irrelevant values to match.

To run the optional suite without changing the system Python installation:

```text
python -m pip install --target BUILD/v1.30/local/test-deps -r tools/requirements-test.txt
make conservative-differential-check
make all
make release-package
```

Original canonical top SHA-256:
`60B7FE19E42766AACFCDEF8320A35D9D5AB7C5F91F0FE3130041F2CFF4799734`

Conservative candidate canonical top SHA-256:
`19E284EEF2FF88EFC4F4E4632FB0F200DC75F0E51CAAA44DEF42FA2E9181336A`

Unchanged worker S19 SHA-256:
`04F46E258924F07510FB113EDB00C788EBA129EAB98B25C284D6AB15C306E69C`

Unchanged public include SHA-256:
`3D95BF54C89A22268E1A4D93DA259A1697DC006E1451489C00ADA9E2B428E371`

## Board evidence: 2026-09-05, COM4, 115200 baud

The pre-update complete B3:F readback matched the original canonical v1.30
outside the live directory. The exact owner-local backup is
`BUILD/v1.30/local/conservative-pre-update-b3-f.bin`, SHA-256
`4FF2F57FCF766F92369CD871584D2307005D7D181FAF68CC153812537DEAD90B`.

The guarded updater was loaded into RAM through the old resident's `L`.
`BACKUP B1F` refreshed the designated B1:F backup. Its `BACKUP VERIFIED`
receipt reported `$48C2`, matching the host sum of the saved current sector.
Only then was `STR8-N 1.30` confirmed. The updater reported
`STR8-N 1.30 VERIFIED; RESET`; the candidate then reached its selector/shell.
Only B1:F backup and B3:F resident flash were written in this test.

After `C`, `BOOT COLD`, `RAM ZERO OK`, and HIMON `00.0902(1707)` appeared.
A full HIMON readback matched all 4,032 non-directory candidate bytes,
including the 110-byte erased margin, worker, configuration, and vectors.
All 64 live directory bytes matched the pre-update capture. The exact image
is `BUILD/v1.30/local/conservative-post-update-b3-f.bin`, SHA-256
`A4073DFBAD7AE4ECE9D1C6A727BF4700D475A96EDAB23C887F29533AD8E4D6DE`.
Its only difference from the canonical candidate is the retained directory.

Additional board checks passed:

- `I` rejected B3:F before a write confirmation; B3:C-E and B0:F displayed
  correct previews and accepted `N` cancellation with the existing `BAD`
  response. No payload installer write was confirmed.
- `W` returned warm to HIMON. An uninterrupted no-key startup also timed out
  to warm HIMON. `J3` printed `J B3`, restarted, and accepted the shell selector.
- Malformed `L` input drained through S9 and returned `BAD` to the shell.
  A separate otherwise valid three-byte S1 with an intentionally wrong
  checksum (`S10620004C00F09C`, correct checksum `$9D`) was likewise rejected.
- Loading the console ABI probe through the new `L` passed ABI_QUERY,
  CONSOLE_INIT, CHAROUT, lowercase `$71`, raw CR `$0D`, CHAR_READY empty/ready,
  CHARIN, register/carry contracts checked by the probe, and BRK.
- After requesting physical RESET, a receive-only window captured `RESET`,
  the intact v1.30 selector, no-key timeout, `BOOT WARM`, and the HIMON prompt.
  No serial reset command was sent during this capture.

Raw exchanges are append-only in the owner-local
`BUILD/v1.30/local/conservative-board-session.jsonl`. An initial old-resident
shell-entry capture had a receive gap; the candidate update/startup and
timeout captures above were kept open throughout. Board dumps are not factory
artifacts. A [new transcript](STR8N_CONSERVATIVE_BOARD_TRANSCRIPT.txt) records
this candidate's session. The earlier transcript is preserved without modification.

The operator then announced a power-off/on test. Power-off disconnected COM4
(`ClearCommError`, access denied); a fresh receive-only connection captured
`BOOT WARM` and HIMON `00.0902(1707)` at its prompt. The initial reset/banner
was missed during USB reconnection, so this is evidence of return to HIMON
after the announced cycle, not a complete cold-power startup transcript.
That first attempt did not establish a complete cold-power startup trace.

The repeated operator-controlled power cycle passed with automatic USB
reconnection. The receive-only `tools/board_capture.py` recorded COM4 loss,
reconnection, `RESET`, the intact `STR8-N 1.30` selector, the no-key timeout,
`BOOT WARM`, and HIMON `00.0902(1707)` at its prompt. Raw evidence is retained
in `BUILD/v1.30/local/conservative-cold-power-retry.jsonl`; it contains no TX
records. Reconnection completed before the first `RESET` byte, so the complete
visible startup was captured. This establishes the candidate's cold-power
startup/return-to-HIMON smoke check; `BOOT WARM` is the expected default
handoff selection, distinct from whether board power was cycled. It does not
claim HIMON RAM preservation across power loss.

Factory WDCMONv2 migration testing remains explicitly
operator-deferred until later. Destructive payload installation and recovery
fault injection were not rerun; dense staging and journal/verification failure
coverage for this pass remains host-based.
