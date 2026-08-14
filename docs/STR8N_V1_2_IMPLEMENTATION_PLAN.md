# STR8-N v1.2 RAM Relocation and Update Plan

Status: implemented, host-qualified, and onboard-update hardware-accepted on
2026-08-11. The retained transcript proves backup, Bank-3 sector-F program and
internal verify, RESET into STR8-N 1.2, live `S` selection, guarded onboard
directory refresh, Bank-3-to-Bank-2 copy+enrollment, and selector launch of the
copy. The remaining Phase 7 smoke checks and external recovery proof are still
open.

This plan coordinates the STR8-N, HIMON, ASM-F2, Bank Maintenance, and related
RAM-tool rebuilds needed to release STR8-N v1.2. It also defines the final
phase that creates a self-contained RAM tool, loaded with STR8-N `L`, which can
replace Bank-3 sector F only after the RAM relocation is complete and proven.

## Goals

1. Remove every maintained runtime allocation from `$1A00-$1FFF`.
2. Rebuild STR8-N, HIMON, and ASM-F2 against one published v1.2 RAM ABI.
3. Rebuild every maintained RAM tool that refers to the moved addresses and
   put `v1.2` in its filename.
4. Preserve the existing `$7B00` record tray and `$7E00-$7EFF` service/IVI
   page.
5. Protect the new STR8 state from ASM output.
6. Produce and qualify an `L`-loadable Bank-3 sector-F updater only after all
   RAM-relocation gates pass.
7. Provide both an onboard update procedure and an external-programmer
   recovery procedure.

This release does not automatically assign `$1A00-$1FFF` to ASM. It makes the
range available as a contiguous Low Expansion Arena. Increasing ASM table
capacity there is a separate, later change with its own tests.

## Frozen v1.2 RAM ABI

```text
$7A00-$7AFF  HIMON command buffer                    unchanged
$7B00-$7BFB  STR8 decoded-record payload tray        unchanged
$7BFC-$7BFF  spare                                     4 bytes
$7C00-$7DBF  High Tool Overlay                       448 bytes
$7DC0-$7DC7  HIMON AP-link scratch                     8 bytes
$7DC8-$7DE8  reserved                                 33 bytes
$7DE9-$7DFF  STR8 Recovery State Capsule              23 bytes
$7DFD-$7DFF  Bank Jump Record inside the capsule       3 bytes
$7E00-$7EFF  HIMON/STR8 service, debug, loader, IVI   unchanged
```

The Recovery State Capsule keeps its existing offsets and changes only its
page: `$1FE9-$1FFF` becomes `$7DE9-$7DFF`. The Bank Jump Record therefore moves
from `$1FFD-$1FFF` to `$7DFD-$7DFF`.

The High Tool Overlay is foreground, volatile, and single-owner. Bank
Maintenance, flash-read/dump tools, CRC inventory, Top Update, and similar RAM
tools may use it, but only one may be active. A tool must initialize every byte
it consumes and must not expect the overlay to survive another tool or an ASM
session.

ASM-F2 may continue to use `$7Cxx` as volatile output, but its exclusive target
limit becomes `$7D00`; `$7D00-$7DFF` is never a legal ASM output destination.
The exact last accepted output byte is `$7CFF`. Multi-byte output crossing from
`$7CFF` into `$7D00` must fail without writing either byte.

## Compatibility Rule

The relocation is a RAM-ABI break. All maintained firmware and tools must be
built from the same v1.2 address contract. Do not publish a mixture containing
v1.1 STR8-N, v1.2 HIMON, and v1.1 ASM as a finished system.

A short migration window is allowed only in this order:

1. v1.1 STR8-N remains the reset supervisor.
2. v1.2 ASM + HIMON are installed below `$F000`.
3. Without using the newly installed ASM for `$7Dxx` output, return to v1.1
   STR8-N and load the v1.2 Top Update tool with `L`.
4. Top Update replaces Bank-3 sector F with v1.2 STR8-N.

HIMON v1.2 must tolerate an absent `$7DFD-$7DFF` record during that migration
window. After v1.2 STR8-N is installed, only the new record is authoritative.

If v1.1 has already been declared frozen, release this work as v1.2. Do not
silently replace v1.1 artifacts or reuse their hashes.

