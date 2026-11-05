# STR8-N UTIL READBACK — BASE1 binary export

Use the PR05 service described in [BASE1 recovery/readback](RECOVERY_BASE1.md).
In a current named kit its packet is
`payload/str8n-util-readback-0.3.0-base1-pr05-ram.bin`; the preserved Foundation
kit calls it `STR8N-F-READBACK-RAM.bin`. Match the manifest hash to the client.
The service prints `RAM SERVICE BASE1> ` and requires frozen F BASE1 / PR05.
Older b15 `RAM SERVICE>` clients and their $64FF RAM limit are incompatible.

| Binary command | BASE1 result |
| --- | --- |
| F then bank byte 00–03 | 32768 flash bytes, CRC16 little endian, prompt |
| M | Owner RAM $0200–$66FF (25856 bytes), CRC16, prompt |
| Z | Owner zero page $00–$DF (224 bytes), CRC16, prompt |
| W then 25856 bytes and CRC16 | Write the fixed owner RAM range as bytes arrive; return a prompt only if CRC/RX checks pass |
| Y then 224 bytes and CRC16 | Validate staged bytes, then restore owner zero page |
| Q / J | Return to recovery / restart through F |

These commands have no line endings. Capture binary bytes with a matching
host, not a text transcript. CRC covers the payload; prompts are excluded.
See the recovery guide for staging, error handling and exact restoration scope.
The service does not write flash or capture a suspended CPU state.
W is not atomic: a failed or interrupted transfer may already have changed
part of owner RAM. Y stages/checks all owner zero-page bytes before copying.

Loading the packet borrows RAM; capture original owner RAM before uploading
any helper. A later dump cannot recover the overwritten prefix, and Q/J does
not undo borrowed RAM. F remains frozen. For SPI SRAM, EEPROM and combined
PC backup/restore use [UTIL MEMORY](MEMORY_UTILITY.md). See
[file formats](FILE_FORMATS.md) and [component/source/releases](COMPONENT_GUIDE.md).
