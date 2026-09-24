# STR8-N v2

**Board monitor and guarded loader for WDC SXB.**

[Read the v2 announcement](docs/STR8N_V2_ANNOUNCEMENT.md) and join its
[GitHub discussion](https://github.com/95westus/STR8-N/discussions).
Report reproducible defects in [GitHub Issues](https://github.com/95westus/STR8-N/issues).

V2 grew from STR8-N v1.3x by keeping the essential console, RAM/S19 loading, flash editing,
bank selection, and boot handoff, while removing the directory, enrollment,
journal, and HIMON-specific policy. You choose what each flash bank holds,
which image to load, and when to boot it. STR8-N checks addresses, asks for
confirmation before flash changes, and verifies writes; it does not choose a
board layout or manage guest applications for you.

HIMON, ASM-F2, AP, and other R-YORS software remain separate guest layers.
The [v2 command and memory guide](docs/STR8N_V2.md) describes the current
interfaces and limits. The v1.34 material farther down this README describes
the earlier release line.

> **AI Assistance & Human Validation**
>
> This project is developed with AI assistance and is grounded in human ideas,
> methods, and engineering judgment. Unless explicitly stated otherwise, all
> code has been tested on physical hardware and approved by a human.

Unresolved defects and hardware investigations are listed in the
[repo issue tracker](ISSUES.md).

The current W65C02SXB operating claim assumes a USB FT245 data host is
connected and enumerated at startup and supplies stable board power. Keep the
USB cable connected; do not reset or remove power during transfers or flash
writes. The ACIA backup-console path remains unqualified. See the
[v2 operating scope](docs/STR8N_V2.md#supported-host-connected-operating-scope).

**STR8-N 2.0a21 RC1 is ready as a binary/S19 release candidate with two
ASM-F2 `.a` utilities.** The
[package README](docs/STR8N_V2_RC1_PACKAGE_README.md) lists the images, the
standalone WDCMONv2-to-STR8-N RAM installer, and the STR8-N guarded top updater.
The [ASM-F2 application guide](docs/STR8N_V2_RC1_ASMF2_APPLICATIONS.md)
describes the public R-YORS carrier workflow and its compatibility limits.
The [W65C816SXB/EDU getting-started guide](docs/STR8N_V2_RC1_GETTING_STARTED_816.md)
is included in the RC1 ZIP.
The [printable 816 qualification checklist](docs/STR8N_V2_RC1_816_QUALIFICATION_CHECKLIST.md)
records SXB-alone and optional EDU results, evidence, and signatures.
The package includes no WDCMONv2 firmware, owner stock-bank image, or R-YORS guest
payload. The [RC decision](docs/STR8N_V2_RC1_2026-09-24.md) states the accepted
board evidence and remaining qualifications. The firmware candidate is v2-alpha21; see the
[alpha21 freeze record](docs/STR8N_V2_ALPHA21_FREEZE.md). It waits before
sampling USB host presence on reset. Alpha20 was installed and read back
exactly on board 2512, but its cold USB reconnect missed the banner; see the
[alpha20 board report](docs/STR8N_V2_ALPHA20_2512_INSTALL_2026-09-24.md).
The [alpha19 qualification matrix](docs/STR8N_V2_QUALIFICATION.md) records
earlier hardware evidence.
The [2512 board session](docs/STR8N_V2_ALPHA19_2512_BOARD_TEST_2026-09-24.md)
passed FTDI, RAM ABI, interrupts, flash and autostart checks; ACIA receive
remains unresolved.

On the `v2` branch, alpha19 adds `C 0|1 0-3 ADDR|V DELAY`: `V` follows the
selected bank's RESET vector when autostart runs, while an explicit address
remains fixed. Alpha19 passes the host checks and its vector autostart path was
accepted on board 2205; see the [alpha19 board test](docs/STR8N_V2_ALPHA19_VECTOR_BOARD_TEST_2026-09-24.md).
The board-tested alpha18 detects W65C02/W65C816, exports CPU and console
state through `BOARD_QUERY` at `$F02B`, and selects either the primary FT245 or
backup W65C51N console at initialization. Alpha18 provides an initialized RAM ABI
at `$7E60`, so applications can use console, discovery, formatting, HOLD, and
RESET services while any flash bank is visible. Its EDU LED contract toggles
valid S-record activity, shows flash page progress with all red LEDs asserted,
and clears at application handoff. Board 2205 retains WDCMONv2 in
Bank 0 and R-YORS/HIMON in Bank 1; see the
[alpha18 operation LED board test](docs/STR8N_V2_ALPHA18_OPERATION_LED_BOARD_TEST_2026-09-23.md).
The earlier physical FT245, W65C02 detection, and direct ACIA transmit checks
are in the [alpha13 board test](docs/STR8N_V2_ALPHA13_BOARD_TEST_2026-09-23.md);
ACIA receive on that board remains suspect.
The alpha21 build and host regression suites pass. It also emits RAM-only
cross-bank ABI and
W65C816 native BRK/NMI acceptance probe for the incoming board; that probe is
assembled and structurally checked but awaits native-mode hardware execution.
Use `make v2-check` for its build and host execution checks. The v1 firmware
sources and normal release targets remain unchanged; the description below
documents the v1 product, not the full planned v2 command set.

**V2 boot limitation:** A valid RESET vector does not prove that the payload
is intact or will run successfully. S-record checksums check individual
records; flash readback checks the programmed contents at verification time.
Neither establishes successful application startup. V2 does not validate the
whole payload at boot, track installation completion, or automatically roll
back a failed boot. After an interrupted or failed install, verify or reinstall
the intended image before booting; confirm its operation on the target board
before relying on autostart. See the [v2 validation limits](docs/STR8N_V2.md#validation-limits-and-operator-responsibility).

# STR8-N v1.34

STR8-N is a reset supervisor, recovery console, and guarded flash installer for
the W65C02SXB/EDU with four 32K flash banks. It occupies the protected Bank 3
top sector at CPU `$F000-$FFFF` and provides a small, dependable layer beneath
the systems installed on the board.

STR8-N is a standalone board management product. R-YORS, HIMON, ASM-F2, OIL,
AP, and 8-xxx guest systems are separate payloads; STR8-N can start compatible
payloads without making them part of STR8-N. Displays, LED patterns, sounds,
and other application behavior belong to those guests.

The name is pronounced *straighten*: its job is to return the machine to a
known, bootable state. `8` refers to the 8-bit platform, and `STR` reverses the
6502 `RTS` mnemonic.

## What it can do

- Take control at RESET and distinguish hardware or unmarked reset entry
  (`RST H`) from cooperating software reset entry (`RST S`).
- Select and start enrolled systems in flash Banks 0-2, or hand off through
  the Bank 3 RESET vector.
- Enter a compatible Bank 3 HIMON cold or warm; warm entry preserves RAM.
- Install dense, payload-only S19 images into guarded 4K flash-sector ranges.
- Load a recovery S19 into RAM and execute its S9 entry address.
- Expose stable console, discovery, and S-record parser services to cooperating
  software.
- Report its own wait, console activity, flash-write, and handoff states on the
  EDU LEDs.

See the [v1.34 EDU LED legend](docs/OPERATORS_GUIDE.md#edu-led-patterns-v134)
for the current patterns, ownership, and flash-operation indication.

The release also includes separate RAM tools for inspected bank maintenance,
copy and enrollment, directory maintenance, protected-top updates, factory
migration, and image preparation. These tools are not always-resident STR8-N
commands and require their own safeguards and confirmations.

## What it does not do

- It is not an operating system, monitor, assembler, application environment,
  or general-purpose flash filesystem.
- It does not include or require R-YORS, HIMON, ASM-F2, OIL, or AP.
- It does not write its own protected Bank 3 top sector through the resident
  `I` command; a guarded RAM updater or external programmer is required.
- It does not install sparse or disjoint S19 ranges in one `I` operation.
- It does not provide a load-without-run form of `L`, roll back RAM records
  accepted before a later load error, or export S-records.
- It does not allocate backups, count flash wear, or expose a general
  destructive flash-worker API.
- It does not eliminate the need for a host computer to build releases,
  transfer files, retain backups, or recover damaged flash.
- It does not include or redistribute WDCMONv2 source or firmware.

## Resident commands

| Command | Action |
| --- | --- |
| `I` | Install a dense payload-only S19 into a selected legal flash range |
| `L` | Load a recovery S19 into RAM and execute its S9 address |
| `C` | Cold-enter compatible Bank 3 HIMON at `$C000` |
| `W` | Warm-enter compatible Bank 3 HIMON at `$C000` |
| `J0`-`J2` | Start an enrolled Bank 0, 1, or 2 guest |
| `J3` | Hand off through the Bank 3 RESET vector |

At RESET, `0`, `1`, and `2` directly select a guest, `C` and `W` enter HIMON,
and `S` stays in STR8-N. A selector timeout attempts a compatible warm HIMON
start while preserving RAM.

## Safety boundaries

Banks 0-2 must have a COMPLETE directory record and a valid RESET vector before
STR8-N will start them. Flash installation commits the final sector and COMPLETE
state last. The resident installer never writes Bank 3 `$F000-$FFFF`.

Flash operations can erase software or leave a bank incomplete. Keep a verified
programmer image, confirm the selected bank and range, and do not interrupt
power, RESET, or NMI during erase or programming. An external programmer is the
final recovery path.

## Documentation

Start with the [release manual index](docs/RELEASE_MANUALS.md) for the guides
and software appropriate to each task.

- [Operator's Guide](docs/OPERATORS_GUIDE.md) — prompts, installation,
  recovery, maintenance, and normal board operation.
- [Worked Examples](docs/EXAMPLES.md) — complete terminal sessions.
- [Technical Guide](docs/TECHNICAL_GUIDE.md) — memory maps, S19 rules, ABI,
  directory, handoff, build, artifact, and host-test details.
- [Maps and Diagrams](docs/MAPS.md) — flash, RAM, boot, install, directory, and
  artifact flows.
- [Bank 0-2 S19 Quick Reference](docs/BANK_0_2_GUEST_S19.md) — guest layouts,
  accepted ranges, conversion, and validation.
- [Stock WDCMONv2 Migration](docs/WDCMONV2_MIGRATION.md) — factory migration,
  preservation, terminal handoff, and optional read-only archive evidence.
- [R-YORS Integration Boundary](docs/R_YORS_INTEGRATION.md) — how a separate
  R-YORS checkout consumes STR8-N artifacts.
- [Software Catalog](docs/SOFTWARE_CATALOG.md) — supplied images and tools.
- [Task List](TASKS.md) — release gates and remaining work.

## Release and validation status

The current v1.34 release has a 3,314-byte resident at `$F000-$FCF1`,
134 free bytes, and a 568-byte worker stored at `$FD78`. It saves 120 bytes
against the preceding v1.33 image. The
[v1.34 COM4 board session](docs/STR8N_V1_34_BOARD_TEST_2026-09-15.md) passed
guarded update/readback, physical/software reset, console/BRK, HIMON/ASM,
and J3. The [follow-up tests](docs/STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md)
also passed power-cycle startup, NMI/IRQ, and worker flash program/erase.
The [factory migration test](docs/STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md)
passed stock restore, erased-B0 preservation, v1.34 installation, D0 adoption,
both B0 launch paths, physical-reset return, and complete four-bank readback.
The full release matrix remains incomplete.
See the [size-change report](docs/STR8N_V1_34_SIZE_OPTIMIZATION.md)
for host validation, relocated interrupt targets, and the remaining board work.

Detailed build commands, host checks, test matrices, artifact paths, hashes,
and historical evidence are maintained outside this overview:

- [v1.33 board report](docs/STR8N_V1_33_TOP_UPDATE_BOARD_TEST_2026-09-10.md)
- [Reset-source contract](docs/RESET_SOURCE_CONTRACT.md)
- [Technical Guide: build, artifacts, and qualification](docs/TECHNICAL_GUIDE.md#build-artifacts-and-qualification)
- [WDCMONv2 migration board test](docs/WDCMONV2_MIGRATION_BOARD_TEST.md)

Run `make release-package` to build and verify the complete STR8-N-only release
bundle at `BUILD/v1.34/str8n-v1.34-release.zip`.

The standalone package contains the exact 4 KiB top-sector BIN, resident S19,
RAM maintenance/update tools, the Bank Maintenance `.a` image carrier, public
ABI include, operator guides, current board reports, and the WDC-to-STR8
migration kit. HIMON, ASM-F2, their application collections, and games are
distributed separately. The migration kit contains project-written tools;
WDCMON firmware and owner-local archives are excluded.

Both archives use explicit file allowlists and file hashes. The release
verifier also compares its resident S19 and embedded updater image with the
accepted canonical BIN, checks the Bank Maintenance `.a` against its S19,
and inspects the nested migration archive. CHECK-LINKS.ps1 verifies local
manual files and headings; unbundled historical references point to the
source repository at the recorded commit. Packaging refreshes its timestamp
and documentation without changing the accepted v1.34 firmware.

> [!NOTE]
> STR8-N and R-YORS are independent projects and are not affiliated with,
> sponsored by, endorsed by, or supported by The Western Design Center, Inc.
> WDC, W65C02S, W65C02SXB, and W65C02SXB/EDU identify the compatibility target;
> associated names and marks belong to their respective owners. Building the
> supplied artifacts requires external WDC assembler/linker tools and Python.
> Toolchain installation, licensing, and support are outside this project's
> scope. Flash programming is performed at the user's own risk and remains
> subject to the repository license and warranty disclaimer.