## Published Address Contract

Create one generated or copied release contract consumed by both repositories.
It must publish at least:

```text
RAM_ABI_VERSION              $12
HIGH_TOOL_BASE               $7C00
HIGH_TOOL_END                $7DBF
HIM_AP_LINK_WORK_BASE        $7DC0
HIM_AP_LINK_WORK_END         $7DC7
STR8_STATE_BASE              $7DE9
STR8_STATE_END               $7DFF
STR8_BANK_JUMP_SIG0          $7DFD
STR8_BANK_JUMP_SIG1          $7DFE
STR8_BANK_LAST_JUMP          $7DFF
ASM_TARGET_END_EXCLUSIVE     $7D00
```

Avoid another set of independent literals in STR8-N, HIMON, ASM, and Bank
Maintenance. The STR8-N manifest must publish the RAM ABI and addresses, and
the R-YORS external lock check must reject a mismatched manifest.

## Versioned Artifact Names

Release artifacts:

```text
BUILD/v1.2/bin/str8n-v1.2-bank3-f000-ffff.bin
BUILD/v1.2/s19/str8n-v1.2-f000.s19
BUILD/v1.2/s19/str8n-v1.2-worker-0200.s19
BUILD/v1.2/s19/str8n-v1.2-bank-maint-2000.s19
BUILD/v1.2/s19/str8n-v1.2-top-update-2000.s19
BUILD/v1.2/s19/str8n-v1.2-directory-refresh-2000.s19
BUILD/v1.2/s19/ryors-v1.2-asm-himon-str8n-bank0-2-8-f.s19
BUILD/str8n-manifest.json
```

R-YORS payload artifacts:

```text
SRC/BUILD/s19/ryors-v1.2-asm-himon-bank3-8-e.s19
SRC/BUILD/s19/ryors-v1.2-himon-bank3-c-e.s19
SRC/BUILD/s19/ryors-v1.2-asm-bank3-8-b.s19
```

Every maintained RAM tool that embeds the shared RAM map or STR8 ABI must also
contain `v1.2` in its source and output filename. The initial inventory is:

```text
str8n-v1.2-bank-maint-2000.asm/.s19
str8n-v1.2-top-update-2000.asm/.s19
str8n-v1.2-directory-refresh-2000.s19
str8n-v1.2-ram-proof-3000.s19
str8n-v1.2-bank-crc-all-3000.a/.s19
str8n-v1.2-flash-bank-read-ap-2000.a
str8n-v1.2-flash-bank-dump-ap-2000.a
asm-session-report-v1.2-ap-2000.a
```

During implementation, run a source inventory for all non-archived references
to `$1A00-$1FFF`. Add every maintained result to this list. Generic RAM
applications such as Life or BASIC need not be renamed unless they consume the
moved ABI. Historical sources and hardware transcripts retain their original
names and bytes.

## Phase 0: Freeze and Recovery Preparation

Before changing addresses:

1. Record the current v1.1 commit IDs, manifest, artifact hashes, top-sector
   BIN, and board readback.
2. Confirm that the exact v1.1 external-programmer BIN can be reproduced.
3. Preserve the current Bank-3 `$FFB0-$FFF9` directory/configuration bytes.
4. Reserve Bank 1 CPU `$F000-$FFFF` as `STR8_TOP_SAFE`, physical
   `$0F000-$0FFFF`, or explicitly choose another documented sacrificial 4K
   sector. Do not overwrite an unknown guest image.
5. Keep an external programmer connected or immediately available for every
   sector-F board test.

Exit gate: a failed Bank-3 sector-F experiment can be recovered externally
without depending on any onboard code.

## Phase 1: Shared RAM ABI and Static Checks

1. Add the v1.2 shared address contract.
2. Change the STR8 state and jump-record equates to `$7DE9-$7DFF`.
3. Move HIMON AP-link scratch from `$1A10-$1A17` to `$7DC0-$7DC7`.
4. Change ASM target validation so `$7CFF` is the final accepted byte and
   `$7D00` is the exclusive boundary.
5. Add exact boundary tests for one-, two-, and three-byte output at
   `$7CFD-$7D00`.
