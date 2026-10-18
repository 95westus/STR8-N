> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# Beta35 draft manuals

Target: **STR8-N 2.0b35, generation 47; FT245/F30D**. These are prerelease
drafts for the frozen candidate. They do not authorize installation or claim
completed hardware qualification. ACIA and crypto remain deferred.

| Guide | Purpose |
| --- | --- |
| [User guide](USER_GUIDE.md) | Console sessions, programs, clock displays and evidence preservation |
| [ASM guide](ASM_GUIDE.md) | ASM 0.5 source editor, assembly, output and application contract |
| [Program and command reference](COMMAND_REFERENCE.md) | Command contexts, syntax and effects |
| [Technical manual](TECHNICAL_MANUAL.md) | Memory, ABI, storage, transaction and recovery design |

The guides remain prerelease drafts despite passing the bounded offline
source/ABI/example audit. Physical acceptance and broader migration routes
remain open. Do not run the examples on the protected campaign
boards. Keep 2512's soak and RTC campaign running, the other three boards off,
and all real clocks, trims and settings unchanged.

See the [qualification plan](../STR8N_V2_BETA35_PRERELEASE_WORK.md),
[migration support matrix](../STR8N_V2_BETA35_MIGRATION_MATRIX.md) and
[current qualification notes](../STR8N_V2_BETA35_RELEASE_QUALIFICATION_2026-10-16.md).
Source links in these guides point to the clean beta35 source tree, not v2.1.
