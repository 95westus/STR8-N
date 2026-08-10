# Bank 0-2 Guest Images And STR8-N S19 Requirements

This document describes how to install a completely user-owned system into
Bank 0, 1, or 2 with STR8-N V1.02. The guest may be WOZMON, OSI BASIC,
fig-FORTH, another monitor, a game, an operating environment, or any other
W65C02 system that obeys the handoff contract below.

> [!WARNING]
> **Flashing is destructive and is performed at your own risk.** STR8-N has
> been thoroughly host- and hardware-tested on its intended system, but a
> wrong image, bank, range, address, interrupted write, power loss, or operator
> mistake can destroy stored software, corrupt firmware, leave the board
> unbootable, or require external-programmer recovery. Incorrect programmer
> voltage, wiring, chip selection, or device settings can physically damage
> the flash device, programmer, or board. Preserve verified backups and a
> known-good Bank-3 recovery image before any write.

Banks 0-2 do not contain or require STR8-N. Each guest owns its entire visible
32K ROM window, including sector F and all hardware vectors:

```text
CPU address       Guest meaning
$8000-$FFF9       entirely guest-defined code, data, and padding
$FFFA-$FFFB       guest NMI vector, little-endian
$FFFC-$FFFD       guest RESET vector and STR8-N Jn entry, little-endian
$FFFE-$FFFF       guest IRQ/BRK vector, little-endian
```

There is no required STR8 signature, boot parameter block, HIMON marker, or
fixed service address in Banks 0-2. Bank 3 remains the physical-reset root and
contains STR8-N plus its default payload.

## Two different S19 files

Keep these artifacts distinct:

1. The **guest payload S19** describes only the guest's selected ROM range.
2. The **STR8-N install stream** prepends STR8-N's exact mutation worker to
   that payload. This combined stream is the file sent at `SEND S19`.

Do not send a payload-only S19 to the V1.02 `I` prompt. It will be rejected
because the transaction receiver first requires the mutation worker at
`$0200-$042A`.

## Complete 32K guest payload

For a fully independent Bank 0-2 computer, the payload S19 must represent
exactly 32,768 bytes from `$8000` through `$FFFF`:

- Use dense, ascending `S1` data records with 16-bit addresses.
- The first data byte must be at `$8000`; the last must be at `$FFFF`.
- There may be no gaps, overlaps, duplicate bytes, or out-of-order records.
- Bytes whose value is `$FF` must still appear. Do not use sparse S-records.
- Every S-record count and checksum must be correct.
- One optional `S0` header may precede the data.
- Exactly one `S9` record must follow the data.
- For a full 32K image, the S9 entry must equal the little-endian RESET vector
  stored at `$FFFC-$FFFD`.
- Do not use `S2`, `S3`, `S5`, `S7`, or `S8` records.

STR8-N can parse larger records, but 32 data bytes per S1 record are the
recommended interoperable shape and match the supplied converter.

The RESET vector must be `$8000-$FFFE`, must not be `$FFFF`, and must point to
code present in the exact 32K image. STR8-N checks this reset-vector range
before `J0`, `J1`, or `J2`. It does not validate the NMI or IRQ/BRK vectors.
Those remain the guest's responsibility.

## Starting from a raw 32K BIN

The safest source artifact is a raw file with byte 0 mapped to `$8000` and
byte `$7FFF` mapped to `$FFFF`. It must be exactly 32768 bytes. Explicitly pad
unused regions with `$FF`; do not ask a programmer or S-record converter to
invent missing areas.

Convert and validate it with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/convert_guest_bin_to_s19.ps1 `
  -BinPath C:\IMAGES\wozmon-bank.bin `
  -S19Path BUILD/s19/wozmon-8000-ffff.s19
