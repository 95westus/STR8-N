# STR8-N release index

Foundation and historical full-system firmware remain distinct release lines. Original tags and asset bytes are preserved. No component version or hardware qualification is reset by consolidation.

| Release | Origin | Original assets | Line |
| --- | --- | ---: | --- |
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
