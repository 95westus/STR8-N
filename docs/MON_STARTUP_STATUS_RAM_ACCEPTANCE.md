# Startup STATUS: RAM acceptance

Passed October31,2026 on **2512 / W65C02SXB / COM4** and **2609 /
W65C816SXB in emulation / COM8**. No 2205/2604 access, simulator or additional
firmware build during the live qualification.

This qualifies the relocated provider source in private RAM payload
`5ce8abf24192c8d22e7012bb880bf2218db9fd415ef2863c671cba5c4285cbf6`,
not the uninstalled ROM artifacts. Both boards passed CRC admission, private
bank-call handoff, CPU/slot identification, actual wear/metadata display, fresh
RTCC, concise UTC TIME, EDU OFF/ON, Q and independent owner RAM/ZP restoration.

2512 displayed its name, -05:00 offset and within-age-policy row. 2609 correctly
displayed no name/policy and UTC: its sector9 tail is legacy code/data, not an
available BN/TZ/BA pocket. Nothing was appended there.

Both actual SS/01 SRAM layouts displayed **63,488 PROGRAM payload bytes** and
**65,504 WORKSPACE bytes** (64 KB boundary). This is not an additional live
SS/02-format conversion test. On 2512, the first read was correctly refused:
DDRB=00, ACR=00, PCR=00, IFR=18, IER=80. Explicit workbench `SRAM PREP`
acknowledged disabled VIA CB flags, then mount and STATUS agreed on capacities.
Startup itself never issued PREP/ACK. RTC power-fail flags were not acknowledged.

Eight local-date cases executed on 2512's CPU with temporary RAM samples and
no RTC SET: previous year, leap-day entry/exit, ordinary February, 2099→2100,
-12:00, +14:00 and UTC without a zone. The fixture enabled G through one
RAM-only discriminator because the RAM smoke MON deliberately refuses G;
provider and production binaries were unchanged. Address/flash guards remained.

Stopped host-fixture runs remain in the evidence: old g8 requires V rather than
VERSION for admission; an assertion assumed a different SRAM boundary; the first
calendar fixture reached deliberate G refusal. Capacity was accepted against
the captured actual workbench page00 layout without repeating that board run.
The corrected calendar fixture passed eight cases. All stopped runs restored
borrowed owner RAM; none wrote flash or device data.

Final: **2512 B3>**, **2609 REC>**, ports released. Fresh owner RAM 0200–66FF and
ZP00–DF restored/read back. Existing images, journals, RTC/trim/history and SRAM
data unchanged. Zero flash/journal writes, power cuts, RTC SET/trim/PF ACK or
SRAM data writes. Explicit disabled-VIA flag ACK above is the control-state
exception. F binary, sources and published downloads remain frozen.

Private evidence, outside Git/packages:

```text
C:\SRC\STR8-N\output\qualification\STATUS-RAM-closeout-20261031-r1\report.json
C:\SRC\STR8-N\output\qualification\2512-STATUS-g1-RAM-20261031-r1
C:\SRC\STR8-N\output\qualification\2609-STATUS-g1-RAM-20261031-r2
C:\SRC\STR8-N\output\qualification\2512-STATUS-bus-guard-20261031-r1
C:\SRC\STR8-N\output\qualification\2512-STATUS-prepared-SRAM-20261031-r1\capacity-review.json
C:\SRC\STR8-N\output\qualification\2512-STATUS-calendar-RAM-20261031-r2
```

ROM placement/startup and native buffer checks were open at this RAM checkpoint.
They are subsequently closed in the [ROM acceptance](MON_STARTUP_STATUS_ROM_ACCEPTANCE.md),
including the documented MON6A/editor-buffer ownership distinction.
