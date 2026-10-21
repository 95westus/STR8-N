# rc1 v1g distribution r9

R9 supplies a uniform source-aware updater for the unchanged generation-50
v1g firmware. The owner authorized correction, both-board qualification and
publication after safe closure. Use the [uniform upgrade guide](UNIFORM_UPGRADE.md).
The [r8 download](https://github.com/95westus/STR8-N/releases/tag/v2.0rc1-v1g-r8)
remains unchanged historical evidence; r9 replaces its installer limitation.

Supported target runtimes are 65C02 and 65C816 **E=1**. Native applications and
debugging remain excluded. The RTC issue is deferred; drift is outside release
qualification and is not a promotion gate. Preservation of owner memory,
settings and borrowed RAM remains required. This qualification starts no new
soak or RTC sampler.

| New physical upgrade qualification | 2604 | 2609 |
|---|---|---|
| Direct WDCMONV2 → v1g | 23 transfers; MON A/B passed | 23 transfers; MON A/B passed, E=1 |
| Direct beta4 → v1g | 22 transfers; MON A/B passed | 22 transfers; MON A/B passed, E=1 |
| Persistent-breakpoint smoke hits | 64 | 64 |
| Original RAM restored and reread | 25,344 bytes, twice | 25,344 bytes, twice |
| EEPROM/SRAM retained | 137 / 131,072 bytes | 137 / 131,072 bytes |
| Exact-current updater | Verified no-write, no RESET | Verified no-write, no RESET |

Original MON B/2604 and MON A/2609, settings, and flash outside exact planned
wear journals were restored. Four lab fixture/install transactions per board
reserved 90 additional erase attempts each; those counts were checked against
the complete final journals. Both workers exited and serial coordination closed.

The current entry passed 12 new host workflow checks. CPU/flash qualification
is inherited through exact runtime member equivalence: 24 registered-rc1 and
eight legacy bootstrap linked-installer executions, plus eight exact private
fixture rehearsals. Do not count them as newly executed r9 CPU tests. Registered
generation49 and generation50 v1e/v1f paths have model coverage; the new physical
routes are WDCMONV2, beta4 and current-v1g no-write. No manual generation49
rollback or arbitrary historical beta support is claimed.

The original beta4 post-boot host protocol check failed on 2604 despite its
verified fixture transaction. The corrected exact-source continuation passed;
the failed receipt is retained. Actual firmware/device verification failures:
zero. Monitor timestamp/terminal-state corrections and earlier model/fixture
development failures remain dated history, not hidden hardware passes.

Firmware and inherited r8 register qualification are unchanged: 5,752 physical
parser checks, 220 resumes (including 48 S/N then C) and 132 expected unsafe-PC
refusals across both boards and monitor slots. Earlier R6 `R` coverage was
query-only; the separate r8 evidence covers PC/A/X/Y/P/SP editing. No new soak
or RTC acceptance is claimed here.

The download contains a manifest, `SHA256SUMS.txt`, a board-free verifier,
portable qualification JSON and original receipt hashes. Vendor fixture
images, private memory/flash captures, raw serial logs and secrets are excluded.
See the [corrected release](https://github.com/95westus/STR8-N/releases/tag/v2.0rc1-v1g-r9).

Exact full-system, F-sector, B3-bank, MON A/B and ASM component BINs are included
with source offsets and hashes. Read the [image map](RELEASE_PATHS.md) and
[flash reclaim guide](FLASH_RECLAIM.md) before treating a component as removable.
The F sector alone is fixed recovery, not a normal Jn bank launcher. ASM/DBG1
share tables and hooks; a general erase-only uninstaller is not qualified.
The component removal checks model MON A on both CPUs and do not change either
physical board. These are separate from the four full-system hardware routes.
