# Manual alpha24 migration - W65C816SXB

Use this guide with the extracted alpha24 kit and the [maps](MAPS.md). Record
each gate on [CHECKLIST-816.pdf](CHECKLIST-816.pdf). This alpha is the completed
core board test; EDU hardware was absent for board 2609 and belongs to the
next alpha. This guide does not qualify the EDU peripheral firmware.

## 1. Inventory and preserve

Identify the physical board as W65C816SXB, its flash device as compatible
`BF/B5` SST39SF010A, and the actual COM port. The WDCMONv2 board tag may be
`SXB6` or another `SXB?` value; the suffix is not a processor-mode bit. Do
not choose the CPU from the tag alone. Preserve a full-chip 128 KiB image on
an external programmer before a manual T48 rewrite. Record its hash. Board
2609 already has B0 stock 816, B2 stock 02 guest, and a B1 S/R record, so
neither B1 nor B2 is scratch space.

Read `MANIFEST.json` and verify the ZIP against its adjacent `.sha256` file.
The two page BINs are each exactly 4096 bytes; F's SHA-256 is
`43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a`.

## 2. Stock WDCMONv2 to alpha24 F, using one host script

In Windows PowerShell, with the stock WDCMONv2 firmware running, execute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\MIGRATE-STR8N-V2-A24.ps1
```

The script lists COM ports and prompts for one. `-Port COM8` selects one
directly; use the current port, not a saved example. The script validates its
bundled RAM installer and F BIN, opens a 60-second physical-reset gate, probes
WDCMONv2's binary board-info command, prints the tag, and requires the
physical model confirmation. It uploads and reads back the RAM installer.
The installer accepts B0 only if erased or already an exact copy of stock B3,
then copies/verifies the full B3 before it writes B3:F. Follow the on-screen
uppercase prompts exactly. Press Ctrl+U once only when it says `SEND STR8-N
TOP BIN`. Keep power stable during flash erase/program. After `MIGRATION
VERIFIED; PRESS PHYSICAL RESET`, press physical RESET and confirm the
`STR8-N 2.0a24 B3 65C816` banner. Session raw and event logs are saved under
`LOCAL` beside the script. The script does not install E.

Skip this stock-board step whenever B3 already runs alpha24. The standalone
script is for a stock WDCMONv2 B3 image; its preflight checks the source and
preserved B0 before writing F.

## 3. E sector and T48 workflow

`FIRMWARE/str8n-v2-alpha24-f000-ffff.bin` maps to chip `$1F000-$1FFFF`.
`FIRMWARE/str8n-v2-alpha24-e000-efff.bin` maps to chip `$1E000-$1EFFF`.
These are raw page images, not full-chip images. Select the exact flash part
in the T48 software and check its addressing convention before writing. Read
and save the entire chip, then create a *board-specific* full-chip working
image by replacing only the intended page ranges. Verify the resulting chip
against that complete working image and retain the original backup.

The packaged E BIN is generic: `$E000-$E7FF` and `$EF00-$EFFF` are `$FF`.
Those margins can carry existing board data/configuration. For board 2609,
preserve its observed E margins and replace only `$E800-$EEFF` from the
packaged E BIN. Verify the combined E page before programming. The separately
qualified board-2609 E updater used its exact observed preimage; this public
kit does not contain a universal resident E installer. Do not use monitor
`I E000 EFFF` on resident B3. If E is already qualified, as on board 2609,
leave it unchanged.

## 4. Application carriers

`APPLICATIONS/str8n-v2-bank-maint-2000.s19` is the static monitor `L` load.
Run `G 2000` after its valid S9 record. The matching `.a` is for public
HIMON/ASM-F2: `ASM NEW`, send the complete ORG/DB file, require `END/SEAL`
with no errors, then enter `.` and `G 2000`. Its map command is read-only;
copy/erase require separate explicit confirmations. Optional S/R remains in
B3:E and uses the published ABI.

`APPLICATIONS/str8n-v2-alpha24-b3-top-update-2000.s19` and `.a` carry the
same alpha23-to-alpha24 B3:F updater. Its preflight checks the exact alpha23
F and **requires B2:F erased** for backup. Board 2609 has an occupied B2:F,
so this updater refuses it and must not be used as its normal migration path.
The WDCMONv2 migrator above preserves stock B3 in B0 and leaves B2 intact.

## 5. Qualification and recovery

Use the checklist for banner, capability ABI, readback, cold boot, BRK/NMI,
bounded S/R, and B2 inventory. Avoid EDU assertions when it is absent. If a
gate fails, stop before another write and retain the transcript and the
original full-chip backup. Do not use a generic full-bank image to repair
board 2609; it would replace its board-specific B3 contents.