6. Add a maintained-source scanner that rejects fixed runtime references in
   `$1A00-$1FFF`, except explicit negative tests and historical material.
7. Update map generators rather than editing generated documents directly.

Exit gate: address checks pass and no current firmware source independently
defines the old capsule, jump-record, linker-scratch, or ASM-limit addresses.

## Phase 2: STR8-N v1.2 Relocation

1. Update resident, unified-worker, jump, directory, and proof paths to use the
   shared v1.2 contract.
2. The original plan kept `$F003/$F006` fail-closed. The accepted resident ABI
   supersedes that constraint: `$F003` is CONSOLE_INIT and `$F006` is
   ABI_QUERY v1/capabilities `$3F`; `$F009/$F010` remain the record and bank
   services.
3. Keep the record tray at `$7B00-$7BFB`, record card at `$7E95-$7EA8`, delay
   cells, and IVI addresses unchanged.
4. Extend layout checks to require `$7DE9/$7DFF/$7DFD-$7DFF` exactly.
5. Extend the manifest with RAM ABI `$12` and the high-RAM ownership rows.
6. Build and run layout, range-matrix, RAM-load, worker, directory, and jump
   tests.

Exit gate: STR8-N and its worker have no active `$1Fxx` state references and
all existing flash safety tests pass with the new capsule.

## Phase 3: HIMON and ASM-F2 Rebuild

HIMON:

1. Consume the new jump-record and linker-scratch addresses.
2. Preserve `$7DFD-$7DFF` across cold clear exactly as v1.1 preserved
   `$1FFD-$1FFF`.
3. Treat an absent or invalid record as `STR8_BANK_NONE` during migration.
4. Keep service vectors, reset signature, trap state, and IVI in `$7Exx`.
5. Update memory-map reporting and generated maps.

ASM-F2:

1. Change the target ceiling to exclusive `$7D00` and exact maximum `$7CFF`.
2. Reject any statement whose complete output span crosses `$7D00`.
3. Update smoke tests that currently prove `$7DFD-$7DFF` output.
4. Keep `$1A00-$1FFF` unallocated for this phase; do not combine relocation
   with an ASM-capacity increase.

Exit gate: `make -C SRC asm-test`, HIMON tests, generated maps, and the combined
ASM + HIMON Bank-3 payload all pass.

## Phase 4: Bank Maintenance and RAM Tools

Pack Bank Maintenance into the High Tool Overlay. Its 254-character input
capacity is unnecessary; the longest accepted command is ten characters plus
the terminator. Use a 16-byte bounded input buffer and reject additional input
without writing past it.

One acceptable packed layout is:

```text
$7C00-$7C1D  result/state                              30 bytes
$7C20-$7C2F  bounded input                             16 bytes
$7C40-$7C7F  staged Bank-3 directory                   64 bytes
$7C80-$7D1A  AP inventory, 31 x 5 bytes               155 bytes
$7D1B-$7DBF  available to the active foreground tool  165 bytes
```

The gaps are deliberate and keep the tables inspectable. The tool must not
touch `$7DC0-$7DFF` except through the published STR8 worker/capsule fields.

For every other maintained RAM tool:

1. Replace private `$1Axx-$1Dxx` status, input, and tables with named High Tool
   Overlay fields.
2. Replace direct `$1Fxx` worker fields with shared v1.2 equates.
3. Bound interactive input to the size actually required.
4. Rename source and output files to include `v1.2`.
5. Update host source checks, expected S19 ranges, hashes, examples, and dump
   addresses.
6. Archive superseded samples only after the v1.2 replacement passes; do not
   rewrite historical hardware evidence.

Exit gate: the active-source scanner finds no unintended `$1A00-$1FFF`
runtime use, every version-sensitive RAM artifact contains `v1.2`, and Bank
Maintenance passes its complete host matrix.

## Phase 5: Integrated Host and Non-Destructive Board Proof

Build the complete generation:

```text
STR8-N v1.2 resident and worker
HIMON v1.2
ASM-F2 v1.2-compatible runtime
Bank Maintenance v1.2
all version-sensitive RAM tools
Bank-3 8-E ASM + HIMON payload
Bank-0/1/2 8-F ASM + HIMON + STR8-N image
programmer BIN and manifest
```

