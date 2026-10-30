# Native utilities candidate 1 package checkpoint

Local, unpublished package: `STR8N-native-g0000000A-candidate1.zip`.
Source checkpoint: `76fbe012082cb4486cc788a19b49e2e3d54cca9b`.
ZIP SHA-256: `021f6ac62d2c47cb077fe1324fcb60803b98b319cb555a78b72d11769a314ca7`.

The ZIP contains the accepted MON A/B gA, services g6, WB2 g8 and native
CLOCK/FLASH-MAINT g1 components, loader r7 and HOST repair r8. The unchanged
published Foundation operator kit supplies its Python serial terminal, RAM
migrator, CONFIG/OPAQUE tools, F and installation manual. The package adds the
native operator manual, acceptance receipt, NFCOPY example, source archive and
host-only installation/factory-image preparers. It contains no vendor ROM or
board captures. No firmware was rebuilt for packaging.

Extraction verification passed for all 128 listed files. Every Foundation
operator file matched the published kit. The extracted native preparer produced
13 targets matching accepted components, retained the target's RTC metadata
tail and archived C/D. F/C/D are not utility image targets. The B2 reference for
this packaging check was composed from accepted target artifacts, rather than
a new board capture. No board connection, flashing, push or publication occurred.

This verifies the archive and preparation path; installing this extracted ZIP
on another board and the remaining [shipping gates](2512_NATIVE_UTILITIES_ACCEPTANCE.md#remaining-shipping-gates)
are separate. See the [operator manual](NATIVE_UTILITIES_MANUAL.md) before use.
The source archive intentionally identifies the checkpoint above, preceding
this package receipt. Published downloads remain unchanged.
