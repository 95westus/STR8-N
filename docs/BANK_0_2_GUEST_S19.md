# Bank 0-2 Guest Images And STR8-N V2 S19 Requirements

Banks 0-2 can contain completely user-owned W65C02 systems. They do not need
STR8-N, a HIMON marker, or any fixed service address. A full image owns the
visible ROM window and vectors:

```text
$8000-$FFF9  guest code, data, and explicit padding
$FFFA-$FFFB  NMI vector
$FFFC-$FFFD  RESET vector used by STR8-N Jn
$FFFE-$FFFF  IRQ/BRK vector
```

> [!WARNING]
> Keep a known-good Bank-3 image and external-programmer recovery. Do not
> remove power or press NMI while STR8-N is erasing or programming flash.

## Payload-only transport

V2 embeds and verifies its worker. Send only the guest payload when `I` prints
`S19`. A historical V1.02 stream beginning with worker records at `$0200` is
invalid and will be rejected.

The selected range may be 4K, 8K, 12K, 16K, 20K, 24K, 28K, or 32K. It starts
on a 4K boundary at or above `$8000` and ends no later than `$10000`. The S19
must contain:

- at most one initial S0;
- dense, ascending S1 data covering every selected byte, including `$FF`;
- no gap, overlap, duplicate, empty, backward, or unsupported record; and
- exactly one final S9 with a valid checksum and nothing after it.

For a complete `$8000-$FFFF` Bank 0-2 image, S9 must equal the non-erased
little-endian RESET vector stored at `$FFFC-$FFFD`. For a partial image, S9 is
`$FFFF` or points inside the selected range.

## Convert a BIN

The converter accepts any 4K-aligned 4K-32K BIN. Byte zero maps to the supplied
base address:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/convert_guest_bin_to_s19.ps1 `
  -BinPath C:\IMAGES\wozmon-bank.bin `
  -BaseAddress 32768 `
  -Bank 0 `
  -S19Path BUILD/s19/wozmon-8000-ffff.s19
```

For a full Bank 0-2 image the converter derives S9 from RESET. For a partial
image its default is `$FFFF`; use `-EntryAddress` to publish an in-range entry.
The default S1 record payload is 32 bytes.

## Validate an existing S19

The historical composer name is retained so existing scripts have an obvious
migration path, but it no longer composes a worker. It validates and writes a
payload-only stream:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/compose_str8n_install_s19.ps1 `
  -PayloadS19Path BUILD/s19/wozmon-8000-ffff.s19 `
  -PayloadStart 32768 `
  -PayloadEndExclusive 65536 `
  -Bank 0 `
  -S19Path BUILD/s19/str8n-i-wozmon.s19
```

It reports the exact extent, S1 count, S9, per-sector CRC-16, and SHA-256.

## Install

At the STR8-N prompt, enter `I`, choose Bank 0, 1, or 2, and enter the sector
range (for example `8-F` for 32K). A new directory row also asks for a two-digit
type and five-character description. Confirm `WRITE?` with `Y`, send the
payload-only S19, and confirm `COMMIT?` with `Y` after S9 validation.

The final sector is not programmed before that last confirmation. A complete
install prints one dot per programmed sector and `OK`. A failed or interrupted
transaction requires a complete 32K recovery install for that bank; a smaller
retry is deliberately refused.

## Jn handoff

`J0`, `J1`, or `J2` selects the bank and jumps through its RESET vector with
IRQ disabled, decimal mode clear, X and the stack pointer set to `$FF`, and RAM
and peripherals otherwise preserved. This is not an electrical reset. The
guest must initialize any power-on state it requires and must not blindly
rewrite the VIA PCR bank-selection bits.

Physical RESET always selects Bank 3 and returns to STR8-N.

## Flash map

```text
Bank 0 physical $00000-$07FFF   CPU $8000-$FFFF
Bank 1 physical $08000-$0FFFF   CPU $8000-$FFFF
Bank 2 physical $10000-$17FFF   CPU $8000-$FFFF
Bank 3 physical $18000-$1FFFF   CPU $8000-$FFFF
```
