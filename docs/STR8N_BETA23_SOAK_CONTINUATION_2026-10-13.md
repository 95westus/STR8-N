> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta23 preserving soak continuation: 2604 and 2609

On October 13 the user authorized another **48 hours** on 2604/COM5 and
2609/COM8, yielding to the ongoing RTC drift collection. This is a new
elapsed-time interval; it does not combine the earlier six-hour exercise into
a continuous 48-hour claim.

The continuation started **October 13, 2026 at 20:43:44 CDT**, with its
48-hour deadline **October 15 at 20:43:44 CDT** (October 16 01:43:44 UTC).
Worker PID: `10956`. All **eight hardware sector-reader preflight units**
passed: B0–B3 on each board, full-byte direct-monitor comparisons, restored
bank-PCR receipts and unchanged retained RTC state. The preflight is separate
from the timed run.

The existing preserving command, RTC SRAM, external SRAM, EEPROM, full-flash
and LED exercises continue. Flash and EEPROM comparisons retain the original
October 11 baseline files. UTC, trims, control, identities, outage history,
EDU mode, flash and stored programs remain unchanged. The same immutable
post-trim campaign is required; a changed campaign stops the worker.

## Added RAM sector reader

[`soak-sector-read.asm`](../tools/v2-rtc/soak-sector-read.asm) executes at
`$4000` and copies one aligned 4 KiB sector from a selected B0–B3 overlay into
`$2000–$2FFF`. Parameters are bank at `$3000` and sector high byte at `$3001`
(`$80,$90,...,$F0`). Status/completed pages return at `$3002/$3003`; the
complete bank PCR before selection/after restoration returns at `$3004/$3005`.
It validates inputs, preserves CPU flags and the bank PCR, and returns through
the RAM HOLD entry. It issues no flash writes or erase commands.

Four new soak units cover B0, B1, B2 and B3 on both boards. Each round advances
one sector, covering all eight sectors over eight rounds. Each 4096-byte RAM
result must match an independent direct monitor dump of the same bank/sector.
The runner records bytes, SHA256, restoration and comparison receipts.

The linked-machine-code model passed **128 valid bank/sector/PCR cases** and
**five invalid-input refusals**, checking byte-exact results, exact flash-read
addresses, restored PCR/flags/stack and bounded RAM writes. The existing RTC
SRAM range, actual I2C model, preservation and EDU guard checks also pass.

Initial hardware integration attempted to inspect the bank PCR with monitor
`D`; the monitor correctly refused protected I/O before the new program ran.
The probe now returns PCR receipts through RAM. That stopped preflight remains
archived separately and is not counted as successful soak evidence.

## Drift priority and records

Each short test owns the shared serial lease only until original data is
restored and its port is closed. Pending drift acquisition takes priority over
the next soak unit, including additional samples between the regular slots.
The regular reservation remains 15 minutes before through 25 minutes after
each three-hourly :45 collection. No drift schedule or calibration changes
are part of this continuation.

Owner-local records:

- Sector preflight: `output/qualification/beta23-soak-sector-preflight2-2026-10-13/`.
- Continuation: `output/qualification/beta23-soak-2026-10-13-continuation/`.
- Active worker registry: `output/qualification/active-beta23-soak.json`.

The continuation's `config.json` records exact UTC start/end, boards, pinned
campaign and probe receipt. `status.json`, per-unit reports, serial captures
and restoration files record progress. Raw captures, board data and backups
remain owner-local and excluded from release packages. Completion is only
claimed after the new elapsed interval and its preservation evidence pass.

## Early-stop closeout, October 14

The worker exited at **October 14, 2026, 16:03:43 CDT**, after
**19.332955 elapsed hours**. Its final status records `completed`,
`completion_reason: user-shortened-duration` and `target_hours: 0.001`,
although the original configuration still contains the 48-hour deadline.
These are the stop helper's recorded fields; this monitor did not request
the stop or independently establish its authorization. **The 48-hour soak
requirement remains unfulfilled.** No worker restart was performed.

| Board | Complete rounds | Successful recorded units | Sector-reader checks |
| --- | ---: | ---: | ---: |
| 2604 | 46 | 966 | 184 |
| 2609 | 46 | 966 | 184 |

All 1,932 per-unit reports pass with retained RTC preservation. Each board's
184 sector-reader checks cover all 32 bank/sector combinations and report
byte-exact direct-monitor matches, restored bank selection and no flash
writes. Counts include documented exclusions and refusal checks; they do not
represent destructive-command coverage. No outstanding `needs_restore`
records or stderr errors were found. The final stop receipt records verified
restoration and released ports; process inspection confirmed PID 10956 exited.

Final `status.json` SHA256:
`13ac9d39e711327e2ba945e66ff9214caec68fcbdfc1a95f7199879a43bad151`.
The prior six-hour run and sector preflight are excluded from these counts
and from this elapsed interval. The soak health-check automation is retired;
independent drift schedules are unaffected by this closeout.
