# Unified RC3 flash areas and dependencies

This map covers the combined STR8-N kit for frozen Foundation 0.3.0 BASE1/PR05,
MON A/B, UTIL and DEV. The same firmware files serve 65C02 and 65C816 in
emulation mode. Use [the file-format guide](FILE_FORMATS.md) to choose the
loader for a RAM BIN, sector image or S-record.

A location includes both a bank and a CPU address. For example, B0:C000 is
part of DBG, B2:C000 is part of CLOCK, and B3:C000 is a protected journal
sector. Each sector is 4 KiB. An address such as B3:9C00 is inside a sector.

## Sector ownership

| Location | Owner | When this area is used |
| --- | --- | --- |
| B0:8000–9FFF | Owner application area | Optional two-sector OSI BASIC opaque image, entry B0:8000. Inventory and back up both sectors before using them. |
| B0:A000–BFFF | DEV ASM | Paired shared AP/02 sectors. Install and verify both before using `R ASM` or `APP ASM`. |
| B0:C000–DFFF | DEV DBG | Paired shared AP/02 sectors. Includes its SF/1 source provider at B0:D800–DFFF. Both sectors are required for the installed DBG tool. |
| B0:E000–FFFF | Owner application area | Available for compatible owner code or data after checking the actual contents and the loader's range. |
| B1:8000–9FFF | Owner application area | Optional Microchess AP/02 uses B1:8000. B1:9000 is a separate owner sector. |
| B1:A000–AFFF | Shared transfer | Flash-transfer gate and record handling for MON/UTIL workflows. Keep it with the shared profile. |
| B1:B000–DFFF | SRAM / WORK | Shared storage code and transfer extensions. Requires matching EDU/SPI hardware for SRAM operations. |
| B1:E000–FFFF | Owner application area | Available for owner code or data after checking the actual contents and the loader's range. |
| B2:8000–AFFF | MAINT workbench, PROGRAM, loaders, STATUS | Shared workbench bundle. Keep all three sectors together. STATUS also uses B2:F000. |
| B2:B000–DFFF | UTIL CLOCK | Three-sector native CLOCK image. Launch with `R CLOCK`; keep the three sectors together. |
| B2:E000–EFFF | Owner application area | Spare in the compact RC3 profile. Full FLASH is supplied as a recovery RAM tool. Check for older tools or owner data before allocating this sector. |
| B2:F000–FFFF | STATUS details | Reserved for MON status support. Preserve the whole sector even though the detail image starts at FA50. |
| B3:8000–8FFF | RTC / I²C and native support | Provider, gateway and helper code used by MON and CLOCK with the matching board hardware. |
| B3:9000–9BFF | RTC history and native return | Shared code. The kit supplies a 3,072-byte prefix. Prepare the whole 4 KiB sector by retaining the board's final 1,024 bytes. |
| B3:9C00–9FFF | Per-board RTC and settings metadata | Retain this range byte for byte during a component install. Settings/history updates use their own validated command paths. |
| B3:A000–AFFF | MON A | Foundation's A monitor slot. Keep a working alternate slot during an update. |
| B3:B000–BFFF | MON B | Foundation's B monitor slot. The four verified boards have B as their saved default. |
| B3:C000–DFFF | Per-board SNBT boot/wear journal | C and D are peer sectors. CONFIG and the qualified native writer append records; a full journal can rotate to its peer. Preserve both sectors, including the saved boot policy and wear counters. |
| B3:E000–EFFF | Shared dispatcher, maps and APPS | MON service entry and application admission. Install this RC3 sector before using the shared ASM, DBG or Microchess AP/02 headers. Keep it reserved for MON services. |
| B3:F000–FFFF | F 0.3.0 | Frozen Foundation, public RAM ABI and recovery. Verify the exact F hash before an RC3 update. Foundation provisioning belongs to the separate recovery/programmer workflow. |

The compact profile allocates 92 KiB including Foundation and C/D. Nine
4 KiB sectors were erased on the four verified boards before examples. On
another board, those owner areas can contain opaque apps, stored data or old
firmware. A sector marked available in this map still needs an ownership
check and a fresh preimage. The loader determines the permitted entry range.

## What each workflow needs

