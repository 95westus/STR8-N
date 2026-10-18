> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta24 bounded startup FIFO drain — October 14, 2026

2609 now runs verified beta24 generation 35 from `BUILD/v2-startup-fifo`, with
one FTDI hardware
receive FIFO drain immediately after initial slot selection and before the
startup-key window. It stops at the first empty poll or after 1024 bytes,
without waiting for additional input, then clears the software RX queue.
There is no second drain between the dots and chooser. Fresh A/a/B/b select
the validated monitor; other keys skip the dots and retain the timed chooser.

The bound prevents continuous incoming data from delaying boot indefinitely.
It does not purge host-side USB buffers; data arriving after the drain, or
remaining beyond the byte cap, is input for the newly opened window.

This update and hardware qualification are scoped to **2609 only**. Generation
34 on 2604 is retained. Both monitor slots and MAINT's core-identity guard are
matched to the new F core. The twentieth RAM-edit service word is retained.
Shared journal/CRC/router entry addresses, RAM worker/vectors, E launcher,
RTC/SPI services and sealed display helpers are unchanged. Compact recovery
messages reclaim the 18 bytes occupied by the drain routine, keeping F at
4061 bytes before the hardware vectors; update commands and confirmation
syntax remain unchanged.

Instruction-model suites pass: stale byte counts from 0 through 8192, exact
1024-byte termination, software-queue clearing, fresh A/B and ESC-to-menu-B
handoff, disconnected USB, slot refusal, RAM edit, NAME including 20 interrupted
writes, timezone including 13 interrupted appends, compact boot, storage
transfers and STR8N-006 named/unnamed power-fail output.

On generation 34 hardware, a queued B injected 0.2 seconds after J3 echo
selects B before any dot. After the update, repeating that calibrated input
phase with A, B, ESC and Enter discards each byte: all 160 dots and the timed
default A boot remain. Fresh keys after the drain still select A/B or skip
the dots normally, and the next menu selection is retained.
Earlier, shorter injection delays were consumed before reset and were not
accepted as evidence of hardware FIFO behavior.

2609's complete flash backup is independently verified twice. The backup-bound
five-sector installer (B3:C/F, B1:8, B3:B/A) passes exact rehearsal and stale
backup/corrupt payload refusal. Fresh retained-memory reference, installation,
physical RESET capture and the complete final hardware retest pass.

| Check | 2609 result |
| --- | --- |
| Physical RESET, both generation 35 slots valid | PASS |
| Queued A/B/ESC/Enter discarded before input opens | PASS |
| Fresh A/a/B/b selection and RAM write/readback/restore | PASS |
| Fresh other-key skipping, menu A/B, S recovery and no-key timing | PASS |
| RAM ABI, actual BRK/VIA1 IRQ and command regression | PASS |
| All four flash banks equal the exact plan | PASS |
| Entire 128 KiB SRAM equals the fresh reference | PASS |
| EEPROM, history, identity, control and trim preserved | PASS |

The 1024-byte cap and oversized/continuous-input bound are qualified in the
instruction model, not by flooding the physical board. Name `2609`, EDU ON,
offset −05:00, control $80 and trim −14 are preserved. All five planned erases
are accounted in wear metadata; tests make no configuration/name appends,
device initialization, UTC/trim/offset changes or history administration.
No new power-cycle, physical NMI/native-entry or extended-soak claim is made.
2604 was neither flashed nor hardware-tested during this FIFO-drain update.

Evidence: `output/qualification/startup-fifo-2026-10-14/2609`; model receipts
are in the candidate directory. Tools: `build_v2_startup_fifo.py`,
`test_v2_startup_fifo.py`, `deploy_v2_startup_fifo.py`,
`retest_v2_startup_fifo.py`, with shared startup-key build/deploy/retest tools.
