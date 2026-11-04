# Beta35: PF duration and recent on/off intervals

2512 (COM4), 2205 (COM3), 2609 (COM8, 65C816 emulation) and 2604
(COM5) now run beta35 monitor B, generation 47 (`0000002F`), with
CLOCK 1.10 and unchanged ASM 0.5. J3 restart and CLOCK/STATS checks passed
on all four. All ports are released. The soak remains stopped and v2.1
code was not flashed.

## Power-fail section

A recorded PF event now includes an estimated elapsed outage:

```text
 [power-fail]
Power down: 10-15 23:59
Power up:   10-16 00:01
Outage: ~000d 00:02 (min)
RTCC: PF logged, ACK
```

This is a two-minute model example. The section appears when the RTC has a
latched power-fail event. Ordinary resets do not create outage records.
Existing durable save-before-ACK behavior is retained: a successful save
and acknowledgment rearm the chip to capture the next power-down/up pair.
The existing EEPROM format and four-event ring are unchanged.

## Recent statistics

```text
B3> R CLOCK
CLOCK> STATS
```

STATS lists the retained events newest first, with each estimated outage
duration. Between adjacent events, `On: ~...` is the powered-on interval
from the older power-up to the newer power-down. At most four retained
events and three completed powered-on gaps are available. The current
unfinished powered-on interval is not included. All four boards currently
show four retained events and three gap rows.

The initialized SRAM boards (2512, 2205 and 2609) also received an updated
saved CLK 1.10, and the model verified:

```text
BATCH SRAM;G CLK;STATS;Q
```

2604's SPI SRAM remains uninitialized; it was not formatted or written.
The flash CLOCK record is available on all four boards. STATS and HISTORY
are read-only. Future real power events continue replacing the oldest
EEPROM records through the existing logger; there are no new per-poll
writes, lifetime counters, or persistent uptime totals.

The RTC's event fields contain minutes and no event year or seconds.
`~` marks an estimate. Years are inferred from the trusted capture date,
assuming an interval shorter than one year. Leap days, month boundaries,
year rollover and 12-hour fields are handled. Missing trusted capture years,
invalid fields, reversed same-day times and unsuitable chronological gaps
produce `unknown`. Calendar changes or outages spanning unobservable years
can prevent a reliable estimate; these are not precision uptime measurements.

## Space and compatibility

- CLOCK is 12,231 bytes at `$2000-$4FC6`, 1,007 bytes larger than 1.9.
  Its 24-byte record header still fits the existing three-sector allocation,
  leaving 33 bytes. The record occupies B1:B-D on every board.
- The resident banner remains 1,263 bytes. Its SPI helper addresses and
  the RTC gateway template at B3:8DF0 are unchanged.
- A 605-byte private duration worker uses a 768-byte sealed image in
  existing unused VERSION-asset padding at B2:FB00-FDFF. It is loaded into
  borrowed monitor staging RAM `$6700-$69FF`, with ten scratch bytes at
  `$6A00-$6A09`, during PF formatting. There is no permanent user-RAM
  reservation or additional flash sector allocation.
- VERSION's original executable code and the B2 vector pocket are retained;
  the whole asset CRC was resealed. The XIP native utility bundle, ASM,
  B3:E, fixed B3:F and beta28 A fallback are unchanged.
- CLOCK's existing private BATCH input addresses (`READLINE`, line buffer,
  length and overflow) remain fixed. New commands use appended helpers.
  This preserves the existing CLOCK/BATCH profile without a new public ABI.

## Installation and validation

The user explicitly requested no new backups or readbacks. Plans used the
existing verified beta34 images. No device backup, RAM snapshot, flash dump
or host readback pass was performed. Normal on-device preimage, payload and
program verification stayed enabled. Each board received seven sector
erases: B3:C journal, B1:D/C/B CLOCK, B2:F shared asset, B3:8 RTC/banner,
then B3:B monitor publication. Erases were included in each board's wear
snapshot. The installer explicitly selected B3 before entering ROM RESET.

Installation used application RAM, which was not backed up or restored.
The saved CLK records on initialized SPI SRAM were replaced using the
existing SRAM program-storage API. Workspace preservation was checked in
the model; no live memory comparison was performed.

Validation included 620 linked machine-code duration cases, boot PF
save/ACK/rearm, reset deduplication, subsequent capture and ring wrap,
read-only STATS, missing capture-year handling, and the Dec 31 capture-year
boundary. An independent rebuild matched 26 files. Each board-specific
installer ran in the CPU model with exact sector results, record commit,
stale-source/corrupt-payload refusal and actual B3 return. Models exercised
the SRAM CLK update and BATCH path where applicable. Hardware checks used
installer completion, J3 startup, VERSION and recognized CLOCK/STATS output.

Build SHA256:
`2f5319ab1d7bc751d61bc4b00af225466d83b983bc7e5806a33417940be68365`

Evidence under `C:\SRC\STR8-N`:

- `output/qualification/beta35-fleet-2026-10-16/report.json`
- `output/qualification/beta35-fleet-2026-10-16/<board>/`: plans, expected
  images derived from earlier verified files, models, serial transcripts,
  boot/VERSION/STATS output and hardware receipts.
- `BUILD/v2-beta35-candidate/`: mirrored qualified candidate and receipt.
- `tmp/b34/BUILD/v2-beta35-candidate/`: 2.0-worktree candidate, test and
  rebuild receipts, example PF/STATS model output and generated sources.

The primary v2.1 checkout and the earlier beta34 evidence remain separate.
