# Binary export and fixed-range RAM restoration

Load `STR8N-F-READBACK-RAM.bin` at $0200 through F raw L. The bootstrap copies
the service to reserved $6800 workspace and prints `RAM SERVICE> `.
There is no flash writer. Use a binary-capable host, not a text-only capture.

| Binary command | Result |
|---|---|
| F followed by one bank byte 00-03 | 32768 flash bytes, CRC16 little endian, prompt |
| M | RAM $0200-$64FF (25344 bytes), CRC16 little endian, prompt |
| Z | Zero page $00-$DF (224 bytes), CRC16 little endian, prompt |
| W then 25344 RAM bytes and CRC16 little endian | Restore that fixed range; prompt only after CRC verification |
| Q | Return to REC with text consoles restored to BOTH |
| J | Restart F using the saved default |

Commands have no line endings. A B0 export starts with bytes 46 00, not the
text F00. CRC is CCITT polynomial 1021, initial FFFF, no reflection/final XOR.
The prompt is excluded. Incomplete transfers or CRC failure may stop the
service; preserve the capture and use the established recovery procedure.

The initial load overwrites its own low-RAM prefix. A later M export contains
that loaded prefix, not the previous bytes. Owner RAM needs an earlier
independent capture. W intentionally replaces the supplied fixed range and
must use matching owner data. Q/J do not restore borrowed RAM automatically.

The service requires matching b15 F/RAM services. It is not a universal
WDCMONv2, g0034 or native-816 reader. The kit manifest gives its hash and size.