Before creating the Top Update artifact, prove on hardware without touching
Bank-3 sector F:

1. Load v1.2 RAM tools through existing STR8-N v1.1 `L`.
2. Prove High Tool Overlay bounds and canaries.
3. Prove Bank Maintenance map and read-only paths.
4. Use a sacrificial Bank 2 for erase/program/copy verification.
5. Prove HIMON cold clear preserves a synthetic valid record at
   `$7DFD-$7DFF` and rejects invalid signatures/banks.
6. Prove ASM accepts output ending at `$7CFF` and rejects every crossing into
   `$7D00` without changing `$7D00-$7DFF`.
7. Prove STR8 record parsing, `L`, `I`, `H`, and `Jn` behavior using RAM/proof
   images or non-F sectors.

Exit gate: retained host results and board transcripts establish the complete
RAM move. Only then may the Top Update release target be enabled.

## Phase 6: v1.2 Top Update RAM Tool

### Artifact and build dependency

Create:

```text
tools/top-update/str8n-v1.21-top-update-2000.asm
BUILD/v1.2/s19/str8n-v1.2-top-update-2000.s19
```

The `make top-update` target must depend on all of the following:

```text
ram-abi-check
layout-check
range-matrix-check
ram-load-contract-check
bank-maint
programmer-bin
R-YORS v1.2 manifest/lock check
```

The builder must embed the exact verified v1.2 programmer BIN; hand-copied
image bytes are not allowed. It must fail if the candidate does not publish
RAM ABI `$12`, state `$7DE9-$7DFF`, jump record `$7DFD-$7DFF`, correct vectors,
and the expected STR8-N v1.2 identity.

### Implemented RAM layout

```text
$2000-...    updater, console, validation, flash worker, and recovery loop
$4000-$4FFF  exact candidate sector image before metadata overlay
$7C00-$7DBF  updater request/result and bounded input
$7DE9-$7DFF  shared v1.2 worker/capsule fields when required
```

The WDC linker emits the loadable image as the dense `$2000-$4FFF` span; the
unused gap before the exact `$4000-$4FFF` candidate is fill, not executable
ROM dependency. The updater's flash mutation code remains in its `$2000`
RAM image and does not call Bank-3 ROM after active erase begins.

The complete S19 must lie inside the existing STR8-N `L` contract
`$2000-$7AFF`, have S9 `$2000`, and start automatically. It must not call
HIMON, ASM, or Bank-3 ROM after active sector-F erase begins.

### Mandatory preflight

Before any active-sector mutation, the tool must:

1. Select Bank 3 and verify the live STR8 signature and readable vectors.
2. Verify the embedded candidate byte-for-byte against a build-published hash
   or CRC and validate its reset/NMI/IRQ vectors.
3. Verify the candidate RAM ABI and version are exactly v1.2.
4. Copy the live `$FFB0-$FFF9` directory/configuration pocket over the
   candidate image. The v1.2 directory format remains unchanged.
5. Leave candidate `$FFFA-$FFFF` vectors intact; never copy old vectors over
   the new image.
6. Verify the complete staged 4K image after the metadata overlay.
7. Create and verify a raw 4K backup of the live Bank-3 sector F in the
   explicitly reserved `STR8_TOP_SAFE` sector. The default is Bank 1 CPU
   `$F000-$FFFF`, physical `$0F000-$0FFFF`.
8. Print an external recovery receipt naming the backup and destination
   physical ranges and their checksums.
9. Require two different exact confirmations: one before preparing or
   replacing `STR8_TOP_SAFE`, and `TYPE STR8-N 1.2` before active Bank-3 erase.

The tool must refuse to overwrite a non-erased `STR8_TOP_SAFE` sector unless
the operator explicitly entered the documented replacement confirmation. It
must never assume Bank 1 is disposable.

### Program ordering

After final confirmation:

1. Print the final status line before flash becomes busy.
2. `SEI`, `CLD`, initialize a private stack, and remain entirely in RAM.
3. Erase Bank-3 sector F and verify every byte is `$FF`.
4. Program and verify `$F000-$FFF9` first.
5. Program and verify NMI/IRQ vector bytes.
6. Program the RESET vector `$FFFC-$FFFD` last.
7. Compare all 4096 live bytes with the staged candidate.
8. Revalidate the v1.2 signature, directory/config bytes, and vectors.
9. Print success and jump through the newly verified RESET vector.

