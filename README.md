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

## Alpha34 VIA port labels

Alpha34 shows `VIA1 $7FC0  A:I2C  B:SPI` in the startup inventory. Board
2205 passed guarded E/F installation, exact full readback, and software
reset. Run `make v2-a34-check`; see the
[board report](docs/STR8N_V2_A34_2205_INSTALL_2026-10-01.md).

## Alpha33 crypto serial number

Alpha33 reads the crypto chip's nine-byte serial number at startup and prints
it beneath the ATECC608 device row. Board 2205 passed guarded E/F installation,
complete image readback, and software reset. Run `make v2-a33-check`; see the
[board report](docs/STR8N_V2_A33_2205_INSTALL_2026-09-30.md).

## Alpha32 device inventory and crypto status

Alpha32 prints a fixed-column EDU inventory and reads the ATECC608 family
chip at I2C `$60` for revision, configuration/data lock state, and two
counters. The crypto replies are CRC-checked; failed reads display
`UNAVAILABLE`. SPI SRAM remains a listed component, not an active capacity
probe. `make v2-a32-check` builds and tests the candidate. Board 2205 passed
guarded E/F installation and exact full readback; see the
[board report](docs/STR8N_V2_A32_2205_INSTALL_2026-09-30.md).

## Alpha31 memory retention and SPI display

Alpha31 adds the 23LCV1024 SPI inventory, address range, and SRAM/EEPROM
retention labels. Board 2205 passed guarded E/F installation, exact full
readback, software reentry, and preserved settings. The SPI and battery text
is descriptive; neither is tested by this display. Run `make v2-a31-check`;
see the [board 2205 result](docs/STR8N_V2_A31_2205_INSTALL_2026-09-30.md).

## Alpha30 I2C hierarchy

Alpha30 places I2C at the top display level and indents the MCP79xxx and its
features beneath it. Board 2205 passed guarded E/F installation, exact full
readback, software reentry, and preserved EEPROM settings. Run
`make v2-a30-check`; see the
[board 2205 result](docs/STR8N_V2_A30_2205_INSTALL_2026-09-30.md).

## Alpha29 VIA1 base display

Alpha29 adds `VIA1 @ $7FC0` to the I2C line on EDU boards. Board 2205 passed
guarded E/F installation, exact full readback, software reentry, and preserved
EEPROM settings. Run `make v2-a29-check`; see the
[board 2205 result](docs/STR8N_V2_A29_2205_INSTALL_2026-09-30.md).

## Alpha28 I2C display

Alpha28 uses the selected, less-indented I2C hierarchy on EDU boards. Board
2205 passed guarded E/F installation, exact full readback, software reentry,
and saved EEPROM configuration checks. Run `make v2-a28-check`; see the
[board 2205 result](docs/STR8N_V2_A28_2205_INSTALL_2026-09-30.md).

## Alpha27 I2C display candidate

Alpha27 adds an indented I2C inventory on EDU boards: MCP79XXX, RTC `$6F`
with date/time, shared-address 64-byte SRAM, and EEPROM `$57` with aligned
settings. The EEPROM format and commands remain those of alpha26. Run
`make v2-a27-check`. Board 2205 passed a guarded installation, exact full
E/F readback, and preserved EEPROM settings. See the
[alpha27 display design](docs/STR8N_V2_A27_I2C_DISPLAY.md) and
[board 2205 result](docs/STR8N_V2_A27_2205_INSTALL_2026-09-30.md).

## Alpha26 EEPROM settings candidate

Alpha26 moves autostart settings into two validated MCP79411 EEPROM records
and adds the aligned EEPROM/settings startup display. It frees the former
B3:E `$EFF0-$EFFF` configuration pocket; 812 bytes are free in E.
Additional EEPROM uses are deferred. Run `make v2-a26-check` for host checks.
Board 2205 passed guarded E/F installation, full flash readback, EEPROM saves,
record recovery, autostart/hold, and physical RESET persistence with the EDU.
Board 2512 passed guarded installation, full flash readback, and no-EDU
software reentry. Board 2609 passed installation and software reentry without
an EDU. See the
[alpha26 design and layout](docs/STR8N_V2_A26_EEPROM.md),
[board 2205 result](docs/STR8N_V2_A26_2205_INSTALL_2026-09-30.md),
[board 2512 result](docs/STR8N_V2_A26_2512_INSTALL_2026-09-30.md), and
[board 2609 result](docs/STR8N_V2_A26_2609_INSTALL_2026-09-30.md).

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
