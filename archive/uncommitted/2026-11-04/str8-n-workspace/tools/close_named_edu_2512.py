"""Close approved named-transfer/EDU scope from immutable receipts; no ports."""
import json
from pathlib import Path
import install_named_edu_2512 as ins
import rtc_drift_campaign as c

t=ins.t;Q=ins.Q;SCOPE=ins.SCOPE
OUT=Q/'2512-named-EDU-closeout-20261101-r1'

def run():
    p=ins.approved();OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    receipts={
        'installation':ins.OUT/'report.json',
        'copies':Q/'2512-named-transfer-positive-20261101-r1/report.json',
        'OFF_save':Q/'2512-EDU-OFF-saved-20261101-r1/report.json',
        'OFF_after_reported_reset':Q/'2512-EDU-OFF-saved-20261101-r1/reset-reported-check/report.json',
        'ON_save':Q/'2512-EDU-ON-saved-20261101-r1/report.json',
        'ON_captured_reset':Q/'2512-EDU-ON-saved-20261101-r1/reset-check/report.json',
        'postreset_PROGRAM_after_PREP':Q/'2512-named-EDU-postreset-PREP-continuation-20261101-r1/report.json'}
    rr={k:json.loads(v.read_text()) for k,v in receipts.items()}
    assert all(r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released'] for r in rr.values())
    assert rr['installation']['erase_requests']==9 and rr['copies']['fixture_erases_requested']==2
    assert rr['OFF_save']['ED_appends']==rr['ON_save']['ED_appends']==1
    assert rr['OFF_after_reported_reset']['owner_reported_physical_reset'] and not rr['OFF_after_reported_reset']['startup_banner_captured']
    for r in rr.values():assert r.get('F_writes',0)==r.get('RTC_SET',0)==r.get('trim_writes',0)==r.get('PF_ACK',0)==r.get('power_cuts',0)==0
    ram_hashes={r['RAM_sha256'] for r in rr.values()};zp_hashes={r['ZP_sha256'] for r in rr.values()};assert len(ram_hashes)==len(zp_hashes)==1
    final=(receipts['ON_captured_reset'].parent/'B3-after.bin').read_bytes();assert final==(SCOPE/'B3-target.bin').read_bytes()
    j=t.classify_journal(final);assert j['sequence']==p['sequence_after'] and j['counts']==p['counts_after'] and j['valid_records']==p['records_after']
    before=(SCOPE/'B3-original.bin').read_bytes();assert before[0x4000:0x4800]==final[0x4000:0x4800]
    assert (SCOPE/'boot-wear-history-original.bin').read_bytes()==before[0x4000:0x6000]
    assert final[-4096:]==before[-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    ledpath=Q/'2512-named-EDU-RTC-readmission-20261101-r1/report.json';led=json.loads(ledpath.read_text())
    assert led['LED_qualified'] and led['scheduled_LED_continuity']['passed'] and not led['native_TIME_qualified']
    with t.serial_lease('2512-named-EDU-host-closeout',timeout=30):
        mp=Q/'device-operations/2512.json';m=json.loads(mp.read_text())
        assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending']
        assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
        assert m['current_physical_bank_sha256']['B3']==t.sha(final) and m['saved_EDU']=='ON'
        assert all(m['current_physical_bank_sha256'][f'B{b}']==h for b,h in [(0,p['after_bank_sha256']['B0']),(1,p['after_bank_sha256']['B1'])])
        assert m['current_owner_RAM_sha256'] in ram_hashes and m['current_owner_ZP_sha256'] in zp_hashes
        t.save(OUT/'marker-before.json',m)
        m.update(block_snapshot=False,named_edu_qualification_pending=False,named_edu_RTC_admission_pending=False,
            named_edu_native_TIME_pending=True,named_edu_native_TIME_issue='Intermittent native TIME RTC decode04; strict qualification remains failed. Primary LED route is qualified.',
            status_admission_hold_reason=None,named_flash_PROGRAM_transfers_verified=True,persistent_EDU_verified=True,
            cold_start_SRAM_PREP_required=True,last_named_EDU_closeout=str(OUT/'report.json'),final_prompt='REC>')
        t.save(mp,m)
        state=c.read(c.STATE);c.save(OUT/'RTC-state-before.json',state)
        assert state['board_admission']['2512']['monitor_generation']=='0000000E'
        old=c.read(Q/'2512-named-EDU-RTC-readmission-20261101-r1/campaign-before.json')
        assert state['baselines']==old['baselines'] and state['segment_boundaries']==old['segment_boundaries']
        state.setdefault('CPU_reset_events',[]).extend([
            dict(board='2512',recorded_UTC=c.NOW(),reason='Owner-reported CPU reset for saved EDU OFF; state verified afterward, startup banner not captured',report=str(receipts['OFF_after_reported_reset']),power_cycle=False),
            dict(board='2512',recorded_UTC=c.NOW(),reason='Captured CPU reset: saved default MON B gE, EDU ON',report=str(receipts['ON_captured_reset']),power_cycle=False)])
        state.setdefault('firmware_profile_events',[]).append(dict(board='2512',UTC=c.NOW(),reason='Approved12-erase named-transfer/EDU increment closed; exact images, settings, retained history/wear and owner RAM verified. Unchanged LED sampler admitted; native TIME04 remains open.',report=str(OUT/'report.json')))
        c.save(c.STATE,state)
    report=dict(passed=True,board='2512',MON_generation='0000000E',saved_EDU='ON',total_erases=12,image_erases=9,fixture_cleanup_erases=2,journal_D_erases=1,
        ED_metadata_appends=2,F_writes=0,RTC_setting_writes=0,power_cuts=0,resets=2,OFF_reset_evidence='owner report plus post-reset state; banner not captured',
        counts_C_D_E_F=j['counts'][28:],sequence=j['sequence'],journal_valid_records=j['valid_records'],old_C_rows_retained_exact=8,old_D_rows_archived_before_replacement=16,
        named_transfers_both_directions_verified=True,temporary_SPI_bytes_restored=320,B0_restored=True,owner_RAM_restored=True,owner_ZP_restored=True,
        RAM_sha256=next(iter(ram_hashes)),ZP_sha256=next(iter(zp_hashes)),final_prompt='REC>',COM4_released=True,RTC_LED_qualified=True,RTC_scheduled_gE_capture_passed=True,
        native_TIME_qualification=False,RTC_baselines_unchanged=True,other_boards_accessed=False,published_downloads_changed=False,
        remaining=['Intermittent native TIME RTC error04','Cold-start PROGRAM requires guarded PREP; automatic startup remains open'],
        receipts={k:dict(path=str(v),sha256=t.sha(v.read_bytes())) for k,v in receipts.items()})
    t.save(OUT/'report.json',report);print(json.dumps(report,indent=2))

if __name__=='__main__':run()
