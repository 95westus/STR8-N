# DBG1 BRK-fix candidate v1g: staged, promotion held

This archive contains the exact **v1g** firmware, offline-prepared install kit,
updated RC1/ASM/debugger documentation, offline results and checksums.
It is a staging snapshot. Package integrity verification does not approve
installation or promotion. **No v1g board, soak or drift result is claimed.**

Scope: RAM debugging on **65C02 and 65C816 E=1**. Native applications and
native debugging are excluded. Application RAM capacity is unchanged.

## Candidate labels and scope

`v1g` is an internal DBG1 build label, following `v1f`; it is not a new public
release number or processor mode. Both builds remain generation 50, with
version text `2.0rc1`, ASM `0.5` and BRK ABI 1. Hashes identify the image.
v1f fixes the MAINT compatibility guard. v1g adds the `$82` invalid-ID and `$84`
terminal-RAM text fixes. Earlier candidate ZIPs and published rc1 generation
49 are unchanged.

The current six-hour board soak uses v1f. Finishing it provides baseline and
drift evidence for that image, but cannot qualify v1g. Completion is not a
technical prerequisite for a later v1g trial. A safe stop must use the runner's
RAM-restoration path; staging neither stops nor changes the current run.
A v1g hardware soak must be separately authorized and recorded against v1g's
hash after installation and requalification.

## Verify without accessing a board

Check the adjacent ZIP `.sha256` file, extract into a new directory, and run:

```text
python verify_package.py
```

The verifier uses only Python's standard library and opens no ports. It checks
the inventory, exact image/kit hashes, debugger CRC, linked sectors, offline
evidence and pending qualification state. Read
[install and rollback](INSTALL_ROLLBACK.md) before any future authorized trial.
2604 and 2609 remain owned by the current soak; do not open their ports.

## Changes and offline results

- `$82` rejects IDs outside `$C0-$FE` before table lookup. `$00` cannot match
  a vacant entry. Valid removals and missing-ID refusal are retained.
- `$84` validates the complete inclusive range, then finishes its count before
  advancing beyond the last byte. Text ending at `$64FF` or released `$66FF`
  preserves saved registers/flags. Invalid ranges print nothing and refuse.
- All 88 original edge checks and 7,256 expanded checks passed on both models
  and slots. Full suites include MAINT, boot, BRK/C/S/N/shared D/M/U, all eight
  persistent breakpoints and 16 documented ASM example executions.
- All 72 registration scenario executions and 21 installer-model groups passed,
  including actual instruction-model install/rollback on both CPUs, eleven
  transfers per transaction, and stale/corrupt input refusal.
- A second build is byte-identical. Only B1:A000-AFFF differs from v1f.
  The debugger has 3,975 code bytes plus two CRC bytes, leaving 119 bytes free.

See [offline results](docs/rc1/DEBUGGER_BOARD_RESULTS.md),
[the debugger guide](docs/rc1/DEBUGGER_GUIDE.md),
[ASM examples](docs/rc1/ASM_GUIDE.md#debugging-ram-programs-with-dbg1) and
[BRK system/user registrations](docs/rc1/ABI_REFERENCE.md#dbg1-brk-functions-and-registrations).

## Contents and remaining work

| Path | Contents |
| --- | --- |
| `install/` | Exact offline-qualified kit; nine firmware sectors and eleven-transfer preserving transaction |
| `docs/rc1/` | Current v1g status and RC1/ASM/ABI/debugger manuals |
| `qualification/offline/` | Full model/manual, edge, registration, installer and reproducibility evidence |
| `qualification/hardware/pending.json` | Both-board hardware requalification pending |
| `qualification/soak/pending.json` | v1g soak and drift pending; parent results are not reused |
| `firmware/` | Exact 96 KiB reference image and sealed debugger component |
| `source/debugger/` | Matching debugger sources and generated linked addresses |
| `diagnostics/` | E=1 observer and registration-scenario source |
| `release/rc1-uchess/` | Credited uChess source and redistribution notice |
| `package-manifest.json`, `SHA256SUMS.txt` | Complete inventory and SHA-256 hashes |

The reference BIN contains development defaults and must not replace a
working board's full banks, settings or wear history. A future installation
uses a fresh exact-source plan. This kit accepts generation 49; it cannot
update either currently installed generation-50 candidate directly. Its
rollback returns to the captured generation-49 source, not to v1f.

Private board captures, RAM archives, serial logs, board-specific plans, B0
and vendor firmware are excluded. Parent hardware/soak evidence is not included
as v1g acceptance evidence. Repository build commands in the manuals require
the source checkout and dependencies. The frozen kit's preparation-time docs
and flags are historical inputs; this archive's [qualification summary](qualification/summary.json)
states the current offline-only scope.

Both-slot physical-board checks, rollback/reinstall, soak, final drift review
and an explicit release decision remain required. Promotion stays held. This
snapshot does not acquire later results automatically.
