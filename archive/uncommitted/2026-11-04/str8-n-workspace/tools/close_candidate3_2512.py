"""Seal candidate3 live/physical-key evidence; receipts only, no serial access."""
import json
from pathlib import Path
import install_named_edu_2512 as ins
t=ins.t;Q=ins.Q
OUT=Q/'2512-candidate3-physical-keys-20261102-r3'
BASE=t.ROOT/'BUILD/unified-g10-candidate3-20261101-r3'

def run():
    path=OUT/'report.json';r=json.loads(path.read_text())
    package=json.loads((BASE/'EXTRACTION-PREPARATION-RECEIPT.json').read_text())
    kit=Path(r['kit']);manifest=json.loads((kit/'CANDIDATE-MANIFEST.json').read_text())
    assert r['passed'] and not r.get('error') and r['GUI_sequence_passed']
    assert r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['stopped_at_REC'] and r['port_released']
    assert r['live_19_extracted_components_exact'] and r['B3_images_F_settings_history_exact']
    assert r['SEND_S19_initial_cancel'] and r['SEND_BIN_initial_cancel'] and r['S19_independent_RAM_verified']
    assert r['BIN_DEMO_execution_and_return'] and r['DEMO_public_software_boot_return']==1
    assert all(r[k]==0 for k in ('F_writes','flash_erases','journal_appends','setting_writes','RTC_SET','trim_writes',
      'PF_ACK','SPI_writes','resets','power_cuts','firmware_builds','CPU_simulations'))
    actions=r['operator_actions'];assert [a['action'] for a in actions]==['F10','Shift+F2','F12','Shift+F3','F12','F2','F4','F10']
    assert actions[0]['source']==actions[-1]['source']=='button'
    assert all(a['source']=='physical-key' for a in actions[1:-1])
    for key in ('Shift+F2','Shift+F3'):
      assert any(k['key']==key and k['state']&1 for k in r['native_keys'])
    events=[json.loads(x) for x in (OUT/'GUI-events.jsonl').read_text().splitlines()]
    tx=b''.join(bytes.fromhex(e['data'][0]) for e in events if e['kind']=='tx')
    rx=b''.join(bytes.fromhex(e['data'][0]) for e in events if e['kind']=='rx')
    expected=b'\rS19\r\x03S19\r'+(kit/'examples/KEY-S19-3500.s19').read_bytes()+b'D 3500 3503\rQ\rL\r\x03L\r'+(kit/'foundation/firmware/payload/STR8N-F-DEMO-RAM.bin').read_bytes()+b'KS'
    assert tx==expected and len(tx)==610,'Unexpected GUI serial command/payload'
    assert b'3500: 4B 45 59 53' in rx and b'1234 + 0001 = 1235' in rx and b'Received key byte, hex: 4B' in rx
    assert r['S19_transfer']['board_accepted'] and r['S19_transfer']['host_complete'] and not r['S19_transfer']['cancelled']
    assert t.sha((kit/'examples/KEY-S19-3500.s19').read_bytes())==r['S19_transfer']['sha256']
    for filename,key in [('owner-ram.bin','RAM_sha256'),('owner-zp.bin','ZP_sha256')]:
      assert t.sha((OUT/filename).read_bytes())==r[key]
    assert t.sha(Path(package['archive']).read_bytes())==package['sha256']
    for name,info in manifest['files'].items():
      body=(kit/name).read_bytes();assert len(body)==info['bytes'] and t.sha(body)==info['sha256'],name
    frozen=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha((kit/'F.bin').read_bytes())==manifest['F_sha256']==frozen['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in frozen['sources'].items())
    import rtc_fleet
    marker=rtc_fleet.admission('2512') # host eligibility only; never opens a port
    assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert marker['current_physical_bank_sha256']['B3']==r['B3_before_sha256']
    assert (marker['current_journal_sequence'],marker['current_journal_valid_records'])==(1177,20)
    c=dict(status='ACCEPTED_2512_CANDIDATE3_LIVE_AND_PHYSICAL_SHIFT_KEYS',passed=True,board='2512',CPU='65C02',
      completed_local='2026-11-02 America/Chicago',receipt=str(path),receipt_sha256=t.sha(path.read_bytes()),
      archive=package['archive'],archive_sha256=package['sha256'],archive_changed=False,published_changes=False,
      terminal_version='0.1.2',MON_generation='00000010',startup='Traditional',F_sha256=frozen['sha256'],
      live_components_verified=19,physical_keys=['Shift+F2','Shift+F3','F12 (twice)','F2','F4'],
      connect_disconnect='Production buttons; no current-version physical F10 claim',
      native_file_dialogs=True,generated_test_key_events=0,S19_cancel=True,SEND_BIN_cancel=True,
      S19_board_accepted=True,S19_independent_harness_RAM_readback=True,
      console_S19_readback_claim=False,BIN_execution_input_and_recovery_return=True,
      exact_GUI_TX_bytes=610,exact_GUI_TX_sha256=t.sha(tx),
      flash_erases=0,journal_appends=0,F_writes=0,settings_writes=0,RTC_data_writes=0,SPI_data_writes=0,
      physical_resets=0,power_cuts=0,DEMO_public_software_boot_return=1,
      owner_RAM_restored=True,owner_ZP_restored=True,owner_RAM_sha256=r['RAM_sha256'],owner_ZP_sha256=r['ZP_sha256'],
      B3_images_F_settings_history_exact=True,sequence=1177,valid_journal_rows=20,counts_CD_E_F=[57,38,37,24],
      final_prompt='REC>',COM4_released=True,RTC_collection_eligible=True,collector_baseline_changes=0,
      limits=['Current19-component profile and terminal accepted on2512/Windows/FT245 only',
        'No installation or migration from this ZIP; identical live images needed no replacement',
        'No latest816 profile, factory flash, source-only rebuild, publication or all-board rollout claim',
        'First2 harness attempts stopped before F10; both verified exact restoration; their failures remain retained'])
    dest=OUT/'completion.json';assert not dest.exists();t.save(dest,c)
    mp=Q/'device-operations/2512.json';m=json.loads(mp.read_text())
    m.update(candidate3_live_extraction_qualified=True,console_012_physical_Shift_keys_qualified=True,
      last_candidate3_closeout=str(dest),current_owner_RAM_sha256=r['RAM_sha256'],current_owner_ZP_sha256=r['ZP_sha256'])
    t.save(mp,m)
    print('CLOSED Candidate3:19 live components;physical Shift keys;S19/BIN cancellation/load;exact owner restore;F golden;REC>;COM4 free')

if __name__=='__main__':run()
