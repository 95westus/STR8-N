> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# bf1 complete firmware image and MON A / MON B naming

`str8n-2.0bf1-firmware.bin` is a **131072-byte (128 KiB) complete flash image**
for the STR8-N FT245/F30D profile. The exact same file is intended for 65C02
and 65C816 emulation-mode runtime. No CPU-specific image is needed. The unchanged
startup detector exception remains accepted; native 816 applications/testing,
ACIA and crypto remain deferred.

## File layout

The file concatenates four 32768-byte logical flash banks in order **B0, B1,
B2, B3**. Each bank represents CPU addresses `$8000-$FFFF`:

`file offset = bank * $8000 + CPU address - $8000`

| Region | File offset | Contents |
|---|---:|---|
| B0 | `$00000` | Erased user-storage space |
| B1 | `$08000` | CLOCK storage and assembler with matching vectors |
| B2 | `$10000` | Utilities, status, battery, local-display and version providers |
| B3 | `$18000` | RTC/journal services, both monitors, defaults and fixed recovery core |
| B3:`$A000-$AFFF` | `$1A000` | **MON A**, bf1 generation 48 |
| B3:`$B000-$BFFF` | `$1B000` | **MON B**, bf1 generation 48 |

They have always been MON A and MON B. `A0` and `B0` are the internal
hexadecimal page identifiers `$A0` and `$B0` for the monitor starts `$A000`
and `$B000`; the zero is not a new monitor version. A component called
`slot-b0.bin` is MON B at B3:`$B000`, not the entire logical flash bank B0.
The default preference selects MON A; MON B remains the alternate/fallback.

All matching providers are included. Unallocated space is `$FF`. The image is
deterministically composed from the same 19 pinned build artifacts used for
both CPU boards, plus a fresh generic configuration/wear record. It contains
no captured board identity, stored program, EEPROM/SRAM backup or RTC state.
The layout manifest supplies the source range and hash for every populated
region, and the checksum accompanies the image.

## Programming scope

This is a **fresh-provisioning/programmer image**, with fresh default
configuration and a zero wear baseline relative to provisioning. Those counters
do not describe a previously used chip's physical erase history. Programming the
whole image replaces flash-resident settings, user-storage contents and wear
journals. Use the separately admitted preserving migration transaction when
those existing values must survive; do not apply this whole image as an
in-place preserving upgrade.

The image contains flash bytes only. It does not set RTC time or trim, provision
EEPROM identity or format retained SRAM. It does not include a generic stock/
legacy migration launcher. Follow the programmer's chip geometry and the
documented logical bank mapping; no new physical programming operation is
performed on the ongoing soak boards to prepare this release artifact.

## Verification and qualification

The firmware components remain byte-identical to the shared 65C02/65C816 E=1
hardware-tested set. The new clean-image composition is checked independently
for bounds, overlaps, input hashes, reset vector, defaults and bank order, then
executed in the W65C02 model for MON A/MON B boot, corrupted-slot fallback,
fixed recovery and utility/CLOCK BATCH handoffs. This is not a claim that this
new whole-image provisioning method was physically flashed on a board, or a
new native-mode 65C816 test.

The [accepted prerelease gates](STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md) still
apply. Distribution as a pilot prerelease does not satisfy the pending longer
2604 endurance, seven-day RTC or broader electrical qualification gates.
