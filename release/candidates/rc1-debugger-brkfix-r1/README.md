# Separate DBG1 BRK edge-fix candidate

`v1g` is the BRK edge-fix candidate based on the MAINT-corrected `v1f`.
Its offline qualification and hardware requalification on 2604 and 2609
passed, including both monitor slots and rollback/reinstall. R3 and R4 closed
cleanly with original RAM, flash/settings and final drift verified. The
R5 continuation also closed safely with its original-phase checkpoint and final
drift passed. The ten-pattern LED R6 continuation passed 93 new offline checks,
actual CPU qualification and both-board hardware preflight with restoration and
drift verified. R6 then closed cleanly at owner STOP after 12,803.703
monitored/active seconds, with 61/60 cycles and 976/960 hits on 2604/2609.
Both original full RAM images were restored/reread after final drift; all
flash/settings matched and actual worker exit was verified.
The owner has approved scoped RC1 promotion. Native applications/debugging remain outside scope;
supported runtimes are 65C02 and 65C816 E=1.

See [current candidate status](../../../docs/rc1/DBG1_CANDIDATE_STATUS.md)
for the authoritative evidence links and remaining closeout work. Live progress
is recorded by the [current soak pointer](../../../output/qualification/rc1-asm-dbg1-soak-current.json)
and its run receipts. The pointer selects the stopped R6 run. Dated startup evidence and the verified
final closure are separate; the owner has approved scoped RC1 promotion.

The source changes only two service paths:

- `$82` rejects IDs outside `$C0-$FE` before searching the user table, so `$00`
  cannot match a vacant entry. Missing valid IDs still return C=0,A=1.
- `$84` finishes the counted output before incrementing past its last byte.
  The complete inclusive range is still validated before any output. Valid
  text ending at the discovered RAM limit preserves saved registers/flags;
  crossing ranges remain rejected before printing.

The inherited MAINT marker guard, C/S/N, persistent breakpoints, public entry
table, registration capacities and application RAM limits are retained.
The builder uses the hash-pinned parent build logic with this directory's
separate source copy. It does not modify the parent or frozen rc1 sources.
Generation remains 50 for this development candidate; its image hash and
`candidate-provenance.json` distinguish it from earlier generation-50 builds.

From the repository root, use a fresh output directory:

```text
python release/candidates/rc1-debugger-brkfix-r1/build.py --out BUILD/rc1-debugger-v1g
```

Full model, boundary, manual-example and installer rehearsals passed in the
offline qualification below. Subsequent owner-authorized board requalification
used fresh backups and verified rollback/reinstall on both boards; its
[hardware report](../../../output/qualification/rc1-dbg1-v1g-hardware-requalification-2026-10-19-222241Z/report.json)
records the results. Earlier v1f soak results remain separate evidence.

## Offline qualification

The 2026-10-19 offline run passed on both CPU models and both monitor slots:

- All 88 original edge checks and 7,256 expanded regression cases. Unregister
  checks cover every ID in five table states, including holes, full tables and
  uninitialized tables. Text checks cover every byte count, saved-context
  preservation, both application RAM limits, zero-length output, page crossings,
  invalid/wrapping ranges and absence of reads beyond the limit.
- Full debugger suites including MAINT, boot, shared D/M/U, C/S/N and all eight
  persistent breakpoints: 23 groups on 65C02 and 26 on 65C816 E=1, including
  16 documented ASM example executions across the CPUs/slots.
- 72 executions of the existing registration scenarios and 21 installer-model
  groups, including actual instruction-model install/rollback on both CPUs,
  eleven transfers per transaction and refusal of stale/corrupt inputs.
- Two fresh builds produced identical firmware and debugger bytes. Only
  B1:A000-AFFF differs from v1f. Code is 3,975 bytes plus a two-byte CRC,
  leaving 119 bytes free. Application RAM remains intact.

The image is `BUILD/rc1-debugger-v1g/firmware.bin`; SHA-256 is
`6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b`.
The separate offline-prepared kit is `BUILD/rc1-debugger-v1g-boardtest-r1`.
Its frozen `hardware_qualified: false` and `soak_qualified: false` flags record
the preparation-time state, before the later hardware qualification. They do
not describe current acceptance. Preparation and simulation opened no board
ports. The full suites including manuals are also retained under the normal
test filenames expected by the existing preparer; `test-aliases.json` records
these exact aliases.

Evidence: `output/qualification/rc1-dbg1-brk-edge-fix-offline-2026-10-19-220608Z`.
All 406 protected parent/soak/staging inputs were rechecked unchanged during
that offline run.

## Continuing soak evidence

The current LED-expanded continuation is
`output/qualification/rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z`.
Its 93 new offline checks, 16 CPU-model onboard assemblies, four full 630-frame
LED executions, fresh backups and both-board hardware preflight passed. R6
then completed 61/60 cycles at owner STOP, with all ten LED patterns and
entry-latch restoration every cycle, retaining preserving base/utilities, the 40-source ASM rotation, all built-in
BRK `$80-$84` per unit and 16-hit debugger smoke. Prior acceptance is explicitly
inherited where the qualified source and scope are unchanged. R3 used the corrected
registry cleanup check and byte-exact fixture admission and has closed cleanly.
The prior r1 continuation stopped on an incorrect harness assertion that
invalidated registry IDs must be zero; r2 stopped before its first cycle when
the fixture integrity check detected copied bytes with normalized newlines.
Those independent runs and their safe restoration/drift receipts remain
historical evidence. Their results are not substituted for later qualification.

R3 closed after 3,387.5 seconds with 42/41 cycles and 672/656 breakpoint
hits on 2604/2609, original full RAM restored, unchanged flash/settings and
passed final drift. R4 subsequently closed with 156/154 cycles and
2,496/2,464 hits, one preserving checkpoint and passed final restoration/drift.
R5 then closed with 7/6 cycles, 3,640/3,120 LED frames and 112/96 hits; its
original-phase checkpoint and final restoration/drift passed. Those separate
results do not substitute for the ten-pattern R6 scope. R6 final restoration,
unchanged flash/settings, preserving drift and worker exit passed, with zero
periodic checkpoints and no actual workload failure or retry. Immutable
distribution r7 packages the reviewed closeout and checksums for the authorized
selective commit. The owner has approved scoped RC1 promotion; see the
[current candidate status](../../../docs/rc1/DBG1_CANDIDATE_STATUS.md).

## Owner-approved distribution r8

The owner authorized staging, archive/checksum verification, the related Git
commit and scoped RC1 promotion. The new package includes the separate R-register
qualification: 5,752 physical parser checks, 220 resume cases and 132 expected
unsafe-PC refusals across both boards and both monitor slots, with original RAM
restored and flash/settings unchanged. Supported runtimes are 65C02 and 65C816
E=1; native applications/debugging are excluded. **RTC drift is not part of
release qualification and is not a promotion gate.** Historical RTC records and
prior held archives retain their original scope and bytes. See the
[release policy](release-policy.json) for the owner decision.
