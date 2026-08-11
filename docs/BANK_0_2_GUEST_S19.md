# Bank 0-2 Guest S19 Quick Reference

Banks 0-2 may hold independent W65C02 systems. A guest does not need HIMON,
STR8-N ROM services, or a copy of the STR8-N worker. Launch is through the
guest bank's hardware RESET vector.

## Full 32K guest layout

```text
$8000-$FFF9  guest code, data, and explicit padding
$FFFA-$FFFB  NMI vector, low byte first
$FFFC-$FFFD  RESET vector, low byte first
$FFFE-$FFFF  IRQ/BRK vector, low byte first
```

The install file contains payload only. Never prepend records at `$0200`;
STR8-N supplies and verifies its own embedded worker.

## Accepted file contract

- Select one contiguous 4K-aligned span inside `$8000-$FFFF`.
- The span may be 4K, 8K, 12K, 16K, 20K, 24K, 28K, or 32K.
- Use at most one leading S0 record.
- Use ascending, nonempty S1 records covering every byte in the selected
  extent. Explicit `$FF` bytes are required.
- Do not use gaps, overlaps, duplicate addresses, backward records, or S2-S8.
- End with exactly one S9 and nothing after it.
- For a full `$8000-$FFFF` image, S9 must match the non-erased RESET vector at
  `$FFFC-$FFFD` and cannot be `$FFFF`.
- For a partial image, S9 is `$FFFF` or an address inside the selected extent.

S9 validates the install; `J0`-`J2` do not jump to it. They read
`$FFFC-$FFFD` after selecting the bank. A partial install can therefore be
valid but not bootable when it does not supply a usable RESET vector.

## Top-aligned size table

```text
Size  Range  Address range
 4K   F      $F000-$FFFF
 8K   E-F    $E000-$FFFF
12K   D-F    $D000-$FFFF
16K   C-F    $C000-$FFFF
20K   B-F    $B000-$FFFF
24K   A-F    $A000-$FFFF
28K   9-F    $9000-$FFFF
32K   8-F    $8000-$FFFF
```

Upper alignment is optional. `8-B`, `A-D`, and `C-E` are also legal examples.
The selected prompt range and S19 extent must match exactly.

## Convert an aligned binary

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/convert_guest_bin_to_s19.ps1 `
  -BinPath C:\IMAGES\guest.bin `
  -BaseAddress 32768 `
  -Bank 0 `
  -S19Path BUILD/v1.2/s19/guest-bank0-8000-ffff.s19
```

For a full image, the converter derives S9 from RESET. For a partial image it
uses `$FFFF` unless `-EntryAddress` supplies an in-range address.

## Validate and normalize a payload S19

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/compose_str8n_install_s19.ps1 `
  -PayloadS19Path BUILD/v1.2/s19/guest-bank0-8000-ffff.s19 `
  -PayloadStart 32768 `
  -PayloadEndExclusive 65536 `
  -Bank 0 `
  -S19Path BUILD/v1.2/s19/str8n-i-guest.s19
```

The validator reports the exact range, record count, S9, per-sector CRC-16,
and whole-file SHA-256.

## Build the R-YORS plus STR8-N `8-F` image

With sibling `R-YORS` and `STR8-N Refactor` folders:

```powershell
make ryors-full-bank
```

Output:

```text
BUILD/v1.2/s19/ryors-v1.2-asm-himon-str8n-bank0-2-8-f.s19
$8000-$BFFF  ASM-F2
$C000-$EFFF  HIMON
$F000-$FFFF  current STR8-N 1.2 top sector
S9 / RESET   $F000
```

Install with `I`, target Bank 0, 1, or 2, and range `8-F`. On a new directory
row, enter TYPE and a five-character DESC. After `OK`, `J0`-`J2` may launch
the corresponding bank. This file cannot update protected Bank 3 sector F.

See the [Worked Examples](EXAMPLES.md) for a terminal session, the
[Operator's Guide](OPERATORS_GUIDE.md) for recovery rules, and the
[Technical Guide](TECHNICAL_GUIDE.md#s19-install-file-contract) for the full
contract.
