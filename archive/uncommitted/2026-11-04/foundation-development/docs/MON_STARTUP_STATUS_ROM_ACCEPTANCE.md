# MON gC / STATUS g1: installed acceptance

Closed October31,2026 on2512/W65C02SXB and2609/W65C816SXB in emulation.
Same MON A/B and shared STATUS source/binaries on both; retained utilities and
metadata differ. This is a development checkpoint, not a new public ZIP.

Later on October31, the [CLOCK/native utility update](CLOCK_2205_EQUIVALENCE.md)
superseded2609's retained older utility profile. The results below describe
the original STATUS checkpoint; current board contents are in the
[2609 inventory](2609_CURRENT_INVENTORY.md).

| Result | 2512 / COM4 | 2609 / COM8 |
|---|---|---|
| A/B | g0000000C, both ROM-tested | g0000000C, both ROM-tested |
| Default | B, rebound to gC | S/REC unchanged |
| Journal | seq1097,20 records | seq1039,25 records |
| C/D/F tracked counts | 55/35/24 | 78/48/31 |
| Largest tracked count | B2:8,601 | B2:8,604 |
| Final prompt | B3> | REC> |
| Owner RAM/ZP | Restored/read back | Restored/read back |
| RTC/NIST | Native gC TIME admitted | Native gC TIME admitted |

The [approved scope](STATUS_2512_2609_INSTALL_SCOPE.md) used five image-sector
erases per board at B2:8/A/F and B3:A/B. 2512 used one native C rotation and
one CONFIG C B append. **Eleven erases total**, no retries/rollback erases.
Its16 older C records are retained in the complete host B3 archive;13 old D
records remain exact on chip. All20 old2609 records remain exact. Every wear
count, unknown mask, enabled-bank mask and entry address matches the plan.

Golden B3:F stayed byte-identical, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
B0/B1, B3:8/9/E, SRAM data/WORKSPACE, RTC settings/trim/history and excluded
boards2205/2604 were untouched. No power cut, RTC SET/ACK or SRAM-data write.

ROM A and B passed rich VERSION, valid slot rows, actual CPU/status, concise UTC
TIME, M1/W/APPS and Q. On2512, native CLOCK VERSION called shared MON status and
returned normally. Active FLASH's own VERSION preserved all16 buffer pages.
MON VERSION preserved6800–69FF and6B00–77FF.

A cross-Q full-buffer assertion initially failed on10 bytes, all inside MON's
6A00–6AFF scratch. Active FLASH borrows that page, with MON state escrowed at5D00;
Q restores MON state and ends editor-buffer ownership. The corrected checks above
passed without a firmware change or additional erase. The original stopped
report, corrected run and exact buffer captures remain archived.

Both first reset receivers expired while awaiting the operator. The operator
then explicitly reported each physical RESET. Each expected post-reset default
was observed **before any A/B selector was sent**: B gC on2512; REC on2609,
followed by one-time A gC. Startup/countdown streams were **not captured**.
Pre-helper owner RAM/ZP and complete B3 matched the installed checkpoint;
borrowed RAM was restored and independently read back afterward.

Both native TIME readers passed nine samples against NIST, exact TX-trace audit
and return to their original prompt. Campaign baseline, prior points/events and
hourly cadence were retained. Historical drivers were retained. 2609's host-only
firmware label was normalized to the canonical BASE1/PR05 spelling after its
already-verified frozen-F hash was checked; board firmware did not change.

Known profile limits:2609's legacy sector9 tail is occupied, so Board--*, UTC
and Battery--* remain until a separate metadata conversion. Its full native
utility-profile upgrade is not included. On2512, pending disabled VIA CB flags
can correctly refuse an automatic SRAM read; explicit workbench SRAM PREP is
available. Both current SS/01 capacities were qualified after admitted reads.
The compact decimal status formatter supports counts through999,999; use W for
larger24-bit counters. Extend that formatter before high imported-count
qualification. SS/02 conversion was not part of these live tests.

Private final receipt and raw evidence are outside Git/packages:

```text
C:\SRC\STR8-N\output\qualification\STATUS-install-20261031-r1\final-receipt.json
C:\SRC\STR8-N\output\qualification\STATUS-install-20261031-r1\2512
C:\SRC\STR8-N\output\qualification\STATUS-install-20261031-r1\2609
```

Published Foundation/manual/terminal downloads and release ZIPs remain unchanged.
