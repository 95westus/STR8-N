# STR8N-F MIN1 candidate toolkit

**Unpublished; hardware acceptance pending.** This kit contains the frozen
4096-byte F and the new RAM migration/opaque tools. It is not a qualified
replacement for the published v0.2.0 release.

| Flash | Role |
| --- | --- |
| B0/B1/B2:8-F | User opaque images |
| B3:8/9/A/B/E | User opaque images |
| B3:C/D | Boot settings and erase-accounting journal |
| B3:F | Bootstrap/recovery |

The programmer file is `firmware/payload/STR8N-F-BOOT-4096.bin`, exactly 4096
bytes. Its SHA-256 is
`ccb923340528a0764102fc270e39dd07c95a76569e19c4f60169e081712164d3`.
Program only B3:F using your device's verified address mapping. No full-device
image is supplied. Existing C/D require inspection/provisioning; programming F
alone does not turn vendor C/D into journals.

The [migration guide](migration-host/README.md) covers the verbose WDC RAM path.
It saves original banks and owner RAM privately, performs admitted F/D/C
operations, requests physical RESET, independently reads the result, and
restores/verifies owner RAM. The new live command requires explicit
`--allow-unqualified`; it has not been run on hardware. Python 3.11+ and
`pyserial` are needed for a later live trial. The RAM templates in `migrator/`
are inputs to the host, not unconditionally executable installation images.

Load matching CONFIG and OPAQUE tools through recovery L. Use the
[OPAQUE host guide](docs/OPAQUE_HOST.md) for read/replace and independent
readback. C/D/F remain protected against ordinary OPAQUE operations. CONFIG
separately enables a bank, sets its entry and saves the default. No monitor,
EDU, SPI SRAM or automatic B0 backup copy is required.

See [the scope and remaining boundaries](docs/MINIMAL_RELEASE.md),
[RAM restoration protocol](docs/RECOVERY_MIN1.md), and `checkpoint.json`.
No board was modified to prepare this kit. Existing-SNBT F upgrades and generic
live F-recovery provisioning are not completed by this candidate.
