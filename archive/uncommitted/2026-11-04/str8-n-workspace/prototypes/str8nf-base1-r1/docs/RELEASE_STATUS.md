# STR8N-F 0.3.0 — release scope and evidence

Release preparation: **October 28, 2026**. F is **0.3.0 g00000001 / BASE1 /
PR05**, exactly 4096 frozen bytes. The public ABI is unchanged. **Mona** is
the planned optional monitor, with no binary included in this release.

> 4KB of firmware. One board. Up to four boot environments.

Compatible, user-supplied images run one at a time on shared CPU/RAM/peripherals.
This describes the bank architecture; hardware qualification is limited to
the receipts.

## Closed 2512 cases

| Case | Result and evidence |
| --- | --- |
| Known-b15 existing-journal F upgrade | [Passed](2512_BASE1_ACCEPTANCE.md): reservation before F, prior history/settings/images retained |
| BASE1 identity, reset, recovery and RAM tools | [Passed](2512_BASE1_ACCEPTANCE.md): physical resets, MAP, READBACK, Ctrl-C and normal BIN loading |
| Python terminal operator acceptance | [Passed](2512_BASE1_ACCEPTANCE.md): native F1-F12, dialogs and real-port disconnect deferral; original RAM restored |
| CONFIG and opaque install/boot | [Passed](2512_B0_POWERCUT_ACCEPTANCE.md): persistence, RAM/flash writes and boot, original images/policy/RAM restored |
| WDC RAM migration | [Passed](2512_WDC_MIGRATION_ACCEPTANCE.md): real vendor debugger/archive, public F/D/C conversion, recovery and preservation |
| Programmer-installed-F C/D entry | [Passed](2512_PROGRAMMER_F_CD_ACCEPTANCE.md): public no-op and declared non-SNBT first journal, four C/D erases, F golden |
| Interrupted C/D journal cases | [Passed](2512_CD_RECOVERY_ACCEPTANCE.md): six named chip-idle cuts, original rows/settings/images/RAM restored, current counts retained |
| Interrupted-F runtime gate | [Closed by scope](GOLDEN_F_RECOVERY_SCOPE.md): F assumed golden; no interrupted-F pass claimed |

All passes are limited to their receipts. The WDC and programmer-F conversions
explicitly archived replaced raw history on the host while importing latest
tracked counts. The 2512 checkpoint is REC>, COM4 released, latest
sequence 1000, three records, C=52/D=32/F=24; original owner images, settings
and RAM/ZP verified. The later 2609 ZIP checkpoint is REC>, COM8 released,
seq1024/11 records and C=78/D=47/F=31, with all ten old rows retained.
2205 was not accessed; 2604 was excluded from the 2609 trial.

## 0.3.0 package scope

The final operator/source packages correct rc1 docs, update release metadata
and include the 2609 receipt. Firmware, console, migration hosts and engines
remain unchanged. The rc1 ZIP stays immutable; its live result belongs to its
exact hash. A static equivalence check does not claim another hardware trial.

| Item | Status |
| --- | --- |
| Existing-SNBT upgrade from extracted rc1 | [2609 passed](2609_RC1_ZIP_UPGRADE_ACCEPTANCE.md), 65C816 emulation/FT245; terminal core checked, native GUI keys not repeated |
| Final 0.3.0 package live trial | NOT RUN; unchanged runtime files, new docs/metadata |
| WDC and programmer-F package routes | NOT RUN from an extraction; reviewed 2512 source/hardware cases passed |
| Python terminal | Included; native keys/dialogs passed on 2512, core cancellation/load passed on 2609 |
| Original captures for b15 upgrade | Operator precondition; no standalone automated capture CLI |
| Mona / expanded service ABI | Planned, outside this release |
| Other CPU modes/adapters/hosts and occupied layouts | Unqualified |
| Interrupted F installation, electrical mid-pulse failures, arbitrary damaged history | Outside qualified scope |

See [release notes](RELEASE_NOTES.md), [installation](INSTALLATION.md),
[rc1 findings](RC1_KNOWN_ISSUES.md) and [packaging workflow](RELEASE_WORKFLOW.md).
Normal runtime recovery keeps F golden. Packaging performs no board actions,
power cuts, firmware builds or CPU simulations. 2205 remains excluded.
