# Traditional firmware presentation:2512 RAM acceptance

November1 local / November2 UTC. MON g00000010 and matching STATUS core5
passed on2512/COM4 in CPU RAM. At that checkpoint they were **not installed**
and ROM remained gF. The subsequent approved three-sector installation,
ROM/UI checks, physical default-B startup and versioned RTC readmission now
pass; see `MON_TRADITIONAL_ROM_ACCEPTANCE.md`. Foundation remains the exact
frozen0.3.0 g1 BASE1/PR05 image.

Seven checks passed: fresh owner escrow, selected startup with dynamic board
status and no duplicate A/B inventory, detailed VERSION, V alias, shared help
and invalid VERSION arguments, concise native TIME with live trim/control,
and EDU OFF/ON unavailable-data/status behavior. Native TIME reported the
existing trim0C/control80. Startup used saved name2512 and current-06:00 offset.

Actual RAM startup capture (time shown is the observation, not a setting):

```text
STR8-N F 0.3.0  Foundation  gen 00000001
Recovery / opaque-image boot

STR8-N RAM  gen 00000010
Board: 2512

RAM $0200-$66FF
EDU ON
SSRAM: PROGRAM payload 63488 bytes
SSRAM: WORKSPACE 65504 bytes

RTCC: Sun 2026-11-01 18:16:08 (-06:00)
FLASH: B2:8 tracked max 604*
Battery: within age policy*
* Health/prior wear unmeasured; attempts.
B3>
```

RAM identifies itself as RAM. ROM builds identify MON A/B, with identical
commands. VERSION adds `0.1.0-dev BASE1/PR05 ABI 2`, CPU and the real validated
installed A/B generations (still gF during this trial). The shared help already
lists VERSION/TIME, S19, storage aliases, APPS/named tools, EDU/SRAM/WORK/BATCH
and protected C/D/F. The manual maps S/T/R to STORE/TABLE/RESTORE. TIME retains
its existing UTC/flags/trim/control format and does not repeat the banner.

Evidence: `output/qualification/2512-startup-traditional-RAM-20261101-r3/report.json`.
The receipt carries hashed successful display/help captures from r2 and
finishes only the remaining TIME/EDU cases. Two host assertions were corrected:
r1 wrongly tried G to recapture startup (RAM correctly refuses G); r2 expected
REFUSED where the correct invalid-argument reply was `Syntax; use ?`. Neither
required a firmware repair or rebuild. Startup is taken from actual RX after
load, not the transmitted image's embedded strings. No passed display cases
were repeated in the final continuation.

Every attempt restored/read back owner RAM0200-66FF and ZP00-DF exactly.
Final RAM SHA256: `ec6ca3fc25398ad645f2d6f4b1a1c22fedea2a705512acd52b743a0e832bfde5`.
ZP SHA256: `0249810f3e614737e567101f8064a37a7151aceb8b76a379b5c69ca21070cc43`.
End: REC>, COM4 released, restore guards clear. Zero flash/boot-wear/metadata
or SPI-data writes, RTC SET/trim/PF-ACK, resets or power cuts. RTC collection
retained priority.2609/2205/2604 and published downloads were untouched.

At RAM closeout, ROM UI binding, installed MON A/B startup, physical saved-default
boot and versioned RTC readmission remained installation gates. The subsequent
approved three-erase scope at `2512-startup-traditional-scope-20261101-r1` has
completed its image writes, ROM/UI tests and physical reset/RTC readmission.
See `MON_STARTUP_STATUS.md` for the current checkpoint.
BOOT/CLOCK positive setting tests are separate. No816-emulation execution
claim is added by this65C02-only RAM receipt; the targeted final path remains
on the common release checklist.
