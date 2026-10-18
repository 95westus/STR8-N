# Windows and Linux full-system migration quick start

Use the [Windows commands](QUICK_START_WINDOWS.md) or [Linux commands](QUICK_START_LINUX.md).
Both packages carry identical rc1 firmware, including UCHESS, CLOCK, ASM,
utilities/providers, MON A/MON B, recovery/core and S/R/T.

## Source and storage admission

The live WDC route admits the exact original SXB6 65C816 WDCMONV2 profile;
the beta4 route admits the exact published generation-13 profile. **B0/B1/B2
must already be erased.** The public migration does not erase occupied user
banks or stage legacy source firmware. Do not erase a working board merely to
make a refused upgrade pass. Back up and obtain a separate provisioning plan.
The SXB2 65C02 WDC profile is recognized for offline preparation, not admitted
for live use by this candidate's hardware qualification.

1. Extract the entire matching host package and run `rc1 verify` through its
   `.cmd` or `.sh` wrapper. Install Python 3.10+ and pyserial 3.5.
2. Close other terminal/debugger sessions. Select the actual port, exact USB
   serial number and a private board label. Unrelated ports are never opened.
3. Choose a new private output directory outside the extracted kit. The tool
   captures B3 twice and application RAM once. B0/B1/B2 are explicitly recorded
   as erased assumptions, not fabricated readbacks; the RAM worker checks every
   byte of all four source banks before any flash mutation.
4. Use stable power and retain the RTC battery. WDC requires an initial RESET
   while its debugger is armed. Type `INSTALL RC1` only after source admission.
5. After all device verification passes, follow the physical RESET prompt once.
   The tool confirms rc1/UCHESS discovery and reloads saved application RAM.
   With `--no-host-readback`, loader acknowledgment does not prove host readback.

The tool never SETs time/trim/offset, acknowledges power events, or programs
EEPROM/external retained SRAM. A prior WDC trial lost RTC continuity, so broad
RTC preservation remains unqualified; see [scope and limits](README.md).

## Failure and recovery

Keep the exact kit, capture, plan, transfers and logs together. Never substitute
another board's metadata or wear counts. Use [bounded recovery](MIGRATION_RECOVERY.md).
An unexplained partially programmed state refuses. Early WDC cuts without a
working rc1 fallback may require an external programmer. Do not repeatedly reset
or force a different installer. Original vendor backups stay private.

## Programmer image

The 96 KiB STR8-N-only `.bin` includes every supported application and UCHESS.
It covers B1/B2/B3; file offset zero is full-device offset `$8000`. It is a
fresh-provisioning image with defaults, not a preserving upgrade or board dump.
See [firmware mapping](FIRMWARE_CONTENTS.md). No WDC/beta4 binaries are included.
