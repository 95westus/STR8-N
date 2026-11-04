# 2512 verified flash map — November 2, 2026

After FLASH/MAINT retirement and the subsequent owner-selected legacy cleanup,
**nine complete sectors are erased: 36 KB total**. Each cell is one 4 KB sector;
8 means $8000-$8FFF, 9 means $9000-$9FFF, and so on.

| Bank | 8 | 9 | A | B | C | D | E | F |
|---|---|---|---|---|---|---|---|---|
| B0 | Free | Free | Current ASM | Current ASM | Current DBG | Current DBG/source provider | Free | Free |
| B1 | Free | Free | Shared transfers | SRAM/WORK | SRAM/WORK | SRAM/WORK | Free | Free |
| B2 | WB2 | WB2 + PROGRAM | PROGRAM + STATUS | CLOCK | CLOCK | CLOCK | Free | STATUS |
| B3 | RTC/services/native loader | History/settings/return code | MON A | MON B | Journal C | Journal D | Command/app services | F recovery |

Fully erased allocations are B0:8000-9FFF, B0:E000-FFFF,
B1:8000-9FFF, B1:E000-FFFF and B2:E000-EFFF.
Blank padding in shared sectors and journal append space are not additional
independently reclaimable sectors. B1:A retains the MON transfer gate/record
worker; B2:F retains STATUS at FA50-FFF9.

The latest cleanup erased exactly B0:E/F and B1:E/F, removing the zero-filled
sector, retained WDC-tagged top bytes and older ASM image. All four sectors
passed independent erased-byte readback. Complete bank comparisons verified
the current ASM at B0:A/B and DBG/source-provider allocation at B0:C/D unchanged,
along with all other nontarget component bytes. No SPI storage was changed.

Four durable erase reservations advanced journal sequence 1195 to 1199; no
journal-sector erase was needed. Boot settings and all prior journal rows were
preserved. Owner RAM, ZP and provider cache were restored, and COM4 released at
REC>. Before/after images are archived privately. The final receipt is
`output/qualification/2512-legacy-reclaimed-20261102-r1/report.json`.

F is the permanent 4 KB recovery foundation. C/D provide the current persistent
boot/wear setup. Other components are optional at the system-design level, but
their current loaders and service dependencies must be addressed before further
reclamation. Both MON copies are not required simultaneously. FLASH and MAINT
are now host-loaded RAM tools; see the [residency policy](LOADABLE_FLASH_AND_MAINT.md).
