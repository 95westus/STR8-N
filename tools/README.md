# Active tools

| Purpose | Entry or implementation |
| --- | --- |
| STR8-N F / MON / UTIL / DEV names, banners and canonical payload filenames | `product_names.json`, `build_named_components.py`, `package_named_components.py`, `test_product_names.py`, `str8n-terminal.py`; [naming scheme](../docs/COMPONENT_NAMING.md) |
| Unified PC memory backup/restore/import/export (2512 full-image round trip passed) | `memory_tool.py`, `build_memory_agent.py`, `test_memory_tool.py`, `trial_memory_2512.py`; [commands and limits](../docs/MEMORY_UTILITY.md), [2512 hardware acceptance](../docs/MEMORY_2512_ACCEPTANCE.md) |
| Read-only four-board inventory and WDCMONv2 preservation | `inventory_boards_readonly.py`, `summarize_board_inventory.py`; [October 28 inventory](../docs/BOARD_INVENTORY_2026-10-28.md). Monitor reads/bank selection only; no flashing or SRAM formatting. |
| Current firmware | `build_current.py`, `str8build/`, `src/current/` |
| Measured RTC tick alignment | `rtc_fleet.py --check-phase` / `--align-ticks`, `rtc_phase_align.py`; [paper](../docs/RTC_TICK_ALIGNMENT.md), [operation](../docs/RTC_TICK_ALIGNMENT.txt), [results](../docs/RTC_TICK_ALIGNMENT_RESULTS_2026-11-01.md) |
| RTC phase board build and offline checks | `build_rtc_phase.py`, `test_rtc_phase.py`, `test_rtc_phase_host.py`, `rtc_phase_contract.py`, `rtc_phase_bus_model.py`; [complete assembly source](../src/rtc-phase/README.md) |
| Existing RTC campaign integration | `rtc_drift_campaign.py`, `rtc_drift_statistics.py` and the preserved `rtc_base1_*`, `rtc_mon*`, `rtc_mona_*` collection adapters; live collection requires owner-local qualified campaign artifacts. |
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

## 2512 Tera Term startup display

Run `powershell -File tools/Launch-2512-TeraTerm.ps1` after closing any direct
COM4 terminal. The launcher discovers only 2512's USB adapter, honors the shared
serial lease and preservation gates, and starts Tera Term through a private
loopback connection. Its copied profile uses character-at-a-time mode with
Telnet and Telnet auto-detection disabled; the normal Tera Term profile is not
edited. The installed local pyserial runtime is used; nothing is downloaded.

For the first received bytes of that connection, `teraterm_boot.py` eats exactly
one FF only if followed immediately by `CRLF WAIT... CRLF`. The byte is retained
in `output/terminal/2512/<session>/serial-raw.jsonl`. Other prefixes, multiple FF
bytes, a truncated marker, and all later bytes pass unchanged. Any transmission
from Tera Term cancels pending recognition before forwarding user data. A held
partial prefix is released unchanged after ten seconds. The launcher itself
sends no board commands and changes no firmware, RAM, configuration or RTC.

This is a **one-shot connection-start filter**: use a fresh launcher connection
before physical RESET, without first typing commands. Reopen it to arm another
startup. `-Raw` bypasses filtering entirely. Closing its Tera Term window closes
COM4 and releases the lease. Direct COM4 connections retain their raw behavior.
TCP mode does not forward modem-line controls or serial BREAK; use a direct
serial connection when those operations are needed.

`python -B tools/test_teraterm_boot.py --out <new-folder> --native` checks the
saved FF-prefixed boot, split reads, nonmatching prefixes, raw retention,
operation gates and binary data. `--native` uses installed Tera Term against a
simulated serial receiver over loopback, including 4,096-byte binary send and
receive files. No board port is opened by the tests. The native test also checks
that the normal Tera Term profile is byte-identical afterward.

Obsolete source/build/install entry points are in the
[verified history archive](../archive/README.md). Restoring history never
executes it. Current Make targets only build, run offline checks, or show help;
there is no target that deletes all of `BUILD` or implicitly opens a board port.
