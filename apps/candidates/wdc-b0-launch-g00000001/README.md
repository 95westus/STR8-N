# WDC B0 opaque launcher, g00000001

Project-authored 65C02 example: 133 code/data bytes, padded to a 4096-byte B0:8000
sector. [Source](../../examples/wdc-b0-launch.asm). It requires the owner's exact
WDC B0:F ROM identified in manifest.json; no vendor ROM is included.

The physical Foundation saved-default boot trial passed on 2512/65C02/FT245.
[Acceptance](../../../docs/2512_WDC_DEFAULT_BOOT_ACCEPTANCE.md). The trial restored
the original FLASH example and B default afterward; the board is not left with
this launcher installed. F and published downloads are unchanged.

The program checks compatibility fingerprints, initializes FT245, prints its
banner and enters the pinned vendor debugger Main. It bypasses vendor F818 reset,
its CS/lamp sweep, EDU VIA DDRB write and application timeout. It hands control
to the binary WDC debugger protocol, not a text-command monitor.

A cold opaque boot has no active MON for HOLD. The qualified host return loads
and verifies a RAM bridge to public B3:F004 RESET, then selects S/recovery and
restores settings. Restarting without selecting S can boot this default again.
If a compatibility fingerprint rejects, public RAM RESET reopens Foundation;
select S there. The Main address is private to the pinned ROM, not a portable ABI.

This does not qualify another CPU/ROM, direct hardware-selector boot into WDC,
or the NFM2 factory migrator. Review occupied-sector ownership and journal room
before installation; see the linked two-erase preserving scope and operator manual.

## Files

- [Opaque launcher](WDC-B0-8000-4096.bin): install at B0:8000 through OPAQUE.
- [RAM return packet](WDC-RETURN-RESET-2000-8192.bin), [source](return-reset.asm):
  WDC upload at 2000–3FFF, verify the complete upload, then execute 2000.
  This is **not** a Foundation raw-L/F-key BIN linked at 0200.
- [Manifest](manifest.json): source, image, return-packet and required vendor-ROM hashes.

The return packet is part of the qualified host workflow. It reopens Foundation's
chooser; the receiver must select S and separately restore original owner RAM/ZP.
The packet alone is not an owner-RAM restoration utility. Both BINs contain only
project code and data; the existing owner-supplied WDC ROM remains required.
