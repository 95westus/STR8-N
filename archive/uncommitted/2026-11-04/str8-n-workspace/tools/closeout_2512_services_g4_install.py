"""Publish hash-only receipts after the installed 2512 physical-boot gate passes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'release/str8nf-v0.2.0'
CASE = ROOT / 'output/qualification/2512-services-g4-installed-20261030-r1'
BOOT = ROOT / 'output/qualification/2512-services-g4-physical-20261030-r1'
PLAN = ROOT / 'output/qualification/2512-services-g4-install-scope-20261030-r1'
sha = lambda body: hashlib.sha256(body).hexdigest()
r = json.loads((CASE / 'final-receipt.json').read_text())
b = json.loads((BOOT / 'report.json').read_text())
p = json.loads((PLAN / 'plan.json').read_text())
assert r['passed'] and b['passed'] and r['physical_boot_verified']
assert r['all_postimages_double_verified'] and r['all_131072_SRAM_bytes_unchanged']
assert r['owner_RAM_restored'] and b['owner_RAM_restored'] and b['COM4_released']
assert b['chooser_keys_sent'] == 0 and b['physical_saved_B_boot_owner_unchanged']
assert r['plan_sha256'] == sha((PLAN / 'plan.json').read_bytes())
receipt = dict(schema=1, board='2512', CPU='65C02', passed=True,
    phase='INSTALLED_AND_PHYSICAL_DEFAULT_BOOT_PASSED', monitor_slot='B',
    monitor_generation='00000008', service_generation='00000004',
    workbench_generation='00000005', program_generation='00000001',
    F_sha256=p['F_sha256'], plan_sha256=r['plan_sha256'], checks=r['checks'],
    component_targets=r['components_completed'], component_erases=4, journal_C_erases=1,
    total_sector_erases=5, journal_appends=5, F_writes=0, D_erases=0, A_B_image_writes=0,
    original_C_records_archived_on_host=16, original_C_archive_sha256=p['original_C_sha256'],
    original_D_records_retained_on_chip=15, original_D_sha256=p['original_D_sha256'],
    all_old_rows_retained_on_chip=False, latest_wear_counts_and_policy_preserved=True,
    sequence_after=1033, valid_journal_records_after=20, default_boot='B', saved_generation='00000008',
    counts_after={'B2:8':596, 'B2:9':265, 'B2:A':13, 'C':53, 'D':33, 'E':28, 'F':24, 'MON_A':41, 'MON_B':48},
    enabled_mask=15, entries=['8000'] * 4, boot_policy_preserved=True,
    all_postimages_double_verified=True, postimages_unchanged_after_physical_RESET=True,
    final_bank_sha256=p['expected_bank_sha256'],
    all_131072_SRAM_bytes_unchanged=True, SRAM_sha256=r['SRAM_sha256'],
    PROGRAM_format='SS1', PROGRAM_boundary='10000', SRAM_data_writes=0, WORKSPACE_writes=0,
    RTC_SET=0, trim_writes=0, PF_ACK=0, power_cuts=0, firmware_builds=0, CPU_simulations=0,
    owner_RAM_ZP_restored_verified=True, physical_saved_B_boot_owner_unchanged=True,
    chooser_keys_sent=0, final_context='B3>', COM4_released=True,
    matched_new_flash_reload_qualified=True, forced_load_over_valid_old_cache_qualified=True,
    cold_spaced_and_bad_argument_cases_qualified=True,
    positive_PROGRAM_write_run_retested=False, positive_AP02_flash_launch_retested=False,
    ASM_DBG_execution_qualified=False, RTC_NTP_profile='MON-G8-NATIVE-TIME',
    RTC_NTP_sampler_and_schedule_unchanged=True, published_downloads_unchanged=True,
    install_report_sha256=sha((CASE / 'report.json').read_bytes()),
    final_receipt_sha256=sha((CASE / 'final-receipt.json').read_bytes()),
    physical_boot_report_sha256=sha((BOOT / 'report.json').read_bytes()),
    install_driver_sha256=sha((CASE / 'install_2512_services_g4.py').read_bytes()),
    finished_utc=r['finished_utc'])
(REPO / 'monitors/validation/2512-services-g4-install.json').write_text(json.dumps(receipt, indent=2) + '\n')
text = '''# 2512 current MON tools: installed and accepted

October 30, 2026. **65C02 / FT245**, MON B g8, services g4, WB2 g5 and
PROGRAM/SP1 g1. [Public receipt](../monitors/validation/2512-services-g4-install.json),
[approved five-erase scope](2512_SERVICES_G4_INSTALL_SCOPE.md),
[preceding RAM acceptance](2512_SERVICES_G4_RAM_ACCEPTANCE.md).

## Installed workflow

Native M1/M2/M3/W, APPS inventory and TIME passed. Actual `MAINT LOAD` from
the new WF/03 board bundle passed over a valid older WB3 RAM cache, with
leading/trailing spaces, and with an empty cache. Extra arguments were
refused before loading. Cached MAINT/FLASH opened WB5; CLOCK read/refreshed
and returned. Explicit EDU/SRAM/WORK queries, SS1 PROGRAM Table,
`BATCH T;T`, malformed separators, missing-name Restore and AUTO preview/NO
passed. No PROGRAM record was stored or retained program executed.

The physical RESET then selected saved B/g8 without a chooser key. It left
owner RAM/ZP intact before any helper upload. Native map/wear/APPS/TIME and
all flash postimages passed again. Final owner RAM0200-66FF and ZP00-DF were
restored and independently read back, original MON B/B3> returned, COM4
released. Both MON slots retain their original g8 bytes; this new installed
workflow was exercised through B.

At B3>, use **MAINT LOAD** to deliberately load the new board-stored tools.
Exact owner-RAM restoration also restores its valid older WB3 cache; bare
MAINT can reuse that cache. Q returns from tools to B3>; Q at B3> returns
to recovery. The saved default remains B bound to generation 8.

## Writes and preservation

Exactly five sector erases: B2:8/9/A, B3:E and native B3:C journal rotation.
Five new journal rows: DF00 intent/seq1029, C000 root/seq1030, then
C100/C200/C300 through seq1033. Every component and journal result matched
its sealed postimage before the next request. No retry or extra erase.

The 16 original C records are durably archived on the host; they are no
longer on chip. All 15 original D records remain byte-identical on chip.
Latest boot policy, generation bindings, wear counts and prior-wear flags
carry forward. Final journal: 20 valid rows, C300/seq1033. Counts (decimal):
B2:8=596, B2:9=265, B2:A=13, C=53, D=33, E=28, F=24; MON A=41/B=48.
Other images, golden F, saved B/g8, mask 0F, four 8000 entries and delay remain
unchanged. Original component sectors and complete banks are archived.

Complete 131072-byte SRAM equality:
`580a60e314e7c91703a319f03516bd803f36a8202f773e4206b6d4aa69d227aa`.
PROGRAM, CLOCK/CLK records, header, WORKSPACE and tail are intact. Zero F,
MON A/B or SRAM-data writes; no clock settings, trim/PF acknowledgements,
power cuts, firmware builds or CPU simulations. Other boards were excluded.
The existing native TIME RTC/NTP sampler, schedule, baselines and samples
remain unchanged; its unchanged MON/F identities and B3> context remain
admitted after verified restoration. The shared serial lease is released.

## Release boundary

This closes the current 65C02 RAM and matching board-flash reload gate.
Positive PROGRAM Store/Restore/run on 2609 retains its separate 65C816
emulation receipt; this trial adds no new 65C02 positive write/run or AP/02
flash-app launch. ASM/DBG remain deferred and nonblocking. Full b35 parity,
advanced CLOCK, the sector editor and CONFIG integration remain separate
increments. Foundation v0.3.0, its F image and published downloads are
unchanged. Private raw captures remain in the parent project's
`output/qualification/2512-services-g4-*` directories.
'''
(REPO / 'docs/2512_SERVICES_G4_INSTALL_ACCEPTANCE.md').write_text(text)
print(json.dumps(dict(public_receipt_sha256=sha((REPO / 'monitors/validation/2512-services-g4-install.json').read_bytes()),
    accepted=True, F_unchanged=True, published_downloads_changed=False), indent=2))
