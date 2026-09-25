# RC1 WDCMONv2 migration on W65C02SXB board 2205

Date: 2026-09-25. Port: COM3, 115200 baud. Board info: `SXB2`, hardware
3.00, WDCMONv2 2.00. Flash ID: `BF/B5`.

## Recovery and factory baseline

The initial STR8-N 2.0a19 Bank 3 monitor dumped all four complete 32 KiB
banks. Banks 1 and 2 were read twice and matched byte for byte. The complete
128 KiB owner-local backup has SHA-256
`3157C56ADE9F29FEE44C6D6EF01AF6D08EB2539A7A5F060C2A38FDC36BA85E81`.
Bank 0 was the known stock WDCMONv2 image (`FNV1A=1249E1F3`, RESET `$F818`,
tag `SXB2`). Bank 2 was fully erased. Backup BINs, raw serial captures, and
bank archives remain owner-local under `BUILD/board/2205-rc-migration/` and
are excluded from the release package.

The checked factory-restore RAM image loaded at `$2000` and received an exact
RAM readback. Its explicit `RESTORE FACTORY BOARD` transaction copied and
verified Bank 0 to Bank 3, then erased and verified Bank 0. A separate
WDCMONv2 archive of every bank proved the resulting factory layout: Bank 0
erased; Bank 3 exactly equal to the saved stock Bank 0; Banks 1 and 2 exactly
equal to their saved images. The stock monitor's board-info probe passed.

## RC installer defect and correction

The first RC package correctly detected `SXB2`, verified its RAM image,
copied and verified stock Bank 3 into Bank 0, and received the canonical
4096-byte top BIN. It refused `INSTALL STR8-N 2.0a21` because its input
routine uppercased the typed `a`, while the comparison token contained a
lowercase `a`. It reported `CANCELLED: INSTALL TEXT DID NOT MATCH`; Bank 3 F
was not written. The source token was corrected to `2.0A21`, and the
installer structure checker now enforces that uppercase token.

## Corrected RC1 migration result

The rebuilt RC package identified `SXB2`, loaded and byte-verified the
corrected RAM installer (S19 SHA-256
`8CC4697F19FC50C6B3DF31320D7D214AF74D4AD10E6BC70D15E87AA0FA2041E1`),
and reported `B0 == ORIGINAL B3 VERIFIED`. Ctrl+U sent the packaged top BIN
with SHA-256
`3738EAB501C50EF0470E9A81EF573B563DA7DC656CC18A83573D16C9BD2E6E49`.
The exact install confirmation then produced `ERASING/PROGRAMMING B3:F` and
`MIGRATION VERIFIED; PRESS PHYSICAL RESET`. Physical RESET booted
`STR8-N 2.0a21 B3 65C02`.
The final corrected RC ZIP has SHA-256
`2125087D9CC928A2728EED98B42C7E4EB53A81F0A3D755797C70891DE4E24420`.

Independent complete four-bank display readback after RESET matched these
expected images byte for byte:

| Bank | Expected content | SHA-256 |
| --- | --- | --- |
| 0 | Saved stock WDCMONv2 Bank 0 | `2F0000C74ECEEC809A814E31F822702977D7BFED5EE6F3BC4869627864CA59A8` |
| 1 | Saved Bank 1, unchanged | `795C202BEFE3DD94AE59FE3036041DC495DCB1B74DE5087AD4ECC3CF20E28A29` |
| 2 | Saved erased Bank 2, unchanged | `2D864C0B789A43214EEE8524D3182075125E5CA2CD527F3582EC87FFD94076BC` |
| 3 | Saved stock Bank 0 `$8000-$EFFF` plus canonical RC top `$F000-$FFFF` | `0292E349A0DAD6D2AEF1B39E98F778EED673913634FDFDB2F8A4785C93E9603E` |

The packaged `VERIFY-STR8N-V2-READBACK.ps1` also passed all 256 Bank 3 F
display rows against the exact top BIN.

This accepts the corrected RC1 factory migration on this W65C02SXB board.
It does not qualify W65C816SXB, EDU behavior, or interruption recovery.
