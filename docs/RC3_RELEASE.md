# Combined RC3 release notes and qualification

The combined BASE1/PR05 [RC3 prerelease](https://github.com/95westus/STR8-N/releases/tag/components-base1-pr05-rc3) was published on
November 8, 2026 (America/Chicago). Its reviewed source checkpoint is
`fbbc14c692fcb51f0cee3b6eca8da4aa3f59d89d`. Components retain their own versions.
Published archives and the release tag remain unchanged by these documentation updates.

## Contents and operator workflow

| Layer | Contents |
| --- | --- |
| F | Foundation 0.3.0 g00000001 / BASE1 / PR05, 4,096 bytes |
| MON | Unified RC3 monitor slots A/B and matching shared services |
| UTIL | CONFIG, FLASH, CLOCK, MAINT, MEMORY, MAP, OPAQUE, READBACK and DEMO |
| DEV | ASM and DBG with shared launchers for 65C02 and 65C816 emulation |
| PC RTC | UTC measurement, calendar SET, drift collection and trim calculation |
| Examples | Credited Microchess ASM/RAM/S19/AP02 and OSI BASIC opaque B0 images |

The same installed RC3 firmware payloads support 65C02 and 65C816 emulation.
Components retain their individual versions and generations. The exact F
SHA-256 is
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.

Use [flash areas and dependencies](FLASH_AREAS.md) to plan an installation.
The B3:E dispatcher supports the shared ASM/DBG headers. The CLOCK bundle
uses three B2 sectors and matching RTC support. Preserve the board's
B3:9C00–9FFF metadata and B3:C/D boot/wear journal through their documented
update paths. Check actual ownership before using an optional application
area. The examples have their own
[qualification scope](../examples/README.md).

The [PC RTC guide](RTC_PC_WORKFLOW.md) covers read-only sampling, UTC SET and
TRIM. Positive offset means the RTC is ahead of the reference. Positive
drift means it gains time.

**UTC SET accuracy caution.** SET targets a whole UTC second. The PC check
accepts a measured offset interval within ±1 second. An already-close clock
can move farther from UTC and still pass. Preview the offset and compare
the before and after measurements. Sub-second work requires separate
tick-phase alignment and a verified resulting offset.

Trim decisions use the rate of change in offset across one uninterrupted
clock/trim/control segment. The dedicated 2512 campaign requires at least
24 hours, 12 valid samples, a compatible drift interval at most one fine-trim
step wide, and one unique supported setting. Its authorized current trim is
−12. Collection continues while the evidence permits multiple settings.
Calendar or trim writes start a new drift segment.

## Published downloads and ZIP contents

- [Operator ZIP](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/str8n-components-base1-pr05-rc3-release-final-r1.zip): 476,110 bytes; 237 files.
- [Matching source ZIP](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/str8n-components-base1-pr05-rc3-release-final-r1-source.zip): 5,417,280 bytes; 2,021 files.
- [Checksums](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/SHA256SUMS.txt), [packaging receipt](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/FINAL-VERIFICATION.json)
  and [final review receipt](https://github.com/95westus/STR8-N/releases/download/components-base1-pr05-rc3/INDEPENDENT-REVIEW.json).

| Operator ZIP area | Files | Contents |
| --- | ---: | --- |
| `payload/` | 32 | Frozen F 0.3.0; MON 0.1.0-dev g00000010 slots A/B; ASM 0.6-dev g00000002 and DBG g00000002 RAM/sector images; CLOCK 1.10; CONFIG, FLASH, MAINT, MAP, MEMORY, OPAQUE, READBACK, DEMO and shared service images |
| `examples/` | 107 | Microchess source, RAM/S19/AP02 images and reports; OSI BASIC source/adapter and B0 opaque images; licenses and notices |
| `docs/` | 60 | Operator, installation, memory, RTC and DEV guides; flash dependencies, qualification limits and release notices |
| `rtc/` | 5 | Read-only sampler BIN/S19, assembly source, manifest and synthetic drift CSV |
| `tools/` | 8 | Host RTC, timing, memory, terminal and supporting Python code |
| Other areas | 5 | Memory-agent build inputs, terminal support and example board profile |
| Root | 20 | Terminal and MEMORY launchers, dependencies, license, README, release index, presets and provenance/artifact manifests |

Extraction installs nothing on a board. Select the matching loader and preserve
board-local metadata and journals. Examples and standalone recovery tools retain
their separate qualification limits. Native 65C816 mode is outside this scope.
The matching source ZIP contains the complete release checkpoint; the operator
ZIP contains the runtime kit plus selected sources and guides.

Operator SHA-256: `da36e59d3dea8a98aa7115d8cb9878443b82221d4f14a3b5a9e778cd133dc79b`.
Source SHA-256: `c5a24424a7ff424a73080c8c69ab02b666065c270b78c7029d439957aad0cc3f`.

The archives preserve their reviewed local-candidate metadata, including
`published: false` and pending-publication text, as a build-time snapshot.
The GitHub prerelease and this record establish publication. No firmware or
archive bytes were changed for publication. Final review passed all nine RTC
host tests using tests from the matching source ZIP, plus launcher help,
source identity, manifests, checksums, local links and controlled TRIM receipts.

## Tested predecessor archives

| Archive | SHA-256 |
| --- | --- |
| `str8n-components-base1-pr05-rc3-unified.zip` | `0309f3677f2a6a3e18a8976a5ebcc16289aed9c7c93242a41936d6cd8f5302fe` |
| `str8n-components-base1-pr05-rc3-release-stage2.zip` | `3472c851a8b83c6378e3877246565ea3edfc8b817830820813188ee2a4789999` |
| `str8n-components-base1-pr05-rc3-release-stage3.zip` | `4d1e4ec528b318c2a4c8194c88e479704e5affa51fe17105f9f2847d9a604811` |
| `str8n-components-base1-pr05-rc3-release-review-r1.zip` | `ba84a6fe6fb97ca77cea42c4c3a7aea145df3a345a262ff72403d8f8c84607ef` |

Stage 3 has 235 members. It includes the UTC SET caution, RTC workflow,
flash dependency guide, release index and accompanying notices. Verification
checked archive paths and CRC, local documentation links, a fresh extraction,
the synthetic trim example, CLI entry points and nine RTC host tests.
All 44 original RC3 firmware/example payloads match byte for byte.

## Qualification status

| Check | Status | Evidence scope |
| --- | --- | --- |
| Unified installed flash | Passed | All 20 component ranges and frozen F matched on 2205, 2512, 2604 and 2609, with 119 KiB shared flash |
| RTC collection | Passed | Live extracted-kit sampling on 65C02 and 65C816 emulation |
| Drift calculation | Passed offline | Synthetic +12.2 ppm clock recommends −12, with host checks for ambiguous measurements |
| Confirmed SET on 65C02 | Passed | 2512 using Stage 2, with RAM and zero page restored |
| Confirmed SET on 65C816 emulation | Passed | 2609 using the exact Stage 3 extraction, with RAM and zero page restored |
| Confirmed TRIM on 65C02 | Passed controlled write-routine test | 2512, review ZIP, explicit −12 → −11 → −12 targets, register readback and owner RAM/zero-page restoration |
| Confirmed TRIM on 65C816 emulation | Passed controlled write-routine test | 2609, review ZIP, explicit −14 → −13 → −14 targets, register readback and owner RAM/zero-page restoration |
| Source checkpoint and release ZIP | Recorded per archive | RELEASE-SOURCE.json identifies the source commit; the external verification receipt and SHA256SUMS.txt record the final assets and extraction checks |
| Release publication | Published prerelease | [components-base1-pr05-rc3](https://github.com/95westus/STR8-N/releases/tag/components-base1-pr05-rc3); five assets; uploaded ZIP hashes and source tag verified |

The 65C02 SET result passed the ±1 second check while increasing its offset.
The 2609 SET result measured +160 to +258 ms before and +158 to +251 ms
after. Those intervals overlap. Both cases verify the confirmed write path
and restoration within the stated accuracy criterion.

Both TRIM tests invoked the unmodified packaged `rtc.apply` routine with
explicit owner-selected temporary targets. The 65C02 test read back raw
OSCTRIM `0B` at −11 and `0C` after restoring −12. The 65C816 emulation test
read back `0D` at −13 and `0E` after restoring −14, with 94 sampler
observations at each written setting. Control and outage evidence were
preserved. Both restored owner RAM, zero page and the original `REC>`
prompt, then released the serial port. The CLI's calibration calculation
and proposal gates retain their separate offline coverage. These physical
tests supply evidence for the confirmed write routine and restoration.
Earlier observations are retained, and each write starts a new drift
segment; collection continues at the restored settings.

The RTC host script SHA-256 is
`9abb3e0e2006496b9f100f2beb76595f09ba79d75261f71c613d89b87ff569c5`.
The 649-byte sampler SHA-256 is
`f06ea23de7687911f17b0554763b0ae1c018b5cd5487ef567a23b1e8721c4e4a`.
These match between Stage 2, Stage 3 and the review ZIP. Both physical TRIM
tests used review ZIP SHA-256
`ba84a6fe6fb97ca77cea42c4c3a7aea145df3a345a262ff72403d8f8c84607ef`.
Hardware evidence belongs to the archive used for that run. Retained
archives record their qualification status at build time; subsequent
completed results are recorded separately in hardware-verification receipts.

## Completed final package procedure

1. Carry forward the completed physical SET and controlled TRIM results on
   both CPU modes. Keep calibration decisions separate and apply a calibration
   change only when the measured interval supports one setting.
2. Update the package's README, RELEASE-STAGE.json and COMPONENTS.json from
   verified results. Describe the tested payload scope and explicit controlled
   TRIM targets consistently. Keep every artifact size/hash entry tied to its
   bytes. Retain older archives unchanged as historical evidence.
3. Commit the scoped release source, PC RTC tools, sampler source and guides.
   Record the source commit used to assemble the kit. Include LICENSE and
   the separate example/vendor notices. Keep board profiles, raw captures,
   BUILD output and experiment-only DEV LINK work in their existing scopes.
4. Build a fresh final archive. Compare every original RC3 payload by bytes,
   verify F's exact 4 KiB hash, check component/example manifests, and compare
   the tested RTC script and sampler hashes. Record the final archive hash
   outside that archive.
5. Verify a fresh extraction through the normal CLI entry points, synthetic
   calculation and RTC host checks. Check local links and dependency files.
   If executable bytes change, qualify the affected paths again.
6. Review the final release title, component versions, source identity,
   install instructions, qualification limits, assets and SHA-256 checksums.
   Tag and publish the reviewed package and matching source checkpoint.

The live fleet drift jobs and the dedicated 2512 calibration remain active
through this preparation. Qualification samples use the shared serial lease
and yield to the scheduled board reads.
