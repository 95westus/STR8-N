# Four-board RTC tick alignment

PASS: all four measured RTC-minus-NIST intervals are within the requested ±100 ms target. The largest verified absolute interval endpoint is 69.0 ms.

| Board | RTC minus NIST, ms | Corrections in successful run |
|---|---:|---:|
| 2205 | +1.6 to +69.0 | 2 |
| 2512 | -45.7 to +21.1 | 1 |
| 2604 | -59.4 to +7.4 | 2 |
| 2609 | -35.1 to +37.2 | 1 |

The program uses host/board handshakes to measure ticks, calibrates an autonomous bounded CPU delay, pauses RTC timekeeping through RTCSEC, and measures and compensates the stop/restart response. NIST packets and performance-counter timing intervals are retained. These compatibility intervals include reference uncertainty; this is not a claim of exact zero error or permanent PPS lock.

All four control/trim pairs remain unchanged: 2205 80/11 (−17), 2512 80/0C (−12), 2604 00/0C (−12), 2609 80/0E (−14). PF evidence/history are preserved. Exact borrowed RAM blocks and original prompts were restored. No phase routine writes EEPROM, flash or SRAM configuration. Old drift points/baselines remain, and new post-adjustment baselines passed their saved-capture audits.

2604 recovery: initial M-command staging failed; even a short M command stopped its current firmware path from responding. The owner authorized and physically performed two CPU resets while keeping power connected. Saved RAM was restored and verified using the established S-record L loader. The finished program never sends M to 2604. CPU resets are logged separately from power events; no recovery remains pending.

The final audit also repaired a rebaselining bug that dropped pinned EUI identity metadata. Identity was recovered from the archived original baselines; three saved capture batches were re-audited without opening ports or changing clocks. New rebaselining preserves EUI and archives prior baselines.

Validation: 30 CPU/I2C-model cases across 65C02 and 65C816 emulation; host staging/refusal/range/S-record/reference/feedback/rebaselining tests; live read-only qualification on all four boards; final tick, RAM, trim/PF and fresh campaign-baseline audits.

Use tools/rtc_fleet.py --check-phase, then --align-ticks --phase-validation <summary.json>. See docs/RTC_TICK_ALIGNMENT.txt. Default collection and the hourly schedule remain read-only.

Device reference: [Microchip MCP79410/11/12 datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/MPD/ProductDocuments/DataSheets/MCP79410-MCP79411-MCP79412-Battery-Backed-I2C-RTCC-DS20002266.pdf).


## Validation evidence

These are the saved November 1, 2026 hardware results. Repository integration reruns offline checks; it does not repeat the clock adjustments. Raw serial captures, RAM backups, campaign state, and board receipts remain owner-local under `output/qualification/`.

| Board | Owner-local receipt relative to `output/qualification/` | SHA-256 |
| --- | --- | --- |
| 2205 | `rtc-phase-20261101T092303Z/2205/report.json` | `95189b8d7c777ed804551917ace6e44c6e3a940ed3e060396d6834f03bb48d8e` |
| 2512 | `rtc-phase-20261101T091405Z/2512/report.json` | `7d2ad25cfb1d32c6884bdeca97d8c0bc55afef41187571c597f2b094b5e58f98` |
| 2604 | `rtc-phase-20261101T092820Z/2604/report.json` | `030e8d349c02a1076ef0843f6c8d794c9d7cc3a01d32ee3290d701d16e7a4593` |
| 2609 | `rtc-phase-20261101T091405Z/2609/report.json` | `dc4907afbe433a9e0661d7b0d11ffc259af40c816b6a7e3a9e5dcbf90f5165bc` |

Qualified board image SHA-256: `28c6ad2421d2d6425dee27605dca5df3d3f58e4efcfb4766cf0f4fffc8550b92`. The [repository source](../src/rtc-phase/phase.asm) rebuilds this same 1077-byte image. The [paper](RTC_TICK_ALIGNMENT.md) explains the measurement and its scope.
