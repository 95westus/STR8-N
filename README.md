# STR8-N 2.0bf1 complete firmware — pilot prerelease

Generation 48; CLOCK 1.11; FT245/F30D. One firmware set supports 65C02 and
65C816 emulation-mode runtime. Native 816 applications/tests, ACIA and crypto
remain deferred. Existing startup CPU detection briefly enters native mode
before restoring E=1; this unchanged exception is accepted.

Start with the [manuals](docs/bf1/README.md), [qualification summary](docs/STR8N_V2_BATCHFIX_R1.md)
and [accepted soak/RTC policy](docs/STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md).
Tonight's prerelease is conditional on the six-hour 2609 soak and verified RAM
restoration. The 72-hour/300-cycle 2604 and seven-day RTC gates are pending.
This is not a fully qualified release or a generic installation package.

The complete **128 KiB** image is `firmware/str8n-2.0bf1-firmware.bin`.
Use the **same file** for 65C02 and 65C816 emulation-mode runtime. It contains
MON A, MON B and all matching providers, with fresh generic configuration and
a fresh wear baseline; it is not a preserving upgrade image. See the
[full-image guide and MON A/MON B naming](docs/STR8N_BF1_FULL_FIRMWARE_IMAGE.md).

All 19 exact pinned binary/application artifacts are under
release/candidates/batchfix-r1/payload. Monitor A0/B0 .bin files are 4096-byte
components, not complete flash bank or device programmer images. Other stored
providers must match this set. Do not combine them with older BATCH providers.
Only exact separately admitted 2604/2609 migration lineages are supported.
No automatic stock/legacy installation, settings reset or wear rollback is
provided. Retain your own full backup before any separately planned migration.

Reproduce from source with Python, WDC02AS and WDCLN on PATH:

```text
python release/candidates/batchfix-r1/build.py --out C:\tmp\bf1build
```

Use a fresh short output directory. Compare all artifacts against
reference-build.json and SHA256SUMS. The frozen candidate README/release.json
record original offline development permissions; current pilot publication
scope is documented in the accepted-policy guide. Firmware inputs are unchanged.
No v2.1 payloads, board dumps, EEPROM/SRAM backups, private receipts or serial
logs are distributed.


Reproduce the whole image from these verified components:

```text
python release/bf1-prerelease/build_full_image.py --payload release/candidates/batchfix-r1/payload --reference firmware/full-image-reference.json --out C:\tmp\bf1image
```

Bank order is B0/B1/B2/B3, 32768 bytes each. MON A is B3:$A000 (file offset
$1A000); MON B is B3:$B000 (file offset $1B000). A0/B0 in internal component
names denotes those hexadecimal pages, not new monitor names or CPU types.
The new whole-image layout has offline boot/fallback/BATCH qualification;
its identical component firmware has prior shared-CPU hardware evidence.
It has not been physically reprogrammed onto the active soak boards.
