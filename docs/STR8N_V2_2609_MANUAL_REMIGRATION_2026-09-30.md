# Board 2609 - manual stock-to-alpha24 F remigration

After [restoring the original B0 stock image into B3](STR8N_V2_2609_B0_TO_B3_RESTORE_2026-09-30.md),
the owner ran the extracted alpha24 kit's single
`MIGRATE-STR8N-V2-A24.ps1` script in Windows PowerShell. The operator selected
`com8`, pressed physical RESET during the 60-second arm, and confirmed the
physical model `W65C816SXB` when WDCMONv2 reported `SXB6` (hardware 3.00,
WDCMON 2.00). The host sent the pinned installer S19, then its RAM readback
was byte-exact at `$2000-$299B` and it executed at `$2000`.

The RAM installer reported flash `BF/B5`, stock B3 FNV-1a `280928EC`, and
`B0 == ORIGINAL B3 VERIFIED`. Thus it accepted the already-preserved B0
without copying or erasing it. At the `SEND STR8-N TOP BIN` prompt, the
operator pressed Ctrl+U for the package's 4,096-byte F BIN (SHA-256
`43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a`),
then entered `INSTALL STR8-N 2.0A24`. The installer reported
`MIGRATION VERIFIED; PRESS PHYSICAL RESET` after programming B3:F.

The owner's terminal subsequently displayed `STR8-N 2.0a24 B3 65C816`,
`ABI 65C02 | 816E | 816N-VEC`, and `B3>`. `J0` booted the stock
`W65C816SXB + EDU Kit Rev 1.0` native-mode menu from the retained Bank 0
image. The menu's device-scan text is stock firmware output; it is not an EDU
daughterboard presence test.

**Current observed flash layout:** B0 retains the original W65C816SXB image;
B3 contains the restored stock sectors 8-E and alpha24 F. This run did not
install the alpha24 E extension, so its S/R features are not part of the
current B3 image. The installer has no B1/B2 write path. No independent
post-write B3:F readback was included in the owner's pasted terminal output;
the installer reported its internal verification and alpha24 boot succeeded.

The extracted kit's host evidence is in its `LOCAL` directory under the
`v2-a24-migration-20260930-152511.raw` and `.raw.events.txt` filenames.
The later [operator-session record](STR8N_V2_A24_2609_OPERATOR_SESSION.md)
includes both exact files in the distributable kit and explains why the
lowercase host input appears uppercase in the board echo.
