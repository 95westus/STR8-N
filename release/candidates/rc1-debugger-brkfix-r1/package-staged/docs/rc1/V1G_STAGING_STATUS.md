# v1g labels and qualification status

`v1g` is the next internal DBG1 build label after `v1f`. It is not a new public
release number. The displayed firmware remains `2.0rc1`, development generation
50, ASM 0.5 and BRK ABI 1. Use the image SHA-256 to distinguish candidates.

| Build | Change | Scope |
| --- | --- | --- |
| v1e | Original DBG1 candidate | Historical results; MAINT guard mismatch found later |
| v1f | Strict MAINT guard synchronized with the DBG1 boot marker | Earlier hardware requalification; current six-hour soak belongs to this build |
| v1g | v1f plus `$82` invalid-ID and `$84` text-end fixes | Offline passed; physical hardware, rollback/reinstall, soak and drift pending |

Finishing v1f's current soak provides an unchanged baseline and drift result,
but it is optional for v1g development and does not qualify v1g. The runner
owns the current deadline, RAM restoration and final drift collection. Staging
leaves that run alone. A requested early stop must use its safe restoration
path. No new soak is started by extracting or verifying this archive.

The v1g [offline evidence](DEBUGGER_BOARD_RESULTS.md) passes. Both-board
requalification and rollback/reinstall, a separately authorized soak and final
drift review, and an explicit promotion decision remain required. Promotion is
held. Native applications/debugging remain outside scope.

Read the [debugger guide](DEBUGGER_GUIDE.md) and
[future install/rollback procedure](../../INSTALL_ROLLBACK.md). Those commands
are documentation for a later authorized trial; do not run them against the
currently soaking boards.