NMI cannot be masked. The operator card must prohibit NMI, RESET, power loss,
or cable/device removal during the transaction.

### Failure behavior

Before active erase, every failure returns to a harmless RAM prompt.

After active erase begins, failure must never jump into ROM or invite RESET.
The tool remains in RAM, prints the first failing address, and offers only:

```text
R  retry the embedded v1.2 candidate
O  restore the verified STR8_TOP_SAFE image
```

Both paths revalidate their complete 4K source before writing. External
programmer recovery remains mandatory if retry and onboard restore cannot
complete.

Exit gate: the updater passes source-order checks, S19 contract checks,
candidate/hash checks, an emulated flash-state matrix, and sacrificial-sector
hardware proof before it is authorized for Bank-3 sector F.

## Phase 7: Release and Hardware Acceptance

Hardware checkpoint 2026-08-11: items 1-5 are accepted by the top-update
transcript, with item 4 covered by internal full-sector verify rather than an
independent readback. Item 6 is accepted for timeout, `S`, `H`, and `J3`;
selector `2` and its Bank-2 launch are also accepted, while explicit command
paths `J0`-`J2` remain open. Items 7 and 8 are accepted. Item 9 is accepted for
read-only `M`, destructive Bank-0 `E ALL`, and the nonempty-directory refusal
paths for B0 and B2. The guarded directory refresh and Bank-3-to-Bank-2
copy+enrollment are accepted. The current Bank Maintenance artifact's
metadata-only `D` adoption and its shared `C` regression are also accepted; AP
put remains open. Item 10 remains open. The
real ASM `IMPORT`/`PACKAGE`/HIMON `AP`/`RJOIN` path has accepted relocated
scratch `$7DC0-$7DC7`, and canaries spanning `$1A00-$1FFF` survived ASM
packaging, AP linking, and ASM output through `$7CFF`. The same canaries then
survived corrected v1.2 Bank Maintenance `M`, `Q`, and live-selector warm `H`.
The non-destructive RAM-relocation hardware test set is complete.

Renewed resident ABI checkpoint 2026-08-11: the retained
[expanded ABI hardware proof](RESIDENT_ABI_HARDWARE_PROOF_2026-08-11.md)
accepts the current resident for guarded onboard update, verified backup,
RESET/live selector, `$F003` CONSOLE_INIT, `$F006` ABI_QUERY, `$F019` CHAROUT,
both `$F03E` CHAR_READY paths and non-consumption, `$F013` raw CHARIN, `$F0E6`
BRK dispatch, warm `H`, cold timeout, and `J3`. The silent NMI action still
needs an explicit operator annotation. The same proof now accepts the onboard
directory refresh, empty-directory map, Bank-3-to-Bank-2 copy+enrollment,
selector `2` launch, return through `J3`, and the current artifact's `D`
adoption guards and commits. External recovery, explicit command-path
`J0`-`J2`, and the remaining destructive matrix stay open.

Retain exact hashes, binaries, maps, source commit IDs, terminal transcripts,
and flash readbacks for:

1. v1.2 ASM + HIMON Bank-3 `8-E` install under v1.1 STR8-N;
2. v1.2 Top Update load through v1.1 `L`;
3. `STR8_TOP_SAFE` backup and verification;
4. Bank-3 sector-F update and full readback;
5. physical RESET into v1.2 STR8-N;
6. selector timeout, `S`, `H`, and `J0`-`J3`;
7. HIMON cold preservation of `$7DFD-$7DFF`;
8. ASM `$7CFF/$7D00` boundary behavior;
9. v1.2 Bank Maintenance map/copy/adopt/erase/AP operations;
10. external-programmer recovery from the retained BIN and, separately, from
    the raw `STR8_TOP_SAFE` sector.

Do not call v1.2 complete until the external recovery path is demonstrated or
the exact programmer procedure is independently verified against a readback.

## Operator Update Instructions

The onboard top update and directory-refresh sequences below were accepted on
hardware on 2026-08-11 with the hashes retained in the linked proof records.
The independent external-programmer recovery demonstration remains an open
release gate, so keep the rollback images and raw backup available.

