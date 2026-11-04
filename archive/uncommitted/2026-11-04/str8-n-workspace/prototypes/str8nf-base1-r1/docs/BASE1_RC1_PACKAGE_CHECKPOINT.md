# BASE1 0.3.0-rc1 package checkpoint

October 28, 2026. Operator and source ZIPs were assembled once from source
commit `1f5db7a94a176c4ad50f47c39653943590d97a21`. This post-package record does not alter
either archive. The reviewed 2512 hardware cases and package construction/
extraction checks are closed. At packaging live migration was NOT RUN; the
later [2609 existing-SNBT ZIP upgrade](2609_RC1_ZIP_UPGRADE_ACCEPTANCE.md) passed
without changing these archives. Other packaged routes remain untested.

> Give me 4KB, I can give you 4 boards.

With ~32KB RAM shared by four selectable bank environments. This describes
the bank architecture; hardware acceptance remains limited to its receipts.

## Immutable assets

| Asset | Bytes | SHA-256 |
| --- | --- | --- |
| STR8N-F-BASE1-0.3.0-rc1.zip | 221946 | `ed9e87ef34323b0504c355bd6b35e0a5095ecd0665d6e67166bd9178c29bddb2` |
| STR8N-F-BASE1-0.3.0-rc1-source.zip | 508531 | `fb0fb6ed6e87faf8883d6b53a4afab77866b897b4eb4c5663f681f8946ab1a09` |
| STR8N-F-BOOT-4096.bin | 4096 | `8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1` |

The output directory is `dist/base1-rc1`. It also contains per-asset checksum
files, `SHA256SUMS.txt`, `PACKAGE_RECEIPT.json` and `EXTRACTION_RECEIPT.json`.
The [sanitized extraction receipt](../validation/base1-rc1-package-acceptance.json)
binds their hashes and the exact archive assets.

The operator ZIP contains 92 manifest-bound files, including Python Serial
Console 0.1.0, pinned pyserial, function keys/guide, the five matching RAM tools,
all three installation hosts, prebuilt engines and the pure wrapper dependency.
The source ZIP contains 229 manifest-bound files. F remains the frozen 4096
bytes, version 0.3.0 g00000001 / BASE1 / PR05.

Fresh extractions passed archive CRC/path checks, complete manifests, required
dependencies, local guide links, static F/component verification, console and
four migration/upgrade CLI help entry points. Cold imports and generation of
the recovery wrapper used only extracted files; no development fallback or
serial import occurred. Old candidate asset hashes remained unchanged.

No firmware build, simulation, GUI interaction, port opening, flashing or
publication occurred. 2205 stayed untouched. A later hardware receipt must
bind the exact operator ZIP hash above; the ZIP itself should stay immutable.
See [the pending migration workflow](RELEASE_WORKFLOW.md).
