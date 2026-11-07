# Combined RC3 release notes and qualification

This draft describes STR8-N F, MON, UTIL and DEV for the combined BASE1/PR05
candidate. The qualification status below was reviewed on November 7, 2026.

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

## Tested archives

| Archive | SHA-256 |
| --- | --- |
| `str8n-components-base1-pr05-rc3-unified.zip` | `0309f3677f2a6a3e18a8976a5ebcc16289aed9c7c93242a41936d6cd8f5302fe` |
| `str8n-components-base1-pr05-rc3-release-stage2.zip` | `3472c851a8b83c6378e3877246565ea3edfc8b817830820813188ee2a4789999` |
| `str8n-components-base1-pr05-rc3-release-stage3.zip` | `4d1e4ec528b318c2a4c8194c88e479704e5affa51fe17105f9f2847d9a604811` |

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
| Confirmed TRIM on 65C02 | Open | Requires a supported proposal and verified register readback through the packaged tool |
| Confirmed TRIM on 65C816 emulation | Open | Same packaged write and preservation checks on this CPU mode |
| Final source checkpoint and release ZIP | Open | Commit the scoped release inputs, verify the final extraction and record final asset hashes |
| Release publication | Open | Review final notes, source identity, assets and checksums before tagging and publication |

The 65C02 SET result passed the ±1 second check while increasing its offset.
The 2609 SET result measured +160 to +258 ms before and +158 to +251 ms
after. Those intervals overlap. Both cases verify the confirmed write path
and restoration within the stated accuracy criterion.

The RTC host script SHA-256 is
`9abb3e0e2006496b9f100f2beb76595f09ba79d75261f71c613d89b87ff569c5`.
The 649-byte sampler SHA-256 is
`f06ea23de7687911f17b0554763b0ae1c018b5cd5487ef567a23b1e8721c4e4a`.
These match between Stage 2 and Stage 3. Hardware evidence belongs to the
archive used for that run. The retained Stage 3 archive records its pending
gates at build time. The completed 2609 result is recorded separately in its
hardware-verification receipt.

## Final package procedure

1. Complete the physical TRIM checks on both CPU modes. Record the input
   series, reference, drift interval, selected value, confirmation, register
   readback, RAM/zero-page restoration, final prompt and released serial port.
   Apply a calibration change when the evidence supports one setting.
2. Update this status and the release notes from verified results. Update the
   final package's README and RELEASE-STAGE.json to agree. COMPONENTS.json
   currently retains the earlier naming-candidate qualification label.
   Correct that label for the final candidate and describe its verified
   payload scope. Keep every artifact size/hash entry tied to its bytes.
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
