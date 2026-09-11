> **AI Assistance & Human Validation**
>
> This project is developed with AI assistance and is grounded in human ideas, methods, and engineering judgment. Unless explicitly stated otherwise, all code has been tested on physical hardware and approved by a human.

# STR8-N v1.32

The current v1.32 working candidate distinguishes hardware/unmarked reset entry
as `RST H` from cooperating software reset entry as `RST S`. Two linefeeds
separate that marker from the immediately printed `STR8-N` identity; the former
hidden six-second pre-banner quarantine is removed. The resident is 3,394 bytes
(`$F000-$FD41`), with 14 bytes free
before the unchanged 608-byte worker at `$FD50`; the layout guard now preserves
an 8-byte minimum. Public ABI versions, public raw-console and record-service
behavior, selector prefix, and prompt text are retained. The formerly reserved
`$7DE7-$7DE8` pair now holds the one-shot software-reset record. The
immediate-banner image passed guarded update and live recovery on COM4 on
2026-09-10; see the
[board report](docs/STR8N_V1_32_IMMEDIATE_BANNER_BOARD_TEST_2026-09-10.md).

See the [reset-source contract](docs/RESET_SOURCE_CONTRACT.md), the
[LED status implementation record](docs/LED_STATUS_PROPOSAL.md), and
the preceding [conservative pass and validation](docs/STR8N_CONSERVATIVE_RESIDENT_PASS.md).
The conservative v1.30 candidate passed guarded update/readback, cold-power
startup, boot-path and console ABI checks on COM4, 2026-09-05. The minimal LED candidate
passed its focused console-ownership, reset/handoff, shell-wait, flash-worker,
and post-mutation map checks on COM4, 2026-09-06. The host-presence follow-on
was installed and verified on the same board; `$43` was observed at the live
STR8-N prompt, and a RAM probe confirmed the same PWE# predicate changes from
`$43` to `$21` and back when Windows disables and re-enables the FTDI USB
device. The
[original v1.30 changes and board evidence](docs/STR8N_V1_30_RECLAIM.md)
apply to the earlier binary, not this follow-up.
The [v1.32 reset-source board report](docs/STR8N_V1_32_RESET_SOURCE_BOARD_TEST_2026-09-07.md)
records the guarded installation, `RST H`/`RST S` checks, physical-reset
capture, and cooperating HIMON cold/warm integration.
The current `$07`/`$0B` activity slice passed its guarded installation and
focused board run: `$07` remained latched after accepted input and `$0B`
remained latched after private output. See the
[I/O activity board report](docs/LED_IO_ACTIVITY_BOARD_TEST_2026-09-06.md).
HIMON and ASM remain separate LED owners.
Older hardware acceptance below retains its original version. The current
v1.32 factory migration and its RAM-worker `$F0` indication were accepted on
physical hardware on 2026-09-08.

STR8-N is the reset supervisor, recovery console, and guarded flash installer
for a W65C02SXB/EDU with four 32K flash banks. It lives in the protected Bank-3
top sector at CPU `$F000-$FFFF`; HIMON, ASM, and guest systems remain separate
payloads.

STR8-N is a standalone product. It does not depend on R-YORS, HIMON, ASM-F2,
OIL, or AP. It can supervise compatible R-YORS payloads or unrelated guest
systems without adopting either as part of its product boundary.

**The name:** STR8-N is pronounced *straighten*, reflecting its role in
restoring a machine to a known, bootable state. `8` identifies its 8-bit
setting, while `STR` reverses `RTS`, the 6502 return-from-subroutine mnemonic.
The letters also loosely evoke **S**oftware or **S**ystem **T**o **R**eset,
**R**estore, **R**ecover, or **R**eturn to **N**ormal.

## Why this project exists

Every microcontroller, FPGA, and single-board-computer project I have worked
with has eventually required another computer. The host builds the software,
programs the board, stores the files, opens the terminal, and often remains
involved whenever the system is used or changed.

