# Changelog

## v0.2.0 — Boot & Recovery Toolkit

Put N/F boot/recovery first. Supply a focused operator ZIP with exact existing
F, CONFIG, OPAQUE, DEMO and READBACK payloads, optional compact monitors, a
standalone integrity checker and operator/image/installation contracts. Keep
the unified source and larger optional modules in a separate source ZIP.
Publish inherited hardware scope without private captures. Firmware remains
b15/PR04/8000000F; no assembly rebuild, CPU simulation or board flashing is
part of release preparation. CI defaults to integrity checks; CPU models are
an explicit manual option. The future SPI WORK journal remains outside 0.2.0.

## Unreleased: unified 2512/2609 source tree

One local-source build now supplies F, common CONFIG/OIP1/DEMO/MAINT/readback,
both MON flavors, VX1, ES1 and the LED-fixed FLASH placements. Profiles retain
each board's image allocation and preservation requirements. The 4096-byte F,
MON variants and other unchanged components reproduce their qualified bytes.
MAINT and EDU-client text becomes generic; MAINT no longer labels every B0 as
a WDC backup or every E as VX1. Firmware identity and SNBT remain unchanged.

This is local development; it does not publish or replace the preview tag.

## v0.1.0-preview.1

Extract the b15 F bootstrap, CONFIG, opaque installer and RAM demo into an independently buildable repository focused on user B0–B3 booting. Preserve the 4096-byte F identity and hashes; replace CONFIG's board-number banner with STR8. Include operator/install/protocol documentation, offline packet preparation, CPU/NOR tests, provenance and reproducible packaging.

This is a source preview. General factory migration, wear-history import, live host opaque installation and final hardware acceptance remain open.
