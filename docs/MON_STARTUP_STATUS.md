# Familiar startup status above Foundation

**MON A/B g0000000C + STATUS g1** is installed and accepted on2512 and2609.
RAM and ROM checks passed on both CPU paths; owner RAM/ZP is restored and
native RTC/NIST sampling is re-admitted. Foundation and published downloads
remain unchanged. See the [ROM acceptance](MON_STARTUP_STATUS_ROM_ACCEPTANCE.md),
[RAM acceptance](MON_STARTUP_STATUS_RAM_ACCEPTANCE.md) and
[installation scope](STATUS_2512_2609_INSTALL_SCOPE.md).

Startup and `VERSION`/`V` now use the same rich display. A and B keep identical
commands. The display identifies the selected monitor and frozen Foundation,
then reports CPU, both validated monitor slots, board name, RAM, the EDU
session, formatted SSRAM capacities, local RTCC, tracked flash wear and battery
age policy. `TIME` retains its existing concise UTC sample for data collection.
Foundation's chooser and recovery text are unchanged; the full screen appears
after entering a monitor.

Illustrative layout, **not a captured hardware result**:

```text
STR8-N 0.1.0-dev g0000000C / MON B
N-F 0.3.0 g00000001 / BASE1 / PR05
CPU: 65C02

MONITOR A gen 0000000C VALID
MONITOR B gen 0000000C VALID default

Board: 2512

RAM $0200-$66FF
EDU ON
SSRAM: PROGRAM payload 63488 bytes
SSRAM: WORKSPACE 65504 bytes

RTCC: Sat 2026-10-31 12:00:00 (-05:00)
FLASH: B2:8 tracked max 601*
Battery: within age policy*
* Health/prior wear unmeasured; attempts.
B3>
```

Names, offset, policy, capacities, generations and counts come from the target;
the example values are not programmed defaults. `--*` means no admitted data.
EDU ON selects the configured Rev D wiring profile; it does not electronically
identify an attached EDU. The RTC reader must find idle released bus pins and
a coherent running calendar. The displayed weekday follows the RTC's weekday
field with any local-day adjustment. Saved offsets are fixed minute offsets;
this does not add automatic daylight-saving rules.

The SRAM query reads only the mode and 64-byte primary header. It admits SS/01
or SS/02 with the existing primary CRC, commit, reserved fields and boundary
rules before computing capacities. VIA ownership guards can decline the query;
startup never issues PREP, acknowledges pending VIA flags, formats SRAM, changes
mode, writes PROGRAM/WORKSPACE, or scans and mutates directory records.

Board, timezone and battery policy use valid latest BN/TZ/BA metadata in
B3:9C00–9FFF. No name or policy is inferred from the host's COM-port assignment.
The captured 2512 image has these records. The captured 2609 image uses the
last 1 KB of sector9 for legacy code/data, not a blank metadata pocket. It has
no valid BN/TZ/BA records, so those fields remain unavailable/UTC until a
separately reviewed conversion. Do not append records over that code.
Startup does not append metadata, advance a battery high-water
date, acknowledge RTC power-fail flags, SET the clock or change trim.

Battery age is a policy estimate, using the existing 30-day-month thresholds;
it cannot measure battery condition. Wear is the largest tracked erase-attempt
count, shown in decimal, and cannot establish prior use or physical health.

## Allocation and preservation

The read-only STATUS provider uses existing B2 tool gaps:

| Address | Allocation | Sealed size | Linked/data bytes | Spare before seal |
|---|---|---:|---:|---:|
| B2:8040–80FF | Text | 192 | 190 | 0 |
| B2:8240–82FF | Text | 192 | 188 | 2 |
| B2:AC00–AFFF | Core | 1024 | 1021 | 1 |
| B2:FA50–FFF9 | Metadata/calendar/SPI | 1450 | 1446 | 2 |

