# STR8-N 1.34 sector-role installation — 2026-09-16

The ordinary updater installed no flash WORK (`$FFF0=$FF`) and protected
backup B2:F (`$FFF1=$2F`) on COM4. FNV policy remains disabled (`$FFF2=$FF`).
Two independent pre-update archives matched; B2:F was erased. Backup and
programming verification, software reset, and full four-bank readback pass.
Only B2:F/B3:F changed; the live directory and previous B1:F backup are intact.
Physical reset and final four-bank isolation pass.

The complete [R-YORS board record](../../R-YORS/DOC/GUIDES/LOGS/SECTOR_ROLES_BOARD_2026-09-16.md)
links hashed archives, scripts, and raw serial evidence. Scoped HIMON/AM02
was not installed. This proof covers the ordinary updater only; factory
installation, directory-refresh, and embedded recovery with these roles
have not acquired new board proof.
