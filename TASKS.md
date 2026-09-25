# STR8-IN/65 Task List

This is the working backlog for the standalone STR8-N / STR8-IN/65 W65C02
project. Check an item only when its artifact hashes, host checks, board
transcript, and final flash readback agree. Keep owner-local WDCMONv2 images
out of published release artifacts.

Defects and hardware investigations are indexed in the
[repo issue tracker](ISSUES.md).

## Deferred v2 hardware issue

- [x] Package the unchanged alpha21 image as a scoped
  [STR8-N 2.0 RC1](docs/STR8N_V2_RC1_2026-09-24.md), with exact artifact and
  board top-sector hash verification. The remaining hardware qualifications
  are disclosed in the RC decision.

- [ ] [W65C51N ACIA receive on boards 2205 and 2512](docs/issues/ACIA_RX_2512_2205.md):
  resume only with meter, logic probe, or scope measurements of the receive
  signal, clock, handshake, supply, and ground. The backup-console
  qualification gate remains open.

## Proposed v2 component storage and interfaces

- [ ] Continue the [fixed-address component/storage design](docs/STR8N_V2_COMPONENT_STORAGE_PROPOSAL.md):
  explicit-bank save, AUTO placement, original-address restore, HAL device
  access, and DEBUG's IRQX dependency. Discussion only; no implementation yet.

## Next v2 layer: public R-YORS integration

Keep this work on `v2`; the v1.34/v1.35 release line stays separate. The
[interface map and ordered proof](docs/STR8N_V2_RYORS_NEXT_LAYER.md) records
the public HIMON/ASM-F2 `00.0915(2324)` boundaries.

- [ ] Adapt HIMON `STR8` return to detect v2 and enter `$F004` after selecting
  the resident bank; retain the existing v1 route for v1 boards.
- [ ] Give HIMON `L` a v2-compatible, HIMON-owned parser or a clear refusal;
  the v1 `SR` record service is absent from v2.
- [ ] Validate RAM-only HIMON/ASM-F2/AP paths before any AP flash install or
  bank-policy changes. Do not reuse v1 directory/WORK/backup assumptions.
- [ ] Record public-release host checks, then authorize and capture a separate
  W65C02SXB board run before claiming integrated v2 compatibility.

## v1.34 release

The current source is a 120-byte size reduction from the accepted v1.33
binary. Its host results and exact image identity are recorded in
[the size-change report](docs/STR8N_V1_34_SIZE_OPTIMIZATION.md).

- [x] Retain [v1.34 COM4 evidence](docs/STR8N_V1_34_BOARD_TEST_2026-09-15.md)
  for guarded update/readback, physical/software reset, console/BRK,
  HIMON C/W and timeout, ASM-F2 entry/return, RAM loading, and J3.
- [x] Retain [follow-up evidence](docs/STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md)
  for power-cycle startup, physical NMI, VIA1 timer IRQ, optimized-worker
  program/verify/erase/verify on B2:9, invalid-write rejection, and red/green LEDs.
- [x] Repeat the [complete v1.34 factory migration](docs/STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md):
  erased-B0 preservation, exact canonical top plus D0, J0/selector 0,
  physical-reset return, and byte-exact four-bank readback.
- [ ] Complete the remaining hardware gates: Bank 1-2 guest boots, resident
  installation, transient LED timing, and injected failure/recovery paths.
- [x] Package the unchanged v1.34 canonical firmware with the exact existing
  board evidence and an explicit statement that the broader matrix is incomplete.
- [x] Split the STR8-N distribution from HIMON/ASM applications and games;
  retain the project-written migration kit and Bank Maintenance `.a`.
- [ ] Commit reviewed release documentation, regenerate from committed source,
  verify the final archives and manual links, and create the release tag.

## Preceding v1.33 release status

The preceding v1.33 release completed the checks below. Its complete factory
migration remains qualified by the accepted
v1.32 hardware run plus v1.33 host checks; repeat that whole path on hardware
before describing the v1.33 migration itself as board-accepted.

- [x] Promote the immediate reset banner and reset-source indication as
  canonical STR8-N v1.33.
- [x] Bring README, maps, operator/technical guides, migration boundaries,
  manifests, filenames, and public contracts into agreement with v1.33.
- [x] From committed source, rebuild and verify the v1.33 release ZIP,
  migration ZIP, S19 set, Bank Maintenance images, and SHA-256 receipts.
- [x] Run the migration-package allowlist and extracted-package self-verifier;
  owner-local WDCMONv2 bytes, bank archives, raw captures, and R-YORS payloads
  are absent from that focused migration kit.