```

The converter refuses any file that is not 32768 bytes or whose RESET vector
is outside `$8000-$FFFE`. It emits dense 32-byte S1 records and an S9 matching
the RESET vector.

A system originally linked only for `$C000-$FFFF`, such as some BASIC or
FORTH images, is still packaged as a complete 32K guest: fill `$8000-$BFFF`
with `$FF`, place the system at its linked addresses, and provide all three
vectors at `$FFFA-$FFFF`. A system with no suitable reset entry needs a
guest-owned startup wrapper and vectors in its own image.

## Compose the file sent to STR8-N

Build the standalone mutation worker first:

```powershell
make workers
```

Then combine the checked worker and payload:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools/compose_str8n_install_s19.ps1 `
  -PayloadS19Path BUILD/s19/wozmon-8000-ffff.s19 `
  -PayloadStart 32768 `
  -PayloadEndExclusive 65536 `
  -S19Path BUILD/s19/str8n-i-wozmon-bank.s19
```

The composer validates the worker identity, dense payload extent, checksums,
S9/reset-vector agreement, and record ordering. Its output contains:

```text
dense worker S1 records       $0200-$042A
dense guest S1 records        $8000-$FFFF
one guest S9                  entry equals $FFFC-$FFFD vector
```

## Install a complete Bank 0-2 guest

From the Bank-3 STR8-N prompt, enter one response at a time:

```text
I
0                 choose 0, 1, or 2
8-F               all eight 4K sectors
A5                example two-hex-digit type for a new directory row
WOZ                example 1-5 character description
Y                 confirm WRITE
```

Existing directory rows retain their original type and description and may
not ask for those two fields. Wait for `SEND S19`, then send only the combined
install stream. A full image produces eight sector dots and must finish with:

```text
I OK
STR8-N>
```

Any `I FAIL`, `DIR FAIL`, missing dot, lost connection, or reset during the
transfer is a stop condition. Do not issue `Jn` until the directory reports a
complete transaction and the programmed bank has been read back.

## Jn is a warm handoff, not electrical reset

After selecting the target bank, STR8-N reads `$FFFC-$FFFD` and jumps with:

```text
PC    guest RESET vector
I     1; maskable IRQ disabled
D     0; binary arithmetic
X     $FF
S     $FF
A/Y   unspecified
RAM   preserved, not cleared
I/O   preserved, not electrically reset
NMI   must remain quiescent during handoff
```

A guest that assumes power-on RAM or peripheral state needs a startup wrapper
that initializes its environment before entering its original cold start.
The guest must preserve or deliberately reassert the VIA PCR bank-selection
bits; blindly rewriting the complete PCR can map its own ROM out.

## Required qualification before routine use

For each exact guest build and destination bank:

1. Record the 32K BIN SHA-256 and all three vectors.
2. Keep a known-good Bank-3 STR8-N image and external-programmer recovery.
3. Program only the intended bank and read back all 32768 bytes.
4. Compare the readback byte-for-byte and record a full-bank CRC.
5. Confirm NMI and IRQ/BRK safety; STR8-N validates only RESET plausibility.
6. Perform one manual `Jn`, identify the guest, and test its console/devices.
7. Use physical RESET to prove reliable return to Bank 3.
8. Repeat the handoff/reset/readback cycle before treating the guest as safe.

WOZMON, OSI BASIC, FORTH, and other systems are not automatically qualified
merely because their S19 is structurally valid. Their exact startup behavior,
vectors, peripherals, and warm-state assumptions must also pass.

## Physical flash map

For the 128K SST39SF010A used as four 32K banks:

```text
Bank 0 physical $00000-$07FFF   CPU $8000-$FFFF
Bank 1 physical $08000-$0FFFF   CPU $8000-$FFFF
Bank 2 physical $10000-$17FFF   CPU $8000-$FFFF
Bank 3 physical $18000-$1FFFF   CPU $8000-$FFFF
```

The standalone 4096-byte STR8-N programmer BIN maps CPU `$F000-$FFFF` to
physical Bank-3 addresses `$1F000-$1FFFF`. Its byte 0 belongs at physical
`$1F000`, not device address zero.
