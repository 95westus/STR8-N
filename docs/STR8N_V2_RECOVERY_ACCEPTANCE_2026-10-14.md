> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Clock history repair and F-only recovery acceptance — October 14, 2026

The user requested this sequence: repair 2604's foreign clock-history layout,
test STR8N-005 physically, then implement and qualify unified b4-to-b25 upgrade.
Only 2604 is used for the destructive recovery fixture. Full repeated flash and
128 KiB SRAM backups were captured before changes; other boards are excluded.

## Clock history: passed

The old 128-byte history region contained no valid saved records: it was erased
except for one `00` at offset 20 hex (the first byte of slot 2). This correctly
triggered the foreign-layout guard. A repeated complete EEPROM/factory/status
snapshot and the still-latched RTC outage were archived before repair.

The exact layout was rehearsed in the linked model. Cancellation preserves the
old bytes; documented CLEAR ALL / DELETE ALL initializes the four slots while
retaining the live outage. ACK / YES then saves/verifies the outage before
clearing its latch. The physical procedure passed with sequence 1, valid CRC,
the original eight raw outage bytes and durable acknowledgement. A fresh
software boot and HISTORY query no longer report failure.

All four flash banks remained byte-identical. Factory/status bytes and EUI,
unbound identity state, RTC control 00 and trim -12 remained unchanged. No UTC
set or trim change was issued. The old EEPROM image is retained owner-locally.
Evidence: `output/qualification/beta25-recovery-2026-10-14/2604/clock-repair/`.

## STR8N-005: physical acceptance passed

Separate F-only A and B fixtures reached recovery after physical RESET and
installed valid monitors without erasing F. Missing slots, canceled uploads,
bad CRC, incompatible cookie and wrong-slot uploads refused. Physical RESET
after 1,024/4,096 bytes returned to recovery with no flash programming.

Both paths passed actual monitor L/G journal provisioning, idempotent retry,
normal inactive-slot update and J3 restart. Original beta24 A/beta25 B, shared
firmware, name/offset and original journal records were restored. One new wear
record accounts for all 23 test/restoration erases. Full 128 KiB SRAM, repaired
EEPROM history, RTC control/trim and EUI compare exactly with saved references.
Evidence: `output/qualification/beta25-recovery-2026-10-14/2604/post-005/report.json`.

Exact-package models cover 123 journal program interruptions and 11 slot
interruptions. No physical mid-program electrical power cut is claimed.

## b4-to-b25: passed

The unified upgrade was physically qualified on 2604 from the published b4
core/MON A/MAINT to beta25 shared firmware and inactive MON B, preserving b4 A.
Both pure-b4 active-slot choices also passed the complete 17-sector linked
installer and mixed-monitor models. The physical fixture retained existing
system records in B1/B2; that scope is recorded separately.

2604's original beta24 A / beta25 B, name, offset and original journal records
were restored afterward. Final physical RESET, full flash, all wear counts,
full SRAM and repaired EEPROM/RTC settings passed. One appended journal record
accounts for all 19 b4-fixture/upgrade/restoration erase attempts, in addition
to the 23 already accounted by STR8N-005. Other boards were untouched.
See [b4-to-beta25 qualification](STR8N_V2_B4_TO_BETA25_2026-10-14.md).
