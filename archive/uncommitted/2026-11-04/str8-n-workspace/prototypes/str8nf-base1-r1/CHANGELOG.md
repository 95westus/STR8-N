# 0.3.0 — the 4KB foundation

- Release frozen STR8N-F 0.3.0 g00000001 / BASE1 / PR05 without ABI changes.
- Include Python Serial Console 0.1.0, function keys, five matching RAM tools,
  verbose migration/provisioning/upgrade hosts and prebuilt engines.
- Record the extracted rc1 existing-journal upgrade pass on 2609 in addition
  to the reviewed 2512 hardware cases; preserve the immutable rc1 archive.
- Correct rc1 layout/upgrade wording; retain the manual-capture precondition
  and distinguish untested final-package/WDC/programmer-F package routes.
- Name the future optional monitor Mona; no Mona payload is included.
- Package existing runtime bytes; no firmware rebuild, simulation or board access.

The historical candidate and source checkpoints follow.

# 0.3.0-rc1 — BASE1 migration-test candidate

> Give me 4KB, I can give you 4 boards.

With ~32KB RAM shared by four selectable bank environments.

- Consolidate the reviewed 2512 hardware closeout and acceptance receipts.
- Include Python Serial Console 0.1.0, function keys and pinned pyserial.
- Package WDC migration, programmer-F C/D provisioning and known-b15 SNBT
  upgrade commands with their unchanged prebuilt engines and wrapper dependency.
- Add a portable manifest/dependency/link checker and extracted-ZIP test workflow.
- Keep F frozen at 0.3.0 g00000001 / BASE1 / PR05, exactly 4096 bytes.
- Leave migration from the extracted candidate **NOT RUN** and publication pending.
- No firmware rebuild, simulation, port access or flashing during packaging.

The earlier source/build and package changelog follows.

## Historical BASE1 identity and RAM-map checkpoint

- STR8N-F 0.3.0, F generation 00000001, BASE1 / PR05 startup identity.
- Bounded public FI identity locator; existing PR05 call addresses preserved.
- Frozen 4096-byte F; later RAM catalogue/tool builds reuse it.
- RAM MAP recognizes known/possible WDC resident monitors, updates BASE1 roles
  and fixes the detailed sector-number printer.
- Matching host SHA/size/prompt bindings; no OS status or recognition logic in F.
- Hardware acceptance and the listed migration release gaps remain pending.
- No flashing, device access, CPU simulation or reproduction build.

The historical package changelog follows; it does not qualify BASE1 hardware.

# Changelog

## v0.2.0 â€” Boot & Recovery Toolkit

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

Extract the b15 F bootstrap, CONFIG, opaque installer and RAM demo into an independently buildable repository focused on user B0â€“B3 booting. Preserve the 4096-byte F identity and hashes; replace CONFIG's board-number banner with STR8. Include operator/install/protocol documentation, offline packet preparation, CPU/NOR tests, provenance and reproducible packaging.

This is a source preview. General factory migration, wear-history import, live host opaque installation and final hardware acceptance remain open.
