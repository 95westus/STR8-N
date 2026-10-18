> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta31 candidate: visible boot flash-wear status

Beta31 makes the existing boot wear check visible at all tracked wear
levels. No board was accessed or flashed. Board 2512 remains on beta30.

Normal boot example:

```text
FLASH: wear check OK - tracked <50,000/sector; prior/direct wear unknown.
```

The worst individual 4 KiB sector determines the status, using the existing
CRC/commit-validated journal and its 24-bit managed erase-attempt counts:

| Status | Meaning |
| --- | --- |
| OK | Every tracked sector is below 50,000 attempts; prior/direct wear remains unknown |
| WARNING | Worst tracked sector is at least 50,000 and below 80,000; back up and plan replacement |
| HIGH | Worst tracked sector is at least 80,000; back up now and replace flash soon |
| UNKNOWN | No valid wear journal; no zero count or health certification is inferred |

WARNING/HIGH retain the affected sector identifier and W guidance. These
are tracked counts since provisioning, not a measurement of total physical
flash wear. Opaque images and direct/out-of-band writes can contain
untracked history. Thresholds and W output are unchanged.

The line appears once on actual boot, including EDU OFF. Ordinary monitor
returns, TIME and BATCH do not repeat it. Battery status follows as before.
The check does not write flash, EEPROM, RTC or SRAM and does not increment
wear counters.

The helper adds 103 linked flash bytes inside its existing 2,560-byte
reservation. Code and seal use 2,226 bytes, leaving 334 bytes. It uses the
existing borrowed monitor staging RAM; there is no new RAM reservation.
The native utility bundle remains 22,012 bytes with 516 bytes spare.
Native utilities, bare-name aliases, CLOCK 1.9, resident B3:E, fixed B3:F,
status loader and application RAM limits are byte-identical to beta30.

CPU-model checks cover 45 threshold/sector cases, 16/24-bit carry edges,
worst-sector selection, missing/corrupt/uncommitted records, ON/OFF boot,
quiet monitor return, unchanged W counts, application RAM and retained
devices, plus bare MAINT/BATCH/TIME integration. An independent rebuild
compares 28 files byte for byte. The sealed offline receipts are under
`BUILD/v2-beta31-candidate`.

Reference bank images are for offline tests only and are marked unsuitable
for installation. No board-specific installer was generated. A subsequent
installation requires fresh board backups, preserving its current saved
programs, name, offset, RTC data and wear counts.
