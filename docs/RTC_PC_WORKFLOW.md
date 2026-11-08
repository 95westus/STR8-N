# STR8-N UTIL RTC on the PC

This workflow uses frozen Foundation 0.3.0, the unified RC3 monitor and
CLOCK, and the MCP79411 on matching WDC SXB/EDU Rev D hardware. It supports
65C02 and 65C816 emulation. The kit adds a read-only executable in RAM
and Python tools. Its installed RC3 flash payloads match the verified kit.

## Files and setup

- `tools/rtc.py` provides collection, synchronization and trim calculation.
- `rtc/rtc-sample.json` gives the SHA-256, load address and entry address
  for the sampler BIN and S19. The 649-byte BIN runs at `$2000`.
- `rtc/sample.asm` is the sampler source. `rtc/sample.csv` is synthetic data
  for offline practice.
- Copy [the profile template](../firmware/memory-agent/profile.example.json)
  to a private location. Set the board ID, COM port, USB serial and CPU.
  Live operations use Windows FTDI serial and the kit's Python requirements.
  For a workstation already running STR8-N board jobs, use `--workspace`
  with that checkout so the tools share its serial lease.
- Leave the board at `REC>` or the MON `B3>` prompt and close other serial
  terminals. Choose a trusted UTC NTP host reachable over UDP port 123.
  Use a fresh private `--out` directory for each run.

Run the examples from the extracted kit root. Set these PowerShell variables
for your workstation:

```powershell
python -m pip install -r requirements-console.txt
$profile = 'private/my-board.json'
$server = 'your-ntp-host'
```

## Collect and calculate

Collect once per invocation. Repeat at separate times into the same CSV,
using a new run directory for every sample.

```powershell
python tools/rtc.py collect --profile $profile --server $server --csv private/drift-1.csv --out private/sample-01
python tools/rtc.py collect --profile $profile --server $server --csv private/drift-1.csv --out private/sample-02
python tools/rtc.py calc private/drift-1.csv
```

The tool verifies the board, F and the installed MON slot. It preserves the
sampler's RAM range, stages the exact BIN, executes it with `G 2000`, and
verifies restoration before writing the CSV. Each measurement bounds the RTC
offset using repeated observations across multiple ticks. Positive offset
means the RTC is ahead of UTC. The CSV records the device, reference, offset
interval, control and trim bytes, and outage evidence. Keep it private.

Collect at least three observations over at least 12 hours at one trim and
under representative conditions. Start a new CSV after a manual clock change,
trim change, reference change or interruption. The tool refuses to mix changed
register evidence or its own sync and trim segments. Keep the private
`*.rtc-segment.json` sidecar beside the same profile once created.

`calc` fits the rate of change in offset and reports the elapsed span, drift
in ppm and the drift interval compatible with the measurements. A positive
drift means the clock runs fast. It proposes a fine-trim value only when the
whole drift interval rounds to the same supported step. Collect longer if the
result is inconclusive. The MCP79411 fine-trim step is about 1.017 ppm.
[Microchip MCP79411 data sheet, digital trimming](https://ww1.microchip.com/downloads/aemDocuments/documents/MPD/ProductDocuments/DataSheets/MCP79410-MCP79411-MCP79412-Battery-Backed-I2C-RTCC-DS20002266.pdf)

Practice offline:

```powershell
python tools/rtc.py calc rtc/sample.csv
```

The synthetic clock runs fast by about +12.2 ppm and the example recommends
`TRIM -12`.

## Preview and apply UTC sync or trim

`sync` measures and reports the offset by default. `trim` without `--apply`
calculates from the CSV without opening a port.

**Caution for UTC SET.** SET targets a whole UTC second. The PC check passes
when the full measured offset interval is within ±1 second of UTC. SET can
move an already-close clock farther from UTC and still pass. Preview the
offset first. For sub-second work, use separate tick-phase alignment and
verify the resulting offset.

```powershell
python tools/rtc.py sync --profile $profile --server $server --out private/sync-preview
python tools/rtc.py sync --profile $profile --server $server --out private/sync-apply --apply
python tools/rtc.py trim --profile $profile --server $server --csv private/drift-1.csv --out private/trim-apply --apply
```

With `--apply`, review the live result and type exact `YES` at the host prompt.
The host verifies CLOCK's own confirmation before sending its final approval.
After SET, compare the measured offset intervals in `before` and `after` in
the run's `report.json`. TRIM requires a fresh, unambiguous calculation and
verifies the resulting control and trim registers.
Both operations preserve and verify owner RAM and zero page and start a new
collection segment. CLOCK applies its alarm, square-wave and power-fail
guards. Starting CLOCK can record a newly reached battery warning stage. An ambiguous write is recorded in the run directory for inspection
before attempting another operation.

Live read-only sampling passed on both CPU modes. The confirmed CLOCK command
sequences are covered by host simulations. Physical SET passed the PC check
on 65C02 from Stage 2 and on 65C816 emulation from the exact Stage 3 ZIP.
The RTC tool and sampler bytes match between those stages. On 65C02, the
packaged TRIM routine passed an owner-selected temporary −12 → −11 → −12
round trip with register readback and RAM/zero-page restoration. Those test
targets were supplied explicitly to the write routine. The normal CLI still
requires a calibration-supported proposal before applying a change.
The same packaged routine passed −14 → −13 → −14 on 65C816 emulation,
including register readback and RAM/zero-page restoration. See the
[combined RC3 qualification record](RC3_RELEASE.md) for package identity and
the remaining release checks.

## Manual sampler entry

The host performs these steps automatically. For a manual diagnostic, save
the original RAM range shown in the manifest before staging the image.
Use MON's S19 receiver to load the supplied S19 at `$2000`, or stage the BIN
bytes at that address. Verify them and use `G 2000`. At the sampler's `!`
marker, send a single lowercase `r` byte with no line ending. The reply is
`@`, status, 17 RTC register bytes and one XOR checksum byte, then the next
`!`. Status zero means a valid read. Status 4 means the snapshot crossed a
seconds rollover. Send a single lowercase `q` at a ready marker to return
through Foundation HOLD, then restore the saved RAM. The sample BIN is linked
for the MON entry at `$2000`. Use the MON loader instead of the `REC> L`
raw BIN path at `$0200`.

