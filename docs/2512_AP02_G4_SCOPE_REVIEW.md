# 2512 current-g4 AP/02 flash-app qualification: scope review

**Owner approved one-erase trial; passed.** October 30, 2026.
See [acceptance](2512_AP02_G4_ACCEPTANCE.md). The scope below retains the
pre-trial review.

65C02 / FT245 / COM4, MON B g8, services g4. The preparation opened no board
port; the approved execution is recorded separately. This closes the
version-specific positive app-launch gap before a proposed soak; a soak is
not started by this review.

## Current evidence and required fresh admission

The latest preserving saved-default WDC trial has two agreeing final captures
of every bank. They match the current device marker: journal seq1041, 28 valid
records, saved default B/generation 00000008, enables 0F and all entries 8000.
Its complete B0:9000-9FFF sector is FF. That erased state is recorded owner
content, not general permission to allocate or erase it.

Original sector SHA-256:
`f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6`.

Original complete B0 SHA-256:
`5b72e8041c01f1fab145f8926a01b2be02ba807c654525bc04eed450a48c245f`.

Before programming, acquire the shared serial lease, verify COM4 USB
A10MQFLCA and MON B g8/CPU02, capture native owner RAM0200-66FF and ZP00-DF
twice, then independently read all four complete flash banks twice. Require
the exact reviewed images/history and still-FF target; stop before any flash
write on mismatch. Save fresh owner data and complete originals on the host.
The fresh escrow is the restoration authority, even if it differs from an
older installer escrow. No stale owner RAM may replace current data.

## Smallest write budget for this trial

| Step | Target change | Erases / journal |
| --- | --- | --- |
| Install unsealed AP/02 fixture | Native guarded !M, fifteen eight-byte commands over 9000-9077; identical FF bytes skipped | No erase or journal append |
| Check admission | Seal header CRC at 901C-901D, then payload CRC at 901E-901F, using two native !M commands | Four 1-to-0 checksum cells; no erase |
| Restore original target | Existing OPAQUE erases B0:9 and verifies all 4096 bytes FF | **One erase**, native **CC00/seq1042** reservation |

Exactly **one sector erase total**, at B0:9 for restoration. Its tracked count
changes **14 to 15**. All **28 old raw journal records** remain at their
original locations; final **29 records**, latest CC00/seq1042. C/D/E/F counts
stay **53/33/28/24**. Two ordinary pages CD00/CE00 remain; CF00 stays reserved.
Zero F writes, C/D erases, monitor/services/tool rewrites, boot-setting writes
or other image writes. No erase retry or journal rotation is included.

The current 120-byte AP/02 example (88 executable/text bytes, entry 9020,
CPU02, PR05) is reused exactly; no assembler, firmware rebuild or CPU model.
Both CRC fields initially remain FF. Require header-CRC refusal, then
payload-CRC refusal, then valid APPS inventory and `APP APPDEMO` execution.
Redisplay help with `?`; bare Q must return through public HOLD to MON B g8.
Do not append CR to the app's immediate Q. The example is temporary.

Restore fresh owner RAM/ZP before running the example; compare all owner
bytes natively after its return. Independently compare each intermediate
bank image, including unchanged B3 until the restoration reservation. Restore
the original FF sector even if a later test fails, within the same single
erase allowance, provided the protocol and other-bank preimages are admitted.
If a native programming failure halts in RAM, stop, retain power/escrow and
arm a recovery receiver before requesting RESET; do not send blind commands
or automatically retry programming. Golden F remains the recovery route.

## Closeout and exclusions

Compare every final bank twice, retain all old journal rows, restore/read
back fresh owner RAM/ZP and verify again through native Dump. Finish at
MON B / B3>, COM4 released, original B/g8 boot policy and every original
image byte restored. B0:8 FLASH and B0:F WDC are outside the write target.

The existing **MON-G8-NATIVE-TIME** RTC/NTP path uses V/TIME with no RAM BIN.
Run its read-only continuity check and exact serial audit afterward. Its
sampler source/profile, RTC settings, trim, PF flags, schedule, old samples
and baselines remain unchanged; it needs no journal-specific adapter change.
There are no SPI SRAM/PROGRAM/WORKSPACE, EEPROM, RTC SET/trim/PF writes, planned
resets or power cuts. 2609, 2604 and 2205 stay outside this trial. Source
commits remain local; frozen F and published downloads remain unchanged.

Private plan/postimages in the parent project:
`output/qualification/2512-AP02-g4-scope-20261030-r1`.

Plan SHA-256:
`0d1570f0b19651271b612c2eb63f67a68ae91d43680aaf1e92d2e40440b21d20`.

The executable host driver accepts a separate owner-approval record bound to
this plan and its exact driver hash. The completed approval grants no
additional erase or programming allowance.
