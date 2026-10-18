> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# 2609 aligned with 2512 firmware

At the owner's request, board 2609 now uses the same STR8-N code images as
hardware-qualified board 2512: beta32 in default monitor B (generation
0000002C), beta28 in monitor A (generation 00000028), the same fixed-F
recovery and resident service code, identical B2 utility/assets, and the
identical CLOCK 1.9 binary saved as CLK in SPI SRAM. This supersedes the
earlier F31B/slot-A-specific installation profile on 2609.

The matching recovery uses the F30D private validator. Matching included
the recovery code itself, rather than relinking applications for the
earlier retained recovery. MAINT is 2.4; SRAM, WORK and EDU are 1.4.

Complete fresh flash and 131,072-byte SRAM backups were each independently
read twice. The exact backup-bound installer was rehearsed, including
stale-preimage and corrupt-payload refusal. The modeled write order kept
the source monitor A until new B was committed, then switched fixed F,
then replaced A with the matching beta28 fallback. Both monitor validity
bytes were committed after verification. Nine erase attempts were added
to 2609's own wear journal before the operations.

Live verification passed for J3 restart, all four full flash bank readbacks,
VERSION, APPS, stored records, TIME and memory map, all four native providers,
`BATCH SRAM;G CLK;Q`, and `BATCH SRAM;G CLK;STATUS;Q`. Beta28 A was booted
through the selection menu and verified for board name and local time;
another J3 returned to default beta32 B. The expected wear line was:

```text
FLASH: wear check OK. Sector B2:8, max 581 tracked erases.
```

Before updating CLK, the complete SRAM image still matched its backup.
Afterward, the complete SRAM image matched the model's exact predicted
CLK update, with the workspace unchanged. Before/after comparisons
verified RTC settings, trim -14, EEPROM, EUI identity and history were
preserved. Board name 2609, local offset -05:00, and EDU ON were retained.
Banks 0 and 1 were preserved. The opaque image in 2512's bank 0 was not
copied to 2609; this alignment concerns STR8-N firmware and utilities.

Evidence is under `output/qualification/beta32-common-code-2609-2026-10-16`,
including complete backups, prepared payloads, model receipts, full hardware
readbacks, boot/BATCH transcripts, retained-data reports and
`hardware-qualification.json`. The original 2512 build was not rebuilt
or changed, and its soak continued using the shared serial lease.
