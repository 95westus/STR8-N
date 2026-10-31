# Local native candidate 2

October 30, 2026. Source commit `f4fe32d633d8f87fe5e728cee149f3fb6655c836` on
`codex/mona-monb`. Source and receipts remain local; nothing was pushed.
The existing Foundation and preview downloads, tags and candidate-1 ZIP
were not changed.

- Archive: `STR8N-native-g0000000B-candidate2.zip`
- Size: 2,018,106 bytes
- SHA-256: `1a6932d8867713018640555cb817fd2a645fec0379f1dd295acb276568da89e0`
- Local output: `C:/SRC/STR8-N/BUILD/native-candidate-gB-r16-20261030/`

The ZIP includes frozen F.bin, MON A/B gB, WB2 gA, PROGRAM g2/cancel r5,
services g8, native apps g1/r16, one current operator manual, sanitized
2512 BATCH/large PROGRAM acceptance and commented examples. The unchanged
published Foundation operator kit supplies its Python serial terminal,
WDC-loadable RAM migrator and CONFIG/OPAQUE tools/manual. No vendor firmware
or private board captures are included.

A fresh extraction passed its file-set/hash verifier. Its preparer produced
thirteen utility targets identical to the accepted 2512 installed images,
using the fresh B3 readback and explicitly composed verified B2 sectors.
Sector9 retained all1024 metadata bytes; F and C/D were not image targets.
These extraction/preparation checks used no port, firmware rebuild or CPU
simulation. There was no migration or reinstall from this ZIP, and it is
not a published/full-b35 release.

See [operator manual](NATIVE_UTILITIES_MANUAL.md),
[BATCH acceptance](2512_BATCH_WIDE_ACCEPTANCE.md) and
[remaining shipping gates](UNIFIED_SHIPPING_RELEASE.md). The archive embeds
its source commit; this later package receipt does not require repacking it.
