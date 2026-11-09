# STR8-N release index

Foundation and historical full-system firmware remain distinct release lines. Original tags and asset bytes are preserved. No component version or hardware qualification is reset by consolidation.

## Current combined release: RC3

[STR8-N components BASE1/PR05 RC3](https://github.com/95westus/STR8-N/releases/tag/components-base1-pr05-rc3) was published as a prerelease on
November 8, 2026 (America/Chicago), from source commit
`fbbc14c692fcb51f0cee3b6eca8da4aa3f59d89d`.

- [Reviewed operator ZIP](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/str8n-components-base1-pr05-rc3-release-final-r1.zip) — 476,110 bytes, 237 files.
- [Matching source ZIP](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/str8n-components-base1-pr05-rc3-release-final-r1-source.zip) — 5,417,280 bytes, 2,021 committed files.
- [SHA-256 checksums](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/SHA256SUMS.txt),
  [packaging verification](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/FINAL-VERIFICATION.json) and
  [final review](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/INDEPENDENT-REVIEW.json).

The operator kit contains frozen F, MON A/B, native shared services, UTIL RAM
and installed tools, DEV ASM/DBG, Terminal, MEMORY backup/restore, PC RTC tools,
Microchess and OSI BASIC examples, manuals and notices. See the
[ZIP contents and qualification record](docs/RC3_RELEASE.md) and
[flash ownership/dependency guide](docs/FLASH_AREAS.md) before installation.

All 44 firmware/example payloads match the four-board RC3 reference. Physical
SET and controlled TRIM passed on 65C02 and 65C816 emulation. Nine RTC host tests
passed final review. Components retain their individual versions. F remains
0.3.0 g00000001 / BASE1 / PR05 with its frozen 4 KiB hash.

Published ZIPs retain their reviewed bytes, including build-time local-candidate
metadata. Publication is recorded here and on GitHub; the tag and matching
source ZIP identify the release source. Later documentation commits do not
change that source checkpoint or the downloaded archives.

## Published releases

| Release | Origin | Assets | Line |
| --- | --- | ---: | --- |
| [components-base1-pr05-rc3](https://github.com/95westus/STR8-N/releases/tag/components-base1-pr05-rc3) | 95westus/STR8-N | 5 | Combined F / MON / UTIL / DEV prerelease |
| [nf-v0.3.0](https://github.com/95westus/STR8-N/releases/tag/nf-v0.3.0) | 95westus/STR8-N | 0 | Foundation announcement (link only) |
| [v2.0rc1-v1g-r9](https://github.com/95westus/STR8-N/releases/tag/v2.0rc1-v1g-r9) | 95westus/STR8-N | 2 | Historical full system |
| [v2.0rc1-v1g-r8](https://github.com/95westus/STR8-N/releases/tag/v2.0rc1-v1g-r8) | 95westus/STR8-N | 2 | Historical full system |
| [v2.0rc1](https://github.com/95westus/STR8-N/releases/tag/v2.0rc1) | 95westus/STR8-N | 1 | Historical full system |
| [v2.0bf1](https://github.com/95westus/STR8-N/releases/tag/v2.0bf1) | 95westus/STR8-N | 13 | Historical full system |
| [v2.0b4](https://github.com/95westus/STR8-N/releases/tag/v2.0b4) | 95westus/STR8-N | 2 | Historical full system |
| [v2.0b1](https://github.com/95westus/STR8-N/releases/tag/v2.0b1) | 95westus/STR8-N | 2 | Historical full system |
| [v2.0a24c1](https://github.com/95westus/STR8-N/releases/tag/v2.0a24c1) | 95westus/STR8-N | 1 | Historical full system |
| [mon-g8-tools-preview1](https://github.com/95westus/STR8-N/releases/tag/mon-g8-tools-preview1) | 95westus/STR8N-F | 4 | Foundation / MON preview |
| [v0.3.0](https://github.com/95westus/STR8-N/releases/tag/v0.3.0) | 95westus/STR8N-F | 12 | Foundation / MON preview |
| [v0.2.0](https://github.com/95westus/STR8-N/releases/tag/v0.2.0) | 95westus/STR8N-F | 5 | Foundation / MON preview |
| [v0.1.0-preview.1](https://github.com/95westus/STR8-N/releases/tag/v0.1.0-preview.1) | 95westus/STR8N-F | 3 | Foundation / MON preview |

The four imported Foundation release records have new GitHub IDs/timestamps; original dates/IDs and asset hashes are retained in [the migration manifest](docs/RELEASE_MIGRATION_MANIFEST.json). Every imported asset keeps its original filename and SHA-256. Duplicate checksum names belong to their own release, never a flattened shared directory.

The nf-v0.3.0 announcement points to [the authoritative Foundation v0.3.0 release](https://github.com/95westus/STR8-N/releases/tag/v0.3.0). Its own source tag remains the historical STR8-N announcement, not the Foundation source identity.

Exact-tag accompanying [project/font notices](docs/release-notices) are retained for v2.0a24c1, v2.0b1 and v2.0b4; the original package bytes are unchanged. Later full-system packages retain their project MIT and Microchess notices. Keep applicable notices with raw binaries as well as source.

Source build instructions, current component names and qualification scope are linked from [README](README.md). Historical raw F/component images are not interchangeable preserving updaters.
