# STR8-N

STR8-N is a guarded reset monitor and flash loader for WDC SXB boards. It
occupies Bank 3's `$F000-$FFFF` sector; guest firmware such as R-YORS remains
separate.

## Stable release: v2.0a24

[v2.0a24](https://github.com/95westus/STR8-N/tree/v2.0a24) remains the stable
release and alpha board-test package. It uses the FT245 console and provides bank
selection, RAM/S19 loading, verified flash writes, boot handoff, and an
optional E-sector S/R/T extension. W65C816SXB board 2609 passed the core
migration and regression checks. W65C02SXB board 2205 passed the unified
installer and no-EDU migration checks. The EDU daughterboard was absent.

## Alpha25 EDU/RTC board tests

Alpha25 is a board-test candidate. With an attached EDU and a valid, advancing
MCP79411 RTC, it prints the weekday, date, and 24-hour time before `B3>`:

```text
STR8-N 2.0a25 B3 65C02
ABI 65C02 | 816E | 816N-VEC
EDU KIT       DETECTED
  RTC         Wed 26-09-30 18:40:16
B3>
```

The RTC is read-only during startup. The display requires valid calendar fields,
a running oscillator, and an advancing seconds value. The weekday abbreviation
comes from the RTC weekday register using board 2205's Sunday-first mapping.
Without a valid running RTC, the monitor reports `EDU KIT       INCONCLUSIVE`
and still reaches `B3>`. The dated reports hold installer details, hashes, and
serial evidence.

| Board | CPU | EDU | Alpha25 result |
| --- | --- | --- | --- |
| [2205](docs/STR8N_V2_A25_2205_DOW_2026-09-30.md) | W65C02SXB | Attached | `DETECTED`; weekday/date/time shown. Exact E/F readback and physical RESET passed. |
| [2512](docs/STR8N_V2_A25_2512_INSTALL_2026-09-30.md) | W65C02SXB | Absent | `INCONCLUSIVE`; exact E/F readback and software reentry passed. Owner-shared reset output reached `B3>`. |
| [2609](docs/STR8N_V2_A25_2609_INSTALL_2026-09-30.md) | W65C816SXB | Absent | `INCONCLUSIVE`; guarded E/F on-board verification and software reentry passed. No live flash readback was requested. |

The host checks (`make v2-a25-rtc-check`) cover valid and invalid dates, all
seven weekday values, 12/24-hour conversion, stopped/absent RTC paths, and
startup placement. The [RTC display notes](docs/STR8N_V2_A25_RTC_DISPLAY.md)
describe the behavior in detail. EDU RTC behavior on the W65C816SXB remains
untested.

[Download the alpha24 board-test package](https://github.com/95westus/STR8-N/releases/download/v2.0a24/str8n-v2-alpha24-board-test.zip)
and its [SHA-256 checksum](https://github.com/95westus/STR8-N/releases/download/v2.0a24/str8n-v2-alpha24-board-test.sha256).

The same alpha24 WDCMONv2 RAM installer runs on both SXB CPU families: its
`$FB` entry byte is XCE on the 816 and a one-byte NOP on the W65C02S. The
65C02 installer runs in an automated CPU/flash model; the 816 qualification
uses recorded manual board tests.

- [W65C816SXB manual migration guide](docs/STR8N_V2_A24_816_MANUAL_MIGRATION.md)
- [Guarded B3:E SAVE/RESTORE installation guide](docs/STR8N_V2_A24_B3_E_INSTALL.md)
- [Alpha24 package contents and limits](docs/STR8N_V2_A24_PACKAGE_README.md)
- [Alpha24 maps and diagrams](docs/STR8N_V2_A24_MAPS.md)
- [816 qualification checklist](docs/STR8N_V2_A24_816_CHECKLIST.md)
- [02SXB no-EDU migration checklist](docs/STR8N_V2_A24_02_NO_EDU_CHECKLIST.md)
- [02SXB board 2205 result](docs/STR8N_V2_A24_2205_NO_EDU_2026-09-30.md)

Run `make v2-a24-package` to build and verify the local alpha24 ZIP. The
[v2 development guide](docs/STR8N_V2.md) and
[release manual index](docs/RELEASE_MANUALS.md) retain earlier contracts and
release history. STR8-N is independent of WDC and R-YORS; see [LICENSE](LICENSE).
