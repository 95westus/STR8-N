# 2512 BOOT and CLOCK metadata positive acceptance

November 1, 2026 local. The owner-approved three-erase trial passed using the
installed g00000010 monitor and existing utilities. No firmware rebuild,
F/MON write, reset, power cut, RTC SET/trim/ACK, EEPROM or SPI-data write was
issued. The scope is closed; further NVM work needs a new review.

| Positive case | Observed result |
| --- | --- |
| BOOT OFF1 | Committed mask0D; RUN1 refused while disabled |
| BOOT B1/8000 | Re-enabled the original entry; mask0F restored |
| BOOT DELAY0B, then0A | Exact committed field/readback;9 refused below the minimum |
| BOOT B0/9000 and RUN0 | Executed the eight-byte opaque flash fixture, wrote RAM18FF=47, returned through public HOLD7E67 to MON B/g10 |
| BOOT B0/8000 | Restored original entry; native D rotation matched its forecast |
| CLOCK ACCEPT EUI | Committed the real EUI in a verified EI row; repeat made no extra row |
| CLOCK OFFSET-05:00 | Committed a verified TZ row; repeat made no extra row |
| CLOCK BATTERY LIMITS13/25 | Committed a verified BA row, preserving the installation date |

Every physical journal page matched the reviewed intermediate snapshots.
Every CLOCK row matched its exact32-byte header/payload/sequence/CRC/commit.
The complete trial metadata sector also matched its predicted image before
cleanup. The FLASH programmer's output showed the exact eight fixture bytes;
the independently read full B0:9 pre-cleanup sector matched the fixture.

The opaque fixture was qualification-only and is removed. This proves RUN
with the known compatible B0:9000 entry; it does not qualify arbitrary old
images at the restored8000 entries. Existing owner images were preserved.

## Exact final state and accounting

- B0:9 restored to its original4096 FF bytes.
- B3:9 restored to its exact original provider code and all14 old metadata
  rows: EUI unbound, offset-06:00, battery limits12/24 and original date/policy.
  The three temporary metadata rows are archived on the host.
- Boot default B/g10, mask0F, all entries8000 and legacy delay0A restored.
- All128 EEPROM bytes preserved, including three committed real outage
  events and the fourth-slot tombstone. Live outage register bytes also matched
  before/after. Time kept running; trim0C/control80 and clear PF remained.
- Owner RAM0200-66FF and ZP00-DF restored and read back exactly; SPI PROGRAM/
  WORKSPACE received no data writes. No other board or download was touched.

Exactly three erases: native B3:D rotation, B0:9 cleanup and B3:9 restoration.
Nine journal appends comprise six policy commits, two cleanup reservations
and one durable D-erase intent. All27 original C/D rows are archived;16 old
D rows were replaced on chip and11 original C rows remain exact.
Final seq1177 has20 valid rows. Counts: B0:9=26, B3:9=21,
C/D/E/F=57/38/37/24. The only final flash changes are the reviewed C/D journal
advance. F, MON A/B and all other final image bytes remain exact.

Receipt: `output/qualification/2512-BOOT-CLOCK-positive-20261101-r1/report.json`.
Sealed completion:
`output/qualification/2512-BOOT-CLOCK-scope-20261101-r2/completion.json`.
Final REC>, COM4 released, all worker/restore guards clear. Host RTC admission
was checked without another board operation. Existing g10 sampling can resume;
no collector, baseline, point or measurement-segment changes were made.

## Remaining limits

Frozen BASE1 keeps its fixed three-second chooser. DELAY writes a legacy
byte0A-FF; only field storage/readback is accepted, not adjustable startup
timing. The manual now explains this. FLASH's older in-tool tick wording
is corrected in source. The later [provenance check](FLASH_HELP_PROVENANCE.md)
found that installed compact FLASH already omits this paragraph and its false
tick claim. No help-only build or board update is required.

Latched SET/ACK and actual changed-trim cases were excluded from this
three-erase trial to protect the real clock/calibration and EEPROM events.
The subsequent14-case [CPU-RAM trial](CLOCK_FAULT_RAM_2512_ACCEPTANCE.md)
passed archive-before-write, failure and trim-ordering cases on the physical
65C02. Its device responses are injected; physical latched-event/changed-trim
writes are not claimed. A no-event ACK or idempotent trim query is not a
positive writer. No physical battery replacement/date test is claimed.
Extracted-kit, physical terminal keys and targeted held816 work remain
separate;2609/2205/2604 were not accessed by these2512 trials.
