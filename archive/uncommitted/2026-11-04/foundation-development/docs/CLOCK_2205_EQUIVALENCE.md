# CLOCK equivalence with 2205

October 31, 2026. The owner requested the equivalent of 2205/COM3 CLOCK on
2512/COM4 and 2609/COM8. Foundation F and published downloads remain frozen.

2205 was already running CLOCK. Its live HELP, TIME, STATUS, HISTORY and
STATS were captured without leaving CLOCK or changing any setting. The
reference has local/UTC time, running/calendar/backup/power-fail flags, raw
registers, trim, EUI and retained outage details. Its command set includes
confirmed SET, OFFSET, TRIM, ACK, identity acceptance and battery policy.

## 2512: passed without flashing

The installed `CLOCK 1.10 / BASE1 g1` already supplies these functions. Use:

```text
B3> R CLOCK
CLOCK> TIME
CLOCK> STATUS
CLOCK> HISTORY
CLOCK> STATS
CLOCK> HELP
CLOCK> Q
```

The opening summary, all those queries, EUI, OFFSET and BATTERY passed live.
An invalid February date was rejected. Valid SET, OFFSET and TRIM requests
reached confirmation and were cancelled with NO. VERSION and quiet Q back
to MON passed. This trial did not perform a positive setting change.

The current clock time, trim, latched power-fail evidence, flash metadata,
boot/wear journal and F were retained. B3 before/after was byte-identical.
Fresh owner RAM $0200-$66FF and ZP $00-$DF were restored and read back; COM4
was released. The RTC's latched outage was deliberately not acknowledged.

Health/prior wear remains unmeasured. The BASE1 version uses `--*` and a
disclaimer for unavailable/unverified health; this differs intentionally
from the old reference's wording. Each board retains its own time, identity,
trim, history and policy rather than copying 2205's values.

## 2609: installed and passed

The owner approved [the exact sector/history scope](2609_CLOCK_NATIVE_SCOPE.md).
The existing 2512-tested native utilities are installed: services g9,
WB2 gB, PROGRAM SP1 g2, CLOCK 1.10 and FLASH/MAINT g1/r16. MON gC/STATUS g1
and F remain unchanged. Both boards now have byte-identical complete B2
utility banks, including the CLOCK image and sealed STATUS extents.

```text
REC> B
B3> R CLOCK
CLOCK> STATUS
CLOCK> HELP
CLOCK> Q
B3> APPS
B3> R FLASH
```

Installed CLOCK summary, HELP/TIME/STATUS/HISTORY/STATS/EUI, invalid-date
refusal, cancelled SET/OFFSET/TRIM, VERSION and quiet Q passed on physical
65C816 emulation. APPS, M1/W and shared STATUS passed. Native FLASH VERSION,
sector READ/VIEW, BOOT inspection and C/D/F protection passed without a
flash edit. Successful CLOCK setting changes and positive FLASH write tests
on this new 816 profile are not claimed by this preserving trial.

Eleven utility-sector erases plus one native C rotation completed: twelve
total, zero D/F erases, no retries or power cuts. The final journal is C400,
seq1051, 21 valid records; default S, mask00 and four $8000 entries remain.
C/D/F counts are79/48/31. All25 old raw records are archived on the host;
the16 old C records were replaced on chip, and all nine old D records remain
byte-identical. All counts and the prior-wear unknown mask carried forward.

Owner RAM/ZP were freshly captured, restored and read back; COM8 was released
at REC>. RTC control/trim still match the retained baseline (control $80,
trim -14). The latched outage remains unacknowledged; RTC EEPROM history,
SRAM/WORKSPACE and the existing NTP baseline/schedule were not changed. The
unchanged native gC TIME sampler passed its host admission preflight; this
does not declare the latched outage cleared or establish power continuity.

2609's legacy sector9 tail had code rather than compatible board metadata.
That code was archived and superseded; the new metadata pocket starts FF.
At that checkpoint CLOCK showed an unnamed board, UTC/+00:00 and unset battery age.
These are configuration differences, not a smaller CLOCK command set. No
2512 identity, offset or battery policy was copied. B0/B1 and MON A/B were
outside every programming target. 2205,2512 and2604 were not accessed during
this 2609 installation; published downloads remain unchanged.

The owner subsequently requested a monitor default on2609. One additional
CONFIG C B append atC500/seq1052 selects MON B gC, retaining all21 previous
records and every count, with no erase or image write. Foundation's software
startup selected B automatically; owner RAM/ZP were restored/read back. The
current prompt is B3>. A separate host TIME reader now handles either MON or
REC while retaining the existing RTC baseline/history and cadence.

The owner then requested name2609 and display offset-05:00. A fresh live
readback verified the installed code ends at9BFF and the separate9C00-9FFF
metadata pocket was blank. BN seq1 at9C00 and TZ seq1 at9C20 were committed,
with no erase or boot/wear append. CLOCK and monitor VERSION display2609 and
-05:00. UTC advanced naturally; raw control/trim and all128 EEPROM history
bytes matched before/after. The complete C/D journal and F remained exact.
Owner RAM/ZP were restored/read back and COM8 released at B3>.

Private evidence, excluded from Git/packages:

```text
C:\SRC\STR8-N\output\qualification\CLOCK-reference-20261031-r2
C:\SRC\STR8-N\output\qualification\2512-CLOCK-equivalence-20261031-r1
C:\SRC\STR8-N\output\qualification\2609-CLOCK-capture-20261031-r1
C:\SRC\STR8-N\output\qualification\2609-CLOCK-native-install-20261031-r1\final-receipt.json
```