- [x] Accept the guarded v1.33 top-sector update, exact readback, reset-source
  behavior, and HIMON warm recovery on hardware.
- [ ] Repeat the complete factory WDCMONv2-to-STR8-N migration on hardware with
  the exact v1.33 artifacts. The corresponding v1.32 path remains the accepted
  hardware evidence.
- [x] Tag the reviewed commit and publish the verified v1.33 release package
  and its SHA-256 receipt.

## LED status service

The ownership and bit-pattern contract is specified in
[LED_STATUS_PROPOSAL.md](docs/LED_STATUS_PROPOSAL.md). Keep the public raw
console ABI free of LED side effects so user applications retain Port A.

- [x] Implement only the minimal `$01`, `$41`, `$F0`, and `$00` slice first.
- [x] Measure the linked resident and worker: 3,331-byte resident, 608-byte
  worker, 77-byte erased margin; `make all` passes.
- [x] Confirm LED order/polarity, flash-mutation coverage, worker-return
  restoration, handoff release, and application ownership on hardware.
- [x] Add the measured PWE# input-wait distinction: `$21` without a configured
  FTDI host and `$43` with one. The current resident is 3,343 bytes, the worker
  remains 608 bytes, and the erased margin is 65 bytes; host checks and the
  focused board test pass.
- [x] Complete board proof for the separately measured STR8-N RX/TX activity
  slice. The host-qualified implementation adds 25 resident bytes, leaves the
  worker unchanged, and preserves 40 erased bytes with a 32-byte layout floor.
  Public character I/O and public record parsing remain LED-neutral; HIMON and
  ASM activity belongs in their own later slices. Guarded installation and
  focused `$07`/`$0B` observations passed on COM4 on 2026-09-06.
- [x] Carry the shared vocabulary into HIMON and ASM as separate, measured
  changes without claiming their states from STR8-N after handoff. R-YORS
  commits `40d6a10` and `fda8401` added and refined the HIMON-owned service
  wrappers; the focused linked-byte check and full ASM host suite pass, and
  COM4 accepted HIMON and ASM-F2 wait/RX/TX states plus physical-reset recovery
  on 2026-09-10.

## Optional board project: Stock SXB3 to a usable multi-bank system

Goal: preserve the factory system twice, install a clean STR8 system in Bank
3, and put one independently bootable example in Bank 1. This is an end-to-end
board deployment project, not a gate on the standalone v1.34 release.

### 1. Freeze the build identity

- [x] Use the canonical product/banner name `STR8-N v1.34` for this pass.
- [x] Use v1.34 consistently in banners,
  filenames, manifests, directory descriptions, transcripts, and hashes.
- [ ] Rebuild and record the exact migration-kit, Bank-3 payload, and example
  payload hashes before touching hardware.

### 2. Clone the original SXB3 flash device

- [ ] Read the complete 128K factory flash twice with an external programmer.
- [ ] Require both reads to be byte-identical and record their SHA-256.
- [ ] Program a compatible spare flash device with that exact 128K image.
- [ ] Read the spare back and require a byte-for-byte match to the saved image.
- [ ] Boot the spare in the SXB3 and capture the stock WDCMONv2 identity.
- [ ] Label and retain the original device as the untouched recovery master;
  use the verified spare for the remaining work.

Acceptance: two recoverable physical devices exist, the saved 128K image and
both readbacks agree, and the cloned device boots stock WDCMONv2.

### 3. Preserve WDCMONv2 in Bank 0 using the RAM migration path

- [ ] Follow
  [WDCMONV2_MIGRATION_BOARD_TEST.md](docs/WDCMONV2_MIGRATION_BOARD_TEST.md)
  Phase A without combining it with a destructive phase.
- [ ] Load the read-only archive application into RAM through WDCMONv2, verify
  RAM readback, inventory all four banks, and export Banks 0 and 3.
- [ ] Extract and retain the owner-local Bank-0 and Bank-3 BIN, S19, receipt,
  FNV, SHA-256, raw terminal capture, and host event log.
- [ ] Require Bank 0 to be erased or already byte-identical to Bank 3. If it is
  used and different, stop; do not overwrite it under this task.
- [ ] Run the documented refusal gates before authorizing a flash write.
- [ ] Load the guarded seed installer into RAM, copy Bank 3 to Bank 0, and
  require per-sector verify, whole-bank FNV agreement, and a complete
  byte-for-byte comparison.
- [ ] After STR8 is installed, launch Bank 0 and use the binary `$0C` identity
  exchange to prove the preserved WDCMONv2 actually runs there. A matching
  flash copy alone is not execution proof.

