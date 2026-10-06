# STR8-N 2.0b4 release notes

STR8-N 2.0b4 is a resident reset monitor and flash loader for W65C02SXB and
W65C816SXB boards. The 816 monitor runs in emulation mode. BANK MAINT 1.5
remains the existing RAM utility, included as a S19 and an installed saved
record. Both migration paths install MAINT into B3 sectors 8/9.

## Release contents

- Windows PowerShell and Linux shell launchers for stock-board migration.
- Windows PowerShell and Linux shell launchers for STR8-N a24-and-later upgrades.
- One portable Python host tool and a guarded, independent RAM installer.
- Two beta4 monitor slot BINs and the matching E/F firmware.
- BANK MAINT 1.5 S19 and generated saved-record image, Markdown/PDF guides and hashes.

The explicit package file list excludes stock monitor firmware, vendor source
code, owner-local readbacks, configuration snapshots and backup archives.
The installer communicates with the stock monitor already on the board;
that monitor's code is neither embedded in the installer nor distributed.

## Firmware

B3:A/B holds two beta4 monitor copies. C/D holds startup configuration and
32 sector erase-attempt counters. E provides program storage services and
launcher support with no installed program descriptors. F is the fixed
reset/recovery core. B3:8/9 stores MAINT; `R MAINT` restores it into RAM and
starts it. Monitor maps use this same saved utility. The public RAM
console/vector interfaces are retained.

The release slot generation is 13. Slot generation is an update-order
identifier, separate from firmware version 2.0b4. The package updates the
help text to describe monitor/program operations without unrelated examples.
The fixed F contract and BANK MAINT program bytes remain unchanged.

See the [operator manual](STR8N_V2_BETA4_MANUAL.md),
[quick start](STR8N_V2_BETA4_QUICK_START.md),
[migration guide](STR8N_V2_BETA4_MIGRATION.md),
[RST guide](STR8N_V2_BETA4_RST.md), and
[maintenance guide](STR8N_BANK_MAINT_RECOVERY.md).

## Qualification

The pre-release clean COM3 beta4 board passed complete flash readback,
both software boot selections and the unchanged maintenance utility's host
load, SAVE, TABLE, load-only RESTORE and run RESTORE sequence. The later
release adds the migration launchers and revised help. Their host protocol,
plan/refusal cases and linked RAM installer are checked offline.

The stock-to-beta4 path completed on COM3's W65C02SXB after the retained B0
image was restored to B3 with B0 preserved. The a24c1/beta1-to-beta4 path
completed on COM8's W65C816SXB. Both passed complete expected-bank comparison,
physical RESET confirmation, both monitor-slot boots and RAM-only maintenance
checks. The stock startup used the established armed Windows probe; the
portable host's remaining migration operations were physically exercised.
The portable startup probe is separately checked with serial fixtures.
See the [hardware report](STR8N_V2_BETA4_HARDWARE_ACCEPTANCE_2026-10-06.md).

The stock launcher now probes while RESET is pressed, because a retained
image may otherwise start a normal program before the debugger connects.
Native-mode 816 program execution, physical power interruption and every
source version on both boards remain outside these checks. Keep stable
power; an initial F rewrite is not power-loss safe.

## Build

```text
make -f Makefile.beta4 check
```

This prepares `output/release/str8n-v2-b4.zip` and its `.sha256` file from
source and performs the firmware/migration checks. The migrator needs no
WDC tools on the user's system; Python 3 and pyserial are sufficient.
The build creates the release locally. Backups remain outside the release.
