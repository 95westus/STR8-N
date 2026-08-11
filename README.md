# STR8-N v1.2

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

| Capability | What STR8-N v1.2 can do | Safety boundary |
| --- | --- | --- |
| Reset supervision | Take physical RESET in Bank 3, provide a visible terminal-attach interval, and enter STR8-N or compatible HIMON | Input received during the initial `WAIT...` interval is deliberately discarded |
| Multi-bank boot | Start enrolled systems in Banks 0-2 with `J0`-`J2`, or hand off through the Bank-3 RESET vector with `J3` | Banks 0-2 must have a COMPLETE directory journal and a valid RESET vector |
| Warm monitor entry | Enter compatible Bank-3 HIMON with `H`, preserving RAM | Refuses an incompatible or missing HIMON marker |
| Flash installation | Install dense S19 payloads with `I` into any legal contiguous 4K sector range | Bank 3 `$F000-$FFFF` is never writable through `I`; final sector and COMPLETE state commit last |
| Recovery loading | Load an S19 program into RAM with `L` and execute its S9 entry | RAM only, `$2000-$7AFF`; there is no load-without-run form |
| Bank maintenance | Load the supplied RAM tool to map banks, copy and verify 32K banks, adopt existing payloads into empty directory rows, erase guarded ranges, and install the narrow AP carrier | Directory adoption never overwrites a row or rewrites payload; Bank-3 sector F remains erase-protected |
| Protected top upgrade | Load the supplied v1.2 updater with `L`, back up Bank-3 sector F into Bank 1, program the embedded v1.2 sector, and verify all 4 KiB | Expanded resident ABI update and probe accepted onboard 2026-08-11; external recovery remains separate |
| Directory refresh | Load the dedicated RAM refresh tool, verify a fresh Bank-1 sector-F backup, and replace Bank-3 sector F with the current image's erased directory/configuration pocket | Backup, rewrite, RESET, empty-directory map, and subsequent B3-to-B2 copy+enrollment accepted onboard 2026-08-11 |
| Image preparation | Convert aligned guest BINs, normalize payload S19 files, and compose a complete R-YORS Bank-0/1/2 image | Generated install files contain payload only, never the `$0200` worker image |
| Reproducible release | Build the resident, worker evidence, maintenance image, programmer BIN, manifest, and host qualification matrices | Layout checks enforce fixed interfaces, the exact 4K image, and the resident reserve |

The v1.2 host verification suite covers the relocated RAM ABI and artifact
layout. Retained v1.1 board sessions remain historical evidence; the v1.2
hardware acceptance sequence is tracked in the
[v1.2 Implementation Plan](docs/STR8N_V1_2_IMPLEMENTATION_PLAN.md).

## Console commands

```text
I        install a dense payload-only S19 in selected flash sectors
L        load a recovery S19 into RAM and execute its S9 address
H        warm-enter compatible Bank-3 HIMON at $C000
J0-J2    start an enrolled Bank 0, 1, or 2 guest
J3       hand off through the Bank-3 RESET vector
```

Ctrl-C during `L` aborts the receive, reports `BAD`, returns to `STR8-N>`, and
does not execute S9. RAM records already accepted are not rolled back.

At RESET, `0`, `1`, and `2` provide direct guest selection, `H` selects HIMON,
and `S` stays in STR8-N. A selector timeout cold-starts compatible HIMON.

## Ready-made artifacts

- The exact 4096-byte Bank-3 top-sector BIN for an external programmer.
- A payload S19 for the resident and an evidence S19 for its relocated worker.
- A self-contained Bank Maintenance S19 loaded and started with `L`, including
  map, copy+directory, adopt, erase, and AP operations.
- A deterministic raw console ABI hardware probe covering blocking input,
  blocking output, non-consuming input readiness, initialization, and ABI
  discovery, loaded and started with `L`.
- A guarded v1.2 top-sector updater S19 loaded and started with `L`.
- A guarded onboard directory-pocket refresh S19 with backup, retry, and
  restore.
- A composed 32K ASM + HIMON + STR8-N image for Bank 0, 1, or 2.
- A manifest containing artifact paths, addresses, ABI versions, sizes, and
  hashes.

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
  — exact `D` adoption guards, commits, and post-refactor `C` regression.
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

STR8-N v1.2 is a recovery and installation layer, not a general-purpose flash
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
