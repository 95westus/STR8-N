# STR8N-F release checkpoint

The foreground product is now **STR8N-F v0.2.0 — Boot & Recovery Toolkit**.
The [product guide](../bootstrap-opaque/README.md) and
[release scope](../bootstrap-opaque/docs/RELEASE_STATUS.md) describe its focused
operator/source packages. It reuses exact existing b15 firmware without an
assembly rebuild, CPU-model rerun or board installation. 2205 remains read-only.

The planning record below concerns the fuller stable-1.0/factory-migration
acceptance scope. It is retained as history; it does not redefine the limited
0.2.0 operator toolkit as an automatic factory migrator or full-system release.

## Historical 1.0 planning record

# STR8-N/F: scope and route to a completed release

Proposed product name: **STR8-N/F — Boot & Recovery Toolkit**. The F identifies
the fixed **$F000–$FFFF, 4096-byte sector**. Suggested artifact names are
`STR8N-F-BOOT-4096.bin` and a separately versioned `STR8N-F-TOOLS` distribution.
This is a naming/scope proposal, not a version promotion, commit or release tag.
The installed identity is still **2.0proto b15 / generation 8000000F**.

The minimum useful release is a bootstrap/recovery sector **plus its matching
software tools**. F itself is not the whole opaque-image installer. Raw L loads
and starts a RAM BIN; the OIP1 RAM installer, matching host transfer and a valid
wear journal perform ordinary image programming. Sending an arbitrary image
to raw L does not install it at its flash destination. Keep those distinctions
in the release name, manifest, instructions and advertised capabilities.

## What depends on what

| Capability | Dependencies / release contract |
|---|---|
| Reset, recovery prompt and raw RAM loading | F and supported board/console hardware; work without MONs and without a valid saved journal |
| Saved default, bank enablement and remembered entries | Valid C/D SNBT records; F reads them, matching RAM CONFIG writes them |
| Opaque-image programming and erase accounting | F/RAM services, matching RAM OIP1 tool and host, admitted target and current journal; first journal provisioning needs durable host reservations |
| MON A/B | Optional matching sectors A/B; useful inspection shells and RAM launch/dump paths, not a prerequisite for F recovery |
| Component repair / journal provisioning | Matching RAM tools loaded through F; must work with missing MONs and distinguish blank, valid and damaged journals |
| VERSION/CAPS extension | Optional VX1 E plus matching consumers; F's own legacy capability query remains distinct |
| EDU/SRAM | Optional ES1 B3:8 plus the matching RAM client and fitted EDU hardware; current port is read-only, explicitly initialized by the client |
| BASIC, fig-FORTH, selector and other opaque applications | Independently built images with documented CPU, bank/span, entry and reset/return contract; do not have to implement the internal MON ABI |

F's current raw loader waits indefinitely for its first byte, lets initial
Ctrl-C cancel, then starts the received prefix after three seconds of silence.
It has no declared length or transfer CRC. Tool self-checks run only after
execution starts. A release must state that contract plainly and provide the
tested independent RAM-readback/re-entry procedure. A future verified loader
would be a separately designed compatibility change, not something already
supplied by the b15 sector.

## Six release gates; CONFIG acceptance complete

These are **six work milestones, not six keystrokes or a fixed time estimate**.
Some need a prepare/test step and a later owner-directed hardware step. The
The CONFIG gate is now complete on 2609 over USB; five gates remain for stable
toolkit acceptance. The separately published STR8N-F source preview does not
claim those remaining acceptance gates are complete.

