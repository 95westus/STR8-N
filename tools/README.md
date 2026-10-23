# Active tools

| Purpose | Entry or implementation |
| --- | --- |
| Current firmware | `build_current.py`, `str8build/`, `src/current/` |
| Compatibility build alias | `verify_current_sources.py` forwards to the same builder |
| Profile-driven installer | `install_current.py`, `installer/` |
| Isolated offline regressions | `test_current_build.py`, `test_current_installer.py` |
| Resident build contract | `test_resident_contract.py`, `resident_module_inventory.py`; [verified capabilities and limits](../docs/RESIDENT_BUILD_CONTRACT.md) |
| Historical recovery | `restore_history.py`, `test_history_archive.py` |
| Resident source/storage CPU harness | `test_rc1_source_store.py`, `test_rc1_source_flash.py`, `test_rc1_source_flash_edges.py` |
| Current ASM/DBG checks | `test_rc1_asm_dev.py`, `test_rc1_asm_equ.py`, `test_rc1_console_edit.py`, `check_rc1_asm_docs.py` |
| Example generation and models | `build_rc1_dev_samples.py`, `name_rc1_demo_constants.py`, `build_rc1_edu_loop_source.py`, `test_rc1_dev_samples.py`, `test_rc1_demo_constants.py`, `build_rc1_sample_listings.py`, `test_rc1_sample_walkthroughs.py` |
| Books and PDF support | `build_rc1_source_pdfs.py`, `build_rc1_asm_docs_pdf.py`, `check_rc1_source_pdfs.py`, `pdf-fonts/` |

Source/sample model helpers honor `STR8_SOURCE_BUILD` and default to
`BUILD/current`. They run linked firmware in CPU/peripheral models. Their model
dependencies remain explicit local prerequisites; this cleanup downloads
nothing. Listing/EQU walkthroughs additionally require generated generic sample
binaries. Book sections describing historical board trials still require their
existing private evidence and do not become clean-build inputs.

Published-release support is retained byte for byte: `test_rc1_debugger.py`,
`fetch_rc1_debugger_816_model.py`, `audit_rc1_dbg_docs.py`, `rc1_v1g_components.py`,
`rc1_dbg_closeout_cases.py`, `test_rc1_uniform_workflow_v2.py`,
`test_rc1_uniform_release_package.py`, and `serial_test_coordination.py`.
Frozen release recipes reference these paths/hashes. They are distinct from
the current build and installer implementation. Model fetching remains an
explicit network operation; offline checks use already installed dependencies.

Obsolete source/build/install entry points are in the
[verified history archive](../archive/README.md). Restoring history never
executes it. Current Make targets only build, run offline checks, or show help;
there is no target that deletes all of `BUILD` or implicitly opens a board port.
