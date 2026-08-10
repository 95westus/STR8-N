# Bank 0-2 Guest S19 Quick Reference

Banks 0–2 may hold independent W65C02 systems. A guest does not need STR8-N,
HIMON, or any STR8-N service address.

## Full 32K guest

```text
$8000-$FFF9  guest code, data, and explicit padding
$FFFA-$FFFB  NMI vector
$FFFC-$FFFD  RESET vector, low byte first
$FFFE-$FFFF  IRQ/BRK vector
```

The install file contains the payload only. Do not put RAM-worker records at
`$0200` in front of it.

## File rules

- Select a 4K-aligned range of 4K, 8K, 12K, 16K, 20K, 24K, 28K, or 32K.
- Use at most one leading S0 record.
- Use ascending, nonempty S1 records covering every byte in the selected
  range. `$FF` bytes must be present too.
- Do not use gaps, overlaps, duplicate addresses, backward records, or other
  S-record types.
- End with exactly one S9 record and nothing after it.
- For a full `$8000-$FFFF` image, S9 must match the non-erased RESET vector at
  `$FFFC-$FFFD` (stored low byte, then high byte).
- For a partial image, S9 is `$FFFF` or an address inside the selected range.

## Top-aligned size table

Every one of these Bank 0-2 ranges is accepted:

```text
 4K  F      $F000-$FFFF
 8K  E-F    $E000-$FFFF
12K  D-F    $D000-$FFFF
16K  C-F    $C000-$FFFF
20K  B-F    $B000-$FFFF
24K  A-F    $A000-$FFFF
28K  9-F    $9000-$FFFF
32K  8-F    $8000-$FFFF
```

They include sector F and therefore carry the hardware vectors. STR8-N still
launches through the RESET vector at `$FFFC-$FFFD`, not through S9, so that
vector must point to code that is present in the bank. Upper alignment is
optional; any contiguous 4K-aligned span inside `$8000-$FFFF` is legal.

## Convert a binary

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/convert_guest_bin_to_s19.ps1 `
  -BinPath C:\IMAGES\guest.bin `
  -BaseAddress 32768 `
  -Bank 0 `
  -S19Path BUILD/s19/guest-bank0-8000-ffff.s19
```

For a full image the converter reads S9 from RESET. For a partial image it
uses `$FFFF` unless `-EntryAddress` supplies an in-range entry.

## Validate a payload S19

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/compose_str8n_install_s19.ps1 `
  -PayloadS19Path BUILD/s19/guest-bank0-8000-ffff.s19 `
  -PayloadStart 32768 `
  -PayloadEndExclusive 65536 `
  -Bank 0 `
  -S19Path BUILD/s19/str8n-i-guest.s19
```

The validator reports the exact range, record count, S9, per-sector CRC-16,
and whole-file SHA-256.

See the [Operator's Guide](OPERATORS_GUIDE.md) for the `I` procedure and the
[Technical Guide](TECHNICAL_GUIDE.md#s19-install-file-contract) for all Bank-3
and interrupted-install rules.
