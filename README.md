> **AI Assistance & Human Validation**
>
> This project is developed with AI assistance and is grounded in human ideas,
> methods, and engineering judgment. Unless explicitly stated otherwise, all
> code has been tested on physical hardware and approved by a human.

# STR8-N v1.33

STR8-N is a reset supervisor, recovery console, and guarded flash installer for
the W65C02SXB/EDU with four 32K flash banks. It occupies the protected Bank 3
top sector at CPU `$F000-$FFFF` and provides a small, dependable layer beneath
the systems installed on the board.

STR8-N is a standalone product. R-YORS, HIMON, ASM-F2, OIL, AP, and guest
systems are separate payloads; STR8-N can start compatible payloads without
making them part of STR8-N.

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

The current v1.33 resident is 3,394 bytes at `$F000-$FD41`, followed by 14 free
bytes and the fixed 608-byte worker at `$FD50`. Its guarded top update, exact
readback, reset-source behavior, and HIMON warm recovery passed on physical
hardware on 2026-09-10. The v1.33 factory-migration artifacts are host-tested;
the complete factory path was last repeated on hardware with v1.32.

Detailed build commands, host checks, test matrices, artifact paths, hashes,
and historical evidence are maintained outside this overview:

- [v1.33 board report](docs/STR8N_V1_33_TOP_UPDATE_BOARD_TEST_2026-09-10.md)
- [Reset-source contract](docs/RESET_SOURCE_CONTRACT.md)
- [Technical Guide: build, artifacts, and qualification](docs/TECHNICAL_GUIDE.md#build-artifacts-and-qualification)
- [WDCMONv2 migration board test](docs/WDCMONV2_MIGRATION_BOARD_TEST.md)

Run `make release-package` to build and verify the complete STR8-N-only release
bundle at `BUILD/v1.33/str8n-v1.33-release.zip`.

> [!NOTE]
> STR8-N and R-YORS are independent projects and are not affiliated with,
> sponsored by, endorsed by, or supported by The Western Design Center, Inc.
> WDC, W65C02S, W65C02SXB, and W65C02SXB/EDU identify the compatibility target;
> associated names and marks belong to their respective owners. Building the
> supplied artifacts requires external WDC assembler/linker tools and Python.
> Toolchain installation, licensing, and support are outside this project's
> scope. Flash programming is performed at the user's own risk and remains
> subject to the repository license and warranty disclaimer.
