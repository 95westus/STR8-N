# STR8N-F — Boot & Recovery Toolkit

**[Download v0.2.0](https://github.com/95westus/STR8N-F/releases/tag/v0.2.0)**
for WDC 65C02 and 65C816 emulation-mode boards, using USB/FT245.

STR8N-F boots your own images in B0-B3 and provides recovery from a single
**4096-byte sector at B3:$F000-$FFFF**. Matching RAM tools configure boot,
transfer opaque sectors and export data. MON A/B are optional. The bootstrap
requires no EDU, SPI SRAM, RTC, filesystem or full STR8-N installation.

The toolkit ZIP is the operator download. A separate source ZIP contains the
unified local-source build and optional components. This is an early toolkit
release, not completed 1.0 factory-migration acceptance. The shipped F remains
**b15 / PR04 / 8000000F**; package version 0.2.0 does not rename its firmware.

## Start here

- [Quick start](docs/QUICK_START.md): recovery, CONFIG and selecting an image.
- [Installation](docs/INSTALLATION.md): exact destinations and preservation.
- [Operator guide](docs/OPERATOR_GUIDE.md): commands and boot records.
- [Opaque image contract](docs/IMAGE_CONTRACT.md) / [OIP1 transfer](docs/OPAQUE_PROTOCOL.md).
- [RAM export/restoration](docs/READBACK.md).
- [Release scope/evidence](docs/RELEASE_STATUS.md) / [Release notes](docs/RELEASE_NOTES.md).

## Operator kit

| File | Destination / purpose |
|---|---|
| STR8N-F-BOOT-4096.bin | B3:F000-FFFF only; reset, boot choices, recovery and raw RAM loader |
| STR8N-F-CONFIG-RAM.bin | RAM $0200; inspect settings/wear, enable entries and save a default |
| STR8N-F-OPAQUE-RAM.bin | RAM $0200; OIP1 read/replace with preimage checks and erase accounting |
| STR8N-F-DEMO-RAM.bin | RAM $0200; small console/capability demonstration |
| STR8N-F-READBACK-RAM.bin | RAM $0200; binary export and fixed-range RAM restore |
| Optional BASE MON A/B | Separate 4 KiB monitor sectors; inspection shells |

The RAM files are BIN programs, not flash images. At REC>, enter C1, then L,
then binary-send the selected RAM BIN after SEND BIN. F executes it at $0200
after approximately three seconds of transfer silence. Initial Ctrl-C cancels.
Raw L has no declared length or transfer CRC; interrupted transfers can execute
a partial tool. Preserve owner RAM before loading if needed.

For an image already installed and verified at B1:$9000, use RAM CONFIG:

```text
B 1 9000
C 1
B
Q
```

Each setting command saves immediately. CONFIG selects an image; it does not
install or validate code. Compatible C/D records are required for saved policy
and ordinary opaque writes. Missing records do not prevent F recovery. I can
initialize completely blank C/D only, recording previous wear as unknown.

## Ownership and optional development

B0, B1 and B2 are user-owned in the N/F profile. It reserves no g0034 source
arena or full-system utility banks there. Existing contents remain owner data;
new profiles do not erase them or make a WDC backup expendable. B3:C/D hold
boot/configuration/wear records, A/B are optional MONs, and F is the bootstrap.
B3:8/9/E can hold separately assigned optional components.

The [unified source guide](docs/UNIFIED_SYSTEM.md) covers optional VX1, ES1,
read-only MAINT and FLASH development. These are not automatically installed
by the operator kit. Detailed EDU/RAM/SSRAM/RTCC status belongs to those system
components. Existing g0034 images require porting before opaque personality use.

The future message journal will reserve optional SPI SRAM WORK space only,
preserving formatted program storage and the separate flash boot journal.
Journaling, WTOR, login/session policy, map cleanup and BASIC/Forth remain planned.
No WDC firmware, owner journal, SRAM or RTC/PF captures are distributed.

## Source and integrity

See [build instructions](docs/BUILD.md). The source is independent of the parent
STR8-N tree. WDC assembler tools are needed only to rebuild. Prebuilt payloads,
SHA-256 baselines and existing evidence are included. The runtime kit has its
own verify_package.py. The source tool tools/verify_system.py checks consistency
without opening a port, rebuilding or running CPU models. No routine simulation
or repeat assembly build was performed for this unchanged firmware release.
