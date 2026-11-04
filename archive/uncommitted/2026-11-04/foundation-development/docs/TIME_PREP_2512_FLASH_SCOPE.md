# 2512 TIME and automatic SRAM PREP: three-erase review

November1,2026. **Review ready, not approved. No flash writes made.**
2512 is at REC>, COM4 released; owner RAM/ZP are restored/read back.
The earlier12-erase named-transfer/EDU allowance is exhausted. This is a new
allowance for2512 only. 2609,2205,2604 and published downloads stay untouched.

## RAM qualification completed

MON gF retries an invalid calendar snapshot within the same three-attempt
budget already used for incoherent reads. Only a newly validated calendar,
control and trim are displayed. Persistent invalid dates return04, persistent
incoherence returns07, and bus NACKs still fail. Earlier intermittent hardware
04 responses did not retain raw bytes; their electrical cause is not claimed.
Old/new behavior was tested on the2512 CPU with bounded RAM fault fixtures;
the unchanged physical I2C path passed a full minute of live reads with fresh,
unchanged trim/control.

STATUS now admits all SRAM ownership guards before reading ORB. That read
captures the port sample and acknowledges disabled CB flags, matching guarded
manual PREP. It then rechecks IFR before any SPI clock. Enabled CB interrupts,
owned PCR/ACR/DDR configurations and flags that remain pending still refuse.
Unrelated ownership is retained. No SPI data/mode or RTC setting is written.
Existing port-input latch limits are unchanged; physical DDR/ACR/PCR/IER
preservation passed.

All22 RAM checks passed, including combined MON/STATUS and EDU OFF/ON gating.
After the owner's physical RESET, old gE showed SSRAM unavailable. The RAM
candidate captured **IFR18/IER80/PCR00/ACR00/DDRB00** before entry, then displayed
PROGRAM63488 and WORKSPACE65504 bytes **without manual PREP**, followed by24
fresh successful TIME samples. The receiver expired, so that reset is
owner-reported and its full startup banner was not captured. Post-reset old
VERSION, actual flag state and new RAM behavior are retained. B2/B3 stayed
exact; owner RAM/ZP were restored/read back.

Evidence:
- `output/qualification/2512-TIME-PREP-RAM-20261101-r2/report.json`
- `output/qualification/2512-TIME-PREP-cold-RAM-20261101-r2/report.json`

A host match-object assertion stopped the initial RAM harness after19 accepted
checks. Its failure/restoration receipt remains intact. The corrected
continuation carried those checks forward; firmware was not rebuilt.

## Exact new write allowance

| Target | Erases | Replacement |
|---|---:|---|
| B2:F | 1 | STATUS-details allocation FA50-FFF9 and enclosing FLASH RP CRC |
| B3:A | 1 | MON A generation0000000F |
| B3:B | 1 | Identical MON B generation0000000F |
| **Total** | **3** | **Zero B3:F writes or C/D erases** |

**B2:F is a utility sector; golden Foundation is B3:F and stays exact.**
Within B2:F, all bytes outside the1450-byte STATUS allocation and two-byte
enclosing RP footer stay exact. FLASH editor/transfer code, STATUS core/text,
all other B2 sectors, B0/B1, B3:8/9/E and saved metadata remain unchanged.
MON bodies use3959/3968 bytes (9 free); STATUS details use1448/1448 plus CRC.
Existing allocations suffice. F is neither rebuilt nor reprofiled.

| Journal page | Sequence | Change |
|---|---:|---|
| D500 | 1147 | B2:F erase reservation18→19 |
| D600 | 1148 | B3:A erase reservation46→47 |
| D700 | 1149 | B3:B erase reservation53→54 |
| D800 | 1150 | Default B generation binding E→F; no count change |

All21 old C/D records remain byte-for-byte **on chip**, plus a host archive.
There is no journal rotation/history replacement. Final25 valid records,
seq1150; C/D/E/F counts remain56/37/36/24. Prior-wear uncertainty flags remain.
Default stays B; bank enables, entries, delay and all other settings remain.
Saved EDU stays ON; no name/zone/battery/EDU record is appended.

## Acceptance after approved installation

One physical CPU RESET, USB power kept connected; no power cuts. Capture
default B gF with automatic SRAM capacity, then verify installed TIME, SRAM
TABLE and existing utility read-only/cancel routes. No temporary flash or
SPI-data write tests are included.

RTC collection keeps serial priority. Versioned2512-only gF native-TIME/LED
readers and routing are prepared privately, not active. The qualified794-byte
LED agent, all old gD/gE instruments/audits, baselines, points, cadence and
other-board admissions stay intact. gF admission requires installed startup,
nine strict TIME/NIST samples and the unchanged62-second LED agent with exact
RAM/LED restoration. Until qualified,2512 defers; other enabled boards keep
their existing collection paths. No clock/control/trim, PF latch/history,
EEPROM or RTC metadata is set/cleared.

Before writing, require matching target preimages, journal state and pinned
candidate hashes; stop on mismatch. Restore fresh owner RAM0200-66FF/ZP00-DF
and verify images/journal/F. Finish at REC>, release COM4. No blind erase
retries or extra replacements are included.

Private pinned targets/preimages, journal archive and inactive RTC candidates:
`output/qualification/TIME-PREP-2512-scope-20261101-r1/plan.json`.
Builds: `BUILD/mon-gF-time-r1`, `BUILD/status-autoprep-r1`.
