# Retired development paths

Phase 5 removes obsolete source trees, transformation builders, copied installer
planners, board-specific scripts and old root launchers from the active tree.
Their original relative paths and exact bytes are in `legacy-source.zip`.
`manifest.json` records every member's size and SHA-256, whether its old path was
retired, and the archive hash. The original Makefile and precleanup versions of
the few updated model helpers are included for reproduction.

Verify or restore without executing any archived code:

```powershell
python -B tools/restore_history.py verify
python -B tools/restore_history.py restore --out tmp/history
python -B tools/restore_history.py restore --out tmp/history-with-context --context
```

Every output directory must be new. Restore validates the entire archive before
creating it, writes original bytes, and refuses unsafe members or overwrites.
`--context` additionally copies current source/build support, baseline fixtures,
published release resources, manuals, examples and license files. Archived
originals take precedence. It never copies `BUILD`, `output`, private backups or
serial captures, and never runs a builder, installer or device command.

Historical commands in dated documents now apply in the restored directory.
For the old Makefile, select its explicit historical target, such as
`make legacy-v1`; current work uses the root Makefile. A restoration makes old
source and algorithms recoverable. Reproduction still needs the original
external compiler/model dependencies and any generic artifacts listed by the
dated recipe. Phase 1's limits still apply: private qualification receipts,
installed-board state and published-package staging are not generic source-only
build outputs. No historical evidence has been relabeled as a fresh hardware pass.

The active paths are `src/current`, `tools/build_current.py`, `tools/str8build`,
`tools/install_current.py` and `tools/installer`. Current source/example model
tests, sample generators and PDF support remain available under `tools`; their
firmware input defaults to `BUILD/current` where applicable. Small, byte-frozen
published-release support helpers remain because sealed release recipes refer
to their exact names or hashes. See [the active tool map](../tools/README.md).

`release/**`, published ZIPs, all Phase 1–4 baselines, existing build results,
original board captures and device-operation markers remain in place. The
archive contains source and generic source fixtures only, with no board backup
or application RAM. Python caches are disposable and are not archived.

Installer regression tests use the frozen [compatibility fixtures](../tests/fixtures/README.md)
and Phase 4 artifact hashes instead of executing the retired preparers. The
current build still checks every firmware byte, all 20 recorded payloads and
29 linked symbol maps against the established baselines.
