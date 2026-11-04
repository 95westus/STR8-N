"""Consolidate installed gF TIME/PREP evidence; no board ports or writes."""
import json
from pathlib import Path
import install_time_prep_2512 as ins
import rtc_drift_campaign as c
t=ins.t;Q=ins.Q;SCOPE=ins.SCOPE;OUT=Q/'2512-TIME-PREP-closeout-20261101-r1'

def run():
    p=ins.approved();paths=dict(writes=ins.OUT/'report.json',installation=ins.OUT/'installation-acceptance.json',
        routes=Q/'2512-TIME-PREP-installed-routes-20261101-r1/report.json',cold=Q/'2512-TIME-PREP-cold-installed-20261101-r1/report.json',
        RTC=Q/'2512-TIME-PREP-RTC-readmission-20261101-r1/report.json',RAM=Q/'2512-TIME-PREP-RAM-20261101-r2/report.json',
        cold_RAM=Q/'2512-TIME-PREP-cold-RAM-20261101-r2/report.json')
    r={k:json.loads(v.read_text()) for k,v in paths.items()};assert all(v['passed'] for k,v in r.items() if k!='writes')
    assert r['writes']['NVM_verified'] and r['writes']['erase_requests']==3 and len(r['writes']['completed'])==3
    assert r['installation']['original_write_sha256']==t.sha(paths['writes'].read_bytes()) and r['installation']['routes_sha256']==t.sha(paths['routes'].read_bytes())
    assert r['cold']['automatic_cold_capacity'] and r['cold']['cold_PROGRAM_TABLE'] and r['cold']['resets']==1
    assert r['RTC']['trim_steps']==-12 and r['RTC']['control']==0x80 and r['RTC']['baselines_unchanged']
    hashes={r[k]['RAM_sha256'] for k in ('writes','routes','cold','RAM','cold_RAM')};zps={r[k]['ZP_sha256'] for k in ('writes','routes','cold','RAM','cold_RAM')};assert len(hashes)==len(zps)==1
    final={b:(paths['cold'].parent/f'B{b}-after.bin').read_bytes() for b in (2,3)}
    for b in (2,3):assert final[b]==(SCOPE/f'B{b}-target.bin').read_bytes()
    old3=(SCOPE/'B3-original.bin').read_bytes();new3=final[3]
    from native_journal_room import valid_snapshot
    rows=[i for i in range(0x4000,0x6000,256) if valid_snapshot(old3[i:i+256])];assert len(rows)==21
    assert all(old3[i:i+256]==new3[i:i+256] for i in rows)
    assert old3[:0x2000]==new3[:0x2000] and old3[0x6000:]==new3[0x6000:]
    freeze=json.loads((t.REPO/'F_FREEZE.json').read_text());assert t.sha(new3[-4096:])==freeze['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in freeze['sources'].items())
    j=t.classify_journal(new3);assert j['sequence']==1150 and j['valid_records']==25 and j['counts']==p['counts_after']
    m=c.read(Q/'device-operations/2512.json');assert m['monitor_generation']=='0000000F' and m['saved_EDU']=='ON'
    assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending'] and not m['block_snapshot']
    assert not any(v for k,v in m.items() if k.endswith('_worker_active')) and not m['time_prep_qualification_pending'] and not m['cold_start_SRAM_PREP_required'] and not m['named_edu_native_TIME_pending']
    for b in (0,1):assert m['current_physical_bank_sha256'][f'B{b}']==p['whole_marker_bank_sha256'][f'B{b}']
    state=c.read(c.STATE);assert state['board_admission']['2512']['monitor_generation']=='0000000F' and state['base1_profile']['qualified'] and state['base1_profile']['profile']=='MON-UI1-GF-TIME-TRIM'
    import rtc_led_mode_gf as mode
    assert mode.enabled(state) and mode.ready(state)
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    report=dict(passed=True,board='2512',MON='A/B g0000000F',Foundation='0.3.0 g1 BASE1/PR05 frozen',total_erases=3,C_D_erases=0,F_writes=0,
        wear_appends=3,default_B_binding_appends=1,metadata_appends=0,RTC_setting_writes=0,SRAM_data_writes=0,power_cuts=0,installed_CPU_resets=1,
        old_records_retained_on_chip=21,sequence=1150,valid_records=25,counts_C_D_E_F=j['counts'][28:],B2_F_count=j['counts'][23],A_B_counts=j['counts'][26:28],
        default='B',saved_EDU='ON',automatic_cold_SRAM_capacity=True,cold_PROGRAM_TABLE=True,native_TIME_NIST_qualified=True,unchanged_LED_agent_qualified=True,
        owner_RAM_ZP_restored=True,RAM_sha256=next(iter(hashes)),ZP_sha256=next(iter(zps)),B0_B1_preserved=True,clock_trim_PF_history_baselines_preserved=True,
        final_prompt='REC>',COM4_released=True,other_boards_accessed=False,published_downloads_changed=False,
        remaining_for_this_request=[],evidence_limits=['Original intermittent hardware04 raw bytes were not captured; invalid-frame retry/refusal was CPU-fault-tested, followed by live RAM and installed TIME/NIST acceptance.',
        'Earlier RAM cold reset used owner report/post-reset pending flags; final installed default-B/gF startup was captured in full.'],
        receipts={k:dict(path=str(v),sha256=t.sha(v.read_bytes())) for k,v in paths.items()})
    t.save(OUT/'report.json',report)
    m.update(last_TIME_PREP_closeout=str(OUT/'report.json'),TIME_invalid_snapshot_retry_verified=True,automatic_SRAM_PREP_verified=True);c.save(Q/'device-operations/2512.json',m)
    print(json.dumps(report,indent=2))

if __name__=='__main__':run()
