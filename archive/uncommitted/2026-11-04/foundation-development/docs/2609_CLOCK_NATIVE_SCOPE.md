# 2609 full CLOCK / matching native utilities scope

October 31, 2026. **Approved and executed; acceptance passed.** The owner
approved “Approve reviewed 2609 update.” Eleven image erases and the one
native C rotation completed without retries or additional erases. See
[CLOCK equivalence acceptance](CLOCK_2205_EQUIVALENCE.md).

2512's installed CLOCK 1.10 passed comparison with the live 2205 CLOCK.
2609 retains the older workbench/RTC utility profile. The recommendation is
to install the same existing native utility profile as 2512 so CLOCK, its
shared loader and APPS/R routes agree. This also brings the already-built
FLASH/MAINT utility; it avoids advertising a missing native tool.

No new build, F replacement, monitor-slot replacement, reset or power cut is
required. The exact prebuilt bytes are pinned in the private plan below.

## Sector replacements

| Target | Replacement |
|---|---|
| B2:8/9/A | Matching WB2 gB / PROGRAM SP1 g2 bundle, preserving STATUS g1 extents |
| B2:B/C/D | Full CLOCK 1.10 / BASE1 g1 |
| B2:E/F | Existing native FLASH/MAINT g1/r16 with shared STATUS g1 retained |
| B3:8 | Matching RTC provider, gateway and native overlay loader |
| B3:9 | Matching history/return code and an empty compatible metadata pocket |
| B3:E | Matching services g9 / named-tool dispatcher |

**Eleven image-sector erases, plus one native C rotation: twelve total.**
There are zero D erases and zero F writes. B2's old utility bodies/vector
bytes and B3:8/9/E legacy utilities are archived before replacement. These
are utility replacements; B0/B1 and MON A/B remain unchanged.

The legacy 2609 sector9 tail contains code rather than valid BN/TZ/BA/EI
records. Its archived code is superseded by the new utility profile. The
new metadata pocket starts FF: no 2512 board name, EUI, offset or battery
policy is copied. Board --*, UTC and Battery --* remain until explicitly
configured. RTC hardware settings and EEPROM history are retained.

## Boot/wear history

Current journal: D800, seq1039, 25 valid records. Six ordinary append pages
D900-DE00 remain; DF00 is the reserved rotation-intent page. Eleven image
replacements require native C rotation after those six appends.

All 25 original raw records are archived on the host before writing. The
16 original C records are replaced on chip; the nine original D records
remain byte-identical. Every existing count and unknown mask is carried
forward. Expected final journal: C400, seq1051, 21 valid records.

| Count | Before | Expected after |
|---|---:|---:|
| B2:8/9/A/B/C/D/E/F | 604/262/15/13/22/37/21/14 | 605/263/16/14/23/38/22/15 |
| B3:8/9/E | 27/20/45 | 28/21/46 |
| B3:C/D/F | 78/48/31 | 79/48/31 |

Saved default S, disabled-bank mask00 and four $8000 entries remain exact.
There is no A/B generation rebinding. Golden F stays SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.

## Execution and acceptance

Fresh relevant B2/B3 captures bind this plan. The installer must refuse if
either preimage changed. Take a fresh owner RAM/ZP escrow immediately before
borrowing RAM; restore/read back $0200-$66FF and $00-$DF afterward. Do not
substitute an older escrow for current owner data.

Test installed R CLOCK summary, TIME/STATUS/HISTORY/STATS/EUI/HELP, invalid
dates, cancelled SET/OFFSET/TRIM, VERSION and Q. Test APPS, named tool
admission, M1/W and intact shared STATUS. Verify exact image readback, old D
records, carried counts, boot policy and F. No retry/rollback erase is
included in the allowance.

Do not SET/trim/ACK, change RTC EEPROM/history, write SRAM/WORKSPACE or cut
power. Retain the native gC TIME sampler and existing measurement baseline
and schedule; update its admitted image hashes after acceptance. Positive
CLOCK setting changes remain outside this preserving trial.

2205, 2512 and 2604 stay outside this installation. Published kits/downloads
remain unchanged. 2205 is the read-only CLOCK reference, left at CLOCK>.

Private review/targets, excluded from Git/packages:

```text
C:\SRC\STR8-N\output\qualification\2609-CLOCK-native-scope-20261031-r1\plan.json
```
