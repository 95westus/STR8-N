# 2609 current recorded inventory

October 30, 2026. **W65C816SXB, 65C816 emulation / FT245, COM8.**
This inventory checks the latest device marker against agreeing complete
captures and the qualification receipts. No new board command, RAM upload,
flash write or clock operation was performed for this inventory.

## Installed flash

| Region | Current content / status |
| --- | --- |
| B0 | Preserved WDCMONv2/SXB6 bank, restored exactly after AP/02 testing |
| B1 | Retained owner/legacy contents; no cleanup or free-space assignment |
| B2:8/9/A | Current WB2 g5 + PROGRAM/SP1 g1 tool bundle |
| Other B2 sectors | Retained older assets; not cleared by the tool installation |
| B3:8/9 | Retained older contents, outside the current replacement scope |
| B3:A | Legacy b15 MON A, generation **8000000F**, private contract **PR04**; unqualified under BASE1 |
| B3:B | Current MON B **0.1.0-dev g00000008**, **PR05**, qualified on 65C816 emulation |
| B3:C/D | Valid boot/wear journal, **19 records**, latest **D200 / 1033** |
| B3:E | Current services g4: maps, wear, APPS and MAINT/tool dispatch |
| B3:F | Frozen **STR8N-F 0.3.0 g00000001 / BASE1 / PR05**, 4096 bytes |

The full B2 bank matches 2512's current tool bank. MON B matches the B image
in the same prebuilt g8 candidate which supplies the proposed MON A upgrade.
Historical marker fields about older debugger/monitor generations are retained
history; the actual current slot headers above identify the installed A/B images.

## Boot policy and journal

Saved default **S/recovery**, all bank boots disabled (mask 00), stored entries
8000. Final qualified context **REC>**, COM8 released. At REC>, `B` and Enter
starts the qualified MON B; its Q returns to recovery. This does not change
the saved default. Do not treat the retained PR04 A as a qualified fallback.

Tracked C/D/E/F counts are **78/48/45/31**; B3:A is 51 and B0:9 is 4.
These are conservative tracked attempts, not lifetime totals. There are twelve
ordinary append pages D300–DE00 before a peer erase would be needed; DF00 is
reserved. Erased-looking or retained regions are not permission to overwrite them.

## Current usable tools

MON B provides Dump/Modify, guarded force Modify, bank selection, TIME, maps,
wear and APPS. MAINT LOAD brings in the matching board-flash workbench with
CLOCK, EDU/SRAM/WORK queries, PROGRAM and flash/SRAM Table/Store/Restore,
AUTO and bounded BATCH. Installed reload, CLOCK and read/query paths passed.
Positive SS1 PROGRAM Store/Restore/run and AP/02 flash-app launch subsequently
passed on 65C816 emulation. APPDEMO was temporary; original WDC B0 was restored.

PROGRAM uses the retained SS1 layout and CLK records; WORKSPACE is separate.
No SRAM reformat or duplicate cleanup on 2609 is included here. Resident
ASM/DBG, advanced CLOCK, the full sector FLASH editor and full b35 parity
remain separate/deferred work. Native 816 execution is not claimed by these tools.

## Owner RAM and RTC/NTP

RTC collection remains admitted as **BASE1-MONB8-RTC-RAM1-2609**, with the
unchanged qualified RAM sampler, frozen READBACK and existing schedule/baselines.
No time, trim or power-fail acknowledgement was issued by this inventory.

A later owner-authorized RAM reconciliation produced a new current reference
on October 30 at 20:32–20:35 UTC, followed by successful RTC qualification at
20:36 UTC. It is distinct from the older installer/AP02 RAM escrows. Future
trials must take fresh native double captures and restore their own fresh
escrow; never substitute the old installer RAM for current owner data.

Reference RAM SHA-256:
`89643196dcf3adb601f62e959c9802e9bcd17ed9b551e336d6e80364ad30d1f1`.

Reference ZP SHA-256:
`106d61c82d3ee7f7c2e3c174888b3dc6a1aae71ad3e2a0afd14e5593cfbf6ba4`.

## Next review and WDC boundary

The [MON A review](2609_MON_A_G8_SCOPE_REVIEW.md) offers one erase to leave A
matching B, or two erases for a temporary test followed by exact legacy-A
restoration. Either needs an owner choice before mutation.

The 2512 WDC launcher is pinned to a **65C02/SXB2** ROM. It is not installed
or qualified on 2609's **SXB6** ROM. The recorded B0 reset vector is F818,
but its serial vectors and firmware differ. A 65C816 launcher needs its own
entry/mode review. Existing BASE1 F and SNBT also mean 2609 is not a fresh
factory-migration fixture; NFM2 provisioning must not erase its retained history
merely to obtain a WDC-source test.

Evidence: [MON/tools](2609_MON_FEATURE_ACCEPTANCE.md),
[PROGRAM](2609_PROGRAM_POSITIVE_ACCEPTANCE.md), [AP/02](2609_AP02_ACCEPTANCE.md).
Private current RAM reference:
`C:\SRC\STR8-N\output\qualification\2609-RAM-reconcile-20261030T203252Z\reference.json`.

Recorded bank SHA-256 values:

- B0: `1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`
- B1: `fb22d9ab58700e66123c200bc68717c8a90e6280379c96a43164ddc46cbfc1eb`
- B2: `c3a5aa83e937fd6a0799360d910725e9974f6ea0b9f24887d11e7e9c599066f7`
- B3: `ace3c7f79f9014393fd09b3dd8f8a4df2b709740279ae5349d750e9f5553162e`
