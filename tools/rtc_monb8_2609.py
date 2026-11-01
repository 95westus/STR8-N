"""Unchanged BASE1 RTC RAM instrument admitted after2609 MON B installation."""
import argparse
import json
import sys
import types
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import rtc_base1_2609 as old
import rtc_drift_campaign as campaign

PROFILE='BASE1-MONB8-RTC-RAM1-2609'
INSTALL=ROOT/'output/qualification/2609-mon-feature-install-20261030-r1'
REPAIR=ROOT/'output/qualification/2609-maint-reload-g4-install-20261030-r1'
RECEIPT=REPAIR/'final-receipt.json'
sha,read=old.sha,old.read


def adapted(name,source):
    source=source.replace(old.PROFILE,PROFILE)
    if name == 'driver':
        # Preserve admission flags when failure occurs before borrowing RAM.
        cleanup = "            mark(one_shot_collection_active=False,application_RAM_restore_pending=borrowed and not r['application_ram_restored'],application_ram_restored=r['application_ram_restored'],block_snapshot=marker['block_snapshot'] if r['application_ram_restored'] else True)"
        assert source.count(cleanup) == 1, 'Frozen driver cleanup changed'
        source = source.replace(cleanup, "            if borrowed:\n    " + cleanup)
    module=types.ModuleType('_monb8_'+name)
    module.__file__=str(Path(__file__).resolve())
    exec(compile(source,str(Path(__file__).resolve()),'exec'),module.__dict__)
    return module,source


driver,DRIVER_SOURCE=adapted('driver',old.DRIVER_SOURCE)
auditor,AUDIT_SOURCE=adapted('audit',old.AUDIT_SOURCE)


def after_ap02(marker, baseline):
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


def after_mon_a(marker, baseline):
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


def ram_reference():
  marker=read(driver.MARK)
  ref=marker.get('RTC_RAM_reference')
  if ref is None:return INSTALL,None
  path=Path(ref['path']);assert sha(path)==ref['sha256']
  r=read(path);assert r['passed'] and r['board']=='2609'
  assert r['double_native_capture'] and r['exact_read_only_TX'] and r['returned_to_REC'] and r['port_released']
  assert not any(r[k] for k in ('RTC_SET','trim_changed','PF_ACK','flash_written','reset','RAM_upload'))
  for name,h in r['files'].items():assert sha(path.parent/name)==h
  for stem,key in [('owner-ram','RAM_sha256'),('owner-zp','ZP_sha256')]:
      body=(path.parent/(stem+'.bin')).read_bytes()
      assert body==(path.parent/(stem+'-1.bin')).read_bytes()==(path.parent/(stem+'-2.bin')).read_bytes()
      assert driver.digest(body)==r[key]
  return path.parent,r


