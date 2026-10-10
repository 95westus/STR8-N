# SPI Phase 6: installed boards and qualification

Recorded 2026-10-08. **Beta14 generation 23, CLOCK 1.5, SRAM 1.1 and WORK 1.0
are installed on 2512, 2205 and 2609.** Installed functionality and exact
preservation checks pass. The user identified the earlier wrong-button presses
on 2609; a continuously captured **S2/RESB** reset subsequently cleared the
workspace latch, retained the saved SRAM image and rejected the old handle.
[STR8N-002](issues/RESET_2609_COLD_PATH.md) is closed and full hardware acceptance
is complete within the stated scope. No commit/push or packaged release is
part of this phase.

## Installation and files

| Board | Port / CPU | EDU | Result |
| --- | --- | --- | --- |
| 2512 | COM4 / W65C02S | No | Resident SPI software, optional-hardware refusals, flash utilities and regression passed |
| 2205 | COM3 / W65C02S | Yes | Both providers, workspace, physical RESET and main-power retention passed |
| 2609 | COM8 / W65C816 emulation | Yes | Both providers, workspace, main-power, software RESET and captured physical S2 RESET passed |

All complete 128 KiB flash images were read independently twice before writes.
RTC status/outage history and ordinary EEPROM/factory data were archived before
installation. Both complete 128 KiB EDU SRAM arrays were read twice; they still
matched the original Phase 2 archives. No battery removal was performed.

The six-sector installer recipe was prepared and modeled from each fresh exact
backup, including stale-source and corrupt-payload refusal. Installation checks
the live full source again before mutation. B3 C/8/9/E/B/A were updated;
fixed F, B0/B1 and the EUI tail were retained. Both monitor slots and complete
post-RESET four-bank readbacks match. B2 was then deliberately extended with
ordinary saved-program records; CLOCK's existing bytes remain unchanged.

| B2 address | Record | Contents |
| --- | --- | --- |
| `$8000` | CLOCK | Existing CLOCK 1.5, unchanged |
| `$A000-$AE57` | SRAM | SRAM 1.1; load `$4000-$4E3F` |
| `$AE80-$AE9D` | SDEMO | EDU boards only; six-byte flash/SPI execution demonstration |
| `$B000-$C211` | WORK | Corrected WORK 1.0; load `$4000-$51F9` |

These use normal flash saved-program space, not new resident service sectors.
`R SRAM` and `R WORK` are available after restart. Their images were checked
against the qualified hashes before loading/writing, RAM readbacks were checked,
and the full B2 final image matches the planned record bytes.

Qualification temporarily initialized the EDU SRAM layout, then restored and
compared **every byte of each original 128 KiB array**. Final state preserves
the original arrays; no fresh layout is left implicitly initialized. To start
using a new layout, explicitly initialize it through WORK with its documented
FORMAT SRAM confirmation after preserving any retained data you need.
Flash SDEMO remains as a deliberate demonstration record; the temporary SPI
copy and workspace table were removed by full-array restoration.

## Hardware checks

- Public raw SRAM WRITE stays denied, including after cold software RESET.
  Explicit SRAM usability probe, READ and workspace operations work on EDU;
  missing hardware is bounded on 2512 in all caller banks.
- WORK's 16/32/48/64 KiB split changes, exact capacity reports, owner/offset
  bounds, release/stale-handle checks, live-claim resize conflicts and verified
  data transfer passed on both EDU CPU types and all caller banks.
- The identical six-byte SDEMO image restored and ran from flash and SPI.
  The two-row RAM cache example printed `W: 00` after writing/checking its
  eight-row workspace table and releasing its claim.
- Workspace handles survived ordinary HOLD and WORK reload. 2205's physical
  RESET invalidated the earlier handle while preserving its saved SPI program.
  Both main-power cycles retained that program and invalidated the previous
  workspace handle. Cold software RESET cleared `$66AF` on all three boards.
- RAM ABI, actual BRK/VIA1 timer IRQ, registers/stack/RTI, interrupt pointers,
  VIA state, RTC all-bank reads, managed I2C reads/raw EEPROM denial, service
  RAM/flash guards, CLOCK reads/canceled controls and MAINT guards passed.
  2609's E=1, D/DBR/PBR=0 state was verified. These are the automated physical
  tests for this phase; a new physical NMI/native-NMI round was not performed.
