# STR8-N 2.0a24 board-test package

This package contains the alpha24 FT245-only monitor and its project-authored
WDCMONv2 migration and bank-maintenance tools. It is a tested alpha package,
not a beta release. The 816 board 2609 migration, Bank 3 E/F readback, cold
boot, RAM ABI, native and emulation interrupt probes, and bounded S/R test
passed. The EDU daughterboard was absent; EDU presence and RTC work belong to
the next alpha. The W65C02SXB alpha24 board results have their separately
recorded scope.

## Contents and use

| Path | Use |
| --- | --- |
| `FIRMWARE/str8n-v2-alpha24-f000-ffff.bin` | Exact 4 KiB Bank 3 F image for the installer or T48 offset `$1F000`; SHA-256 `43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a`. |
| `FIRMWARE/str8n-v2-alpha24-e000-efff.bin` | Separate 4 KiB generic E page for T48 offset `$1E000`; merge board-specific E margins before using on an occupied board. |
| `FIRMWARE/str8n-v2-alpha24-wdcmonv2-install-2000.s19` | RAM installer for a stock WDCMONv2 board. It preserves original B3 in erased B0 before installing F. |
| `FIRMWARE/str8n-v2-alpha24-e000-ffff.bin` and `.s19` | Generic E/F image for a deliberate external-programmer or compatible new-bank workflow. Its E margins are `$FF`; board 2609 retained its pre-existing E margins instead. |
| `FIRMWARE/str8n-v2-alpha24-8000-ffff.bin` and `.s19` | Generic full 32 KiB bank image for an external-programmer or expressly selected full-bank workflow. It replaces the entire target bank. |
| `APPLICATIONS/str8n-v2-bank-maint-2000.s19` | Static RAM bank maintenance image, load with STR8-N `L` then `G 2000`. |
| `APPLICATIONS/str8n-v2-bank-maint-2000.a` | ASM-F2 ORG/DB carrier of the same 703 machine bytes. Live ASM-F2 ingestion was not tested on board 2609. |
| `APPLICATIONS/str8n-v2-alpha24-b3-top-update-2000.s19` and `.a` | Matching alpha23-to-alpha24 B3:F updater carriers. They require erased B2:F for backup and therefore refuse board 2609. |
| `PUBLIC/str8n-v2-public.inc` | Published ROM/RAM ABI addresses, modes, and capability bits. |
| `MIGRATE-STR8N-V2-A24.ps1` | Single Windows WDCMONv2 migration script; prompts for COM if `-Port` omitted. |
| `GUIDE-816.md`, `MAPS.md` | Manual 816 migration, T48 offsets, preservation map, and diagrams. |
| `STR8N_V2_2609_*` | Board 2609 stock restore and later F-only remigration records linked from the map. |
| `CHECKLIST-816.md`, `CHECKLIST-816.pdf` | Printable and fillable qualification record. |

`MANIFEST.json` records every packaged file's SHA-256 and the source commit.
The archive contains no WDCMONv2 firmware, stock-bank image, raw board capture,
HIMON, ASM-F2 firmware, or crypto-device access code.

## Stock-board migration

Keep the FT245 host connected and board power stable. Inspect and retain the
current board state before starting. On Windows, extract the ZIP and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\MIGRATE-STR8N-V2-A24.ps1
```

Select the actual COM port when prompted, or pass `-Port COM8` with the correct
number. The script accepts `SXB?` board tags, displays the
exact tag, and requires you to confirm the physical W65C02SXB or W65C816SXB
model before loading RAM. It does not infer CPU type from the tag suffix. The
installer requires a compatible `BF/B5` flash device and an erased B0 or an
exact existing stock-B3 copy there. Follow its prompts; Ctrl+U supplies the
packaged top BIN only when requested. Wait for verified completion before
pressing physical RESET. Do not reset or remove power during a flash write.

The F-sector installer does not install the optional E-sector S/R extension.
E installation on board 2609 required a guarded updater built for its exact
observed E preimage. The package has no general-purpose resident B3:E updater.
Do not issue ordinary monitor `I E000 EFFF` against resident B3; it is protected.

The `.a` carrier is for a separate public HIMON/ASM-F2 session. STR8-N `L`
accepts S19, not `.a`. Bank maintenance can map all sectors with `M`; copy and
erase require explicit choices and confirmation. The tested 816 board used only
its read-only map path. See the repository's
`docs/STR8N_V2_2609_INVENTORY_2026-09-30.md` for the exact board evidence.

Read `GUIDE-816.md` and `MAPS.md` before T48 use. Preserve a full-chip backup,
merge pages at their exact physical offsets, and verify the programmed chip.
The optional top updater's B2:F backup preflight protects board 2609's 02
guest; it is not its resident upgrade path.
