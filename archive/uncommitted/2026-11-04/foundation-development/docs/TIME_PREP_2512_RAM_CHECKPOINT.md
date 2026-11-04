# 2512 TIME and cold SRAM preparation: RAM checkpoint

November1,2026. This records the RAM stage, when installed MON remained gE.
The subsequent three-erase installation and physical gF cold acceptance are
now complete: see [installed acceptance](TIME_PREP_2512_ACCEPTANCE.md).
Foundation0.3.0 g1 BASE1/PR05 and its sources remain frozen. 2609/2205/2604
and published downloads are excluded.

## Candidate changes

MON gF shares the existing three-attempt budget between incoherent and invalid
calendar snapshots. A fresh valid retry supplies calendar/control/trim; it
never displays an invalid frame or substitutes cached time. Persistent bad
calendars still return04, incoherent snapshots return07, and NACKs still fail.
The exact raw bytes responsible for the earlier hardware04 responses were not
captured. An old-code diagnostic completed721 live reads without reproducing
that transient; the candidate's behavior is proved separately with CPU-RAM
fault fixtures and live device reads.

STATUS's SRAM reader now checks IER, PCR, ACR and DDR ownership before reading
ORB. Only with those guards admitted does it capture ORB and acknowledge
disabled CB flags, then recheck pending flags before any SPI clock. Enabled
interrupts, owned pins or a persistent pending condition still refuse. There
are no SPI data/mode writes, RTC settings or journal writes.

MON A/B bodies are3959/3968 bytes, leaving9 bytes each. STATUS details use
1448/1448 code/data bytes plus the existing CRC. Unchanged STATUS core/text
were reused. No new flash sectors or public Foundation ABI are needed.

## Accepted RAM evidence

The22 checks on2512 include old/new invalid-first TIME behavior; valid retry,
persistent invalid/incoherent/NACK refusal, leap-day and12-hour decoding;
old/new pending-CB behavior, IER/PCR/ACR/DDR-owner refusal, stuck flags and
unrelated-owner preservation. Fault transport/registers are CPU-RAM fixtures;
physical hardware is tested separately.

The new physical SPI reader validated the real64-byte PROGRAM primary and
preserved DDR/ACR/PCR/IER. Combined RAM MON/STATUS showed the actual capacity;
live TIME ran for a full minute with no error and fresh unchanged trim/control.
EDU OFF skipped device reads; ON restored capacity. B2/B3 stayed exact, and
fresh owner RAM0200-66FF/ZP00-DF were restored/read back. Final REC>, COM4 free.

Receipt: `output/qualification/2512-TIME-PREP-RAM-20261101-r2/report.json`.
It carries19 accepted checks from r1, whose host match-object assertion stopped
the live TIME phase. That failure/restoration receipt remains intact; firmware
was not rebuilt, and accepted fixture cases were not repeated.

Builds: `BUILD/mon-gF-time-r1`, `BUILD/status-autoprep-r1`.

## RAM-only cold test accepted

The owner reported one physical CPU RESET on2512 with USB power connected.
The receiver expired, so its full startup banner was not captured. Post-reset
old gE VERSION showed SSRAM unavailable. The RAM candidate captured actual
IFR18/IER80/PCR00/ACR00/DDRB00 before entry without reading ORB, displayed
capacity without manual PREP, and passed24 fresh TIME samples. B2/B3 stayed
exact; the verified owner escrow was restored/read back. REC>, COM4 released.

Receipt: `output/qualification/2512-TIME-PREP-cold-RAM-20261101-r2/report.json`.
There were zero flash, journal, metadata, SRAM-data or RTC-setting writes.
The candidate acknowledged disabled VIA CB flags only through its guarded
path. RTC collection keeps lease priority. The three-sector
[flash review](TIME_PREP_2512_FLASH_SCOPE.md) was subsequently approved and
completed; its sealed review and original RAM receipts are retained.