I also kept finding 6502 systems in which a supporting microcontroller, FPGA,
or host computer did more of the work than I wanted. Those are useful and
successful designs, but they are pursuing a different balance.

STR8-N/65 is my attempt to let the W65C02 board become the center of its own
system.

The host is not being rejected. It remains the practical place to build a
release, transfer files, preserve backups, and recover damaged flash. The goal
is simply to make that interaction as small and well-defined as possible.

After the initial setup, the W65C02 should increasingly know what it contains
and what it can do. It should take RESET itself, choose what to start, keep
track of installed systems, load its own tools, and provide understandable
ways to install software or recover from mistakes.

This is why the project is becoming more than a boot menu. STR8-N, HIMON, ASM,
applications, banked storage, installation, and recovery are being brought
together as parts of one understandable computer rather than remaining
separate experiments that happen to use the same board.

The aim is not necessarily to eliminate the host. It is to keep the host from
being the permanent operator of the machine.

This may be ambitious, and parts of it may prove impractical. The boundary
between useful independence and needless reinvention will have to be tested
honestly.

But the vision is clear: turn a W65C02 SBC from a target attached to a
development computer into a persistent, understandable, self-directed computer
in its own right.

## Prior release baseline — 2026-08-29

STR8-N 1.29 promotes the STR8-iN/65 resident as the production image,
including the EDU quiet-start initialization that holds the buzzer inactive
and clears the LEDs before normal console initialization. The factory loader
copies and exactly proves stock Bank 3 in opaque Bank 0, receives the canonical
4096-byte `STR8-N-v1-29.bin`, installs it at B3:`$F000-$FFFF`, and leaves the
Bank-3 directory empty. The separate production Bank Maintenance image owns
the explicit D0 `FF WDCV2` adoption after the first verified boot.

The complete v1.29 factory migration is accepted on a physical W65C02SXB/EDU.
It exercised erased-B0 `COPY B3 TO B0`, installed the external canonical top,
committed `D0 FF WDCV2 FFFF FCFFFFFF`, launched retained WDCMONv2 through shell
`J0` and reset selector `0`, and returned through physical RESET after both
launches. The operator separately confirmed that the EDU buzzer became silent
as soon as the RAM adapter started.

## Historical hardware validation baseline — 2026-08-28

The v1.28 factory WDCMONv2 migration is accepted on a physical W65C02SXB/EDU.
It copied and exactly verified all of stock B3 in B0, installed STR8-N 1.28 in
B3:F, published retained WDCMONv2 as COMPLETE D0 `WDCM2`, launched it through
`J0`, and captured physical RESET returning to STR8-N 1.28. The retained EDU
application reached its full menu with OLED, RTC, SPI SRAM, ADC, and CardKB all
`OK`; the operator visually verified the CS0-CS3 chase. B1/B2 remained
untouched, and no HIMON, ASM-F2, or R-YORS payload was installed by the
migration.

The earlier v1.22 Bank-2 recovery/guest proof remains below as historical
evidence of the general multibank handoff path.
>
> <details>
> <summary>Earlier 2026-08-21 v1.22 board transcript</summary>
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
>
> The STR8-N, HIMON, and ASM-F2 implementations are independently authored.
> They use WDC names, documented interfaces, memory maps, and protocol values
> only for compatibility. They do not include or redistribute the privately
> supplied WDCMONv2 source or firmware. The source-comparison record and the
> stricter migration-tool boundary are documented in
> [WDCMONv2 Migration Provenance](docs/WDCMONV2_MIGRATION_PROVENANCE.md).

## Feature card