| Workflow | Required pieces |
| --- | --- |
| Foundation recovery or raw RAM load | Frozen F and its initialized console/RAM ABI. Use the matching RAM packet from `REC>`. |
| Save a boot choice or replace a component sector | Frozen F, a valid board-local C/D journal, and the matching CONFIG or native OPAQUE workflow. Journal reservations can change even when the target is in B0, B1 or B2. |
| Enter MON A or B | Frozen F and the valid selected monitor slot. Saved defaults also depend on the board's journal. Basic MON commands are in the slot. |
| MON maps, APPS and installed app launch | Running MON and matching B3:E. The RC3 dispatcher accepts the shared CPU tag `$00` and matching legacy tags. |
| Installed ASM or DBG | MON, B3:E, and the selected app's pair of B0 sectors. Standalone DEV RAM BINs have their own recovery-load route. |
| Workbench, PROGRAM, SRAM / WORK and flash transfer | MON, B3:E and B2:8–A. Use the matching B1 storage or transfer sectors for the selected operation. Hardware-backed SRAM requires the matching EDU/SPI device. |
| CLOCK and RTC history | MON, B3:E, the three B2 CLOCK sectors and the B3 RTC support at 8/9. Commands that save board metadata use the board-local records. |
| Standalone CONFIG, full MAINT, FLASH, MAP or READBACK | Matching RAM tool loaded through Foundation recovery. Commands that change persistent state also require the matching storage, journal or metadata contract. |
| PC MEMORY | Matching host CLI and RAM agent, verified Foundation and MON, and the correct board profile. Select storage regions that are fitted. |
| Opaque OSI BASIC | Foundation and the owner image. Use the opaque boot route with the verified executable entry at B0:8000. Saving an opaque default uses C/D. |
| Optional AP/02 Microchess | MON and the RC3 dispatcher. After verifying the optional B1:8000 image, use `APPS` and `R UCHESS`. |

The same sector letter has a different purpose in each bank. In particular,
**B3:C/D are journal data and B3:E is a MON service.** They are reserved in
this profile. The B0 C/D pair and B2 C/D pair are executable tool allocations.

## C/D and boot choices

- **Valid SNBT:** keep both sectors. The current record comes from the
  validated journal. Native writes can append or rotate the journal with
  wear accounting. If an update changes the monitor generation, confirm
  the saved binding before enabling unattended boot.
- **Completely blank C/D after F provisioning:** use the blank-journal path
  in the [Foundation manual](USER_MANUAL.md). Matching CONFIG can initialize
  blank C/D after inspection.
- **Occupied, foreign or inconsistent C/D:** archive both sectors and follow
  the applicable [C/D provisioning guide](LIVE_CD_PROVISIONING.md). The
  combined kit ships board-independent firmware payloads.

At `REC>`, `A` or `B` enters the corresponding monitor for the current session.
In CONFIG, `C B` saves the validated MON B choice. An opaque boot entry instead
uses `B bank entry` and `C bank` for its verified executable entry. In RC3,
B3:E000 is the MON dispatcher. Use `APPS` and `R name` or `APP name` for AP/02
images, and the raw RAM load path for standalone recovery tools.

## Update sequence for an existing BASE1 board

1. Verify the board identity and frozen F. Capture all four flash banks and
   preserve owner RAM and board storage before borrowing them. Review the
   board's live C/D journal and the original bytes of every proposed target.
2. Plan only the component differences. Exclude direct payload writes to
   B3:C, B3:D and B3:F. For B3:9, merge the kit's code prefix with the live
   metadata suffix. Use the native wear-accounted writer and its peer-rotation
   forecast. An existing journal stays board-local.
3. Install B3:E before shared AP/02 launchers. Update and verify both sectors
   of ASM or DBG before launching that app, and all three CLOCK sectors
   before launching CLOCK. Keep one known working MON slot available until
   the other slot and the shared services are verified.
4. Reread all four banks. Compare component bytes and the planned journal
   changes against the board's own preimages. Test MON and the installed tools,
   then restore and verify the owner RAM borrowed by the workflow.

An erased-sector template is available for an explicitly reviewed retirement
operation. A normal component update uses the active target list in
`NATIVE-COMPONENTS.json`. See [the MON and utilities manual](NATIVE_UTILITIES_MANUAL.md),
[Foundation recovery](RECOVERY_BASE1.md), [OPAQUE host](OPAQUE_HOST.md) and
[worked examples](EXAMPLES.md) for the individual commands.