| Gate | Concrete completion criterion | Existing evidence / remaining work |
|---|---|---|
| 1. CONFIG save/restore acceptance — complete | From seq1021, save A at C700/seq1022, prove automatic A boot, append S at C800/seq1023, prove automatic REC; banks00 and all counts/B0/SRAM retained | USB hardware and independent audit passed. Both CONFIG uploads were independently checked; two full flash reads before/two after and three full SRAM reads match exact expected images/both backups. No erase. [Receipt and console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step19-CONFIG-save-restore-live/receipt.md). |
| 2. Freeze the release identity and contract | Choose final name/version, supported CPUs and consoles, F ABI/entry locations, journal format, protected sectors and raw-loading behavior | F is reproducible and installed. It still has a prototype identity and private/exact-image tool bindings. Freeze identity before rebuilding CRC-bound tools. |
| 3. Complete the current-board opaque-image lesson | Admit a matching OIP1 RAM/host pair with B0/VX1/ES1 protection; back up an explicitly selected disposable target; install, no-op repeat, independent readback, deliberate launch/return and restore with wear retained | Ordinary OIP1 and prior 2512 demonstrations exist. The current 2609 ES1/VX1 profile, target/entry and full preservation procedure still need preparation/acceptance. |
| 4. Assemble the matching provisioning/recovery toolset | Ship CONFIG, OIP1/host, readback/export, journal/MON repair and promised MAINT functions against the frozen F; support F-only, missing-MON and factory versus existing-owner histories | Many components are demonstrated, but several are board-specific exact plans or old F-CRC-bound kits. Generalize packaging without copying 2609 counts. Separate component tools are sufficient; a combined installer is optional. |
| 5. Accept the final candidate on its advertised matrix | Reproduce the final candidate; run applicable CPU/NOR/console models and hardware reset, recovery, cancel/load, policy, install/restore and preservation tests; bind receipts to the exact shipped files | b15 has 512 offline core groups and USB hardware evidence on 2512/2609; later components have their own receipts. Existing evidence is reusable when bytes/contracts are unchanged, but does not automatically qualify a renamed/rebuilt kit or new claims. ACIA remains outside the current physical claim. |
| 6. Produce a clean release commit and distributable kit | Build from a complete, documented source/tool closure in a clean checkout; reproduce BINs; provide address/compatibility manifests, changelog, operator guide, recovery limits and public qualification summaries; review and commit only this release scope | Prototype builders currently depend on a versioned build chain/frozen outputs. The worktree also has unrelated RC1 edits. Isolate the F release, keep private WDC/SRAM captures and owner wear records out of the public kit, and bind evidence by hashes. No commit/tag/publish is performed by this plan. |

The final candidate must explicitly state what happens with missing or invalid
journals/MONs, a torn application image and a damaged F sector. A healthy F can
load repair tools; it cannot promise self-repair when its own code/reset vectors
are destroyed. Model interruption coverage is distinct from physical power-cut
qualification. Test the advertised recovery boundary and document the rest.

For an initial USB toolkit release, BASIC/fig-FORTH, the B1 menu, full SRAM
named storage/WORK, RTC/NTP tools, debugger expansion, native 816 application
support and physical ACIA qualification need not delay the F release unless
they are explicitly included in its promised feature set. ES1 may be an optional
read-only add-on. Keep C/D journals in flash; SRAM-backed journals remain an idea.

## If the release also includes the complete 2609 application bundle

Add **three application milestones**, giving roughly **nine gates total**:

1. Package and validate the OSI BASIC and fig-FORTH opaque images with their
   exact spans, CPU modes, entry and return contracts; install through OIP1.
2. Build/test/install the B1 selector with BASIC, FORTH and two reserved slots;
   prove unavailable/reserved choices and explicit recovery/return behavior.
3. Perform final integrated policy/boot acceptance, then select B1 as the saved
   default and export the completed owner inventory, backups, wear and evidence.

These counts describe the chosen scope, not an assurance that no defects will
be found. Commit a completed F toolkit separately from an optional application
bundle so an unfinished peripheral or language port does not redefine F's ABI.

## Current evidence and next prepared step

- [F qualification: 512 groups](../BUILD/pr04-b15-cancel-r3/b15-qualification.json)
- [2512 b15 USB audit](../output/qualification/b15-2512-install-20261026/audited-results.json)
- [2609 F-only migration](../output/qualification/2609-b15-onboarding-20261027T212009Z/step03-F-only-install/receipt.md)
- [2609 ES1 installation/SRAM preservation](../output/qualification/2609-b15-onboarding-20261027T212009Z/step17-EDU-SRAM-install/receipt.md)
- [Current seq1021 CONFIG exercise source](../prototypes/boot-record-v2/prepare_config_save_restore_seq1021_2609.py)
- [Prepared CONFIG exercise and exact procedure](../output/qualification/2609-b15-onboarding-20261027T212009Z/step18-CONFIG-exercise-seq1021-ready/receipt.md)
- [Completed CONFIG A/S hardware exercise and console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step19-CONFIG-save-restore-live/receipt.md)
- [Operator F-up guide](STR8N_B15_FROM_F_GUIDE.md)
- [Opaque installer and tool-distribution flow](STR8N_B15_USER_DEMO_AND_INSTALL_ROUTES.md)

Physical 2609 is now stopped at REC, seq1023, S, banks00, with B3:8 count27 and
all other counts, B0 and retained SRAM unchanged. The old CONFIG source plan is
consumed; admit the current state before later writes.