| Capability | What STR8-N v1.32 can do | Safety boundary |
| --- | --- | --- |
| Reset supervision | Take physical RESET in Bank 3, run the pre-I/O settling interval, print a blank line and `RST H`; cooperating software restart paths print `RST S` | The one-shot `RS` RAM record is commit-last and consumed on entry; `H` also covers unmarked legacy software entry because the CPU has no reset-cause latch |
| Multi-bank boot | Start enrolled systems in Banks 0-2 with `J0`-`J2`, or hand off through the Bank-3 RESET vector with `J3` | Banks 0-2 must have a COMPLETE directory journal and a valid RESET vector |
| HIMON entry | Enter compatible Bank-3 HIMON warm with `W`, preserving RAM, or explicitly cold with `C` | Refuses an incompatible or missing HIMON marker |
| Flash installation | Install dense S19 payloads with `I` into any legal contiguous 4K sector range | Bank 3 `$F000-$FFFF` is never writable through `I`; final sector and COMPLETE state commit last |
| Recovery loading | Load an S19 program into RAM with `L` and execute its S9 entry | RAM only, `$2000-$7AFF`; there is no load-without-run form |
| LED status | Show `$43` while STR8-N waits with FTDI configured, `$21` when that wait begins without a configured host, `$07` for private receive activity, `$0B` for private transmit activity, `$F0` throughout RAM-worker flash mutation, and `$00` at program handoff | Public console and record services never touch the LEDs; HIMON, ASM, and user programs own their display after handoff; STR8-N states board-proven 2026-09-06 |
| Record parser ABI | Validate one buffered or console S0/S1/S9 record through `SR/02` at `$F009` | Parser-only; callers own destination and execution policy, and the generated public contract exports the complete request/result card |
| Factory migration | Preserve stock WDCMONv2 from B3 into opaque B0, receive the canonical 4096-byte STR8-N 1.32 BIN, and install it in B3:F through the RAM loader | v1.32 accepted on `SXB2`, HW 3.00, WDCMON 2.00, `$BF/$B5` flash from erased B0 on COM4, 2026-09-08; the operator confirmed solid `$F0` during both mutation/verification intervals and clear at safe waits; B1/B2 remain untouched |
| Bank maintenance | Load the supplied RAM tool to map banks, copy and verify 32K banks, adopt existing payloads, reclaim stale D0-D2 rows after an erased-bank proof, compact an exhausted D3 journal, erase guarded ranges, and install the narrow AP carrier | Reclaim/compaction requires exact confirmation and rewrites/verifies the complete protected Bank-3 sector F while preserving all unrelated bytes |
| Protected top upgrade | Load the supplied v1.32 updater with `L`, back up Bank-3 sector F into Bank 1, program the embedded v1.32 sector, and verify all 4 KiB | Conservative candidate passed guarded update and exact readback on COM4, 2026-09-05; live directory retained; see the follow-up report for test scope |
| Directory refresh | Load the dedicated RAM refresh tool, verify a fresh Bank-1 sector-F backup, clear the Bank-3 directory, and install the current configuration pocket | The canonical v1.32 image publishes B1:E WORK at `$FFF0=$1E` and B1:F backup at `$FFF1=$1F` |
| Image preparation | Convert aligned guest BINs, normalize payload S19 files, and compose a complete R-YORS Bank-0/1/2 image | Generated install files contain payload only, never the `$0200` worker image |
| Reproducible release | Build the resident, worker evidence, maintenance image, programmer BIN, manifest, and host qualification matrices | Layout checks enforce fixed interfaces, the exact 4K image, and no overlap with the fixed worker |

Current R-YORS HIMON is a direct client of that record-parser ABI. Its bare
`L` uses `$F009` for every record, then applies HIMON's load-only RAM policy;
it has no private S19 parser. Retired HIMON `L G` and `L F` examples belong
only to historical image records. Persistent payload installation is owned by
STR8-N `I`.

The v1.32 host verification suite covers the relocated RAM ABI, artifact
layout, quiet-start build configuration, and byte-exact promotion of the
production STR8-iN/65 image. The guarded v1.32 top update, EDU quiet-start,
and complete factory migration are board-accepted. The complete v1.29 factory
path remains historical board evidence. Retained
v1.1/v1.2 board sessions also remain historical evidence; the
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

The 2026-08-28 WDC board run accepts the v1.28 cold-start sequence: its
calibrated pre-I/O delay, no reset-time `$7FEC` write, and silent timing pulses
survive software reset, physical RESET, and cold power-up. The promoted
resident occupies `$F000-$FD40`, leaving 27 bytes before the fixed worker.

