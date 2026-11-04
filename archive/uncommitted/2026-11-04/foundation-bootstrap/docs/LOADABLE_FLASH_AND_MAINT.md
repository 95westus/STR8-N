# Host-loaded FLASH and MAINT

Owner direction, 2026-11-02: provide FLASH as a loadable BIN like MAINT;
remove stored FLASH and MAINT utilities from 2512. Apply the same residency
policy when other boards are subsequently migrated. This does not request
immediate removal on those boards.

## RAM package

The [host RAM package](../../firmware/ram-tools/flash-g2/README.txt) contains:

| File | Load and entry | Purpose |
|---|---|---|
| FLASH.bin | $0200 | FLASH g2 with its dense S19 control library included |
| MAINT-RO.bin | $0200 | Read-only map/read/display/CRC/compare tool |

At F recovery, use L and send the selected raw BIN at SEND BIN. Recovery starts
the image after the transfer's idle interval. A compatible MON can instead load
the BIN at $0200 and run it with R. Q restarts F using the saved boot policy.
Both tools borrow application RAM; Q does not restore that RAM.

FLASH.bin occupies $0200-$4544 as a transfer image. Its core executes at $2000;
the included library is stored at $4300 and copied to $4000. It also uses tool
state and the high-RAM sector buffer. It requires the frozen N-F 0.3.0 BASE1/PR05
F hash recorded in the package manifest. It does not fetch a stored FLASH or
BANK MAINT image, a MON return bridge, or the dense-library fragments formerly
stored in MAINT padding. Q uses the public F RAM-reset entry at $7E64.

MAINT-RO is not the full BANK MAINT editor. FLASH supplies flash editing and
guarded configuration functions; the host keeps historical images and source
for restoration or further development.

Reproduce the package with:

```text
python -B release/str8nf-v0.2.0/tools/build_base1.py --out BUILD/loadable-maint-PR05-r1 --only map
python -B tools/build_loadable_flash.py --out BUILD/loadable-flash-fresh
```

The first command builds only MAP/MAINT against frozen PR05; omit it if that
verified build directory already exists. It does not rebuild F.

The builder reuses hash-pinned qualified core/library inputs, changes the
library's source-address table to RAM, and redirects Q to F reset. It does not
modify frozen release sources or rebuild F. The 2512 RAM trial verified help,
VERSION, flash read/display, S19 range rejection and cancellation, Q/default
boot behavior, unchanged flash banks, and RAM/ZP/provider-cache restoration.

## 2512 retirement layout

The completed retirement removed the old B0 FLASH example as well as the native
FLASH and BANK MAINT images. It preserves the shared MON services that happen
to occupy their padding:

| Allocation | Verified result |
|---|---|
| B0:8000-8FFF | Erased; old standalone FLASH example removed |
| B1:8000-9FFF | Erased; BANK MAINT header and body removed |
| B1:A000-AFFF | MAINT remainder/dense fragments removed; sealed MON transfer gate and record worker retained |
| B2:E000-EFFF | Erased; native FLASH header/body removed |
| B2:F000-FFFF | FLASH remainder/seal removed; STATUS $FA50-$FFF9 retained |
| B3:E000-EFFF | Executable services retained; APPS/map text describes RAM BINs and shared transfer allocation |

This reclaims **four complete 4 KB sectors, 16 KB total**. The two partially
occupied sectors are not advertised as wholly free. The retained transfer code
supports MON STORE/RESTORE/S19, rather than an installed FLASH/MAINT utility.

All eight PROGRAM directory slots were inspected on 2512; no FLASH or MAINT
records were present. Existing CLK, CLOCK and NFCOPY records remain. The plan
does not write SPI SRAM or WORKSPACE. Boot defaults, entries and enabled masks
remain unchanged; the former B0:$8000 FLASH entry no longer contains an image
after retirement. Reassign it before choosing that entry for boot.

The run used seven component erases, including the service text
update, and one accounted journal-sector rotation. C/D retain the current
settings and physical-sector wear history through the normal durable reservation
mechanism. Older journal rows displaced by rotation are archived on the host.
F, MON A/B, CLOCK, RTC/history, ASM/DBG and unrelated storage remain intact.

Final 2512 verification passed on November 2, 2026: all four flash banks match
the planned images, journal sequence advanced from 1187 to 1195 with eight
accounted erases, shared STORE/S19 and STATUS remain usable, and both host BINs
work after retirement. PROGRAM directory bytes are unchanged. Owner RAM, ZP
and provider cache were restored and COM4 released at REC>. A corrected M2
host check completed without repeating any erase.

The final private receipt is
`output/qualification/2512-utility-retirement-verified-20261102-r1/report.json`;
the original write receipt and full before/after images are retained alongside
the referenced plan. The current 2512 marker records the verified layout.
Other-board removals require their own fresh inventory and dependency checks.

The subsequent B0:E/F and B1:E/F legacy cleanup reclaimed another 16 KB while
preserving the current ASM and DBG. The [current 2512 map](2512_FLASH_MAP.md)
records 36 KB of fully erased flash in total.
