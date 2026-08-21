# STR8-N v1.22 Board Candidate

> [!IMPORTANT]
> **Hardware validation announcement — 2026-08-21:** STR8-N v1.22 has been
> validated on a physical WDC W65C02SXB/EDU system. Before programming, the
> board's original flash contents at physical `$18000-$1FFFF` (Bank 3) were
> copied to `$10000-$17FFF` (Bank 2). A combined 32K STR8-N/HIMON/ASM binary
> was then programmed into Bank 3. After the flash device was reinstalled,
> STR8-N booted, warm-started HIMON `00.0821(1059)`, returned through the
> STR8 bootloader, and launched the copied Bank-2 firmware through both the
> `J2` prompt path and the reset-selector `2` path. The EDU application reached
> its full menu and detected the SSD1306 OLED, MCP79411 RTC, and SPI SRAM.
>
> The operator was pleasantly surprised to see the newer board's full SPI menu; only CS0-CS3 and EDU LED activity had been expected.
>
> <details>
> <summary>Retained board transcript</summary>
>
> ```text
> RESET
> WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
> STR8-N 1.22
> 0-2 C W S: ......
> BOOT WARM
>
> HIMON V 00.0821(1059)
>
> > STR8
> > RUN STR8: BOOTLOADER @F000 K=03 ? y
> > RESET
> > WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
> > STR8-N 1.22
> > 0-2 C W S: .S
> > I L C W J
> > STR8-N>J2
> > J B2
>
> ================================
> W65C02SXB + EDU Kit  Rev 1.0
> W65C02S @ 8 MHz  |  5V System
> I2C/SPI bit-banged via W65C22
> =============================
>
> Initializing...
> Scanning devices...
> OLED (SSD1306)     $3C  OK
> RTC  (MCP79411)    $6F  OK
> SPI SRAM           OK
> ADC  (ADS1015)     $48  not found
> CardKB             $5F  not found
> Init complete.
>
> --- W65C02SXB + EDU Kit ---
> T - Set Time   (HHMMSS)
> D - Set Date   (MMDDYY+DOW)
> P - Print Time/Date
> N - Set Name   (16 max)
> S - SRAM Test
> H/? - Help
>
> > RESET
> > WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
> > STR8-N 1.22
> > 0-2 C W S: .2
> > J B2
> > 3S
>
> ================================
> W65C02SXB + EDU Kit  Rev 1.0
> W65C02S @ 8 MHz  |  5V System
> I2C/SPI bit-banged via W65C22
> =============================
>
> Initializing...
> Scanning devices...
> OLED (SSD1306)     $3C  OK
> RTC  (MCP79411)    $6F  OK
> SPI SRAM           OK
> ADC  (ADS1015)     $48  not found
> CardKB             $5F  not found
> Init complete.
>
> --- W65C02SXB + EDU Kit ---
> T - Set Time   (HHMMSS)
> D - Set Date   (MMDDYY+DOW)
> P - Print Time/Date
> N - Set Name   (16 max)
> S - SRAM Test
> H/? - Help
> ```
>
> The operator repeated the complete sequence with the same result.
>
> </details>

> [!NOTE]
> **WDC and toolchain disclaimer:** STR8-N and R-YORS are independent projects
> and are not affiliated with, sponsored by, endorsed by, or supported by The
> Western Design Center, Inc. WDC, W65C02S, W65C02SXB, and W65C02SXB/EDU names
> are used only to identify the hardware and compatibility target; associated
> names and marks belong to their respective owners. Use of this software and
> any flash-programming procedure is at the user's own risk and remains subject
> to the repository license and warranty disclaimer. Rebuilding the supplied
> artifacts requires an external toolchain, including WDC assembler/linker
> tools and script dependencies that include Python. Installing, configuring,
> learning, licensing, or supporting that toolchain is outside this project's
> scope. Contact WDC for W65C02SXB/EDU hardware and WDC toolchain information
> and support.

STR8-N is the reset supervisor, recovery console, and guarded flash installer
for a W65C02SXB/EDU with four 32K flash banks. It lives in the protected Bank-3
top sector at CPU `$F000-$FFFF`; HIMON, ASM, and guest systems remain separate
payloads.

STR8-N is part of R-YORS, but is deliberately R-YORS-agnostic: it does not
depend on HIMON, ASM-F2, OIL, or AP, and can supervise compatible non-R-YORS
guest systems.

**The name:** STR8-N is pronounced *straighten*, reflecting its role in
restoring a machine to a known, bootable state. `8` identifies its 8-bit
setting, while `STR` reverses `RTS`, the 6502 return-from-subroutine mnemonic.
The letters also loosely evoke **S**oftware or **S**ystem **T**o **R**eset,
**R**estore, **R**ecover, or **R**eturn to **N**ormal.

## Feature card

