# 2512/2609 STATUS installation review

**Approved and executed October31,2026.** Owner: "Approve both reviewed installs."
All11 erases and the one B-generation binding completed; no additional erase or
image write was needed. See [ROM acceptance](MON_STARTUP_STATUS_ROM_ACCEPTANCE.md).
Fresh October31 captures and
[RAM acceptance](MON_STARTUP_STATUS_RAM_ACCEPTANCE.md) pin the candidates.

Install MON A/B g0000000C and STATUS g1 at **B2:8/A/F and B3:A/B on each
board**: ten image erases, plus one native C rotation on2512, **eleven total**.
No retries, rollback erases, power cuts or further targets are included.
**B2:F is a utility sector; golden Foundation B3:F is never written.**
Its exact4096-byte SHA-256 remains
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.

## 2512 / COM4

Seq1090,29 records, latestDC00; DD00/DE00 are the only ordinary append pages,
DF00 is reserved for intent. Five replacements plus one CONFIG B-generation
binding require **one C erase**, no D/F erase. All29 old raw records are archived
on the host; the16 old C records are replaced on chip by native rotation,
the13 old D records remain exact, and every wear count carries forward.
This preserves older raw history on the host, not every record on chip, and
needs the owner's decision under the preserve-history requirement.

Expected seq1097,20 valid records. Default stays **B**, bound to **0000000C**;
enabled mask0F and all bank entries8000 stay unchanged.

| Sector | Count before→after |
|---|---|
| B2:8 / A / F | 600→601 / 15→16 / 15→16 |
| B3:A / B / C | 43→44 / 50→51 / 54→55 |
| B3:D / E / F | 35 / 32 / 24 unchanged |

Native FLASH/MAINT header/body are retained. STATUS fills FA50–FFF9 and its
whole RP-slot checksum changes. WB/PROGRAM executable bytes/checksums stay exact.

## 2609 / COM8

Seq1034,20 records, latestD300. Five appends fit D400–D800: **zero C/D erases**,
all20 old records retained on chip. Expected seq1039,25 records; default **S**,
mask00 and bank entries8000 stay unchanged.

| Sector | Count before→after |
|---|---|
| B2:8 / A / F | 603→604 / 14→15 / 13→14 |
| B3:A / B | 52→53 / 55→56 |
| B3:C / D / E / F | 78 / 48 / 45 / 31 unchanged |

B2:F holds legacy LT: its sector is archived and explicitly superseded by
STATUS, retaining B2's six vector bytes. Other workbench/PROGRAM/legacy assets,
B3:8/9 and services E stay unchanged. This does not install2512's full native
CLOCK/FLASH profile on2609.

2609's sector9 tail is legacy code/data, not a metadata pocket. There are no
BN/TZ/BA writes in this scope. Its display remains **Board: --***, **UTC** and
**Battery: --***. Name/zone/policy are not fabricated. Converting that metadata
and native profile requires a separate scope.

## Preservation and acceptance

No writes to B0/B1, B3:8/9/E/F, SRAM PROGRAM/WORKSPACE or RTC data/trim/history.
No2205/2604 access or published-download changes. Archive the relevant before
images/history outside Git. Require matching fresh B2/B3 preimages and fresh
owner RAM/ZP escrow immediately before writes; changed preimages invalidate plan.

Reuse frozen qualified OPAQUE/CONFIG/readback tools. Reserve wear before each
erase and verify each sector. Install provider first, test A before replacing B,
then bind2512's existing B default to gC. No unreviewed retry/erase.

Acceptance: ROM CRC admission/status on both CPU paths, concise UTC TIME, CLOCK
shared VERSION/return and active-FLASH VERSION buffer preservation where installed,
MON VERSION preserving buffer regions outside MON-owned6A, Q, boot/wear postimages,
and independent owner RAM/ZP restoration. Admit gC to the existing RTC sampler
without changing baseline/history/cadence. Physical RESET checks use an armed
receiver handshake; no power cuts. No additional firmware build is needed.

Pinned sector files, complete relevant before-images/history, counts and hashes:

```text
C:\SRC\STR8-N\output\qualification\STATUS-install-scope-20261031-r1\review.json
C:\SRC\STR8-N\output\qualification\STATUS-install-scope-20261031-r1\2512\plan.json
C:\SRC\STR8-N\output\qualification\STATUS-install-scope-20261031-r1\2609\plan.json
```

Keep both boards idle through approval/final preimage admission, or recapture
and review if their images, settings, journal or metadata change.
