# 2512 TIME and cold-start SRAM fixes accepted

November 1, 2026. Installed and verified on **2512: MON A/B g0000000F**,
above unchanged STR8N-F 0.3.0 g1 BASE1/PR05. Both requested fixes are closed
on this board. Other boards and published downloads are unchanged.

## Result

- TIME retries an invalid calendar snapshot within the existing three-attempt
  budget shared with incoherent reads. It displays only a fresh, validated
  calendar/control/trim snapshot. Persistent invalid clocks still return $04;
  persistent incoherence returns $07, and NACKs still fail.
- Cold startup automatically prepares disabled VIA CB flags after all SRAM
  ownership guards pass. It rechecks flags before any SPI clock. Enabled
  interrupts, owned pins and persistent pending flags still refuse.

The captured physical default-B gF startup showed:

```text
MONITOR A gen 0000000F VALID
MONITOR B gen 0000000F VALID default
Board: 2512
RAM $0200-$66FF
EDU ON
SSRAM: PROGRAM payload 63488 bytes
SSRAM: WORKSPACE 65504 bytes
```

No manual PREP was issued. Post-reset SRAM TABLE showed CLK, CLOCK and NFCOPY.
Installed A selection/TIME and B's SRAM, MAINT, CLOCK and FLASH read-only routes
passed. Native TIME passed nine strict NIST-referenced samples, retaining raw
trim $0C (−12) and control $80. The unchanged 794-byte LED sampler passed its
62-second qualification with exact RAM/LED restoration.

Versioned gF readers and routing are registered for 2512. Old gD/gE readers,
historical audits, baselines, points, cadence and other-board admissions remain.
The fleet lease was released while waiting for RESET, and final registration
yielded to scheduled RTC collection.

## Preservation and exact scope

The approved three erases were used once: B2:F and B3:A/B. B2:F is the utility
sector; **golden Foundation at B3:F and its frozen sources remain exact**.
Three wear reservations plus one default-B generation binding were appended
at D500–D800. All 21 old journal records remain byte-for-byte on chip. Final
journal: sequence 1150, 25 valid records. Counts C/D/E/F remain 56/37/36/24;
B2:F is 19, and A/B are 47/54. There were zero C/D erases or extra replacements.

Default stays B; enables, entries and delay remain. Saved EDU remains ON;
name, zone and battery metadata remain exact. B0/B1 and all images outside
the reviewed replacements are preserved. No SPI data/mode, RTC setting/trim,
PF acknowledgement/history or EEPROM write was performed. No power cut.

Fresh owner RAM $0200–$66FF and ZP $00–$DF were restored and read back after
borrowing. Final state: **REC>, COM4 released**. The approved erase scope is
exhausted; further persistent changes need their own review.

## Evidence and limits

Private closeout receipt:
`output/qualification/2512-TIME-PREP-closeout-20261101-r1/report.json`.
It pins RAM, installed-image, tool-route, cold-start and RTC receipts.
The [approved review](TIME_PREP_2512_FLASH_SCOPE.md) remains sealed and unchanged.

Twenty-two RAM checks preceded installation. They include old/new invalid-first
TIME behavior, valid retry, persistent failure/NACK/date refusal, and SRAM
ownership/flag cases. Physical SRAM reads and a full minute of live RAM TIME
passed separately. The old post-reset guard was reproduced with actual
IFR $18 / IER $80 before the RAM candidate cleared the disabled flags safely.
That earlier RAM reset used the owner's report after its receiver expired;
the final installed gF default-B startup was captured in full.

The raw hardware bytes behind the original intermittent $04 were not captured,
so no electrical cause is claimed. Retry/refusal behavior was tested on the
2512 CPU, followed by live RAM and installed TIME/NIST acceptance.

Two host-checker failures are retained: a match-object assertion during RAM
testing and a prompt transition after programming. Accepted checks and exact
write receipts were carried forward into preserving continuations. Firmware
was not rebuilt or reflashed to address those host errors.

MON bodies have 9 bytes free each; STATUS details fill their existing allocation.
This checkpoint does not qualify another board or publish a new kit.
