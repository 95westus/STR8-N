# Beta23 preserving soak: 2604 and 2609

The user-approved six-hour run completed on October 11, 2026, from
**16:09:42 to 22:09:43 CDT** (6.000249 hours). The safe deadline helper stopped
only the host test worker after verified restoration and port release. Boards
remained powered; independent RTC drift collection remains active.

| Board | Complete passes | Partial next pass | Recorded units |
| --- | ---: | ---: | ---: |
| 2604 / COM5 | 17 | 9 units | 298 |
| 2609 / COM8 | 17 | 9 units | 298 |

All **596 recorded units** reported success within their documented scope,
including expected exclusions/refusals. No unexpected failures or unresolved
SRAM restorations were recorded. These counts include the excluded saved-example
unit on 2604; they do not mean every destructive or unavailable command was run.
The separate initial 16-unit smoke round also passed and is not added to these totals.

RTC SRAM pattern writes were verified and original bytes restored after every
chunk; scoped external SRAM writes likewise restored and verified their originals.
Repeated EEPROM/factory-data and full flash readbacks matched the soak originals.
UTC, calibrated trim/control, EUI/binding and retained outage history checks passed.
Wig-wag and left/right LED patterns ran between units. Destructive commands,
resets, allocation changes and EEPROM history initialization were excluded.

The 18:45 CDT four-board drift collection passed fresh NIST and baseline/report
hash checks while the soak yielded its ports. The user requested early resumption
after that successful sample; worker progress was verified afterwards. The next
sampling reservation was also honored. Drift collection continues independently.

The final policy was six hours or **15% total Codex account usage**, whichever
came first, checked every 15 minutes. Completion was caused by the six-hour
deadline; reported account usage at closeout was **7%**. The earlier soak-budget
ledger policy was superseded. The deadline helper's final JSON still contains a
legacy `threshold_percent: 20` default alongside `used_percent: null`; it was a
time stop, not a usage-triggered stop. The completed soak monitor was removed.

Owner-local evidence: `output/qualification/beta23-soak-2026-10-11-2109Z/`,
including per-unit reports, restoration records, original data and deadline logs.
Final `status.json` SHA256:
`12768082b834396bf6a5076ec9d57f2ff77dcd7640bfc9cf8497095dd91239be`.
Raw captures and board backups remain excluded from Git/release packages.

This closes the revised **six-hour exercise**, not the original **48–72-hour
soak qualification**. That longer elapsed-time evidence is not claimed.
APPS defect STR8N-004 remains **Deferred**, awaiting the user's direction.

## Preserved state

UTC, calibrated trims, control settings, RTC identity, outage evidence,
EEPROM allocation, flash and stored programs are retained. No reset, power
cycle, EDU mode change, flash operation, history initialization, ACK, CLEAR,
ACCEPT EUI, clock setting or allocation/format/repair operation is included.
The deferred 2604 EEPROM initialization remains deferred during drift testing.

The current immutable drift campaign is
`rtc-trim-validation-2026-10-11-204223Z/baseline-index.json`, SHA256
`0eafd3fc7b952a2b77f02eb2d3231e39da4562b99f64efaa6c797ed52c065dd2`.
2604 retains trim −12/control $00; 2609 retains trim −14/control $80.
Changing the active campaign stops the soak for review.

## Repeated tests

| Program/path | Included commands/tests | Excluded operations |
| --- | --- | --- |
| Monitor | Help, TIME, APPS, all bank tables, bank selection, maps, wear, boot configuration query, descriptor dump; verified RAM diagnostic uploads/execution | Persistent writes/install/erase/preferences, boot/reset, arbitrary execution |
| CLOCK 1.6 | HELP/?, R/TIME, S/STATUS, EUI, HISTORY, SHOW 1–4, TRIM and OFFSET queries, quit | All setters, ACK, CLEAR and ACCEPT EUI |
| EDU 1.2 | Status and quit | ON/OFF during the active drift comparison |
| SRAM 1.2 | Help/table and R/G missing-name refusal after confirming the name is absent | Save/delete/compact/format and unreviewed program execution |
| WORK 1.2 | Help and capacity query, including uninitialized refusal | Allocation changes, upgrade, repair and format |
| MAINT 1.8 | Help, maps, wear, tables, read/display editor, CRC, compare, quit | Persistent writes/transfers/erase/boot and editor modifications/staging |
| RTC SRAM | All four 16-byte chunks of $20–$5F, double-read backup, pattern write/read, original restoration/read verification | RTC time/control/alarm registers and EEPROM |
| External SPI SRAM | Rotating 64-byte ranges, double-read backup, pattern write/read, original restoration/read verification, protection/PCR checks | Management region $00000–$007FF and reserved final probe region |
| Preservation readback | Complete flash, bank by bank, and repeated EEPROM/factory data readback, compared to the soak originals | All persistent writes |

Only installed and reviewed non-destructive command paths are executed.
Uninitialized storage is tested as found; it is never initialized to increase
coverage. Persistent mutation commands are explicitly excluded, rather than
claimed as exercised. The stored SDEMO on 2609 is restored without executing,
compared byte-for-byte with its reviewed six-byte increment-and-HOLD program,
then run only after that check; its CPU scratch bytes are restored afterwards.
Other unreviewed saved programs are excluded.

The RAM-only RTC diagnostic enforces range/count checks before I2C access.
The [Microchip MCP79411 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf)
defines the 64-byte SRAM at $20–$5F. This diagnostic does not relax the public
I2C service's protection. External writes use the previously model-qualified
scoped hardware diagnostic, restoring the public protection latch after calls.

Each write test saves its original bytes to disk before writing. A restoration
failure stops the worker and retains the backup and `restore-state.json` for
recovery; it is never counted as a successful unit.

After each test unit, eight host-paced LED frames alternate between wig-wag,
shift-left and shift-right. The original LED output is restored afterwards.
The serial port is then closed before releasing the coordination lease.

## Drift coordination and evidence

The worker reserves 15 minutes before through 25 minutes after each scheduled
three-hourly :45 collection, beginning October 11 at 18:45 CDT (23:45 UTC).
The analyzer, status acquisition and UTC acquisition tools use the same serial
lease; pending drift acquisition takes priority over subsequent soak units.
Occupied ports are retried without terminating or taking over another owner.
Manual work should use those coordinated tools or wait for an idle lease.

`tools/run_beta23_soak.py` writes owner-local configuration, live `status.json`,
serial transcripts, original SRAM bytes, restoration state and per-unit reports
under `output/qualification/`. These files are excluded from the public package.
`tools/test_v2_soak_probes.py` checks the actual RTC I2C model, range refusals,
restoration, driven GPIO state and EDU guard before hardware writes.
The worker inhibits Windows idle sleep while running and releases that request
on exit; it does not change the power plan or keep the display on.

Acceptance requires the full elapsed interval, successful restoration receipts,
reviewed command coverage, continuing drift evidence and no unexplained retained
state changes. Functional qualification on other boards does not substitute
for this two-board elapsed-time record. The deferred ACIA receive limitation
on 2512/2205 remains documented.

## Open observation

Read-only inventory on both boards showed `APPS` printing eight corrupt $FF
names followed by `not installed`, while `T 1`/`T 2` correctly listed MAINT,
CLOCK, SRAM, WORK and EDU. This remains a deferred beta23 qualification issue;
the soak launches programs through their verified stored-record names.
