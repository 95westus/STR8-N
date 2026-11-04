"""Prepare/apply admission-only RTC adapter changes after the AP/02 restoration."""
import argparse
import ast
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t

ROOT=t.ROOT; SCOPE=ROOT/'output/qualification/2609-AP02-scope-20261030-r1'
SOURCE=ROOT/'tools/rtc_monb8_2609.py'
STATE=ROOT/'output/qualification/rtc-drift-3hour-campaign.json'
CASE=ROOT/'output/qualification/2609-AP02-trial-20261030-r1'


def prepare():
    old=SOURCE.read_text()
    helper='''def after_ap02(marker, baseline):
    if not marker.get('AP02_flash_trial_closed'):
        return baseline
    folder=ROOT/'output/qualification/2609-AP02-trial-20261030-r1'
    plan_path=ROOT/'output/qualification/2609-AP02-scope-20261030-r1/plan.json'
    path=folder/'final-receipt.json'
    assert Path(marker['last_AP02_flash_preservation_receipt']).resolve()==path.resolve()
    latest=read(path);plan=read(plan_path)
    assert sha(plan_path)==latest['plan_sha256']=='01b1753b72c20069f85f89db7226b489d8a97dd603115d2a13b42f8700fb50e8'
    assert latest['passed'] and latest['CPU']=='65C816 emulation'
    assert latest['erase_requests']==latest['erases_completed']==2
    assert latest['F_writes']==latest['C_D_erases']==latest['MON_A_B_E_writes']==0
    assert latest['owner_RAM_restored'] and latest['owner_ZP_restored'] and latest['COM8_released']
    assert latest['original_WDC_bank_restored'] and latest['all_expected_final_banks']
    assert latest['APP_run_owner_RAM_ZP_unchanged'] and not latest['flash_restore_pending']
    assert latest['all_17_original_journal_records_retained']
    assert latest['final_context']=='REC> ' and latest['sequence_after']==1033 and latest['valid_records_after']==19
    assert latest['counts_after']==baseline['counts_after']
    assert latest['final_bank_sha256']==plan['expected_final_bank_sha256']
    assert latest['final_bank_sha256'][:3]==baseline['final_bank_sha256'][:3]
    for n in range(4):
        for repeat in (1,2):
            assert sha(folder/f'final-pass{repeat}-B{n}.bin')==latest['final_bank_sha256'][n]
    return dict(baseline,sequence_after=1033,valid_records_after=19,
                final_bank_sha256=latest['final_bank_sha256'])


'''
    token='def inputs():\n'
    assert old.count(token)==1
    new=old.replace(token,helper+token)
    a="    assert marker['current_journal_sequence']==receipt['sequence_after']==1031\n    assert marker['current_journal_valid_records']==receipt['valid_records_after']==17\n"
    b="    latest=after_ap02(marker,receipt)\n    assert marker['current_journal_sequence']==latest['sequence_after']\n    assert marker['current_journal_valid_records']==latest['valid_records_after']\n"
    assert new.count(a)==1;new=new.replace(a,b)
    a="    assert banks==receipt['final_bank_sha256']\n"
    assert new.count(a)==1;new=new.replace(a,"    assert banks==latest['final_bank_sha256']\n")
    a="    return marker,RECEIPT,meta,bodies,proof,image,reader,banks\n"
    b="    if marker.get('AP02_flash_trial_closed'):\n        meta['AP02_preservation_receipt']=marker['last_AP02_flash_preservation_receipt']\n        meta['AP02_preservation_receipt_sha256']=sha(meta['AP02_preservation_receipt'])\n    return marker,RECEIPT,meta,bodies,proof,image,reader,banks\n"
    assert new.count(a)==1;new=new.replace(a,b)
    a="    assert marker['current_journal_sequence']==1031 and marker['MON_B_generation']=='00000008'\n"
    b="    expected_sequence=1033 if marker.get('AP02_flash_trial_closed') else 1031\n    assert marker['current_journal_sequence']==expected_sequence and marker['MON_B_generation']=='00000008'\n"
    assert new.count(a)==1;new=new.replace(a,b)
    a="        campaign.save(driver.MARK,marker)\n"
    b="        if marker.get('AP02_flash_trial_closed'):marker['AP02_RTC_admission_pending']=False\n        campaign.save(driver.MARK,marker)\n"
    assert new.count(a)==1;new=new.replace(a,b)
    a="reason='Physical CPU RESET accepted MON B g8; F/RTC instrument unchanged; no power cycle, time set or PF acknowledgement'"
    b="reason=('AP/02 fixture restored; two new wear reservations admitted; MON/F/RTC instrument unchanged; no reset, clock set or PF acknowledgement' if marker.get('AP02_flash_trial_closed') else 'Physical CPU RESET accepted MON B g8; F/RTC instrument unchanged; no power cycle, time set or PF acknowledgement')"
    assert new.count(a)==1;new=new.replace(a,b)
    ast.parse(new)
    target=SCOPE/'rtc_monb8_2609-after-ap02.py';target.write_text(new)
    (SCOPE/'rtc_monb8_2609-before-ap02.py').write_bytes(SOURCE.read_bytes())
    state=json.loads(STATE.read_text());old_sha=t.sha(SOURCE.read_bytes())
    assert state['dependencies']['tools/rtc_monb8_2609.py']==old_sha
    recipe=dict(old_adapter_sha256=old_sha,new_adapter_sha256=t.sha(target.read_bytes()),
        adapter_changes='Admission only; accept verified D100/D200 wear rows; correct requalification event reason',
        instrument_bytes_unchanged=True,profile_unchanged='BASE1-MONB8-RTC-RAM1-2609',
        sampler_dependencies={n:h for n,h in state['dependencies'].items() if n!='tools/rtc_monb8_2609.py'},
        baselines=state['baselines'],clock_set=False,trim_change=False,PF_ACK=False)
    t.save(SCOPE/'RTC-admission-recipe.json',recipe)
    print(json.dumps(dict(old_adapter_sha256=old_sha,new_adapter_sha256=recipe['new_adapter_sha256'],
        instrument_bytes_unchanged=True,applied=False),indent=2))


