# rc1 installation choices and component map

One generation-49 STR8-N firmware set serves 65C02 and 65C816 emulation runtime.
The accepted startup CPU detector briefly enters native mode; native 816
applications/tests, ACIA and crypto remain deferred.

These downloads are the published generation-49 release. The separate local
[DBG1 generation-50 candidate](DEBUGGER_GUIDE.md) is now board-tested on
2604/2609, both slots; it is not included in those ZIP/BIN downloads. Its
[experimental preserving procedure](../../release/candidates/rc1-debugger/BOARD_TEST.md)
requires fresh exact-source captures and matching ASM/MON/core components.

## Choose a path

| Path | Download | Contents and use |
| --- | --- | --- |
| Bootloader / monitor core | `str8n-2.0rc1-boot-core-b3.bin` | 32 KiB B3 provisioning image: fixed F boot/recovery, E core/S/R/T, MON A/MON B, RTC/journal services and generic configuration/wear records. For an advanced programmer setup without B1/B2 utilities/apps. |
| Full STR8-N with utilities/apps | `str8n-2.0rc1-apps-str8n-only.bin` | 96 KiB B1/B2/B3 provisioning image: the same core plus CLOCK, ASM, MAINT/SRAM/WORK/EDU, status/version/display/battery providers and UCHESS. Recommended complete system. |
| WDCMONV2 or beta4 migration | Windows/Linux launchers in this ZIP | Exact-source, already-empty B0/B1/B2 routes install the full system with utilities/apps, with source admission, RAM preservation and bounded recovery. |
| Component maintenance/recovery | Separate MON A, MON B and B3 F files | Matching parts for a reviewed recovery/update plan. Individual component files are not complete installations. |

The core-only image was booted with B0/B1/B2 erased in the W65C02 instruction
model. MON A boot, MON B fallback, core console commands and J3 restart passed
without persistent model-device changes. A separate physical core-only
installation has not been performed. The prior bf1 full-system empty-bank
migrations were tested on physical 65C02 and 65C816 boards; rc1 is verified offline. Utilities such as
CLOCK, ASM and VERSION require their B1/B2 providers and are absent from the
core-only path. Adding only F or MON A/B to an arbitrary bank does not create
the complete core layout.

## Raw-image programmer offsets

| File | Bytes | CPU destination | Offset in a full 128 KiB flash-device image |
| --- | ---: | --- | --- |
| `str8n-2.0rc1-boot-core-b3.bin` | 32768 | B3:`$8000–$FFFF` | `$18000` |
| `str8n-2.0rc1-apps-str8n-only.bin` | 98304 | B1/B2/B3:`$8000–$FFFF` | `$08000` |
| `str8n-2.0rc1-monitor-a.bin` | 4096 | B3:`$A000–$AFFF` | `$1A000` |
| `str8n-2.0rc1-monitor-b.bin` | 4096 | B3:`$B000–$BFFF` | `$1B000` |
| `str8n-2.0rc1-b3-f000-ffff.bin` | 4096 | B3:`$F000–$FFFF` | `$1F000` |

File offset zero maps to the stated destination, **not** automatically to device
offset zero. Follow the programmer's actual chip/bank mapping. Raw provisioning
images replace covered flash contents, including settings/wear records; their
generic tracked baseline is not lifetime erase history. They contain no B0,
WDCMONV2, EEPROM, RTC or external SRAM image. Use the matching scripted full
migration when its admitted source/storage conditions apply; do not substitute
a raw image for a preserving upgrade.

MON A and MON B are the user-facing slot names. A0/B0 in internal code or old
component filenames are B3 page values `$A0/$B0`, not flash banks B0/B1. Both
MON files are generation 49 and require matching rc1 E/F/core services and the
matching provider build for utility/BATCH capabilities. Prefer the verified RAM
tools or a reviewed component recovery plan; blind single-sector writes can
leave incompatible code or remove a fallback monitor.

## J0/J1/J2/J3 behavior

`Jn` selects bank n and follows that bank's `$FFFC/$FFFD` reset vector. Invalid
or erased vectors refuse. In this rc1 layout, **J3 restarts rc1**. The B3 F
bootstrap selects B3 and relies on the B3 A/B/E layout. It is not relocatable
as a standalone J0/J1/J2 monitor; copying it into B1/B2 would replace their
application/provider pages. Earlier bank-resident STR8-N layouts were different
builds. A genuinely standalone monitor in another bank needs a separate build
and qualification, rather than a renamed rc1 F component.

## Manuals, recovery and known limits

This complete release ZIP provides installed-board and migration quick
starts, name/UTC clock/local-offset setup, user/operator guides, ASM manual,
command reference, technical manual, public ABIs and Mermaid source/rendered
diagrams. Run the documented host migration commands from this ZIP using the Windows
or Linux launchers. Keep private captures and recovery receipts private.
uChess source and its full Peter Jennings license, with Daryl Rictor and Bill
Forster credits, accompany the application packages and documentation download.

This is the owner's scoped prerelease: the earlier RTC continuity issue remains
open and disclosed; the recorded stopped soaks are accepted as recorded. Both
soaks and RTC collection remain stopped. Full endurance/rate qualification,
Linux physical serial migration and generic occupied-bank upgrades are not
claimed. Native 816 applications, ACIA and crypto remain deferred.
