# STR8-N 2.0a24 - W65C816SXB manual migration checklist

One copy per board. Mark pass, fail, or NA. Stop at a failed write gate.

## A. Board and package record

Date / operator: ____________________  Board ID / revision: __________________
CPU and flash markings: _________________________________________________
COM port / host: ____________________  EDU attached: [ ] yes [ ] no
ZIP filename / SHA-256: _________________________________________________
Full-chip backup path / SHA-256: _________________________________________
Measured board tag / physical model: _____________________________________

[ ] Physical W65C816SXB model confirmed; WDC tag suffix not treated as CPU ID.
[ ] Flash device and full-chip 128 KiB backup verified before T48 writing.
[ ] B0, B1, B2, B3 ownership inventoried; occupied B1/B2 preserved.

<!-- PAGE BREAK -->

## B. WDCMONv2 RAM migration (stock board only)

Script: `MIGRATE-STR8N-V2-A24.ps1`  Port: __________  Gate: __________

[ ] Installer and F BIN package hashes accepted by script.
[ ] Physical RESET within 60-second gate; `SXB?` info received.
[ ] Physical W65C816SXB board confirmed before RAM load.
[ ] RAM upload and byte-exact readback passed.
[ ] Flash ID `BF/B5`; B0 erased or exact stock B3 copy.
[ ] Stock B3 copied to B0; full verify passed before B3:F change.
[ ] Ctrl+U sent the 4096-byte F BIN only at its request.
[ ] B3:F write and readback verification completed.
[ ] `MIGRATION VERIFIED; PRESS PHYSICAL RESET` received.
Transcript / event log paths: ____________________________________________
Gate B result / time: ____________________________________________________

## C. T48 page programming (only if chosen)

F file: `str8n-v2-alpha24-f000-ffff.bin` -> chip `$1F000-$1FFFF`.
E file: `str8n-v2-alpha24-e000-efff.bin` -> chip `$1E000-$1EFFF`.

[ ] Each raw page is 4096 bytes; F SHA-256 matches package manifest.
[ ] Board-specific 128 KiB working image made from full-chip backup.
[ ] Existing E margins `$E000-$E7FF`, `$EF00-$EFFF` retained if required.
[ ] T48 device and offset mode confirmed; chip readback matches working image.
T48 device / source backup / programmed hash: ____________________________

<!-- PAGE BREAK -->

## D. Boot and ABI

[ ] Physical RESET / cold power cycle reaches `STR8-N 2.0a24 B3 65C816`.
[ ] Banner reports `65C02 | 816E | 816N-VEC` and `B3>` prompt.
[ ] Board/capability query agrees with W65C816SXB and FT245 mode.
[ ] B3:F readback matches F BIN; B3:E code slice matches manifest.
[ ] Native and emulation BRK/NMI probes pass with physical NMI where needed.
[ ] B0 stock image and B2 W65C02SXB guest remain reachable.
[ ] B1 bounded S/R record passes save, table, restore, and readback.
Results / capture paths: _________________________________________________

## E. Static application carriers and disposition

[ ] Bank maintenance `.s19` loads with `L`; `G 2000` map works.
[ ] Bank maintenance `.a` ASM-F2 carrier ingests byte-exactly, if available.
[ ] Top updater `.s19`/`.a` identity checked; B2:F empty gate respected.
[ ] EDU absent marked NA, or EDU observations recorded for next alpha.
Known failures / deviations: _____________________________________________
Next action / owner: _____________________________________________________
Operator signature / date: _______________________________________________
