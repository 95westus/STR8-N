# MIN1 independent readback and owner-RAM restoration

The matching `STR8N-F-READBACK-RAM.bin` is 3071 bytes and loads through F's raw L
at 0200, then copies a 438-byte service to 6800. Its visible prompt is
`RAM SERVICE MIN1> `. This is a new fixed-range protocol; old `RAM SERVICE>`
clients are incompatible.

| Command bytes | Response or input |
| --- | --- |
| F, then bank byte 00-03 | 32768 flash bytes, CRC16 little endian, prompt |
| M | RAM 0200-66FF: 25856 bytes, CRC16, prompt |
| Z | Owner ZP 00-DF: 224 bytes, CRC16, prompt |
| W, then 25856 bytes and CRC16 | Restore 0200-66FF; prompt only if CRC/RX valid |
| Y, then 224 bytes and CRC16 | Stage at 6700, check CRC/RX, then restore 00-DF |
| Q | Return to F recovery |
| J | Software restart through F; not a physical-reset test |

The service never writes flash. F must match PR05 and remain visible for CRC
calls; each flash-data fetch temporarily selects its bank and restores B3.
The service at 6800 and its 6700 staging frame do not overlap owner RAM.
ZP E0-FF and the runtime stack are system scratch, not restored owner bytes.

The host client `tools/nf_recovery.py` opens no port. The WDC migration executor
uses it only after observing the physical-reset recovery face. It loads the
matching image, independently reads all four final banks and compares their
SHA-256 values to the admitted plan. It then restores RAM and ZP, reads both
back byte-for-byte and returns to `REC>`. Only that completed path reports owner
restoration verified. A timeout, CRC or byte mismatch stops without retries.

Loading a RAM tool borrows application RAM. Original escrow must precede the
first helper upload; a dump taken afterward cannot recover the overwritten
prefix. The programmer-installed F route needs an explicit disposable-RAM or
pre-existing-escrow procedure before it can make any preservation claim.

Current evidence: source/build inspection and fake-stream host tests. No CPU
model or physical device has qualified the new MIN1 service or its integration.
