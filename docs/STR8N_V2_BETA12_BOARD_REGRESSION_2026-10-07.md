# Beta12 / CLOCK 1.4 on-board regression

The owner's requested regression passed on physical boards 2512 (COM4, no EDU),
2205 (COM3, EDU) and 2609 (COM8, EDU). All ended at the normal B3 monitor prompt.
The final integrity audit passed. No firmware, clock, trim, outage or remembered
identity changes were made by this regression.

| Check | 2512 | 2205 | 2609 |
| --- | --- | --- | --- |
| Both monitor slots and software recovery/return | PASS | PASS | PASS |
| Bank-safe RAM ABI, capability and board queries | PASS | PASS | PASS |
| BRK and physical VIA1 Timer-1 IRQ; A/X/Y, stack, RTI | PASS | PASS | PASS |
| Physical NMI; A/X/Y, stack, RTI and pointer restoration | PASS | PASS | PASS |
| Native BRK/NMI; native frame/PBR and RTI | N/A | N/A | PASS |
| 816 return to E=1, D/DBR/PBR zero | N/A | N/A | PASS |
| RAM edit/execute; malformed S19 rejection | PASS | PASS | PASS |
| RTC calls through all four caller banks | Bounded absent response | PASS | PASS |
| Shared I2C RTC reads and raw EEPROM denial | PASS | PASS | PASS |
| Reserved-RAM execute/edit/SAVE and B3:8/9 guards | PASS | PASS | PASS |
| CLOCK/MAINT byte-exact RESTORE, table/maps and protection | PASS | PASS | PASS |
| TIME and runnable read-only example | Correct unavailable response | PASS | PASS |
| CLOCK EUI/STATUS/HISTORY/SHOW and safe input handling | Correct unavailable response | PASS | PASS |
| Before/after and post-NMI complete flash comparison | PASS | PASS | PASS |
| EEPROM history, factory/protection bytes and identity retained | N/A | PASS | PASS |
| UTC advancing; RTC control/trim retained | N/A | PASS | PASS |

The timer probe refused any pre-existing enabled VIA interrupt source before
testing. All three boards were safe to test. It restored handler pointers, ACR,
timer latches and interrupt enable state; snapshots verified restoration. Physical
NMI probes were RAM-only and restored their handler pointers. The native probe
on 2609 returned to emulation before calling monitor services; an independent
CPU-state probe confirmed E=1 and zero D/DBR/PBR afterward. Native RTC/I2C calls
remain outside the supported ABI and were not attempted.

CLOCK checks included unchanged-identity acceptance with no confirmation/write,
canceled CLEAR ALL and SET, malformed-date SET rejection, and unavailable-device
paths. All four EEPROM history slots were displayed on both EDU boards without
clearing them. Saved CLOCK and MAINT binaries were restored/read back exactly;
ordinary monitor and MAINT ownership checks rejected writes to the RTC/journal
sectors and service RAM. Guards were tested without accepting a flash operation.

The starting, post-automation and post-physical-interrupt images for every bank
matched byte-for-byte and matched the accepted beta12 installation. Both EDU
ordinary EEPROM arrays, factory EUI and protection status matched repeated reads
before and after testing. Binding records remained intact. Original UTC baseline
report hashes were verified unchanged by the final audit.

## Evidence and harness notes

Owner-local evidence is under `output/qualification/rtc-regression-2026-10-07`;
`acceptance.json` binds per-board reports and image hashes. The RAM-only probes
are built by [build_v2_board_regression.py](../tools/build_v2_board_regression.py),
with the existing public ABI and probe sources. No vendor firmware is published.

Initial harness attempts are retained separately. Direct monitor memory display
of the I/O page was correctly refused; a RAM probe replaced that inappropriate
snapshot request. The shared I2C result was initially read after HOLD, when the
monitor's time READ had replaced it. The revised RAM client copies its result
before HOLD. Its serial output already showed the correct read/denial values.
These were corrected harness assumptions, not firmware failures.

This acceptance covers the listed physical cases. No new flash erase/program
test, power-cycle retention test, battery-removal test, physical interrupted-flash
test, or native RTC/I2C call is claimed. Existing installation/binding and host
fault-injection evidence remains separate. User RAM is still $0200–$64FF inclusive
with optional service software installed, even without EDU. Hardware absence
does not release the $6500–$66FF reservation.
