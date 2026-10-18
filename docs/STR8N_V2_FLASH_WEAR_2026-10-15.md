> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta25 flash-wear reminders — October 15, 2026

The beta25 `BUILD/v2-battery` candidate now also reports flash wear at boot and
in R EDU, including EDU OFF. Build with `tools/build_v2_battery.py`; the existing
offline update planner installs the combined helper. No additional flash sector,
counter record format or recovery/monitor-slot changes are needed.

The SST39SF010A family datasheet specifies **100,000 cycles typical**, rather
than a guaranteed per-device failure point. See [Microchip DS20005022](https://ww1.microchip.com/downloads/aemDocuments/documents/MPD/ProductDocuments/DataSheets/SST39SF010A-SST39SF020A-SST39SF040-Data-Sheet-DS20005022.pdf).
The following thresholds are maintenance policy, not a prediction of remaining
physical life. They are fixed defaults in this candidate, not user settings.

| Recorded attempts on the most-used individual sector | Reminder |
| --- | --- |
| Below 50,000 | No wear reminder; this does not certify flash health. |
| At least 50,000 | `Flash wear: >=50,000 tracked erase attempts. Back up; plan replacement. Sector Bx:s.` |
| At least 80,000 | `Flash wear HIGH: >=80,000 tracked erase attempts. Back up now; replace flash soon. Sector Bx:s.` |

Both messages append `W lists counts (hex). Prior/direct wear unknown.`
The highest counter selects the reported sector; ties retain the first sector
in bank/sector order. Compare all 24 bits, including values beyond 100,000.
Thresholds apply per 4 KiB sector, not to an average across the 128 KiB chip.
The higher message continues above 100,000; there is no automatic write lock at
a nominal endurance number. Actual erase/program/verification failures remain
errors regardless of count.

## Existing accounting and its limits

Beta25 already maintains 32 unsigned 24-bit erase-attempt counters in the
CRC/commit-validated B3:C/D journal. W and MAINT display them. Managed erase
paths persist an attempt before issuing the erase, including journal rollover
erases. A failed accounting save prevents the managed erase. Interrupted or
failed operations can therefore conservatively overcount attempts. A count is
not an exact physical-cycle measurement or a percentage of useful life left.

Ordinary byte programming and 1-to-0 appends do not increment an erase-attempt
counter. Programming many bytes after one sector erase is not one sector
endurance cycle per byte. The new reminder reads existing counters; it neither
programs nor erases flash and adds no wear-accounting writes of its own.

Known counters cover managed operations since provisioning. Earlier chip use,
external programmers, old firmware, and direct flash command sequences from
user programs are not observable by STR8-N. The current format cannot mark a
bank's complete historical provenance; the UI therefore always qualifies the
counts as tracked attempts. Missing or invalid committed journal history is
reported as unavailable, never as zero.

An opaque B0 image still has known installation erases if STR8-N installs it
through an accounted path. Its contents do not affect counting. If that image
later erases/programs flash directly, those operations are unknown. Rewriting
an identical image can leave identical contents, so later dumps/CRCs cannot
reconstruct its wear. Software cannot enforce universal tracking on this board
without cooperation from every writer or added hardware protection.

## Application interface direction (proposal, not implemented here)

Provide a versioned, guarded flash service rather than publishing private
worker addresses. Suitable operations are:

- `GET_WEAR(bank, sector)` returns the recorded u24 attempts, valid/unavailable
  status and scope `tracked since provisioning; prior/direct operations unknown`.
- `ERASE_SECTOR(bank, sector)` validates ownership/protected ranges, persists
  the attempt before erasing, verifies the outcome and returns an error on
  failure. A caller must not increment the journal independently.
- `PROGRAM(bank, address, data)` validates bounds and permissions and verifies
  programming. If a higher-level operation requires an erase, it must go
  through ERASE_SECTOR and account for each attempt/retry.

Applications can implement their own dashboards and reminders using GET_WEAR;
they should not maintain a competing persistent copy of STR8-N's counters.
The API should be foreground, non-reentrant and support the existing 65C02/
816-emulation contract. Firmware, journal, active-slot and recovery protection
must remain in force. Raw chip erase/direct command access is not an accounted
application service. There is no new public erase/program ABI in this change.

Updates should preserve counts. Restoring an older full-flash image must not
be treated as restoring the physical chip's earlier wear: preserve current
known accounting and add the restore operations. Unobserved history remains
unknown rather than being replaced with fabricated counts.

## Implementation and verification

`tools/v2-rtc/flash-wear.inc` runs from the combined sealed helper at $6E00,
calls the existing B3 journal reader with the resident bank visible, restores
the incoming bank and scans all 32 counters. It prints only the highest
applicable warning. The shared status formatter tail-loads the helper on EDU
ON/OFF; OFF skips battery/RTC calls and preserves reclaimed application RAM.
TIME and ordinary quiet monitor returns retain their existing behavior.

`tools/test_v2_flash_wear.py` executes 45 boundary/sector combinations covering
49,999/50,000/79,999/80,000, 16-bit carry, 100,000 and 24-bit saturation, B0 and
journal sectors. It also checks worst-sector selection, uncommitted/corrupt
newer records, invalid history, actual ON/OFF boot warnings, quiet returns,
the existing W report, bank/RAM preservation and absence of flash/device writes.
Its hash-bound receipt is `BUILD/v2-battery/flash-wear-test-results.json`.

The battery, CLOCK summary, compact boot and complete offline installer suites
are also required for the combined candidate. The offline planner requires the
wear receipt before preparing an installer. Physical execution and flash-current
or endurance characterization are not claimed by these instruction-model tests.

On October 15 the combined candidate passed all five suites: flash wear,
battery, CLOCK summary, compact boot and the complete seven-sector installer
rehearsal (including stale-preimage and corrupt-payload refusals). The existing
F and both monitor-slot binaries remain identical to the baseline. No hardware
was accessed or flashed.
