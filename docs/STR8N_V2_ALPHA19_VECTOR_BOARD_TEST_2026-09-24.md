# STR8-N v2 alpha19 vector autostart board test — 2026-09-24

Board 2205, COM3 at 115200 baud. Alpha19 adds `C 0|1 0-3 ADDR|V DELAY`;
`V` reads the selected bank's RESET vector after the hold interval. The full
`make v2-check` host suite passed before hardware installation.

Preflight captured the running alpha18 banner and reconstructed the live B3
E–F S19 from complete `D` readbacks. Its SHA-256 exactly matched the recorded
alpha18 image, `7C4F3DC72F20045200653BDD6757B439B7A57BD245A7F401A9D6244B37FF4323`.
All 4096 bytes of B2:F were `$FF` before the update.

The guarded RAM updater loaded with `L` and reported `Entry 2000`. `G 2000`
identified `BACKUP B2:F; TARGET B3:F`, copied the old top to B2:F, and reported
`BACKUP VERIFIED`. After exact `STR8-N 2.0A19` confirmation it reported
`STR8-N 2.0a19 VERIFIED; RESET` and booted alpha19 in B3. Complete B3:F
readback matched the built alpha19 top byte for byte; SHA-256
`4DF7DBD19B4891DFE5D381600E3EDBA185578AEA1969DF798C50CBB606814E91`.
Complete B2:F readback matched the prior B3:F byte for byte; SHA-256
`ADA5C6D2F5D24424C1440EDEEA95ABA52D86232D5D2092E7725D597F866C39A9`.

`C 1 1 V 0A` programmed and read back as `C 01 01 V 0A`. `J3` restarted
alpha19, displayed the configured vector mode and `S/Ctrl-C hold`, then
entered Bank 1's STR8-N 1.35 through its RESET vector at `$F000`. Bank 1's
`J3` reported `HSH_NF!` for the changed B3 image. Physical RESET selected B3;
the serial listener sent `S` during the hold window and alpha19 printed
`Canceled` at `B3>`. `C 0 1 V 0A` then disabled autostart and read back as
`C 00 01 V 0A`. A subsequent `J3` restarted alpha19 and stayed at `B3>`
without an autostart window.

The established all-`FF` cleanup S19 erased the temporary B2:F recovery copy;
complete B2:F readback was all `$FF`. Final B3:E readback was erased except
for the valid disabled config at `$EFF0-$EFFF` (sector SHA-256
`FE7011F30AA54366865BBF71A26ABAA535DAD58565EFA86E1BE927B822F9FFEF`).
Final complete B3:F readback still matched the alpha19 image exactly.
Bank 0 `$8000-$8003` retained `57 44 43 00`, and Bank 1's installed payload
remained accessible; its `$8000-$8003` bytes were `46 4E D6 00`.
The board was left at alpha19's B3 prompt with autostart disabled and B2:F
erased. This accepts the tested vector autostart path on 2205; it does not
complete the broader v2 hardware qualification matrix.

| Artifact | SHA-256 |
| --- | --- |
| Alpha19 E–F S19 | `8137D389683DC5310831618C4E14B64DEF185E33DD737CD95D2D72E11FB99053` |
| Alpha19 guarded updater S19 | `2B9AA6B5E2A4BAD9EA1C5AB8CB295FB9AD1B4FC2A8BED43C09EF5A32D16F2B9E` |
| B2:F all-FF cleanup S19 | `8672CE88FCA2642A18807D87F0F860971C63BE82485A2F8313F8AA4BA8BCC7CE` |
| COM3 JSONL exchange log | `19ECE2978EF76D3C99C20D5C112EBDB1408BC6553F080B6F04B70A40A3003F0D` |

Append-only serial evidence and extracted readbacks are in ignored
`BUILD/v2-alpha19/` files beginning `board-2205`.