| Capability | What STR8-N v1.22 can do | Safety boundary |
| --- | --- | --- |
| Reset supervision | Take physical RESET in Bank 3, print `RESET`, provide a visible terminal-attach interval, and enter STR8-N or compatible HIMON | Input received during the initial `WAIT...` interval is deliberately discarded |
| Multi-bank boot | Start enrolled systems in Banks 0-2 with `J0`-`J2`, or hand off through the Bank-3 RESET vector with `J3` | Banks 0-2 must have a COMPLETE directory journal and a valid RESET vector |
| HIMON entry | Enter compatible Bank-3 HIMON warm with `W`, preserving RAM, or explicitly cold with `C` | Refuses an incompatible or missing HIMON marker |
| Flash installation | Install dense S19 payloads with `I` into any legal contiguous 4K sector range | Bank 3 `$F000-$FFFF` is never writable through `I`; final sector and COMPLETE state commit last |
| Recovery loading | Load an S19 program into RAM with `L` and execute its S9 entry | RAM only, `$2000-$7AFF`; there is no load-without-run form |
| Bank maintenance | Load the supplied RAM tool to map banks, copy and verify 32K banks, adopt existing payloads, reclaim stale D0-D2 rows after an erased-bank proof, compact an exhausted D3 journal, erase guarded ranges, and install the narrow AP carrier | Reclaim/compaction requires exact confirmation and rewrites/verifies the complete protected Bank-3 sector F while preserving all unrelated bytes |
| Protected top upgrade | Load the supplied v1.22 updater with `L`, back up Bank-3 sector F into Bank 1, program the embedded v1.22 sector, and verify all 4 KiB | The final v1.22 C/W selector update is board-accepted as of 2026-08-19 |
| Directory refresh | Load the dedicated RAM refresh tool, verify a fresh Bank-1 sector-F backup, and replace Bank-3 sector F with the current image's erased directory/configuration pocket | Backup, rewrite, RESET, empty-directory map, and subsequent B3-to-B2 copy+enrollment accepted onboard 2026-08-11 |
| Image preparation | Convert aligned guest BINs, normalize payload S19 files, and compose a complete R-YORS Bank-0/1/2 image | Generated install files contain payload only, never the `$0200` worker image |
| Reproducible release | Build the resident, worker evidence, maintenance image, programmer BIN, manifest, and host qualification matrices | Layout checks enforce fixed interfaces, the exact 4K image, and no overlap with the fixed worker |

The v1.22 candidate host verification suite covers the relocated RAM ABI and artifact
layout. Retained v1.1/v1.2 board sessions remain historical evidence; the
original migration sequence is tracked in the
[v1.2 Implementation Plan](docs/STR8N_V1_2_IMPLEMENTATION_PLAN.md).

The last board-accepted v1.21 line uses R-YORS `00.0814(1303)`: guarded
B3:F update, dense Bank-3 `8-E` installation, physical-reset persistence,
renamed Bank Maintenance load/map, and an uninterrupted synthetic `J3` handoff
all pass. The 2026-08-18 continuation additionally accepts the combined menu's
guarded `U`, full-bank copy/enrollment, separate metadata-only `D2` adoption,
directory-gated `J2` launch of the factory onboard firmware, and physical-reset
recovery. The v1.22 C/W selector is board-accepted as of 2026-08-19 for guarded
update, automatic and explicit warm entry, and explicit cold entry. The operator
cleared the uncaptured canary, prompt-C, installed-byte, and uninterrupted-J3
items as acceptance blockers. Its protected sector uses `$F000-$FD54` for the
3413-byte resident, leaves `$FD55-$FD5B` available, and retains the fixed worker
at `$FD5C-$FFAF`.

## Console commands

```text
I        install a dense payload-only S19 in selected flash sectors
L        load a recovery S19 into RAM and execute its S9 address
C        cold-enter compatible Bank-3 HIMON at $C000
W        warm-enter compatible Bank-3 HIMON at $C000
J0-J2    start an enrolled Bank 0, 1, or 2 guest
J3       hand off through the Bank-3 RESET vector
```

After a fatal `L` or `I` receive error, STR8-N keeps the command prompt closed
and discards records through a syntactically valid S9 or Ctrl-C. Ctrl-C during
`L` reports `BAD`, returns to `STR8-N>`, and does not execute S9. RAM records
already accepted are not rolled back.

At RESET, `0`, `1`, and `2` provide direct guest selection, `C` cold-enters
HIMON, `W` warm-enters HIMON, and `S` stays in STR8-N. A selector timeout also
warm-starts compatible HIMON and preserves RAM. `C` and `W` have the same
meanings at the `STR8-N>` prompt.

## Ready-made artifacts

- The exact 4096-byte Bank-3 top-sector BIN for an external programmer.
- A payload S19 for the resident and an evidence S19 for its relocated worker.
- A self-contained Bank Maintenance S19 loaded and started with `L`, including
  map, copy+directory, adopt, erase, and AP operations.
