"""Admission-only update after verified MON A installation; sampler unchanged."""
import argparse
import ast
import json
import install_2609_mon_a_g8 as install

t = install.t
SOURCE = t.ROOT / 'tools/rtc_monb8_2609.py'
STATE = t.ROOT / 'output/qualification/rtc-drift-3hour-campaign.json'
SCOPE = install.SCOPE
CASE = install.CASE


def prepare():
    old = SOURCE.read_text()
    helper = '''def after_mon_a(marker, baseline):
    if not marker.get('MON_A_g8_install_closed'):
        return baseline
    folder=ROOT/'output/qualification/2609-MON-A-g8-install-20261030-r1'
    scope=ROOT/'output/qualification/2609-MON-A-g8-scope-20261030-r1/install-and-keep'
    path=folder/'final-receipt.json'
    assert Path(marker['last_MON_A_g8_preservation_receipt']).resolve()==path.resolve()
    latest=read(path);plan=read(scope/'plan.json')
    assert sha(scope/'plan.json')==latest['plan_sha256']=='f75cb157c40deea697e0e7d42b2e712251a2e9e3e8d27a9a779a348d8f8d6363'
    assert latest['passed'] and latest['CPU']=='65C816 emulation'
    assert latest['erase_requests']==latest['erases_completed']==1
    assert latest['F_writes']==latest['C_D_erases']==latest['B_E_or_tool_writes']==0
    assert latest['boot_setting_writes']==latest['SRAM_data_writes']==latest['WORKSPACE_writes']==0
    assert latest['RTC_SET']==latest['trim_writes']==latest['PF_ACK']==latest['power_cuts']==0
    assert latest['owner_RAM_restored'] and latest['owner_ZP_restored'] and latest['COM8_released']
    assert latest['all_banks_expected'] and latest['all_19_old_records_retained']
    assert latest['physical_MON_A_boot'] and latest['original_owner_RAM_ZP_restored_and_verified']
    assert latest['final_context']=='REC> ' and latest['sequence_after']==1034 and latest['valid_records_after']==20
    boot=read(latest['physical_boot_report'])
    assert boot['passed'] and boot['physical_MON_A_boot'] and boot['ROM_startup_owner_RAM_ZP_unchanged']
    assert boot['all_banks_expected'] and boot['owner_RAM_restored'] and boot['owner_ZP_restored'] and boot['COM8_released']
    assert boot['flash_writes']==boot['journal_writes']==boot['boot_setting_writes']==boot['power_cuts']==0
    assert latest['counts_after']==baseline['counts_after']
    assert latest['final_bank_sha256']==plan['final_bank_sha256']
    assert latest['final_bank_sha256'][:3]==baseline['final_bank_sha256'][:3]
    assert sha(folder/'archived-original-A-PR04-4096.bin')==plan['old_MON_A']['sha256']
    for n in range(4):
        for repeat in (1,2):
            assert sha(folder/f'final-pass{repeat}-B{n}.bin')==latest['final_bank_sha256'][n]
            assert sha(folder/'physical-boot'/f'final-pass{repeat}-B{n}.bin')==latest['final_bank_sha256'][n]
    assert marker['MON_A_generation']=='00000008' and not marker['MON_A_g8_boot_pending']
    return dict(baseline,sequence_after=1034,valid_records_after=20,
                final_bank_sha256=latest['final_bank_sha256'])


'''
    assert old.count('def ram_reference():\n') == 1
    new = old.replace('def ram_reference():\n', helper + 'def ram_reference():\n')
    a = "    latest=after_ap02(marker,receipt)\n"
    assert new.count(a) == 1
    new = new.replace(a, a + '    latest=after_mon_a(marker,latest)\n')
    a = "    expected_sequence=1033 if marker.get('AP02_flash_trial_closed') else 1031\n"
    assert new.count(a) == 1
    new = new.replace(a, "    expected_sequence=1034 if marker.get('MON_A_g8_install_closed') else (1033 if marker.get('AP02_flash_trial_closed') else 1031)\n")
    a = "    return marker,RECEIPT,meta,bodies,proof,image,reader,banks\n"
    assert new.count(a) == 1
    new = new.replace(a, "    if marker.get('MON_A_g8_install_closed'):\n        meta['MON_A_preservation_receipt']=marker['last_MON_A_g8_preservation_receipt']\n        meta['MON_A_preservation_receipt_sha256']=sha(meta['MON_A_preservation_receipt'])\n" + a)
    a = "        campaign.save(driver.MARK,marker)\n"
    assert new.count(a) == 1
    new = new.replace(a, "        if marker.get('MON_A_g8_install_closed'):marker['MON_A_g8_RTC_admission_pending']=False\n" + a)
    # Preserve old event reasons while naming this exact new firmware event.
    a = "            reason=('Current owner RAM reference reconciled"
    assert new.count(a) == 1
    new = new.replace(a, "            reason=('MON A g8 installed with one A erase and D300 reservation; physical CPU RESET qualified; F, RTC sampler, owner RAM authority, clock settings and baselines unchanged' if marker.get('MON_A_g8_install_closed') else 'Current owner RAM reference reconciled")
    ast.parse(new)
    state = json.loads(STATE.read_text())
    assert state['dependencies']['tools/rtc_monb8_2609.py'] == t.sha(SOURCE.read_bytes())
    (SCOPE/'rtc_monb8_2609-before-mon-a.py').write_bytes(SOURCE.read_bytes())
    target = SCOPE/'rtc_monb8_2609-after-mon-a.py'; target.write_text(new)
    recipe = dict(old_adapter_sha256=t.sha(SOURCE.read_bytes()), new_adapter_sha256=t.sha(target.read_bytes()),
        instrument_bytes_unchanged=True, profile_unchanged='BASE1-MONB8-RTC-RAM1-2609',
        baselines=state['baselines'], sampler_dependencies={k:v for k,v in state['dependencies'].items() if k!='tools/rtc_monb8_2609.py'},
        clock_set=False, trim_change=False, PF_ACK=False)
    t.save(SCOPE/'MON-A-RTC-admission-recipe.json', recipe)
    print('Prepared admission-only source; no sampler/board/schedule change', flush=True)


