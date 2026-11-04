# Installation boundaries

## Preserve the board first

Inventory the CPU, bank layout, entry addresses and resident firmware. Save complete original bank images, settings, erase history and any attached SRAM/provider data. Verify two independent reads agree before a destructive operation. Original WDC firmware and owner captures are not distributed by this repository.

B0 may be the owner's WDC backup. Preserve that B0 unless the owner explicitly assigns it as an installation target. Opaque installation and boot configuration are different operations: selecting an entry must not implicitly copy sectors or replace a backup.

## The F-only image

`firmware/payload/STR8N-F-BOOT-4096.bin` is **exactly 4096 bytes** for **B3:$F000â€“$FFFF only**. Reset vector is $F004. For a physical flash programmer, the bank/sector offset depends on its selected device and wiring; calculate and verify the actual address mapping before programming. Do not write this file as a complete 32 KiB bank or 128 KiB device image. Verify the programmed 4096 bytes byte-for-byte, reset into F and confirm `REC>`.

A factory WDC board needs an audited RAM migrator to perform that F-only write while keeping original banks unchanged. That board-specific migrator is not included in this toolkit release. Its eventual public workflow must back up WDC, choose the backup bank, preserve/import wear evidence, write only F, verify and stop at `REC>`. A blanket full-flash image would violate that workflow.

For the standard linear B0/B1/B2/B3 ordering of a 128 KiB flash device, B3:F
occupies device offsets $1F000-$1FFFF. Confirm the actual programmer mapping.
Use a preserving sector operation; whole-chip erase is not a preserving update.
Keep a full original chip read and the correct external recovery path.

## Optional compact monitors

BASE MON A is exactly 4096 bytes for B3:$A000-$AFFF; BASE MON B is exactly
4096 bytes for B3:$B000-$BFFF. Their standard linear device offsets are
$1A000 and $1B000. F does not require them. They are component images,
not raw L RAM input, and OPAQUE refuses those protected destinations.
Install them only with an explicitly admitted component/programmer procedure
that preserves current journals, owner bytes and actual wear accounting.
The kit does not supply an automatic MON installer.

## C/D journals and wear counts

F-only recovery and DEMO do not require C/D. Saved bank/default choices and normal opaque erase accounting require compatible, valid C/D journals.

CONFIG `I` is a **blank-only primitive**: it refuses any nonblank byte in either journal sector and never erases them. It creates default S, all banks disabled and zero observed erase counters with unknown history marked. Those zeros mean no recorded erases in this journal, not a lifetime count or proof of unused flash. Factory programming also contributes unknown history.

Do not use this primitive to replace owner counts or invent a lifetime starting value. Existing C/D must be inspected and preserved or restored with a qualified owner-history process. The general factory provisioning policy and wear-history import tool remain release gates. The previously qualified board-specific history importer is not silently generalized by this preview.

## Optional sectors

| B3 sector | Role in this layout |
|---|---|
| 8, 9, E | Potential opaque/provider space; inventory before use |
| A, B | Optional matching monitor slots |
| C, D | Configuration and wear journals |
| F | Bootstrap and recovery |

B3 user booting is supported at a configured allowed entry when an appropriate image is present. It does not make all B3 sectors available. Journal relocation to D/E or SPI SRAM is a future layout change, not a configuration option in this build.

## Release boundary

The supported evidence and remaining 1.0 work are listed in
[release scope](RELEASE_STATUS.md). No board was flashed to prepare 0.2.0;
the existing b15 firmware bytes are retained. General factory migration and
owner-history import remain separate work.