def apply():
    recipe=json.loads((SCOPE/'RTC-admission-recipe.json').read_text())
    trial=json.loads((CASE/'final-receipt.json').read_text())
    assert trial['passed'] and trial['original_WDC_bank_restored'] and trial['owner_RAM_restored']
    assert trial['erase_requests']==trial['erases_completed']==2 and trial['sequence_after']==1033
    with t.serial_lease('2609-AP02-RTC-source-admission-update',timeout=180):
        marker=json.loads((ROOT/'output/qualification/device-operations/2609.json').read_text())
        assert marker['block_snapshot'] and marker['AP02_RTC_admission_pending']
        assert marker['AP02_flash_trial_closed'] and not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        assert t.sha(SOURCE.read_bytes())==recipe['old_adapter_sha256']
        body=(SCOPE/'rtc_monb8_2609-after-ap02.py').read_bytes()
        assert t.sha(body)==recipe['new_adapter_sha256']
        state=json.loads(STATE.read_text())
        assert state['dependencies']['tools/rtc_monb8_2609.py']==recipe['old_adapter_sha256']
        assert state['baselines']==recipe['baselines']
        for n,h in recipe['sampler_dependencies'].items():assert state['dependencies'][n]==h
        t.save(CASE/'RTC-campaign-before-admission.json',state)
        schedule=ROOT/'output/qualification/rtc-hourly-schedule.json'
        if schedule.exists():(CASE/'RTC-hourly-schedule-before-admission.json').write_bytes(schedule.read_bytes())
        SOURCE.write_bytes(body)
        state['dependencies']['tools/rtc_monb8_2609.py']=recipe['new_adapter_sha256']
        t.save(STATE,state)
        t.save(CASE/'RTC-admission-source-applied.json',dict(recipe,applied_utc=t.utc()))
    print('Applied admission-only adapter; block remains until live read-only RTC requalification passes',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    if parser.parse_args().apply:apply()
    else:prepare()
