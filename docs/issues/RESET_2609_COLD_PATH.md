# STR8N-002: 2609 RESET-button cold-path observation

Status: **Closed**, 2026-10-08. Board 2609, COM8, W65C816SXB with EDU. Observed during
[SPI Phase 6](../STR8N_V2_SPI_PHASE6_2026-10-08.md), beta14 generation 23,
CLOCK 1.5, SRAM 1.1 and WORK 1.0. The user reported that the earlier presses
used the wrong button. A continuously captured main SXB **S2/RESB** press
passed the physical cold-reset check; no reset-button or firmware fault was
established. WDC identifies S2 as RESB and S1 as NMIB.
[WDC getting-started guide](https://wdc65xx.com/gettingstarted/816-sxb-getting-started/).

After a successful WORK claim, the private workspace session latch `$66AF`
was 1 and the committed handle was `0300010000000400`. Two reported physical
RESET-button presses left `$66AE/$66AF` at `01/01`, read before another WORK
call. 2205's corresponding test produced `01/00` and stale-handle refusal.

2609's main-power restart produced `01/00`, retained the saved SRAM program,
and rejected the previous handle. The documented RAM RESET route through
`$7E64` also produced `01/00` after full SRAM restoration. All four installed
flash banks, both monitor slots, RTC settings, EUI and EEPROM checks passed.

The verified F-sector vector points to `$F004`. That cold path clears system
state, including SVC_ACTIVE, then copies the complete gateway template whose
latch default is zero. Ordinary HOLD/reentry deliberately preserves it. No
816 branch preserves the latch on the cold path, and autostart is disabled.
Actual CPU RESET forces emulation mode/zero bank registers and fetches the
reset vector. [WDC W65C816S datasheet, section 2.25](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf).

The observation is consistent with the cold path not being reached by those
button actions. It does not identify the cause. Earlier beta13 qualification
also recorded reset-only startup problems followed by a successful power
cycle; that history is context rather than proof of a shared cause.

Evidence remains ignored under the Phase 6 board folder: `storage-reset-check`
and `storage-reset-check-2` serial logs, VIA snapshots, `storage-power-check`
and `final-check/software-reset.txt`. Original SRAM was fully restored and the
cleanup software RESET left the latch zero. UTC/trim were never set; boot
journaling preserves the new main-power outage.

Resume/close condition: identify the actual button/route used, capture a main
SXB RESET while listening continuously, and read the latch before any WORK
operation. Close after a verified physical cold restart gives `01/00` and
rejects the previous live handle while retaining the saved program. If it
still fails, investigate button/RESB routing with board-specific evidence;
do not count a banner or ordinary monitor reentry as a cold reset.

## Resolution and closeout

At 17:02 UTC, the correct S2/RESB press was recorded continuously, including
bootstrap dots, both generation-23 monitor checks and the beta14 banner.
Before WORK was called, `$66AE/$66AF` was `01/00`. The earlier live handle
`0300010000000100` returned stale `$4B`; the six-byte `RESETCHK` image remained
eligible and restored byte-exactly. The temporary first 8 KiB was independently
archived twice and restored/verified afterward. No flash or RTC setting changed.

VIA1 IFR was `$00` both before and after this correct reset; IER `$80`,
PCR/ACR/DDRB `$00`. Five later passive snapshots retained those values without
reading Port B or acknowledging flags. The earlier main-power `$1A` snapshot
is a separate startup observation, not an explanation for the mistaken button
test. `$1A` is CA1/CB1/CB2 edge evidence; all sources were disabled. The same
SPI guard protects both CPU boards and remains unchanged.

The full 128 KiB SRAM and all four flash banks were reread and match Phase 6's
final images/archives. CONTROL `$80`, trim `$00`, backup/running time, protected
EUI and factory EEPROM data are preserved. A separate outage at 16:55 UTC,
journaled at 16:59:36 as sequence 11/slot 3, predates the 17:00:23 captured-test
preparation. It remains recorded; other outage slots are unchanged. Chip outage
fields have minute precision and no year; the dated journal capture supplies
context. UTC/trim were not set and no manual ACK was issued.

Ignored evidence: `output/qualification/reset-2609-2026-10-08/s2-capture-2`,
including `physical-reset.txt`, `report.json`, `closeout-index.json` and its
selected closeout folder. The initial `s2-capture` attempt hit the monitor's
direct-I/O display guard before any SRAM mutation; it is retained as diagnostic
history. Full Phase 6 hardware acceptance now includes the corrected S2 result.
