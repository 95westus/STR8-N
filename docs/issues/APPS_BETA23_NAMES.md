> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Issue: beta23 APPS displays corrupt names

ID: STR8N-004

Status: **Closed**

Opened: 2026-10-11

Resumed at the user's direction on October 14. The earlier October 11
deferral is retained below as history. Hardware qualification remains required
before accepting the application-listing release path.

## Impact

The advertised monitor application listing is unreliable on the current
beta23 images on 2604 and 2609. Release acceptance for this path remains open.

## Reproduction and evidence

With EDU enabled, enter `APPS` at B3. Both boards print eight lines containing
twelve $FF bytes followed by `not installed`. `T 1` and `T 2` correctly list
MAINT, CLOCK, SRAM, WORK and EDU; `R <name>` launches those applications.
Owner-local captures are under
`output/qualification/soak-inventory-2026-10-11/`.

## Findings

This observation used only inventory commands. No flash, preference or RTC
setting was changed. The cause has not yet been established. The preserving
soak records the failure and uses the valid stored-record table.

## Next action

Deferred at the user's request on October 11. Keep the current soak running;
do not change or flash its candidate image to address this defect during testing.

Compare the APPS table/addressing with the exact installed beta23 image and
identify why its display reads erased bytes. Keep any repaired image distinct
from the frozen candidate and qualify it independently.

## Close criteria

Correct names and installed status on the affected boards, exact artifact
identity and retained regression evidence, including EDU-enabled execution.

## October 14 diagnosis and separate candidate

The native descriptor table has the correct `AT 01 08` header at B3:E6F0,
but its eight 32-byte rows at E6F4-E7F3 were left erased by
`build_v2_rtc_kernel.py`. The original beta4 builder initialized empty rows to
zero; the later kernel builder omitted that step. APPS treated a nonzero first
name byte as a row and printed twelve `$FF` bytes for each erased row.
The exact parent extension reproduces all eight corrupt lines in the
instruction model; retained final readbacks from both affected boards contain
the same erased rows.

APPS lists native `AP` descriptors. `T`/`R` use the separate legacy `SR`
saved-program records. MAINT, CLOCK, SRAM, WORK and EDU appearing in T does
not imply corresponding native APPS descriptors exist. An empty native table
should produce no application rows.

The isolated candidate is `BUILD/v2-fix004`, based on the unflashed local-only
TIME candidate. It initializes empty rows and checks the table header and
bounded uppercase/NUL-padded names before output. It uses the existing
read-only probe to check descriptor/header/image CRCs, ABI, ranges, workspace
and exception vectors before reporting `installed`. A readable named row that
fails installation validation reports `not installed`.

The compact E000-E7FF launcher allocation is 1760/1760 code bytes; all prior
private entry addresses remain fixed. F/A/B and other program/display assets
remain unchanged. Build and tests do not access either board. This issue
remains open pending the required affected-board retest.

Six instruction-model suites and the exact-artifact receipt audit pass,
including malformed/native app cases, monitor A/EDU ON, monitor B/EDU OFF,
TIME/R CLOCK, startup FIFO, compact boot, power-fail labels and storage
transfers. A repeated build produces identical binaries. No serial ports or
boards were accessed. See [candidate qualification](../STR8N_V2_FIX004_2026-10-14.md)
for the E-image hash, boundaries, test commands and retained evidence.

## Beta25 installation on 2609

The user authorized beta25 shared changes and only the inactive monitor on
2609. The same repaired E extension is now installed and qualified there under
both the untouched beta24 MON A and new beta25 MON B. Actual APPS and T/R paths,
EDU ON, normal app returns, complete flash readback and retained-device checks
pass. Board 2604 was excluded and remains pending, so the issue stays open.
See [beta25 installation](../STR8N_V2_BETA25_2026-10-14.md).


## October 14 fleet closure

The unified beta25 upgrade and hardware retest now also passed on 2604.
Both retained beta24 MON A and new beta25 MON B produce the correct empty
native APPS list, with EDU ON and normal T/R/application returns. Complete
flash readbacks, 128 KiB SRAM, EEPROM/history/EUI, RTC settings, board name
and offset, startup/FIFO, ABI/interrupt and wear-count checks passed.
The repaired E sector SHA256 is `d999ab7f2f9029eb36796e4095903de5b8e92d3ef760ee65e0db584aaeca5ec7`.

Together with the completed 2609 qualification, this satisfies the affected-board
close criteria. The issue is closed. The same shared fix is also qualified on
2205/2512 with retained beta23 and new beta25 monitors. See the
[fleet report](../STR8N_V2_BETA25_FLEET_2026-10-14.md) and retained evidence under
`output/qualification/beta25-fleet-2026-10-14/`. STR8N-005 remains open for its
separate destructive physical F-only acceptance.