The prior v1.29 resident occupies `$F000-$FD55` (3,414 bytes), leaving six
bytes before the fixed worker at `$FD5C`. The complete v1.29 factory migration
and EDU quiet-start path is board-accepted.

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

Run `make release-package` to build and verify the complete STR8-N v1.32-only
bundle at `BUILD/v1.32/str8n-v1.32-release.zip`. It gathers the canonical
resident, maintenance and recovery tools, public contract, manifest,
checksums, essential guides, and the separately verified WDCMONv2 migration
kit. It contains no WDCMONv2 firmware, owner bank archive, HIMON, ASM-F2, or
R-YORS payload.

- The exact 4096-byte Bank-3 top-sector BIN for an external programmer.
- A payload S19 for the resident and an evidence S19 for its relocated worker.
- A self-contained Bank Maintenance S19 loaded and started with `L`, including
  map, copy+directory, adopt, guarded rename/reclaim, erase, and AP operations.
- A host- and board-qualified menu Bank Maintenance variant that adds `U` for the current
  guarded Bank-3 sector-F update. Its generated `.a` image carrier reproduces
  the WDC `.asm` S19 byte-for-byte under ASM-F2; update, copy, adopt, launch,
  and recovery edges are board-accepted as of 2026-08-18. The new guarded `N`
  rename path is host-checked and still awaits its separate board transcript.
- A deterministic raw console ABI hardware probe covering blocking input,
  blocking output, non-consuming input readiness, initialization, and ABI
  discovery, loaded and started with `L`.
- A guarded v1.32 top-sector updater S19 loaded and started with `L`.
- A guarded onboard directory-pocket refresh S19 with backup, retry, and
  restore.
- A composed 32K ASM + HIMON + STR8-N image for Bank 0, 1, or 2.
- A read-only `$2000` bank inventory/archive S19, an explicit binary-WDCMONv2
  load/readback/execute bridge, and a host extractor that produce a checked
  local 32K BIN, S19, and receipt. This migration stage is board-accepted on
  the retained transcript.
- A two-confirmation factory-board RAM loader that accepts only an erased or
  already-identical B0, preserves and exactly verifies stock B3 there, receives
  the canonical 4096-byte STR8-N 1.32 BIN, installs it in B3:F, and leaves
  B1/B2 untouched. The kit exposes it as `STR8-iN65-LOADER.ps1`; it enumerates
  ports when `-Port` is omitted. D0 adoption is a separate, explicit production
  Bank Maintenance step after the first verified boot.
- An explicit `make wdcmonv2-package` publication kit containing the verified
  STR8-N artifacts, source, binary-monitor/terminal host bridge, procedures,
  license, manifest, and self-verifier. Its allowlist excludes WDCMONv2
  firmware, owner bank archives, and every R-YORS/HIMON/ASM-F2 payload.
- A manifest containing artifact paths, addresses, ABI versions, sizes, and
  hashes.
- A generated public assembly contract consumed by adjacent R-YORS builds.

Build the combined tool with `make bank-maint-menu`. Its terminal
card is deliberately one command per line:

```text
STR8-N 1.32 BANK MAINT + TOP
 M  MAP+DIR
 C  COPY+ENROLL
 D  ADOPT DIR
 N  RENAME DIR
 R  RECLAIM DIR
 E  ERASE BANK RANGE
 P  PUT AP $7000 -> BANK SECTOR
 U  UPDATE B3:F (BACKUP B1:F; RESET)
 ?  MENU
 Q/ENTER  RETURN TO STR8-N
BM>
```

