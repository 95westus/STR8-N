# Release-candidate gates and reset notices

The published release remains beta4. Boards 2512, 2205 and 2609 have verified
beta23 generation-32 uploads and captured physical starts. Exact readback and
core startup/EDU/ABI/IRQ/NMI checks pass; wider qualification remains pending. The
previous hardware acceptance is beta22 generation 31 / CLOCK 1.6. Beta22 hardware
acceptance does not qualify beta23 or a new RC package. The user has expanded
the matrix to include 2604. The [four-board functional/preservation/recovery
checkpoint](STR8N_V2_BETA23_FOUR_BOARD_STORAGE_2026-10-09.md) passed through the
21:50 test window; the soak and final RC package remain outstanding.
The [October 10 drift/soak summary](STR8N_V2_BETA23_DRIFT_SOAK_2026-10-10.md)
records continued exercises and the current battery-backed power-off segment.

## In-program reset messages

| Operation | Requirement | Visible message/behavior |
|---|---|---|
| Verified firmware upload | Physical main-board RESET; installer is halted | `MIGRATION VERIFIED; PRESS PHYSICAL RESET` |
| Confirmed saved EDU ON/OFF change | Cold restart to activate the saved mode | `Saved; RESET required.` |
| R EDU status with active/saved modes different | Requirement remains until cold restart | Beta23 shows active `EDU ON`/`OFF`, then `RESET required: OFF`/`ON` |
| Canceled, failed or unchanged EDU save | No new requirement | No success/reset notice; an existing pending setting stays pending |
| CLOCK OFFSET, SET or TRIM | Immediate after successful verification | No reset-required message |
| Saved records and WORK claims | No activation reset | RESET invalidates workspace handles |

For saved EDU mode, physical RESET or the monitor's cold `J3` restart activates
the new state. `Q`, HOLD and ordinary monitor return do not. Do not type a
nonexistent `RESET` command. After an upload the halted installer cannot accept
J3: press the main physical RESET. On 2609 use S2/RESB, not S1/NMIB or an EDU
control. The pending notice clears once the active and saved settings agree.

## Remaining gates, in order

October 9 phase 1: gates 1–2 below passed for the retained beta23 snapshot.
See [freeze and rehearsal evidence](STR8N_V2_BETA23_PHASE1_2026-10-09.md).
All three beta23 uploads, captured physical starts, full readbacks and core
startup/mode/interrupt checks pass. The expanded four-board checks now close
gates 3–4 within the documented scope, including controlled recovery and actual
power retention. Gate 5's 48–72-hour soak and final gate 6 packaging remain
pending. See [hardware status](STR8N_V2_BETA23_HARDWARE_2026-10-09.md) and the
[four-board closeout](STR8N_V2_BETA23_FOUR_BOARD_STORAGE_2026-10-09.md).

1. **Freeze beta23.** Pass the bound candidate audit and reset-notice models;
   retain source/build/model hashes. Keep SPI recovery, outage handling, public
   ABI and fixed recovery intact. Re-run affected gates after any later edit.
2. **Rehearse the exact beta22-to-beta23 upgrade.** Take fresh repeated per-board
   backups; model complete final images, stale-preimage and corrupt-payload
   refusal, record/identity/offset preservation, saved EDU and wear accounting.
   Private helper references relink, so this is not an arbitrary text-sector
   patch. Hardware installation requires a separate authorized flash run.
3. **Qualify that exact image on all four boards.** Test A/B slots, repeated
   main RESET and J3, quiet M1/HOLD, EDU ON/OFF, pending/saved reset notices and
   their clearance, reclaimed RAM limits, all caller banks, IRQ/BRK/NMI and
   816 emulation state and the advertised native-vector BRK/NMI entry/return
   contract. Native RTC/I2C services are outside this matrix.
4. **Regress time and storage workflows.** Check compact local boot, detailed
   TIME/CLOCK, EUI, offset persistence/defaults, fractional offsets and date
   boundaries, normal/coarse trim labels and guarded alarm/output ownership;
   flash/SRAM save/restore/run/table/delete; workspace resize/claims
   and stale-handle refusal. Use backed-up test records, restore test data and
   retain exact full flash/SRAM/EEPROM and RTC-control/identity comparisons.
5. **Exercise recovery and complete a 48–72-hour soak.** Retain model write-cut,
   corrupt/full record and bus-failure coverage. Qualify supported recovery and
   retention with controlled cold/power cycles and ordinary hardware use.
   Preserve outage evidence: real power failures may append new valid events
   and replace the oldest full-ring slot; archive the prior history and verify
   every other slot unchanged. The current four-board zero-trim campaign uses
   its own immutable fresh-NIST baselines and scheduled checkpoints; see
   [campaign policy](STR8N_RTC_ZERO_TRIM_CAMPAIGN_2026-10-09.md).
   Stop a comparison if UTC/trim
   changes. This checks continuity, not a promise of optimal trim from a short
   measurement window.
   The user narrowed the extended soak to 2604 and 2609; the other two boards
   retain their completed functional qualification. Record this reduced soak
   matrix explicitly rather than implying all four were observed for 48–72 hours.
6. **Reproduce and verify the RC package/docs.** Build from a clean checkout;
   compare artifact hashes, ZIP contents and packaged installers for supported
   source versions. Run `tools/check_no_board_backups.py --history`. Ship no
   board backups, stock firmware or raw qualification evidence. Document current
   placement, commands, reset behavior, migrations and limitations.
   **The user requires the examples in the release ZIP and published source.**
   Include the three annotated 65C02 sources, shared ABI include, tutorial,
   technical guide and checked S19 applications. The mandatory example file
   mapping is [release-package.json](../examples/beta23/release-package.json).
   Preserve its relative documentation paths, cover every member in the package
   checksum manifest and verify archive readback. Rebuild/model-check the examples
   against the final packaged firmware before collecting them. Ship the build/test
   scripts with their dependency closure or a documented complete source kit.
   Keep the examples' model/hardware qualification labels accurate; a package
   inclusion check does not establish hardware acceptance. Do not omit examples
   simply because their generated outputs reside in ignored BUILD directories.

RC1 requires these applicable gates on the same frozen image, no open blocking
defect in advertised paths and complete evidence for the supported matrix.
Historical acceptance does not substitute for new-image/package qualification.

## Exclusions and known limitation

- Board 2604 now participates in the expanded firmware/RC test matrix;
  acceptance requires its own current receipts rather than inherited results.
- STR8N-001 ACIA receive on 2512/2205 remains deferred. Advertise the qualified
  USB console, not that ACIA receive path. If ACIA receive becomes a release
  requirement, the issue becomes a blocker.
- Native RTC/I2C, general external mikroBUS devices, RTC alarms/MFP, crypto and
  automatic application of drift-derived trim remain outside this RC.

See [beta22 qualification](STR8N_V2_SPI_STARTUP_2026-10-09.md),
[current operator checkpoint](STR8N_V2_BETA23_OPERATOR_2026-10-09.md),
[beta23 compact boot](STR8N_V2_COMPACT_BOOT_2026-10-09.md),
[issues](../ISSUES.md) and [EDU mode](STR8N_V2_EDU_MODE_2026-10-08.md).
