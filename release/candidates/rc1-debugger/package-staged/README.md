# Corrected rc1 DBG1 candidate: staged, promotion held

This archive stages the exact MAINT-corrected `v1f` generation-50 firmware and
its tested board kit. It is a review artifact. Promotion remains held, the
corrected-image six-hour soak and final drift snapshot are pending, and two
BRK service findings remain open. Package integrity verification does not
mean release qualification has passed.

Scope is RAM debugging on **65C02 and 65C816 E=1**. Native applications and
native debugging are excluded. Application RAM capacity is unchanged.
The published generation-49 rc1 release and older candidate ZIP are unchanged.

Verify the adjacent archive checksum, extract into a fresh directory, then run:

```text
python verify_package.py
```

This uses the Python standard library and opens no ports. Do not access the
soaking boards or execute install/rollback commands during this review.
Future installation requires its own authorization and fresh exact-source
backups/plans; see [install and rollback](INSTALL_ROLLBACK.md).

## Evidence and outstanding work

The corrected image passed MAINT, BRK/C/S/N/shared D/M/U, all eight persistent
breakpoints, system/user registrations and supported-app checks in both slots
on both boards. Requalification recorded 72 registration scenarios, 128
breakpoint hits and 84 verified transfers, including old-candidate removal and
corrected-candidate install/rollback/reinstall. Original RAM/preferences and
RTC settings were restored or preserved as recorded in the board evidence.

Additional offline review found `$82` can acknowledge invalid ID `$00` after
the registry is initialized, and `$84` changes A/P after printing text ending
exactly at the application RAM limit. See [known findings and workarounds](docs/rc1/DEBUGGER_GUIDE.md#candidate-review-status).
Both findings need resolution before promotion. The pending soak does not
exercise these exact edges. A future firmware fix needs fresh qualification.

The original `v1e` eight-hour results remain historical and are not included
as passing `v1f` soak evidence. This staged snapshot cannot acquire later
results automatically; create a new package after qualification is complete.

## Contents

| Path | Contents |
| --- | --- |
| `install/` | Exact tested kit: nine firmware sectors, eleven-transfer preserving installer, rollback planner and smoke programs |
| `docs/rc1/` | RC1/ASM/debugger manuals, BRK ABI, both-board results and review findings |
| `qualification/boards/` | Portable corrected-image requalification summaries |
| `qualification/offline/` | Model/manual checks and installer instruction-model results |
| `qualification/review/` | Coverage, edge-case observations, MAINT review and documentation audit |
| `qualification/soak/pending.json` | Explicit pending six-hour soak/drift state |
| `qualification/summary.json` | Completed evidence and remaining promotion gates |
| `firmware/` | Exact tested 96 KiB reference image and sealed debugger component |
| `diagnostics/` | E=1 observer and source for the bounded registration scenarios |
| `release/rc1-uchess/` | Credited uChess source and redistribution notice |
| `package-manifest.json`, `SHA256SUMS.txt` | Complete inventory and SHA-256 checksums |

The reference BIN contains development defaults; use a fresh preserving plan
for an authorized future installation. It must not replace a working board's
full banks, settings or wear history. B0, private captures, application RAM
archives, serial logs and board-specific plans are excluded.

The frozen kit's preparation-time flags/docs predate requalification; current
scope is recorded in this archive's [qualification summary](qualification/summary.json).
The archive-relative install procedure is [INSTALL_ROLLBACK.md](INSTALL_ROLLBACK.md).
The candidate source build commands require the repository and dependencies.

Read the [debugger guide](docs/rc1/DEBUGGER_GUIDE.md),
[ASM examples](docs/rc1/ASM_GUIDE.md#debugging-ram-programs-with-dbg1),
[system/user ABI](docs/rc1/ABI_REFERENCE.md#dbg1-brk-functions-and-registrations)
and [board results](docs/rc1/DEBUGGER_BOARD_RESULTS.md).
