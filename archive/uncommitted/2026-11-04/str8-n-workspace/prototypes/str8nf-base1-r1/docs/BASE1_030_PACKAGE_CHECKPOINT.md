# STR8N-F 0.3.0 package checkpoint

October 28, 2026. Packaged once from source commit `a5f1d83f6a7017eb30e6268c6e0b1fd12fce6a8d`.
No firmware rebuild, simulation or board access. Mona is planned separately.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| STR8N-F-BASE1-0.3.0.zip | 243843 | `3c3631ec8de5dfead44e3b54a8e885a82c3d508f90b04f7d3d18ce70a91a7a4f` |
| STR8N-F-BASE1-0.3.0-source.zip | 529511 | `128b5d74ace51aa61083112cfaf0c1ab03049b4fad4ecfc21d4d0a81e332e3aa` |
| STR8N-F-BOOT-4096.bin | 4096 | `8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1` |

Both fresh extractions passed manifests, local links, frozen F/component checks,
and operator console/migration CLI imports. All 54 prior non-document/runtime
files, including nine BINs, match the immutable rc1 operator kit exactly.
This proves file equivalence, not another hardware trial. Final-package live
migration remains NOT RUN; the 2609 hardware pass retains its rc1 ZIP hash.

[Package receipt](../validation/base1-0.3.0-package-acceptance.json),
[runtime equivalence](../validation/base1-0.3.0-runtime-equivalence.json),
[release scope](RELEASE_STATUS.md) and [Mona](MONA.md).

The source/package metadata published=false fields describe packaging time.
Later publication is recorded externally without changing these archives.

## Publication

Published October 28, 2026, 23:35:49 America/Chicago as [v0.3.0](https://github.com/95westus/STR8N-F/releases/tag/v0.3.0).
All nine GitHub asset sizes and SHA-256 digests matched local files;
freeze-integrity CI passed. [Publication receipt](../validation/base1-0.3.0-publication.json).
The release tag points to the exact packaged source checkpoint; later
receipt commits do not change either ZIP or the frozen F.
