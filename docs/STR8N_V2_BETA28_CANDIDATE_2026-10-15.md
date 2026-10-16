# Beta28 candidate — flash-resident utilities

Offline candidate only. Board 2609 remains on beta27; no serial port was opened and no hardware was flashed. No beta28 installer is provided.

Instruction-model qualification and an independent byte-for-byte rebuild passed. Hardware qualification remains pending.

MAINT 2.3, SRAM 1.3, WORK 1.3 and EDU 1.3 execute their main code and constant text from B2. The shared RAM gateway performs cross-bank calls/reads and restores B2. Flash mutation uses the existing fixed-ABI RAM worker. WORK retains the callable $5003 ABI and reinstalls its gate when called from any bank.

B2 NMI and IRQ/BRK vectors route to the initialized RAM dispatchers at $7E20 and $7E31. Its reset vector routes through RAM reset ABI $7E64, which selects B3 before restarting. B2 remains a provider entered after B3 boot, not a standalone cold-boot bank. The VERSION asset code is unchanged; its whole-image CRC seal moves to $FFF6–$FFF7 so the vector pocket remains available. Fixed B3:F stays byte-identical beta27.

## Measured flash usage

| Component | Start | Exclusive end | Linked bytes |
| --- | ---: | ---: | ---: |
| MAINT | $8097 | $A928 | 10,385 |
| SRAM | $A928 | $B711 | 3,561 |
| WORK | $B711 | $C9E6 | 4,821 |
| EDU | $C9E6 | $CC2E | 584 |
| Shared header, RAM images, gateway thunks and APPS | | | 1,097 |
| CRC seal | | | 2 |

B2:$8000–$D7FF reserves **22,528 bytes (22 KiB)**. The candidate uses **20,450 bytes**, leaving **2,078 bytes** of reserved utility padding. Beta27 used 20,759 bytes in this region and left 1,769 bytes. The other B2 firmware assets stay at D800–FFFF; B1 remains entirely free.

## Active RAM footprint

Rows are separate utility lifetimes, not additive. These figures include reserved private buffers and gateway slots; they exclude the unchanged monitor, device-service RAM, zero page and stack.

| Utility | Beta27 RAM | Beta28 RAM | Reduction |
| --- | ---: | ---: | ---: |
| MAINT | 16,099 | 5,232 | 10,867 |
| SRAM | 4,256 | 736 | 3,520 |
| WORK | 5,259 | 847 | 4,412 |
| EDU | 615 | 124 | 491 |

MAINT additionally borrows the same 4,096-byte $6800–$77FF sector staging buffer during flash writes in both versions. Launching a utility still temporarily borrows the existing 2,560-byte status/loader staging area. The utility gateway itself links to 68 RAM bytes within its reserved 112-byte slot. WORK adds a 62-byte bootstrap within its 64-byte compatibility block.

SRAM and EDU preserve all application RAM on query/return. WORK preserves application RAM outside $5000–$503F; its $6400–$643F transfer window is restored on return and cannot be used as a WORK I/O buffer during the call. WORK reloads its transient caches from retained storage on every API call; handles remain in SPI SRAM. MAINT preserves $0200–$4FFF and reserves $5000–$63FF for its editor and state.

**MAINT:** 5000-63FF editor, line, state, transfer requests; 7B90-7BFF shared gateway; 6800-77FF additional 4096-byte sector staging during flash writes.

**SRAM:** 67C7-67F6 mutable state (48 bytes); 6900-6AFF directory and transfer workspace (512 bytes); 6400-643F temporary preserved transfer window (64 bytes); 7B90-7BFF shared gateway.

**WORK:** 5000-503F compatibility block, API 5003 (64 bytes); 6800-6A1E cleared transient state/cache allocation (543 bytes; includes a 64-byte vacated slot); 6A40-6A7F transfer-window backup (64 bytes); 6400-643F temporary preserved transfer window (64 bytes); 7B90-7BFF shared gateway.

**EDU:** 7CF0-7CFB mutable state (12 bytes); 7B90-7BFF shared gateway.

## Behavior and candidate limits

`R MAINT`, `R SRAM`, `R WORK` and `R EDU` now validate the sealed flash bundle and enter it directly. APPS lists all four as FLASH utilities. T remains an inventory of saved RAM records; these utilities are no longer SR images. Native utility load-only syntax is refused. The retained SRAM CLK program continues to load into CPU RAM and execute as before.

MAINT protects B2 against writes/erases while executing its utilities there. Its former S 8 / S 9 self-staging feature is removed because the utility is no longer a RAM image. User saved-program copies between free flash banks and SPI SRAM remain supported. A future flash update requires a separately qualified RAM installer.

WORK, SRAM and EDU use the existing foreground-only, non-reentrant service contracts. W65C02 instruction-model qualification also covers the common 816 emulation instruction set; physical behavior and native 816 execution have not been qualified.

## Build and qualification

Build: `python tools/build_v2_beta28.py`. Test: `python tools/test_v2_beta28_candidate.py` and `python tools/test_v2_beta28_workers.py`. Generate this report: `python tools/report_v2_beta28.py`. The package is BUILD/v2-beta28, with reference bank images in candidate/ and exact linked footprints in usage.json and xip/build.json. Candidate reference images are for offline qualification, not direct installation.

The complete core/worker suites passed before the final provider-vector addition. Their immutable receipts and reference bank bytes are archived under output/qualification/beta28-core-2026-10-15/. The vector suite compares all four final bank images with that qualified reference: only B2:$FFF6–$FFFF vector/seal padding may differ, and the entire XIP utility bundle must be identical. It then exercises VERSION, XIP EDU, actual NMI/IRQ/BRK vector fetches, the NMI hold gate and reset routing on the final image. This avoids repeating unchanged core tests while binding their evidence by exact bytes.

Final receipts: BUILD/v2-beta28/beta28-qualification.json and beta28-vector-test-results.json. Confirm their passed fields and build/utility hashes. The independent rebuild receipt is reproducibility-test-results.json. Physical timing, electrical behavior and native 816 mode remain unqualified; no port was opened.
