# STR8-N

**Keep the board bootable while changing everything above it.**

STR8-N is a compact Bank-3 reset supervisor, image installer, and recovery
front door for the W65C02SXB/EDU four-bank flash system. It starts before the
payload, protects its own top sector during ordinary installs, and hands the
machine to the selected bank without requiring the payload to understand
STR8-N.

STR8-N began inside R-YORS, but its job is deliberately narrower: keep the
board recoverable, install and verify target images, and then get out of the
way. HIMON is the default bundled payload, not a requirement for STR8-N.

> [!WARNING]
> **Flashing is destructive and is performed at your own risk.** Historical
> STR8-N releases have hardware evidence; this V2 refactor still requires the
> qualification listed below. No flash operation can be made risk-free. A
> wrong image, bank, address, device selection, interrupted write, power loss,
> or operator mistake can erase
> stored software, corrupt firmware, leave the board unbootable, or require an
> external programmer for recovery. Incorrect programmer voltage, wiring, or
> device settings can also physically damage the flash device, programmer, or
> board. Keep verified backups and a known-good recovery image before writing.

In practical terms, STR8-N can turn one W65C02SXB/EDU into as many as four
different computers. Banks 0-2 can hold independent 32K systems, while Bank 3
pairs STR8-N with a default payload. Choose a personality at reset, and the
selected system owns the machine.

## What STR8-N can do

- Own physical reset in Bank 3 and offer a timed boot/recovery selector.
- Boot opaque images in Banks 0-3 through the non-destructive `J0`-`J3`
  handoff path.
- Warm-enter a compatible local HIMON image with `H`, while rejecting an
  erased, foreign, or corrupt identity marker.
- Receive dense Motorola S-record images through the FTDI console.
- Install any contiguous 4K-aligned range from 4K through 32K in Banks 0-2.
- Install 4K through 28K in Bank 3 while refusing to overwrite its live
  protected sector F.
- Stage, erase, program, and verify flash through one RAM-resident worker so bank
  switching never depends on code in the bank being rewritten.
- Journal install progress in the fixed Bank-3 directory, allowing interrupted
  operations to fail closed and be retried deliberately.
- Provide stable reset, NMI, IRQ/BRK, record-service, and bank-selection entry
  points for the surrounding system.

The V2 refactor embeds its complete worker in the protected top sector. `I`
accepts payload-only S19; legacy streams that prepend worker bytes at `$0200`
are rejected.

## Source layout

```text
src/str8.asm               resident STR8-N supervisor and installer
src/str8-worker.asm        unified RAM-resident bank and flash worker
src/str8-*-eq.inc          shared directory, record, jump, and worker ABI
src/himon-image-eq.inc     optional HIMON warm-entry identity contract
src/util-delay.asm         calibrated 8 MHz startup/selector delay
src/str8-version.inc       compact ROM banner
```

The R-YORS repository retains the historical V1.02 qualification record.
R-YORS HIMON uses the supported `$F010` selector and `$0203` RAM entry; the
retired `$F003` gate is no longer part of the live integration.

## Build

The Makefile expects the WDC W65C02 tools `wdc02as` and `wdcln` on `PATH`.
From this directory:

```text
make             build, enforce layout, and make the programmer BIN
make resident    build the V2 resident at $F000
make workers     build the one unified RAM worker
make layout-check
                 require exact ABI addresses and at least 32 unused bytes
make programmer-bin
                 build the 4096-byte Bank-3 $F000-$FFFF T48 image
make clean       remove this folder's BUILD directory
```

Build products are written below `BUILD/`; the source tree is left clean. The
primary outputs are:

```text
BUILD/s19/str8n-f000.s19
BUILD/s19/str8n-worker-0200.s19
BUILD/bin/str8n-bank3-f000-ffff.bin
```

The 4096-byte BIN is a complete new STR8-N top-sector image: resident code,
relocated unified worker, erased V2 directory/configuration pocket, and hardware
vectors. File offsets `$000-$FFF` map to CPU `$F000-$FFFF` and to physical
SST39SF010A Bank-3 addresses `$1F000-$1FFFF`. Do not load it at device address
zero in the T48 software.

The S19 outputs remain components rather than a complete flashable R-YORS ROM.
See [Bank 0-2 Guest Images And S19 Requirements](docs/BANK_0_2_GUEST_S19.md)
for creating a user-owned 4K-32K Bank 0-2 image and the payload-only stream
accepted by STR8-N's `I` command.

[Embedded Worker And Payload-Only `I` Refactor](docs/EMBEDDED_WORKER_REFACTOR_PLAN.md)
records the settled V2 design, exact layout, recovery rules, and remaining
hardware qualification work.

## Deliberately outside V2

STR8-N V2 does not provide STR8 self-update, sparse S-record transport,
ACIA transport, catalog-aware repair, managed backup allocation, external
S-record export, or flash-wear accounting.

## Flash safety

Before exercising any write path:

- Keep a programmer-recoverable image and a known-good Bank 3.
- Verify the selected chip, programming voltage, image offset, bank, and
  address range.
- Do not remove power or press NMI during an erase, program, or restore
  operation.
- The directory journal provides 16 install pairs. When it is full, refresh
  the protected sector with an external programmer; STR8-N does not erase its
  own sector in place.

Before releasing V2, exercise all 4K-32K Bank 0-2 ranges, all 4K-28K Bank-3
ranges, interruption recovery, readback, `J0`-`J3`, and physical RESET on
sacrificial hardware. The clean host build is necessary evidence, not a
substitute for those tests.