- A host- and board-qualified menu Bank Maintenance variant that adds `U` for the current
  guarded Bank-3 sector-F update. Its generated `.a` image carrier reproduces
  the WDC `.asm` S19 byte-for-byte under ASM-F2; update, copy, adopt, launch,
  and recovery edges are board-accepted as of 2026-08-18.
- A deterministic raw console ABI hardware probe covering blocking input,
  blocking output, non-consuming input readiness, initialization, and ABI
  discovery, loaded and started with `L`.
- A guarded v1.22 top-sector updater S19 loaded and started with `L`.
- A guarded onboard directory-pocket refresh S19 with backup, retry, and
  restore.
- A composed 32K ASM + HIMON + STR8-N image for Bank 0, 1, or 2.
- A manifest containing artifact paths, addresses, ABI versions, sizes, and
  hashes.
- A generated public assembly contract consumed by adjacent R-YORS builds.

Build the combined tool with `make bank-maint-menu`. Its terminal
card is deliberately one command per line:

```text
STR8-N 1.22 BANK MAINT + TOP
 M  MAP BANKS + DIRECTORY
 C  COPY BANK + ENROLL
 D  ADOPT BANK INTO DIRECTORY
 R  RECLAIM DIRECTORY
 E  ERASE BANK RANGE
 P  PUT AP $5000 -> B0:BF00
 U  UPDATE B3:F (BACKUP B1:F; RESET)
 ?  MENU
 Q/ENTER  RETURN TO STR8-N
BM>
```

`U` uses the same two exact confirmations, verified `B1:F` backup, live
directory/configuration preservation, candidate verification, retry/restore
recovery loop, and RESET finish as the standalone top updater.
The combined image occupies `$2000-$4FFF`, so its `P` path reads the AP
envelope from `$5000`; the standalone Bank Maintenance tool continues to use
`$4000`.

## Start here

- [Operator's Guide](docs/OPERATORS_GUIDE.md) — board operation, prompts,
  installs, recovery, and maintenance.
- [Worked Examples](docs/EXAMPLES.md) — complete terminal sessions for HIMON,
  ASM, full-bank, RAM, directory refresh/adoption, copy, and interrupted-install
  recovery.
- [Bank 0-2 S19 Quick Reference](docs/BANK_0_2_GUEST_S19.md) — guest layouts,
  accepted ranges, conversion, and validation.
- [Technical Guide](docs/TECHNICAL_GUIDE.md) — exact S19, memory, transaction,
  ABI, directory, build, and handoff contracts.
- [Expanded ABI Hardware Proof](docs/RESIDENT_ABI_HARDWARE_PROOF_2026-08-11.md)
  — exact tested artifacts and retained renewed-board transcript.
- [Directory Maintenance Hardware Proof](docs/DIRECTORY_MAINT_HARDWARE_PROOF_2026-08-11.md)
  — exact `D` adoption guards, commits, post-refactor `C` regression, and the
  v1.21 combined-menu copy-cancel-adopt-`J2` continuation.
- [R-YORS Ownership-Cutover Hardware Proof](docs/R_YORS_OWNERSHIP_CUTOVER_HARDWARE_PROOF_2026-08-13.md)
  — separated-build install, both RAM-loader paths, guarded Bank-3 copy,
  durable Bank-0 enrollment, and final cold boot.
- [Maps and Diagrams](docs/MAPS.md) — flash, RAM, boot, install, directory, and
  artifact flows.
- [R-YORS Integration Boundary](docs/R_YORS_INTEGRATION.md) — how an adjacent
  R-YORS checkout consumes STR8-N artifacts.
- [Implementation Record](docs/EMBEDDED_WORKER_REFACTOR_PLAN.md) — settled
  design decisions, retained hardware evidence, and open board-proof work.
- [v1.2 Implementation Plan](docs/STR8N_V1_2_IMPLEMENTATION_PLAN.md) — the
  coordinated high-RAM relocation, rebuild, versioned RAM tools, top-sector
  updater, and board migration sequence.

## Deliberate scope

STR8-N v1.21 is a recovery and installation layer, not a general-purpose flash
filesystem. The resident `I` installer does not rewrite its protected top
sector, export S-records, allocate backups, count flash wear, or expose a
general destructive worker API. Separate, explicitly confirmed RAM tools can
replace sector F either while preserving the live directory/configuration
bytes or while intentionally refreshing them to the erased state. An external
programmer remains the recovery fallback.

> [!WARNING]
> Flash operations can erase software or leave a bank incomplete. Keep the
> verified programmer BIN, confirm the selected bank and range, and do not
> interrupt power, RESET, or NMI while flash is being erased or programmed.

Detailed startup transcripts, accepted range tables, RAM ownership, build
commands, artifact paths, and qualification status are maintained in the
linked operator and technical documents rather than duplicated here.