Each extent has its own two-byte CRC. A monitor validates every extent before
executing it. Missing or damaged support prints `STATUS tools unavailable`.
MON A and B each link to 3,958 of their 3,968 payload bytes, leaving 10 bytes.

The provider uses monitor scratch in 6A00–6AFF, system ZP E0–FF, and the existing
6700 boot snapshot. A 20-byte private bank-call gate occupies 7BE8–7BFB, after
the exact frozen worker's end. It does not replace worker code or extend the
public Foundation ABI. Normal ROM status does not borrow owner RAM 0200–66FF,
owner ZP 00–DF, native tool context, or CLOCK history at6B00 and above.
MON owns6A00–6AFF. Active FLASH temporarily borrows that page as part of its
6800–77FF sector buffer, with MON state escrowed at5D00. FLASH's own VERSION
does not call shared MON status. Q restores MON6A and ends that active editor
buffer's ownership; a monitor command cannot promise to retain those256 bytes.
The non6A buffer regions must stay unchanged through MON VERSION, and the
entire4K buffer must stay unchanged through VERSION while FLASH is active.

The 2512 native FLASH/MAINT body ends at FA48. Its body and RP header remain
identical when adding STATUS at FA50; the existing whole-slot RP checksum is
updated. Existing WB and PROGRAM executable images and checksums remain intact.

2609 still has legacy LT code in B2:F. Its archived sector is **occupied**.
The prepared composition explicitly replaces LT with STATUS, preserves B2's
vector bytes, and archives LT on the host. This is an installation-scope choice,
not an erased-space assumption. No owner B0/B1 image is involved.

## Qualification and installation checkpoint

The RAM trial links the same provider source at 3000/3400, with text at
2000/20C0, alongside the RAM monitor. It temporarily borrows 0200–39A9 and must
first escrow fresh owner RAM/ZP, then restore and read back all 0200–66FF and
00–DF before releasing the port. It makes zero flash, journal, SRAM-data or
RTC-setting writes. Only 2512/COM4 and 2609/COM8 are eligible; 2205 and 2604
are excluded. No simulator or power-cut trial is required.

Before installation, capture the current relevant B2/B3 images and review the
five image targets per board: B2:8/A/F and B3:A/B. On the archived 2512 journal,
five replacements plus binding the existing B default to gC require native
journal rotation; retain the old raw history on the host and carry every count
forward. The archived 2609 journal has enough ordinary pages for its five
replacements without a C/D erase; its S default stays S. Exact pages/counts
must follow the fresh capture, not this provisional description.

The gC native TIME reader is now admitted for both boards without changing
their campaign baselines, history or cadence. RAM checks covered both CPU paths,
saved configuration, concise UTC TIME, disabled devices, Q, owner restoration
and eight local-date edge cases. ROM checks covered A/B, native CLOCK VERSION,
active FLASH's own VERSION preserving4K, and MON VERSION preserving non6A
buffer regions. Both owner-reported RESET outcomes were observed before selector
commands; receiver windows expired, so startup/countdown streams were not captured.

2512 retains default B bound to gC;2609 retains S/REC. Both now have the same
core monitor/status code. Their existing utility profiles and metadata still
differ. On2512, pending disabled VIA CB flags can make SSRAM show `--*`; explicit
`MAINT`, `EDU ON`, `SRAM PREP`, `SRAM`, `Q`, `VERSION` admits a read when the
bus is free. Startup never performs that acknowledgement automatically.

Whole B2 bundle/native-FLASH replacements must retain or recompose the STATUS
extents above. Installing an older tool image over those gaps invalidates STATUS;
MON then reports unavailable support rather than executing it.

Builders: `tools/build_status.py`, `tools/build_mona.py`,
`tools/build_status_ram_trial.py`; preserving RAM driver:
`C:\SRC\STR8-N\tools\trial_status_ram.py`. `tools/compose_status.py` prepares
sectors from a supplied target capture and never opens a serial port.