def inputs():
    marker=read(driver.MARK);receipt=read(RECEIPT)
    assert marker['board']=='2609' and marker['current_firmware_profile']=='BASE1'
    assert marker['state']=='BASE1-MON-B-g8-tools-g5-accepted'
    assert marker['monitor_generation']=='00000008' and marker['MON_B_generation']=='00000008'
    assert marker['current_F_sha256']==driver.F_SHA and marker['final_prompt']=='REC>'
    # Owner removed the stale historical restored-flag gate on 2026-10-31.
    # A pre-borrow prompt failure formerly set that flag false without a restore
    # pending. Keep pending work blocked; live RAM authority and restoration
    # verification below remain mandatory for every successful collection.
    assert not marker['application_RAM_restore_pending'], '2609 RAM restoration pending'
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not marker.get('one_shot_collection_active') and not marker.get('physical_reset_pending')
    assert not marker.get('feature_install_boot_pending') and not marker['firmware_verification_pending']
    assert Path(marker['last_preservation_report']).resolve()==RECEIPT.resolve()
    assert receipt['passed'] and receipt['CPU']=='65C816 emulation'
    assert receipt['additional_erases']==2 and receipt['total_erases_this_feature_upgrade']==7
    assert receipt['F_writes']==receipt['C_erases']==0
    assert receipt['all_previous_C_records_retained'] and receipt['original_owner_RAM_ZP_restored_and_verified']
    assert receipt['installed_features_passed'] and receipt['physical_MON_B_boot_previously_verified']
    assert receipt['original_D_record_preserved_on_host']
    assert sha(REPAIR/'archived-original-D-4096.bin')==receipt['D_archive_sha256']
    boot=read(receipt['physical_boot_report'])
    assert boot['physical_MON_B_boot'] and boot['ROM_startup_owner_RAM_ZP_unchanged']
    assert boot['owner_RAM_restored'] and boot['COM8_released'] and boot['final_context']=='REC> '
    latest=after_ap02(marker,receipt)
    latest=after_mon_a(marker,latest)
    assert marker['current_journal_sequence']==latest['sequence_after']
    assert marker['current_journal_valid_records']==latest['valid_records_after']
    assert marker['current_tracked_erase_counts']==receipt['counts_after']=={'C':78,'D':48,'E':45,'F':31}
    assert marker['default_boot']=='S' and marker['enabled_banks']==0
    banks=[marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]
    assert banks==latest['final_bank_sha256']
    bodies={name:(INSTALL/name).read_bytes() for name in ('owner-ram.bin','owner-zp.bin')}
    for name,size,key in [('owner-ram.bin',0x6500,'RAM_sha256'),('owner-zp.bin',0xe0,'ZP_sha256')]:
        assert len(bodies[name])==size and driver.digest(bodies[name])==receipt[key]
    reference_folder,reference=ram_reference()
    if reference:
        bodies={name:(reference_folder/name).read_bytes() for name in ('owner-ram.bin','owner-zp.bin')}
    proof=read(driver.BUILD/'proof.json');state=read(campaign.STATE)
    for name in ('tools/rtc_base1_collect.py','tools/rtc_base1_audit.py','tools/build_rtc_base1.py',
                 'BUILD/rtc-base1-2512-20261029/proof.json','BUILD/rtc-base1-2512-20261029/2512-RTC-BASE1-RAM.bin',
                 'BUILD/rtc-base1-2512-20261029/sampler.bin'):
        assert sha(ROOT/name)==state['dependencies'][name]
    image=(driver.BUILD/'2512-RTC-BASE1-RAM.bin').read_bytes()
    reader=(driver.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert proof['passed'] and len(image)==1733 and driver.digest(image)==proof['sha256']
    assert len(reader)==3078 and driver.digest(reader)==driver.live.READBACK_SHA256
    assert sha(driver.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin')==driver.F_SHA
    meta=dict(capture=str(INSTALL),restored_by_receipt=str(RECEIPT),receipt_sha256=sha(RECEIPT),
              prefix_authority='Original pre-helper escrow retained, verified by approved installation and physical MON B startup/restoration; tail/ZP freshly double-read per collection.')
    if reference:
        meta.update(capture=str(reference_folder),RAM_reference=str(reference_folder/'reference.json'),RAM_reference_sha256=sha(reference_folder/'reference.json'),prefix_authority=reference['authority'])
    if marker.get('AP02_flash_trial_closed'):
        meta['AP02_preservation_receipt']=marker['last_AP02_flash_preservation_receipt']
        meta['AP02_preservation_receipt_sha256']=sha(meta['AP02_preservation_receipt'])
    if marker.get('MON_A_g8_install_closed'):
        meta['MON_A_preservation_receipt']=marker['last_MON_A_g8_preservation_receipt']
        meta['MON_A_preservation_receipt_sha256']=sha(meta['MON_A_preservation_receipt'])
    return marker,RECEIPT,meta,bodies,proof,image,reader,banks


driver.inputs=inputs


def _prompt(link):
    import time
    end=time.monotonic()+15
    while time.monotonic()<end:
        for token in (b'REC> ',b'B3> '):
            pos=link.pending.find(token)
            if pos>=0:
                pos+=len(token);body=bytes(link.pending[:pos]);del link.pending[:pos]
                return token,body
        link.pending.extend(link.read(max(1,link.serial.in_waiting)))
    raise TimeoutError('2609 requires an idle REC or B3 prompt')


def _enter_rec(link):
    link.send(b'\r');original,_=_prompt(link)
    if original==b'B3> ':
        link.send(b'V\r');face=link.until(b'B3> ',seconds=15)
        assert b'g00000008 / MON B' in face and b'CPU $16' in face
        # Qualified native MON Q returns to REC without reset or saved writes.
        link.send(b'Q\r');link.until(driver.live.REC,seconds=15)
    return original


def _return_mon(link):
    link.send(b'\r');link.until(driver.live.REC,seconds=15)
    link.send(b'B\r');face=link.until(b'B3> ',seconds=15)
    assert b'g00000008' in face and b'CPU $16' in face
    link.send(b'V\r');face=link.until(b'B3> ',seconds=15)
    assert b'g00000008 / MON B' in face and b'CPU $16' in face


def collect(folder):
    folder=Path(folder);side=folder.parent/(folder.name+'-prompt')
    with driver.serial_lease('drift',timeout=30):
        inputs();side.mkdir(parents=True,exist_ok=False)
        original=None;proof=dict(board='2609',passed=False,reset=False,saved_setting_writes=False)
        try:
            with (side/'entry.jsonl').open('x',encoding='utf-8') as log:
                link=driver.transport.RecoveryLink('COM8',log,usb_serial='A10MPQXCA')
                try:original=_enter_rec(link)
                finally:link.close()
            proof['original_prompt']=original.decode('ascii')
            result=driver.collect(folder)
            (folder/'adapted-driver.py').write_text(DRIVER_SOURCE,encoding='utf-8')
            (folder/'adapted-audit.py').write_text(AUDIT_SOURCE,encoding='utf-8')
            return result
        finally:
            # Never enter MON while borrowed RAM still needs restoration.
            if original==b'B3> ' and not read(driver.MARK)['application_RAM_restore_pending']:
                with (side/'return.jsonl').open('x',encoding='utf-8') as log:
                    link=driver.transport.RecoveryLink('COM8',log,usb_serial='A10MPQXCA')
                    try:_return_mon(link);proof['original_prompt_restored']=True
                    finally:link.close()
            elif original==driver.live.REC:
                proof['original_prompt_restored']=not read(driver.MARK)['application_RAM_restore_pending']
            proof['passed']=bool(proof.get('original_prompt_restored'))
            campaign.save(side/'report.json',proof)


def audit_board(item,state):
    point=auditor.audit_board(item,state)
    assert item['board']==point['board']=='2609'
    report=read(item['report']);folder=Path(item['report']).parent
    assert report['initial_qualified_receipt_sha256']==sha(RECEIPT)
    assert report['usb_serial']=='A10MPQXCA' and report['port']=='COM8'
    marker=read(folder/'marker-before.json')
    expected_sequence=1034 if marker.get('MON_A_g8_install_closed') else (1033 if marker.get('AP02_flash_trial_closed') else 1031)
    assert marker['current_journal_sequence']==expected_sequence and marker['MON_B_generation']=='00000008'
    escrow=read(folder/'escrow-authority.json')
    authority=Path(escrow['RAM_reference']).parent if escrow.get('RAM_reference') else INSTALL
    if escrow.get('RAM_reference'):assert sha(authority/'reference.json')==escrow['RAM_reference_sha256']
    assert (folder/'owner-ram-before.bin').read_bytes()==(authority/'owner-ram.bin').read_bytes()
    assert (folder/'owner-zp-before.bin').read_bytes()==(authority/'owner-zp.bin').read_bytes()
    return point


def accept(path):
    with driver.serial_lease('drift',timeout=30):
        inputs();state=read(campaign.STATE);path=Path(path).resolve();r=read(path)
        item=dict(board='2609',report=str(path),sha256=sha(path),offset=r['rtc_minus_reference_interval_s'],
                  trim=r['trim_steps'],RAM_restored=True,capture_profile=PROFILE)
        point=audit_board(item,state);root=Path(state['root']);run=path.parent.parent
        points,events=read(root/'points.json'),read(root/'events.json')
        if not any(p['board']=='2609' and p['time']==point['time'] for p in points):points.append(point)
        new=[]
        for event in point['events']:
            event=dict(event,board='2609')
            if event['up']>=state['baselines']['2609']['time']-120 and not any(e['board']=='2609' and e['down']==event['down'] and e['up']==event['up'] for e in events):
                events.append(event);new.append(event)
        summary=dict(passed=True,started_utc=r['started_utc'],finished_utc=r['finished_utc'],boards=[item],failures=[],
                     clock_set=False,trim_changed=False,explicit_ACK_sent=False,flash_writer=False,ports_released=True)
        campaign.save(run/'summary.json',summary)
        audit=dict(passed=True,issues=[],new_PF_events=new,summary_sha256=sha(run/'summary.json'),
                   exact_read_load_restore_trace=True,all_banks_double_verified_unchanged=True,
                   owner_RAM_ZP_restored=True,original_REC_restored=True,sampler_bytes_unchanged=True)
        campaign.save(run/'campaign-audit.json',audit)
        marker=read(driver.MARK);marker.update(block_snapshot=False,RTC_sampling_owner_stopped=False,
            current_sampling_profile=PROFILE,last_BASE1_RTC_qualification=str(path),last_BASE1_RTC_qualification_sha256=sha(path))
        if marker.get('AP02_flash_trial_closed'):marker['AP02_RTC_admission_pending']=False
        if marker.get('MON_A_g8_install_closed'):marker['MON_A_g8_RTC_admission_pending']=False
        campaign.save(driver.MARK,marker)
        state['board_admission']['2609']={key:marker.get(key) for key in state['board_admission']['2609']}
        state['base1_profiles']['2609']=dict(board='2609',qualified=True,profile=PROFILE,
            F_sha256=driver.F_SHA,qualification_report=str(path),qualification_report_sha256=sha(path),
            qualification_audit=str(run/'campaign-audit.json'),qualification_audit_sha256=sha(run/'campaign-audit.json'))
        state.setdefault('firmware_profile_events',[]).append(dict(board='2609',UTC=point['UTC'],
            reason=('MON A g8 installed with one A erase and D300 reservation; physical CPU RESET qualified; F, RTC sampler, owner RAM authority, clock settings and baselines unchanged' if marker.get('MON_A_g8_install_closed') else 'Current owner RAM reference reconciled by fresh native MON double capture; no firmware, RTC, trim or PF changes' if marker.get('RTC_RAM_reference') else ('AP/02 fixture restored; two new wear reservations admitted; MON/F/RTC instrument unchanged; no reset, clock set or PF acknowledgement' if marker.get('AP02_flash_trial_closed') else 'Physical CPU RESET accepted MON B g8; F/RTC instrument unchanged; no power cycle, time set or PF acknowledgement')),report=str(path)))
        state['dependencies']['tools/rtc_monb8_2609.py']=sha(__file__)
        state.update(last_attempt_utc=campaign.NOW(),last_summary=str(run/'summary.json'))
        campaign.save(root/'points.json',points);campaign.save(root/'events.json',events)
        campaign.save(campaign.STATE,state);campaign.report(state)
        print('PASS new2609 RTC profile accepted; hourly schedule and all prior samples/baselines retained',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);p.add_argument('--accept-report',type=Path)
    a=p.parse_args()
    if a.accept_report:accept(a.accept_report)
    elif a.out:collect(a.out)
    else:inputs();print('Inputs admitted; no port opened')