### Host preparation

1. Clean-build both repositories from the accepted v1.2 commits.
2. Run the complete STR8-N and R-YORS host suites.
3. Match every artifact against `BUILD/str8n-manifest.json` and the release
   record.
4. Save these files somewhere independent of the board:

```text
str8n-v1.1-bank3-f000-ffff.bin             rollback image
str8n-v1.2-bank3-f000-ffff.bin             new programmer image
ryors-v1.2-asm-himon-bank3-8-e.s19         Bank-3 payload
str8n-v1.2-top-update-2000.s19             onboard top updater
str8n-v1.2-directory-refresh-2000.s19      onboard directory refresh
str8n-v1.2-bank-maint-2000.s19             post-update maintenance
```

5. Read and save the live Bank-3 sector F with the external programmer when
   possible.
6. Confirm that the selected `STR8_TOP_SAFE` sector may be overwritten.

### Board migration

1. Boot the existing v1.1 STR8-N and press `S` during the live selector.
2. Use `I`, Bank 3, range `8-E`, and send
   `ryors-v1.2-asm-himon-bank3-8-e.s19`.
3. Reset, return to the STR8-N menu, and do not use old ASM to write `$7Dxx`.
4. Enter `L` and send `str8n-v1.2-top-update-2000.s19` at normal full speed.
5. Verify the tool reports candidate v1.2, RAM ABI `$12`, candidate checksum,
   live-directory checksum, and the exact physical backup/destination ranges.
6. Authorize `STR8_TOP_SAFE` only after confirming its selected sector is
   sacrificial.
7. Require the tool to print `BACKUP VERIFIED` before proceeding.
8. At the final prompt, type the exact release confirmation
   `STR8-N 1.2`.
9. Do not touch NMI, RESET, power, FTDI, or the flash device until the tool
   reports full-sector verification and transfers to the new RESET vector.
10. After v1.2 starts, press `S`, verify the v1.2 identity, then test `H` and a
    cold HIMON timeout.
11. Load `str8n-v1.2-bank-maint-2000.s19` with `L` and run its read-only map.
12. Verify ASM accepts an endpoint at `$7CFF` and rejects `$7D00` and every
    crossing write.
13. Update Bank 0-2 R-YORS clones with the v1.2 `8-F` image only after Bank 3
    passes all smoke tests.

### External-programmer alternative

A reflash of physical `$1F000-$1FFFF` is always sufficient and remains the
safest first-board path:

1. Read and archive the existing physical `$1F000-$1FFFF` sector.
2. Erase only physical `$1F000-$1FFFF`.
3. Program `str8n-v1.2-bank3-f000-ffff.bin` file offset `$000-$FFF` there.
4. Verify all 4096 bytes.
5. Install the v1.2 Bank-3 `8-E` payload.

The raw programmer BIN contains the release directory/configuration defaults;
unlike the onboard Top Update tool, it does not preserve the live directory
unless a separate programmer-side merge is deliberately performed and
verified.

### Recovery after a failed onboard update

If the RAM updater is still running, do not reset. Use its retry or verified
old-image restore command.

If RESET no longer reaches STR8-N:

```text
external programmer source  PHY $0F000-$0FFFF  STR8_TOP_SAFE
external programmer target  PHY $1F000-$1FFFF  active Bank-3 sector F
```

Alternatively program the retained v1.1 or v1.2 4096-byte BIN directly at
physical `$1F000`. Verify before reinstalling the flash device or applying
power.

## Definition of Done

STR8-N v1.2 is complete only when:

- current firmware and maintained RAM tools contain no unintended runtime
  allocation in `$1A00-$1FFF`;
- all version-sensitive RAM tools contain `v1.2` in their filenames;
- STR8-N, HIMON, ASM-F2, Bank Maintenance, and combined images build cleanly;
- ASM cannot write `$7D00-$7DFF`;
- HIMON cold clear preserves `$7DFD-$7DFF`;
- the manifest locks the v1.2 RAM ABI and all artifact hashes;
- the Top Update tool is generated only from the final verified top BIN;
- onboard update, reset, handoff, and recovery evidence is retained; and
- the external-programmer restore procedure is verified.
