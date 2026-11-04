# 0.3.0 packaging and evidence

The final release packages the existing frozen F, matching RAM tools,
Python Serial Console 0.1.0 and unchanged installation hosts/engines.
Corrected documentation and the planned Mona name do not expand F's ABI.
See [release notes](RELEASE_NOTES.md) and [scope](RELEASE_STATUS.md).

## Package once from a committed source checkpoint

```text
python tools/package_base1.py --out dist/base1-0.3.0
```

Use a fresh directory. Packaging verifies and copies existing files; it does
not assemble, simulate, open serial ports or flash. Keep old archives intact.
Supply the identical standalone 4K F BIN, operator ZIP, source ZIP and checksums.
The operator ZIP includes Python terminal/core, requirements, five RAM tools,
public installation hosts and prebuilt engines. Do not include owner firmware,
RAM, per-board plans or private fixture packets.

## Verify a fresh extraction

```text
python tools/verify_release_kit.py .
python tools/verify_base1.py
python tools/nf_console.py --help
```

Verify ZIP paths/CRC, complete manifests, local links, runtime dependencies
and frozen bytes. Compare runtime files with the hardware-tested rc1 ZIP.
This is file verification, not another live trial. Record final asset hashes
and the source commit outside the archives to avoid self-referential hashes.

## Hardware evidence and future routes

The [2609 existing-SNBT route](2609_RC1_ZIP_UPGRADE_ACCEPTANCE.md) passed
using only extracted rc1 product files. Its exact ZIP hash remains attached
to that result. The final ZIP has no additional live trial. WDC and programmer-F
provisioning from an extraction remain untested; their source paths passed on
2512. These limits remain visible in the release rather than being labelled
as completed tests.

Any future board trial needs fresh independent backups, original owner RAM/ZP
escrow, a reviewed write budget, durable intent/commit evidence, physical-reset
recovery and independent final image/settings/history/RAM readback. Finish at
REC> with the port released. No blind retry or power cut is part of packaging.
Keep 2205 excluded. Native console keys/dialogs and core transfer paths retain
their distinct scopes. [Mona](MONA.md) is separately planned work.
