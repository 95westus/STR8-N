# STR8-N v2-alpha8 size pass

Reclaims another **142 bytes**, reducing the complete monitor from **3599
to 3457 bytes** and leaving **607 bytes free** before the hardware vectors
at $FFE0. The three size passes have saved **425 bytes** from alpha5.
Commands, descriptive messages, configuration format, and all alpha7 checks
are retained. Hardware qualification remains pending.

## Changes

Scratch values whose lifetimes do not overlap now share zero-page bytes.
D retains the parsed end address instead of copying it. I retains just the
end high byte because its checked inclusive end always has a low byte of FF.
This removes copies and allows shorter zero-page instructions.

The builder emits a startup copy loop sized to the actual RAM worker. For
the current 432-byte worker, it copies two overlapping 256-byte windows.
Only worker bytes are read and written; no padding or additional RAM is
required. The builder still supports the complete 768-byte worker budget.

The hex decoder folds letter case after subtracting ASCII zero. The pointer
write check folds bit 4 to check both allowed ten-byte groups with one
comparison. Both keep exactly the previous accepted inputs. Nearby branches,
shared bank restoration, and removal of redundant flag-setting instructions
provide the remaining savings.

| Component | Alpha7 | Alpha8 |
| --- | ---: | ---: |
| Resident executable code | 2742 | 2617 |
| Text | 322 | 322 |
| Dispatch tables | 30 | 30 |
| Stored RAM worker | 449 | 432 |
| Stored interrupt entries | 56 | 56 |
| **Total** | **3599** | **3457** |
| **Free before hardware vectors** | **465** | **607** |

## Scratch lifetimes

Application RAM reservations, $F000/$F003 entry addresses, and vector pointer
slots are unchanged. All $E0-$FF remains monitor scratch. These internal
aliases are not application storage or stable subroutine parameters:

| Bytes | Uses |
| --- | --- |
| $E8-$E9 | Hex token value; D end address after parsing |
| $E8 | I completion flag after confirmation |
| $E9 | I end high byte, retained from command parsing |
| $EB | Token digit limit; S19 record type during L/I |
| $EC | CR/LF pairing state |
| $ED | Console input byte temporary |
| $F5 | M/F edit kind during preflight; self-edit flag during flash operations |
| $F6 | First configuration sum during validation; flash error during mutation |
| $FE-$FF | Handoff/edit address; next expected install address during I |

Flash errors are initialized before mutation. C finishes integrity checks
before using the worker, and the result display reads the configuration copy,
not the scratch sums. S19 decoding does not invoke command token parsing.
Console polling keeps its own scratch throughout these phases.

## Validation and artifacts

`make v2-check` builds the image and runs all five host execution suites.
Additional checks execute all 256 possible hex input bytes with either
incoming carry, verify the exact startup worker copy and untouched RAM above
it, and exercise M/D/L/I/C/F/G consecutively without restarting the monitor.
The existing exhaustive 65,536-address M policy test covers the smaller
pointer check. Full-sector verification, timeout, cancellation, self-edit,
bank-handoff, and configuration integrity tests remain in place.

The linked minimum autostart window measures **8,155,786 CPU cycles**, about
**1.019473 seconds at 8 MHz**. Branch page crossings affect software timing;
the test checks the final linked image against the existing timing bounds.

Artifacts and test receipts are under `BUILD/v2-alpha8/`. The dense E-F image
is `str8n-v2-alpha8-e000-ffff.s19`, with a matching `.bin`. The v1.35 host
installer validator accepts it for Banks 0-2. Installing it replaces both E
and F sectors; retain v1.35 in Bank 3 for recovery during board qualification.
No physical board was flashed or tested during this pass.

Configuration and command behavior remain as documented in
[alpha5](STR8N_V2_CONFIG_MILESTONE.md),
[alpha6](STR8N_V2_COMPACT_MILESTONE.md), and
[alpha7](STR8N_V2_LEAN_MILESTONE.md).