- Neither UTC, trim nor remembered EUI was set. Both clocks continued running
  with backup enabled, CONTROL `$80`, OSCTRIM `$00`, coarse mode off.
  EEPROM/factory/EUI content remained unchanged except the single expected
  power-fail journal event on each EDU board. Other three outage slots match.

2609 exposed disabled pending CB flags after restart: IFR `$1A`, IER `$80`,
PCR/ACR/DDRB zero. The SPI driver correctly refused. The registers were archived
before the qualified setup helper acknowledged only those disabled flags;
IFR became `$02`. The driver itself never silently acknowledged them. Later
power restart required the same explicit setup. This behavior is retained as
a hardware qualification condition, not hidden by the driver.

The correct S2 reset follow-up observed IFR `$00` before/after and in five
later passive snapshots, with the other controls unchanged. Both failed earlier
button checks had IFR `$02` with CB flags clear. These distinguish the button
mistake from the extra CB flags at main-power startup. WDC defines IFR bits 4/3
as CB1/CB2 and IER `$80` as no enabled sources; disabled edge events can still
latch. [WDC VIA datasheet, sections 2.14/3.9](https://www.wdc65xx.com/wdc/documentation/w65c22.pdf).
The electrical cause of different startup input edges remains unmeasured;
there is no CPU-specific SPI acknowledgement policy. Driver behavior is unchanged.

## RTC power-cycle evidence

| Board | New journal sequence / slot | Down / up (UTC convention, minute precision) | Final clock read |
| --- | --- | --- | --- |
| 2205 | 6 / 2 | 10-08 15:47 / 10-08 15:47 | 2026-10-08 15:59:41 |
| 2609 | 10 / 2 | 10-08 15:45 / 10-08 15:45 | 2026-10-08 15:59:41 |

Boot logged and verified the new event, acknowledged the chip latch, and left
UTC running. Same-minute fields do not establish exact duration. Original UTC
drift baselines remain untouched. The journal capture contains a UTC-convention
date/time; the chip's own outage fields lack a year and seconds.

## Fix and measured ownership

Pre-rollout review found that WORK FORMAT could preserve corrupt committed
claims when retaining a valid session. FORMAT now invalidates and verifies all
four claim markers on every path. Recovery from corruption, 213 FORMAT and
205 UPGRADE write cuts and epoch/revision/ticket exhaustion pass models, along
with the existing 133 resize/100 claim cuts and actual SPI integration. WORK
is 4,602 bytes, including 542 bytes of private state; the client is unchanged.

The resident image and permanent reservation are unchanged from the Phase 4
candidate: `$6500-$66FF`, application top **`$64FF`, inclusive, even without
EDU**. Installed extension ownership does not depend on hardware presence.
WORK occupies ordinary application RAM while loaded; SRAM temporarily borrows
monitor staging/cache RAM. Reload SRAM after returning to the monitor or using
other staging users. Native service calls, crypto, alarms/MFP configuration,
automatic compaction and assembler/session recovery remain deferred.

## Evidence

Owner-local evidence is under `output/qualification/spi-phase6-2026-10-08` and
is ignored/untracked. Its `acceptance.json` binds repeated archives, fresh-source
models, installed-image hashes, utility images, reports, restored arrays and the
corrected 2609 S2 reset evidence. Each board's `final-check` contains four complete final
flash images plus repeated EEPROM reads and clock/history/EUI transcripts.

Restored SRAM SHA-256:

| Board | SHA-256 |
| --- | --- |
| 2205 | `7cd6b6850f512192b127e1a6829c98651d19f398e91bd348b4d67fb95be77caa` |
| 2609 | `0e769960d5e945c1b3cab9c5d496105db91a2f14c6b0d70ff558534c19757bac` |

Both EDU final B2 images hash to
`ba986fd0d624b82486720e44c17f5475ce98d7177d65a4a6362ac8a896e6c96a`.
2512's image excludes SDEMO. B0/B1 are byte-identical to fresh backups and
each B3 is byte-identical to its qualified installer expectation, including
retained identity bytes. Audit with `tools/audit_v2_spi_phase6.py --root` and
`tools/check_no_board_backups.py --history`; no raw backups enter Git or ZIPs.

The ignored reset follow-up also contains a fresh full 128 KiB SRAM/four-bank
readback, identical to these images, and verified cleanup. A separately recorded
2609 outage at 16:55 UTC was journaled before the S2 diagnostic as sequence 11;
it is preserved with the other three slots. EUI/factory data, UTC and trim remain
unchanged. The qualification audit includes the follow-up through its stored
reset-resolution index. Phase 7 delivery remains separate.
