> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta32 candidate: highest tracked flash erase count

This records the sealed offline build checkpoint. Subsequent installation
and hardware qualification passed on 2512; see [the installed report](STR8N_V2_BETA32_2512_2026-10-16.md).
The original offline scope below is retained as build history.

Beta32 adds the exact highest tracked erase-attempt count and its bank/sector
to every valid FLASH boot status (OK, WARNING and HIGH). Counts are printed
in unsigned decimal; sector identifiers retain their normal hexadecimal
notation. Illustrative normal output:

```text
FLASH: wear check OK. Sector B3:C, max 123 tracked erases.
Prior/direct wear unknown. W lists counts (hex).
```

The first strictly greatest count in bank/sector order wins. Equal maxima
therefore choose the lowest bank and sector; a valid all-zero history shows
B0:8, max 0. The full 24-bit range is supported, up to 16777215. The original
maximum and journal counters are preserved while a scratch copy is divided
for decimal formatting.

Missing valid history still reports UNKNOWN and prints neither a peak count
nor a sector. A stale previous maximum is never reused in that case. WARNING
at 50,000 and HIGH at 80,000 retain their existing backup/replacement advice.
These are managed erase-attempt counters, not a measurement of prior/direct
or out-of-band wear. W still displays the detailed counts in hexadecimal.

The status appears once at boot, including EDU OFF. Ordinary monitor return,
TIME and BATCH remain quiet. No flash, EEPROM, RTC or SRAM write is performed
by the wear check. Native utilities, bare aliases, CLOCK and the protected
monitor/service ABI are unchanged.

The battery/wear helper adds 76 linked bytes over beta31. Code/data and seal
use 2,302 of its existing 2,560 flash bytes, leaving 258 bytes. Decimal
formatting uses 12 bytes inside the existing borrowed helper staging RAM;
no additional RAM reservation or application-RAM reduction is required.
The native utility bundle still has 516 free bytes.

CPU-model validation covers 105 peak/sector/boundary cases, 131 direct
decimal-format cases, ties, corrupted and uncommitted journal records,
missing history, ON/OFF boot, retained application/device data, unchanged W
output and bare MAINT/BATCH/TIME integration. An independent rebuild compares
28 files byte for byte.

Package: `BUILD/v2-beta32-candidate`.
Sealed offline receipt: `beta32-qualification.json` in the package.
At this offline checkpoint no board port was opened or flashed; 2512 was on beta31.
Reference bank images are for offline testing only, not installation; no
board-specific installation plan was generated.
