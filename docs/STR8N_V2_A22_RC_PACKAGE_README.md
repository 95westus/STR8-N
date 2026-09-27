# STR8-N 2.0a22 release candidate

This package contains the dot-enabled a22 Bank 3 F monitor, its matched
E-sector S/R/T extension, a new v2 RAM bank maintenance utility, guarded
top-write updater, and stock WDCMONv2 migration installer. The a22 E/F pair
passed a scoped W65C02SXB/EDU COM3 regression. W65C816 hardware and ACIA
receive remain unqualified. This is a candidate, not a general release.
Release-candidate testing is scheduled for 2026-09-27; those results are not
part of this package's qualification claim.

## Start here

Read `DOC/STR8N_V2_A22_QUICKSTART.md`, then
`DOC/STR8N_V2_A22_OPERATORS_GUIDE.md`. The technical manual
describes the memory map and ABI. `MANIFEST.json` has SHA-256 for each file.
The package contains no stock WDCMONv2 firmware or owner bank archives.

## Firmware and update paths

| File | Use |
| --- | --- |
| `FIRMWARE/str8n-v2-alpha22-f000-ffff.bin` | Exact 4096-byte Bank 3 F top for the stock migration RAM installer or external programmer. |
| `FIRMWARE/str8n-v2-alpha22-e000-efff.bin` / `.s19` | E sector image; the dense image has erased neighbors and configuration and must **not** overwrite a live E sector directly. |
| `FIRMWARE/str8n-v2-alpha22-e000-ffff.bin` / `.s19` | Dense E/F reference image, not a preservation-aware installer. |
| `FIRMWARE/str8n-v2-alpha22-b3-top-update-2000.s19` | Guarded a21 source-built Bank 3 F to a22 top updater. Requires its exact old F identity and a matching a22 E extension installed first. |
| `TOOLS/str8n-v2-bank-maint-2000.s19` | New v2 RAM bank map, copy, and erase utility. Load with `L`, then `G 2000`. |
| `FIRMWARE/str8n-v2-alpha22-wdcmonv2-install-2000.s19` | Stock WDCMONv2 RAM installer. Copies and verifies original B3 into erased B0 before writing a22 F. |

### Stock WDCMONv2 board

Run `START-STR8N-V2-A22.ps1 -Port COMx` on Windows. The launcher verifies the
exact F BIN, loads the RAM installer, and presents its terminal. The installer
checks the board and Bank 0 policy, copies and verifies the complete original
Bank 3 to Bank 0, receives the packaged F BIN on Ctrl+U, and requires
`INSTALL STR8-N 2.0A22`. After verification, press physical RESET.

This stock path installs **F only**. `S`, `R`, and `T` report `SR unavailable`
until the matched E extension is separately installed. A board-specific E
sector must preserve `$E000-$E7FF` and `$EF00-$EFFF`, including configuration.
The source-repository tool `tools/prepare_v2_a22_sr_upgrade.py` accepts an
exact supported a21 readback for the tested a21-to-a22 path; it does not accept
an arbitrary stock E sector or install flash. Do not feed the dense E image
to a live configuration sector. A stock-to-full-E/F installation therefore
needs a separately qualified preservation-aware E writer or external
programmer with a verified full E readback.

### Existing source-built alpha21 board

Prepare the E image from an exact B3 E/F readback with the repository's
`prepare_v2_a22_sr_upgrade.py`. Install and verify the preserved E S19 using
the alpha21 monitor's `I E000 EFFF` path, then load the packaged guarded
B3:F top updater. It backs up old B3:F to B2:F and confirms before writing.
The E and F images are a matched build; the reported SHA-256 identities are
in `DOC/STR8N_V2_A22_SR_CANDIDATE.md`. Read the installation report before applying this
sequence to another board.

## V2 bank maintenance

From a running a22 Bank 3 monitor, load `TOOLS/str8n-v2-bank-maint-2000.s19`
with `L`, then enter `G 2000`. The utility requires Bank 3 residency and uses
the installed a22 RAM flash worker. At its prompt:

* `M` maps B0-B3 sectors 8-F as `E` (erased) or `U` (used).
* `C` followed by a source digit `0`-`3` and destination digit `0`-`2`
  copies all eight sectors. It refuses the same bank and any used destination
  sector before writing; a final `Y` confirms. An interrupted copy can leave
  a partial destination.
* `E` followed by a bank digit `0`-`2` and an uppercase sector `8`-`F`
  erases that sector after `Y`. Bank 3 is never a write target.
* `Q` returns to the monitor.

The utility is host-model tested for copy, occupied destination refusal,
erase, and Bank 3 protection. It has not had a physical board write test.
Keep stable power during active writes and verify the destination afterward.