def apply():
    recipe = json.loads((SCOPE/'MON-A-RTC-admission-recipe.json').read_text())
    final = json.loads((CASE/'final-receipt.json').read_text())
    assert final['passed'] and final['physical_MON_A_boot'] and final['erases_completed']==1
    with t.serial_lease('2609-MON-A-RTC-admission-update', timeout=30):
        marker = json.loads(install.MARK.read_text())
        assert marker['block_snapshot'] and marker['MON_A_g8_RTC_admission_pending']
        assert not marker['MON_A_g8_boot_pending'] and not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        assert t.sha(SOURCE.read_bytes())==recipe['old_adapter_sha256']
        body=(SCOPE/'rtc_monb8_2609-after-mon-a.py').read_bytes()
        assert t.sha(body)==recipe['new_adapter_sha256']
        state=json.loads(STATE.read_text())
        assert state['dependencies']['tools/rtc_monb8_2609.py']==recipe['old_adapter_sha256']
        assert state['baselines']==recipe['baselines']
        for name,digest in recipe['sampler_dependencies'].items(): assert state['dependencies'][name]==digest
        t.save(CASE/'RTC-campaign-before-admission.json',state)
        SOURCE.write_bytes(body)
        state['dependencies']['tools/rtc_monb8_2609.py']=recipe['new_adapter_sha256']
        t.save(STATE,state)
        install.mark(MON_A_g8_install_closed=True)
        t.save(CASE/'RTC-admission-source-applied.json',dict(recipe,applied_utc=t.utc()))
    print('Applied exact postimage admission; collection remains blocked until read-only requalification',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    (apply if parser.parse_args().apply else prepare)()