`U` uses the same two exact confirmations, verified `B1:F` backup, live
directory preservation, candidate-configuration installation, verification, retry/restore
recovery loop, and RESET finish as the standalone top updater.
`N` accepts exactly five description characters and exact confirmation
`RENAME Dn XXXXX`. It preserves the selected record's type, seal, entry, and
journal, as well as every other directory row.
The combined image occupies `$2000-$4FFF`, and ASM-F2 owns `$5000-$6D6D`, so
its `P` path reads the AP envelope from `$7000`; the standalone Bank
Maintenance tool continues to use `$4000`. `P` accepts an AP v2 envelope of
`$0005-$00FF` bytes at a Bank 0-2
sector base, rejects configured WORK/BKUP roles, requires the complete package
range to be erased, and uses a target-specific confirmation such as
`PUT B28000`.

## Start here

- `QUICKSTART.txt` in the factory migration ZIP is the compact operator card;
  the loader's default presentation follows it, while `-Details` adds hashes,
  addresses, bank policy, and evidence paths without changing the transaction.
  Normal Windows onboarding needs only Windows PowerShell 5.1, the board's USB
  COM-port driver, an extracted writable folder, and exclusive access to that
  COM port; the release package lists an exact preflight. The kit also includes
  an experimental Python/pySerial Ubuntu loader with offline protocol tests,
  explicitly marked untested on hardware until a Linux board run is accepted.
  During migration, read the screen before entering commands or pressing
  control keys: `Ctrl+U` and `Ctrl+D` send different packaged files and should
  be pressed once, only when requested. After `J0` starts the preserved factory
  system, physical RESET is the intentional, designed return path to STR8-N;
  this is not a flaw.

- [Task List](TASKS.md) - release-staging gates and later Bank-1 example
  backlog.

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
- [Stock WDCMONv2 Migration](docs/WDCMONV2_MIGRATION.md) — one-command factory
  migration, retained Bank-0 WDCMONv2, ordinary-terminal handoff, and optional
  read-only map/dump/archive evidence.
- [HIMON And ASM-F2 After STR8-N](docs/HIMON_ASMF2_AFTER_STR8N.md) - optional
  separate component loads performed only after WDC migration is complete.
- [LED Status Proposal](docs/LED_STATUS_PROPOSAL.md) - explicit ownership,
  shared STR8-N/HIMON/ASM meanings, application freedom, and the minimal
  safety-first implementation slice.
- [LED Status Board Test](docs/LED_STATUS_BOARD_TEST_2026-09-06.md) - exact
  minimal-slice artifacts, physical observations, worker mutation proof, and
  final unchanged bank map.
- [WDCMONv2 Migration Board Test](docs/WDCMONV2_MIGRATION_BOARD_TEST.md) —
  exact artifacts, refusal tests, preservation/install sequence, readback
  checks, and evidence required for physical acceptance.
- [Implementation Record](docs/EMBEDDED_WORKER_REFACTOR_PLAN.md) — settled
  design decisions, retained hardware evidence, and open board-proof work.
- [v1.2 Implementation Plan](docs/STR8N_V1_2_IMPLEMENTATION_PLAN.md) — the
  coordinated high-RAM relocation, rebuild, versioned RAM tools, top-sector
  updater, and board migration sequence.

## Deliberate scope

STR8-N v1.32 is a recovery and installation layer, not a general-purpose flash
filesystem. Bank 3 publishes two packed sector roles: `$FFF0=$1E` assigns
B1:E as application WORK, and `$FFF1=$1F` protects B1:F as the raw B3:F
recovery backup. `$FFF2-$FFF9` remain erased for later configuration,
including a possible larger-directory locator. The resident
`I` installer does not rewrite its protected top
sector, export S-records, allocate backups, count flash wear, or expose a
general destructive worker API. Separate, explicitly confirmed RAM tools can
replace sector F either while preserving the live directory or while
intentionally refreshing it. Both install the candidate configuration. An external
programmer remains the recovery fallback.

> [!WARNING]
> Flash operations can erase software or leave a bank incomplete. Keep the
> verified programmer BIN, confirm the selected bank and range, and do not
> interrupt power, RESET, or NMI while flash is being erased or programmed.

Detailed startup transcripts, accepted range tables, RAM ownership, build
commands, artifact paths, and qualification status are maintained in the
linked operator and technical documents rather than duplicated here.
