# STR8-IN/65 Task List

This is the working backlog for the standalone STR8-N / STR8-IN/65 W65C02
project. Check an item only when its artifact hashes, host checks, board
transcript, and final flash readback agree. Keep owner-local WDCMONv2 images
out of published release artifacts.

## Task 1: Stock SXB3 to a usable multi-bank system

Goal: preserve the factory system twice, install a clean STR8 system in Bank
3, and put one independently bootable example in Bank 1.

### 1. Freeze the build identity

- [ ] Choose the product/banner name for this pass: `STR8-N v1.xx` or
  `STR8-IN/65`.
- [ ] Assign the exact version and use the same name/version in banners,
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
