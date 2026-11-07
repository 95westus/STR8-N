# STR8-N release index

Foundation and historical full-system firmware remain distinct release lines. Original tags and asset bytes are preserved. No component version or hardware qualification is reset by consolidation.

## Next combined release

Use the firmware payloads from `str8n-components-base1-pr05-rc3-unified.zip`.
The reference ZIP SHA-256 is
`0309f3677f2a6a3e18a8976a5ebcc16289aed9c7c93242a41936d6cd8f5302fe`.
Live readback on 2205, 2512, 2604 and 2609 matched all 20 component ranges and
frozen Foundation 0.3.0. The four boards share 119 KiB of identical flash.
The RTC metadata and boot/wear journals are board-specific. The same ASM and
DBG launchers support 65C02 and 65C816 emulation.

Include PC tools and operator instructions for UTC time synchronization and
RTC trim calculation. The sync workflow should show the reference source,
measured offset and uncertainty, then apply and verify a confirmed correction.
Trim calculation should report drift, the observation interval, uncertainty,
and the proposed trim. Applying a trim is a separate confirmed operation.
Qualify the extracted clock tools on both supported CPU modes with separate
evidence for the read, calculation and confirmed write paths.

Keep the RC3 ZIP and its checksum as the reference. After adding the clock
tools and guides, compare every firmware payload in the final ZIP against RC3
and record the new ZIP checksum. Use synthetic examples in the public kit and
keep board captures and settings private.

Stage 2 adds the [PC RTC workflow](docs/RTC_PC_WORKFLOW.md) to the RC3
payloads. Live read-only sampling passed in both CPU modes. In Stage 3,
physical SET on 65C02 passed the PC tool's ±1 second check while increasing
the measured offset from UTC. Sub-second synchronization uses separate
tick-phase alignment. Physical SET on 65C816 emulation passed from the exact
Stage 3 ZIP, with owner RAM and zero page restored. Physical TRIM qualification
on both CPU modes remains open.

The [combined RC3 release notes and qualification checklist](docs/RC3_RELEASE.md)
record the tested archive, completed checks and remaining release work.

Use the [flash ownership and dependency guide](docs/FLASH_AREAS.md) as the
operator map for the combined kit.

## Published releases

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
