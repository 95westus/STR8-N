# STR8-N v1.30 FTDI host-presence LED board test — 2026-09-06

> **Historical candidate:** STR8-N v1.31 first promoted this image by changing
> only its final identity digit, then added private I/O activity. See the
> [version report](STR8N_V1_31_VERSION_BOARD_TEST_2026-09-06.md) and current
> [activity report](LED_IO_ACTIVITY_BOARD_TEST_2026-09-06.md).

The first LED follow-on passed on the W65C02SXB/EDU at COM4, 115200 baud.
This candidate replaces the unsampled `$41` STR8-N command wait with `$43`
when FTDI PWE# is asserted low and `$21` when PWE# is high. Public raw console
services remain LED-neutral.

The earlier `$00`, `$01`, `$41`, and `$F0` ownership and flash-safety results
remain preserved in the
[minimal-slice board report](LED_STATUS_BOARD_TEST_2026-09-06.md). This report
covers the 12-byte resident host-presence addition and its exact replacement
top image.

## Exact artifacts

| Artifact | SHA-256 |
| --- | --- |
| Bank-3 `$F000-$FFFF` BIN | `F69B2C5127B1AD19CBA998BC608A8574A4B6DCA03128FAB40E22A707CB3973B3` |
| Guarded top updater S19 | `5FE565170EEC6B7B06A041624170BD0FE5B1073B305141F0F64418217BFE8E23` |
| Production worker S19 | `CBD477AD62A0FF7FC14DE22F3575C7B05834C973A5DF622A6678DEF6C4577713` |
| Local 17-byte PWE# probe S19 | `9893CAE20B5D9339A237850D38576D4CBE0F9A8703CFF122CD0FAFE0A81D65BC` |

The linked resident occupies `$F000-$FD0E` (3,343 bytes). The worker occupies
`$0200-$045F` and is stored at `$FD50-$FFAF` (608 bytes), leaving 65 erased
bytes at `$FD0F-$FD4F`. This is one byte above the enforced 64-byte minimum.
The public selector prefix remains `$0200-$0228`.

## Installed-image result

The first S19 transport reached the updater, refreshed and verified the B1:F
backup, and stopped at the second confirmation. An empty confirmation safely
reported `ABORT - NO ACTIVE TOP UPDATE`; Bank 3 was not erased. This retained
cancellation demonstrates that the final guard remained effective.

The clean retry again required and verified `BACKUP B1F`, then accepted the
exact `STR8-N 1.30` confirmation. It reported:

```text
STR8-N 1.30
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 1.30 VERIFIED; RESET
```

RESET reached the normal selector and warm HIMON handoff. Entering Bank-3
`$F000` again and selecting `S` reached the newly installed `STR8-N>` prompt.
The operator observed `$43`, proving that the installed command loop sampled
the configured FTDI PWE# input low and published RUN + HOST + RX_WAIT.

## PWE# high/low result

The board is USB-powered, so unplugging its only cable cannot preserve a
no-host display. A RAM-only probe was therefore loaded through STR8-N. Its
complete 17-byte loop is the same PWE# predicate and output sequence guarded
in the resident image:

```text
A9 20 2C E0 7F D0 04 A9 43 80 01 1A 8D A0 7F 80 EF
```

It samples active-low PWE# on VIA Port B bit 5, writes `$43` when configured,
writes `$21` when unconfigured/suspended, and repeats. It does not alter flash.

With the probe running, the operator used Windows 11 Device Manager, selected
**View → Devices by connection**, and disabled the FTDI **USB Serial
Converter** parent rather than the COM4 child or USB hub. USB VBUS continued
to power the board. The display changed from `$43` to `$21`. Re-enabling the
converter returned it to `$43`. This confirms the board wiring, active-low
PWE# polarity, and both output values.

The installed command loop samples PWE# only when it enters a command wait; it
does not continuously monitor a host transition during an existing wait. The
RAM loop was required to make the transition observable while COM4 itself was
disabled. The resident `$21` branch is also covered by an exact-byte host
check, while `$43` was observed directly at the installed prompt.

The compact retained serial record is
[LED_HOST_PRESENCE_BOARD_TRANSCRIPT_2026-09-06.txt](LED_HOST_PRESENCE_BOARD_TRANSCRIPT_2026-09-06.txt).
The append-only owner-local JSONL remains under `BUILD/v1.30/local/` and is
excluded from published release artifacts.
