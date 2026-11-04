"""Record the completed 2512 RAM pass and its separately approved install scope."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'release/str8nf-v0.2.0'
CASE = ROOT / 'output/qualification/2512-services-g4-RAM-20261030-r2'
PLAN = ROOT / 'output/qualification/2512-services-g4-install-scope-20261030-r1'
sha = lambda body: hashlib.sha256(body).hexdigest()
r = json.loads((CASE / 'report.json').read_text())
p = json.loads((PLAN / 'plan.json').read_text())
assert r['passed'] and r['owner_RAM_restored'] and r['COM4_released']
assert r['all_flash_banks_unchanged'] and r['all_131072_SRAM_bytes_unchanged']
assert sha((CASE / 'report.json').read_bytes()) == p['source_report_sha256']
for name in ('qualify_services_g4_2512_ram.py', 'prepare_2512_services_g4_install.py', 'install_2512_services_g4.py'):
    shutil.copyfile(ROOT / 'tools' / name, CASE / name)
receipt = dict(schema=1, board='2512', CPU='65C02', passed=True,
    phase='G4_RAM_65C02_PASSED_NOT_INSTALLED', monitor_generation='00000008',
    service_generation='00000004', workbench_generation='00000005', program_generation='00000001',
    F_sha256='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1',
    checks=r['checks'], service_RAM_sha256=r['service_RAM_sha256'], tools_RAM_sha256=r['tools_RAM_sha256'],
    source_manifest_sha256=r['source_manifest_sha256'],
    source_report_sha256=sha((CASE / 'report.json').read_bytes()),
    qualification_driver_sha256=sha((CASE / 'qualify_services_g4_2512_ram.py').read_bytes()),
    all_flash_banks_unchanged=True, journal_sequence=1028, valid_journal_records=31,
    default_boot='B', saved_generation='00000008', boot_policy_preserved=True,
    all_131072_SRAM_bytes_unchanged=True, SRAM_sha256=r['SRAM_sha256'],
    PROGRAM_format=r['PROGRAM_format'], PROGRAM_boundary=r['PROGRAM_boundary'],
    owner_RAM_ZP_restored_verified=True, fresh_native_prehelper_double_escrow=True,
    final_context=r['final_context'].strip(), COM4_released=True,
    flash_writes=0, journal_writes=0, SRAM_data_writes=0, WORKSPACE_writes=0,
    RTC_SET=0, trim_writes=0, PF_ACK=0, power_cuts=0, firmware_builds=0, CPU_simulations=0,
    matched_new_flash_reload_qualified=False, actual_old_bundle_refusal_qualified=True,
    positive_PROGRAM_write_run_retested=False, positive_AP02_flash_launch_retested=False,
    host_only_initial_attempt='Shared serial lease busy; no port opened',
    ASM_DBG_execution_qualified=False, finished_utc=r['finished_utc'])
(REPO / 'monitors/validation/2512-services-g4-RAM.json').write_text(json.dumps(receipt, indent=2) + '\n')
approval = dict(owner_answer='Aproved', context='Approval of explained five-erase installation and 16-C-record host archive',
    plan_sha256=sha((PLAN / 'plan.json').read_bytes()), total_sector_erases=5, journal_appends=5,
    F_writes=0, power_cuts=0, original_C_records_archived_on_host=16,
    original_D_records_retained_on_chip=15)
(PLAN / 'owner-approval.json').write_text(json.dumps(approval, indent=2) + '\n')
print(json.dumps(dict(RAM_receipt_sha256=sha((REPO / 'monitors/validation/2512-services-g4-RAM.json').read_bytes()),
    plan_sha256=approval['plan_sha256'], original_C_sha256=p['original_C_sha256'],
    original_D_sha256=p['original_D_sha256'], expected_bank_sha256=p['expected_bank_sha256']), indent=2))
