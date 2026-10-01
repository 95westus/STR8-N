# Alpha27 I2C startup display

Alpha27 keeps the alpha26 EEPROM record and configuration commands. On an EDU
board with a validated, advancing RTC, startup groups the MCP79xxx features:

```text
EDU KIT       DETECTED
  I2C         READY
    MCP79XXX
      RTC     $6F  Wed 26-09-30 20:14:41
      SRAM    $6F  64 BYTES
      EEPROM  $57  VALID
        AUTOSTART  DISABLED
        TARGET     B3 $F007
        DELAY      1.0 SEC
B3>
```

The value columns of the EEPROM status and its settings align. `$6F` and
`$57` are 7-bit I2C addresses. SRAM shares `$6F` with the RTC and occupies
registers `$20-$5F`; the line reports capacity, not a memory test. `MCP79XXX`
names a compatible family because the device does not expose a model register.
An inconclusive RTC still prints `EDU KIT INCONCLUSIVE` and the separately
obtained EEPROM status. EEPROM writes and the autostart setting format are
unchanged from alpha26. See the alpha26 EEPROM layout for record details.

Build and host validation: `make v2-a27-check`.