Acceptance: Bank 0 is an exact preserved copy of factory Bank 3, `J0` reaches
a working WDCMONv2 guest, and physical RESET still returns to Bank 3.

### 4. Install a clean STR8 system in Bank 3

- [ ] Install and verify the chosen STR8 top sector in Bank 3 from the RAM
  seed installer; do not reset, press NMI, or remove power during the active
  Bank-3 sector-F write.
- [ ] Prove physical RESET enters the selected `STR8-N v1.xx` or `STR8-IN/65`
  build.
- [ ] Install the matching HIMON/ASM-F2 payload into Bank 3 sectors `8-E` with
  the resident `I` path and commit the new Bank-3 directory row last.
- [ ] Start from an otherwise clean directory/configuration state. Do not
  silently assign WORK, backup, VTOC, automatic FNV/AP search, or other bank
  roles; make each later assignment an explicit, separately verified action.
- [ ] Prove cold and warm HIMON entry, return through `STR8`, and another cold
  start.
- [ ] Re-prove the Bank-0 WDCMONv2 guest after the Bank-3 install.

Acceptance: Bank 3 owns RESET and boots the named/versioned STR8 build; its
directory contains only deliberately committed records; Bank 0 remains the
working stock-monitor recovery guest.

### 5. Create and install the Bank-1 example

- [ ] Use ASM-F2 source (`.a`) and the existing W65C02 style for a minimal
  Bank-1 `HELLO WORLD` guest unless one richer period-appropriate candidate
  below is deliberately selected instead.
- [ ] Keep the baseline example unsealed at the ASM-F2/AP layer: after `END`,
  leave `SEAL>` without using `SEAL`, `PACKAGE`, or AP `INSTALL`. Persist it as
  a validated STR8 guest S19 instead. This does not remove the STR8 directory
  row's required identity/seal byte; the two mechanisms are separate.
- [ ] Make the baseline a fixed-vector guest with explicit NMI, RESET, and
  IRQ/BRK targets in the image.
- [ ] If a patchable-vector variant is wanted, make it a separate artifact:
  keep the hardware vectors fixed on small trampolines, place the replaceable
  targets in RAM, and add reset/default/invalid-target tests.
- [ ] Make the guest self-contained: initialize the required console state,
  print a visible identity/version line, and provide a defined halt, loop, or
  return behavior.
- [ ] Supply valid NMI, RESET, and IRQ/BRK vectors for the Bank-1 launch
  contract even when the chosen policy makes their targets minimal.
- [ ] Build a dense, validated Bank-1 S19 whose selected range, S9, RESET
  vector, padding, checksums, and manifest hash satisfy
  [BANK_0_2_GUEST_S19.md](docs/BANK_0_2_GUEST_S19.md).
- [ ] Install it with `I`, commit its Bank-1 directory row, and prove both `J1`
  and the reset selector reach it.
- [ ] Press physical RESET and prove recovery to Bank 3, then re-prove `J0`
  WDCMONv2 and the Bank-3 STR8/HIMON path.

Richer candidate pool (select one only after the minimal Bank-1 path is
understood):

- [ ] Period-appropriate command adventure with at least `GO NORTH`.
- [ ] Conway's Game of Life, preferably by adapting the existing R-YORS app.
- [ ] ELIZA.
- [ ] A small, legally redistributable 6502 BASIC port, with Ben Eater's
  WOZMON/BASIC work evaluated as a lead rather than assumed to be drop-in.
- [ ] fig-FORTH or another provenance-checked 6502.org-era system.

For imported software, record provenance, license/redistribution terms,
original memory and I/O assumptions, porting changes, size, vectors, and the
exact source-to-artifact reproduction command.

Acceptance: Bank 1 has one reproducible, independently bootable example with
the unsealed-ASM/fixed-vector baseline contract (plus a separately identified
patchable variant, if built), retained source, build evidence, install
transcript, and cold-boot proof.

### 6. Final preservation evidence

- [ ] Read the complete 128K flash after all installs.
- [ ] Compare every bank with its intended artifact or preserved pre-image;
  unexplained bytes are a failure.
- [ ] Retain pre/post images, hashes, manifests, commands, board/flash part
  identification, transcripts, and recovery notes together.
- [ ] Update the relevant operator and board-test documents with appended
  hardware evidence; do not rewrite earlier hardware-proven transcripts.

Task 1 is complete only when the external clone, Bank-0 WDCMONv2, clean
Bank-3 STR8 system, Bank-1 example, and final full-device readback have all
passed independently.
