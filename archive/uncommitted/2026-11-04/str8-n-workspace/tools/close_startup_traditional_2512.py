"""Reconcile approved g10 presentation receipts; no board access or writes."""
import json
from pathlib import Path
import install_startup_traditional_2512 as ins

t=ins.t;Q=ins.Q;SCOPE=ins.SCOPE

def run():
    p=ins.approved()
    locations=dict(installation=ins.OUT/'report.json',
        physical_boot=Q/'2512-startup-traditional-reset-20261101-r2/report.json',
        RTC_readmission=Q/'2512-startup-traditional-RTC-readmission-20261101-r1/report.json')
    reports={name:json.loads(path.read_text()) for name,path in locations.items()}
    assert all(r['passed'] for r in reports.values())
    install,reset,rtc=(reports[n] for n in ('installation','physical_boot','RTC_readmission'))
    assert install['erase_requests']==3 and install['NVM_verified'] and install['functional_checks_passed']
    assert install['owner_RAM_restored'] and install['owner_ZP_restored'] and install['COM4_released']
    assert reset['resets']==1 and reset['new_resets']==0 and reset['selected_startup_and_cold_capacity']
    assert reset['VERSION_and_TIME'] and reset['owner_RAM_readback_verified'] and reset['owner_ZP_readback_verified']
    assert rtc['baselines_unchanged'] and rtc['owner_RAM_LEDs_restored'] and len(rtc['qualified'])==2
    original=(SCOPE/'B3-original.bin').read_bytes();after=(ins.OUT/'B3-after.bin').read_bytes()
    assert after==(SCOPE/'B3-target.bin').read_bytes()
    j=t.classify_journal(after);assert j['sequence']==1168 and j['valid_records']==27 and j['default']=='B'
    from nf_migrate import valid_snapshot
    old_rows=[]
    for i in range(0x4000,0x6000,256):
        if valid_snapshot(original[i:i+256]):
            assert original[i:i+256]==after[i:i+256];old_rows.append(i+0x8000)
    assert len(old_rows)==23
    assert original[:0x2000]==after[:0x2000] and original[0x6000:]==after[0x6000:]
    assert j['counts']==p['counts_after'] and j['counts'][28:]==[57,37,37,24]
    for target in p['targets']:
        actual=(ins.OUT/f'B{target["bank"]}-{target["page"]:02X}-after.bin').read_bytes()
        assert t.sha(actual)==target['sha256'] and actual==(SCOPE/target['file']).read_bytes()
    b2old=(ins.OUT/'B2-A0-before.bin').read_bytes();b2new=(ins.OUT/'B2-A0-after.bin').read_bytes()
    assert b2old[:0xC00]==b2new[:0xC00]
    assert t.sha(after[-4096:])==p['F_sha256']
    frozen=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in frozen['sources'].items())
    for name,digest in p['RTC']['files'].items():
        path=t.ROOT/'tools'/('rtc_drift_campaign.py' if name=='rtc_drift_campaign.candidate.py' else name)
        assert t.sha(path.read_bytes())==digest
    assert all(t.sha((t.ROOT/'tools'/n).read_bytes())==h for n,h in p['RTC']['original_readers_sha256'].items())
    marker=json.loads((Q/'device-operations/2512.json').read_text())
    assert marker['monitor_generation']==marker['default_monitor_generation']=='00000010'
    assert marker['current_journal_sequence']==1168 and marker['current_journal_valid_records']==27
    assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
    assert not any(marker.get(k) for k in ('block_snapshot','physical_reset_pending','startup_install_pending','startup_qualification_pending','one_shot_collection_active'))
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    receipt=dict(status='ACCEPTED_2512_TRADITIONAL_G10_STARTUP_VERSION_AND_RTC',passed=True,board='2512',
        monitor_generation='00000010',default='B',status_core=5,image_erases=3,journal_sector_erases=0,
        wear_appends=3,binding_appends=1,physical_resets=1,extra_resets=0,F_writes=0,RTC_settings_writes=0,
        SRAM_data_writes=0,power_cuts=0,old_rows_retained_on_chip=23,final_valid_rows=27,final_sequence=1168,
        counts_CD_E_F=[57,37,37,24],F_sha256=p['F_sha256'],owner_RAM_restored=True,owner_ZP_restored=True,
        native_TIME_NIST_passed=True,unchanged_LED_agent_passed=True,baseline_and_history_preserved=True,
        final_prompt='REC>',COM4_released=True,receipts={n:dict(path=str(path),sha256=t.sha(path.read_bytes())) for n,path in locations.items()},
        limits=['physical reset owner-reported and captured; continuation issued no second reset',
            'old banner assertion corrected in host; inventory verified by post-reset VERSION',
            '65C02 trial only; held2609 and references2205/2604 untouched',
            'BOOT/CLOCK positive setting tests, extracted kit and publication excluded'],
        allowance='Three erases/four appends/one reset fully spent; new writes require a new scope')
    destination=SCOPE/'completion.json'
    assert not destination.exists();t.save(destination,receipt)
    print('CLOSED2512 g10:3 erases;23 old rows retained;B default;physical boot;RTC admitted;F golden;REC>;COM4 free',flush=True)

if __name__=='__main__':run()
