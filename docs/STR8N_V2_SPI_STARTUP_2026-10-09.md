# Beta22 unified SPI startup candidate and board qualification

Beta22, generation 31, is one firmware for W65C02SXB and W65C816SXB in
emulation mode, with optional EDU. Board 2604 is excluded from this run.

The sealed cold-boot status asset now handles idle disabled VIA CB flags before
the first allocation read. It refuses enabled CB interrupts, nondefault CB
modes, shift/latch owners, driven SPI pins and resident busy owners. Explicit
TIME/EDU queries do not acknowledge pending CB flags. The resident SPI API
remains conservative. EDU OFF skips the device path.

The exact linked guard passed 46 executed ownership/status cases. The integrated
model passed recovery of the observed 2609 startup flags, active IRQ refusal and
read-only preservation. Local-time/CLOCK, offset setup, quiet A/B returns and
public RTC/service lifecycle suites passed. The asset uses 2551 of 2558 code
bytes. CLOCK 1.6 and the local-display asset are unchanged from beta21.

Owner-local evidence is under
`output/qualification/beta22-all-2026-10-09`; raw banks and device images remain
ignored. `flash-manifest.json` pins the build, candidate check, board-specific
plans, installers, exact-image model reports and preparation/install scripts.
Every board had two matching full four-bank backups. Each installer model
passed exact final images, stale-preimage refusal and corrupt-payload refusal.

| Board | Source | Update | Saved EDU | Retained trim |
|---|---|---|---|---|
| 2512 | beta20 | 12 modeled sectors; relocate CLOCK 1.6 | OFF | RTC unavailable |
| 2205 | beta20 | 12 modeled sectors; relocate CLOCK 1.6 | ON | -18, normal |
| 2609 | beta21 | 5 modeled sectors; CLOCK unchanged | ON | -14, normal |

Both EDU boards had two matching complete 128 KiB SRAM readbacks and repeated
EEPROM/factory inventory before installation. RTC status, outage history and EUI
were archived. No UTC, trim, EEPROM or SRAM data changes are authorized by this
display/startup upgrade. Flash metadata wear counts and monitor generation are
updated; saved EDU mode, B0, other records, provider, identity tail and fixed
recovery core are preserved.

All three upload runs reported `MIGRATION VERIFIED; PHYSICAL RESET REQUIRED`.
Receive-only physical startup capture completed, with TX=0 and DTR/RTS
inactive. Post-reset hardware qualification passed: exact four-bank image,
saved EDU mode, weekday/local/trim TIME output, quiet M1 return, three A/B/A
software cold boots, SRAM access without manual acknowledgment, complete SRAM
comparison and unchanged EEPROM/history/EUI/trim checks. Two physical resets
were captured per board, and post-repeat SRAM READs succeeded from all four
caller banks on both EDU boards, without manual acknowledgment. Read-only VIA
snapshots showed IFR=$02, IER=$80 and idle PCR/ACR/DDRB. The 46 active-owner
refusal cases were model tests of the exact installed guard, rather than
deliberate hardware ownership changes. STR8N-003 is **Closed**; the three-board
evidence audit is `qualification-summary.json`, with per-board qualification
reports. Native 816 mode and board 2604 remain outside this qualification.
