# W65C02SXB alpha24 migration test, no EDU board

This checklist is for a physical W65C02SXB with stock WDCMONv2 and no EDU
daughterboard. Record the board number, COM port, WDCMON tag/version, flash ID,
and observed bank state in the session log. The tag suffix alone does not
identify the CPU. This test qualifies the same alpha24 installer S19 used on
the W65C816SXB. EDU peripherals are outside this test.

## Before loading RAM

- Confirm the physical board label is `W65C02SXB` and the EDU board is absent.
- Use the [package instructions](STR8N_V2_A24_PACKAGE_README.md) and one
  extracted alpha24 package. Keep its `MANIFEST.json` and session logs.
- Verify the script's binary probe reports a printable `SXB?` tag and
  WDCMONv2. Record the exact reply. The board-type prompt must be answered
  `W65C02SXB` before any RAM write.
- Preserve any owner data before migration. The installer accepts B0 only when
  erased or byte-identical to stock B3; it refuses a different occupied B0.
  It reads and copies B3 to B0 as needed. B1 and B2 are outside its write path.

## Installer and reset

1. Run `MIGRATE-STR8N-V2-A24.ps1` and select the observed COM port. Press
   physical RESET only after its receive gate is armed.
2. Confirm byte-exact `$2000-$299B` RAM readback. The image begins
   `SEC; $FB; SEI`; `$FB` is a one-byte NOP on W65C02S and XCE on W65C816S.
3. Confirm flash ID `BF/B5`. If B0 is erased, authorize `COPY B3 TO B0` at the
   installer prompt and wait for `B0 == ORIGINAL B3 VERIFIED`. If B0 is already
   identical, record that result. Stop on any different B0 or comparison error.
4. At `SEND STR8-N TOP BIN`, send the packaged 4,096-byte F BIN once with
   Ctrl+U. Enter the install phrase shown on screen; the comparison accepts
   uppercase `2.0A24`. Wait for `MIGRATION VERIFIED` before physical RESET.
5. After RESET, require `STR8-N 2.0a24 B3 65C02` and a working `B3>` prompt.
   Read back B3:F and compare all 4,096 bytes with the package BIN. Record
   B0's stock copy and confirm B1/B2 were not changed if prior captures exist.

## No-EDU regression

- Cold power cycle and confirm the same 65C02 banner and prompt.
- Run bounded monitor RAM load/execute and console checks from the alpha24
  regression procedure; verify bank-maintenance read-only `M` and `Q` paths.
- Leave S/R, EDU RTC/SPI/I2C, crypto, and EDU presence detection unqualified
  unless their hardware is present and separately tested. An absent peripheral
  is expected here; do not use LEDs or the buzzer as an EDU presence probe.
  The stock EDU demo may print peripheral `OK` for absent hardware, so its
  scan text is not an EDU-presence result.

The [W65C02S datasheet](https://www.wdc65xx.com/wdc/documentation/w65c02s.pdf)
lists `$FB` among one-byte NOP opcodes. [Board 2205](STR8N_V2_A24_2205_NO_EDU_2026-09-30.md)
completed this checklist's migration and readback path on 2026-09-30.
