# Uniform upgrade to rc1 DBG1 v1g

Distribution **r9** corrects the source-bound installer supplied in r8. The
existing r8 archive remains unchanged. Use the new package's `upgrade/upgrade.py`
entry; its archived `install/` directory retains the earlier source-bound kit.

The target firmware is the same generation-50 v1g image already qualified in r8.
The correction is the source-aware installer and its qualification, rather than
a new firmware build. Native applications/debugging remain excluded; supported
target runtimes are 65C02 and 65C816 E=1. RTC drift is outside release
qualification. Preserving owner settings, retained memory and borrowed RAM is
still required.

## One entry point

From the verified, extracted r9 package, run:

```text
python -B upgrade/upgrade.py --port COM5 --usb-serial YOUR-USB-SERIAL --board 2604 --out NEW-PRIVATE-DIRECTORY --coordination-root PRIVATE-SHARED-COORDINATION --accept-unknown-wear-history
```

Select the actual board's port and USB serial number. The output directory must
be new and private: it contains the board's recovery captures, RAM, plans and
serial transcripts. Never upload it with a release or commit it to Git.
Keep the output and shared coordination directories outside the extracted kit.
Use the same coordination directory as any other board tools. The corrected
live host path uses Windows, Python 3.10+ and pyserial 3.5. Earlier Linux launcher
checks do not qualify this Windows host path on Linux.

The installer detects the source and selects the required transport and plan.
Users do not select ABI profiles, build an installer, install an intermediate
release, or roll back through generation49. Press physical RESET only when
the installer reports that device verification has completed and asks for it.
An installed exact v1g image needs verification, rather than another flash or
journal rewrite, and takes the no-write path.

`J3` is the preferred software restart from an idle B3 monitor prompt. The
linked RAM flash installer finishes in its own halt loop after replacing the
core; it has no monitor command parser and cannot accept `J3`. This installation
therefore requires physical RESET after device verification. An ordinary
monitor restart and this post-install handoff are different operations.

`--accept-unknown-wear-history` applies only to a WDC source that has no STR8-N
wear journal. It acknowledges a new tracked migration baseline; it does not
claim that the chip has never been erased. A verified board-bound history can
instead be supplied with `--history`. Beta4 and installed rc1 sources retain
their existing conservative tracked counts.

## Source admission

| Source | Planned route |
|---|---|
| Exact supported WDCMONV2 SXB2/65C02 image | Direct full v1g bootstrap |
| Exact supported WDCMONV2 SXB6/65C816 image | Direct full v1g bootstrap; target E=1 |
| Published beta4, generation13, admitted A/B preference | Direct layout conversion and full v1g installation |
| Exact rc1 generation49 | Direct preserving v1g update |
| Registered generation50 v1e/v1f | Direct preserving v1g update |
| Exact current v1g | Full verification with no RAM/flash/journal rewrite |

Generation alone never admits a source: v1e, v1f and v1g share generation50 but
have different bytes. Unknown, mixed or corrupt images refuse before mutation.
The complete registered core/provider ranges must match. Occupied provider or
debugger destinations on a legacy source refuse without discarding user data.
This is not arbitrary-image conversion or automatic relocation of unknown
applications.

WDC's host debugger supplies repeated B3 and application-RAM reads. The guarded
factory workflow assumes erased B0/B1/B2 and the RAM installer verifies those
complete bank preimages before its first mutation. It does not claim that the
host independently dumped those banks through WDCMONV2. The 816 WDC debugger's
live `$0700-$07FF` stack is excluded from stable repeated RAM comparison and
full restoration is deferred until the target monitor is running.

Beta4 sources use repeated four-bank captures. An autostart that overlaps the
target service RAM refuses. Retained startup settings and valid A/B preferences
carry forward. The new application RAM boundary and metadata layout must be
respected; an old monitor is not retained under an unsupported shared-ABI promise.

## Preservation and recovery

The installer binds the plan to the capture, USB/board receipt identity, exact
preimages, payloads and linked RAM installer. It checks transfers before their
erase/program operation, verifies destination bytes and commits monitor/journal
records only after their contents are present. B0 is never replaced.

Preservation includes owner data outside declared firmware destinations,
settings, conservative wear accounting, and borrowed application RAM. Private
qualification fixtures also retain the original complete board escrow and
restore owner bytes after the source-route tests. Fixture staging is test
apparatus; it is not an end-user installation step.

An interrupted update is not a reason to rerun blindly. Preserve the original
private output and obtain a fresh capture. Offline recovery accepts only exact
attested transaction boundaries. Unknown partial programming refuses. An early
fixed-F interruption can require an external programmer; electrical power-loss
atomicity is not claimed. A completed target has a no-write recovery result.
For registered rc1 sources, rollback planning uses the immediate source escrow.
This does not qualify automatic rollback to WDCMONV2 or beta4. Keep the complete
private captures for legacy recovery; the supported installation route goes
directly forward to v1g without a generation49 rollback.

## Qualification record

Direct WDCMONV2 → v1g and beta4 → v1g trials passed on both 2604 and 2609.
Each route verified both MON A/B, eight smoke cases and 32 persistent-breakpoint
hits. Both original 25,344-byte RAM images were restored and reread twice.
Full retained EEPROM/SRAM and original settings/preferences matched. The four
source-fixture and upgrade transactions reserved exactly 90 additional erase
attempts per board; final flash matched the planned target and wear journals.
Fixture staging is lab apparatus, not an end-user intermediate release.
Exact-current no-write checks passed on both boards.

Twelve new host workflow checks cover the corrected entry. The unchanged
planner/transport/linked installer inherits 32 CPU-model installer executions
and eight exact private fixture rehearsals, with member hashes proving byte
equivalence; these are not newly executed r9 CPU tests. Earlier r8 firmware,
register and soak evidence is inherited in its original scope. No new
continuous soak is claimed. Durations include owner RESET waits and are not
reported as active flash time.

One 2604 beta4 post-boot host check failed because beta4 has no `VERSION`
command. Device verification had passed. The corrected host admits beta4 only
after exact repeated source captures; the failed report and successful
continuation remain separate evidence. The SXB6 live stack comparison was also
corrected before its physical direct upgrade. No firmware/device verification
failed. Monitor timestamp/terminal-state bookkeeping corrections are recorded
separately from hardware results.

See [current release status](V1G_RELEASE_STATUS.md). The package includes
portable JSON evidence and original receipt hashes; private vendor fixtures,
RAM/flash/EEPROM/SRAM captures and raw serial logs remain excluded.
