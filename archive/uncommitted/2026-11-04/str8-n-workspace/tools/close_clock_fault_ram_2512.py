"""Close CLOCK CPU-RAM acceptance using receipts only; no serial access."""
import json
import trial_clock_fault_ram_2512 as trial
t=trial.t;OUT=trial.OUT;Q=trial.Q

def run():
    path=OUT/'report.json';r=json.loads(path.read_text())
    assert r['passed'] and not r.get('error')
    assert set(r['cases'])=={n for n,m,k in trial.CASES}
    assert r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released'] and r['stopped_at_REC']
    assert r['physical_EEPROM_outage_trim_preserved'] and r['B3_F_settings_journal_exact']
    assert all(r[n]==0 for n in ('flash_erases','flash_writes','journal_appends','metadata_appends','RTC_SET',
      'trim_writes','PF_ACK','EEPROM_writes','SPI_writes','WORKSPACE_writes','resets','power_cuts','CPU_simulations'))
    for n,m,k in trial.CASES:
      data=(OUT/(n+'-result.bin')).read_bytes()
      assert json.loads(json.dumps(trial.validate(data,k,m)))==r['cases'][n]
      if k in ('SET','ACK') and m in (0,5,6):
        assert data[116:124]==bytes.fromhex('EA 07 0B 02 E1 0C 22 38')
        assert data[628:636]==data[116:124] # pre-SET UTC and quality retained
    for filename,key in [('owner-ram.bin','RAM_sha256'),('owner-zp.bin','ZP_sha256')]:
      assert t.sha((OUT/filename).read_bytes())==r[key]
    assert (OUT/'before-EEPROM.bin').read_bytes()==(OUT/'after-EEPROM.bin').read_bytes()
    assert (OUT/'before-outage.bin').read_bytes()==(OUT/'after-outage.bin').read_bytes()
    f=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert r['F_sha256']==f['sha256'] and t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
    import rtc_fleet
    marker=rtc_fleet.admission('2512') # host eligibility only, no serial port
    assert not marker['block_snapshot'] and marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert (marker['current_journal_sequence'],marker['current_journal_valid_records'])==(1177,20)
    completion=dict(status='ACCEPTED_2512_CLOCK_SOFTWARE_FAULT_CASES',passed=True,board='2512',
      receipt=str(path),receipt_sha256=t.sha(path.read_bytes()),cases=list(r['cases']),case_count=14,
      boundary=r['boundary'],F_sha256=f['sha256'],flash_erases=0,journal_appends=0,real_RTC_data_writes=0,
      real_EEPROM_writes=0,SPI_data_writes=0,resets=0,power_cuts=0,owner_RAM_restored=True,owner_ZP_restored=True,
      physical_EEPROM_outage_trim_preserved=True,settings_and_history_preserved=True,
      final_prompt='REC>',COM4_released=True,RTC_collection_eligible=True,collector_or_baseline_changes=0,
      software_gates_closed=['latched SET/ACK archive-verify-before-clock-write and cleared-record state',
        'EEPROM data/commit/readback/write-protect refusals before any clock attempt',
        'pending archived event retained when RTC SET/ACK NACKs','changed trim order/restore, active-output guard, NACK and readback handling',
        'foreign EEPROM refusal and no-event ACK distinguished from positive writes'],
      limits=['Injected CPU-RAM device responses; no physical RTC/EEPROM write acceptance or electrical-failure claim',
        '65C02 only; held816 path remains separate','No changed calibration or manufactured real outage; collection remains intact',
        'FLASH DELAY help correction is source-only, not installed or packaged'])
    assert not (OUT/'completion.json').exists();t.save(OUT/'completion.json',completion)
    mp=Q/'device-operations/2512.json';marker=json.loads(mp.read_text())
    marker.update(CLOCK_RAM_fault_cases_qualified=True,last_CLOCK_fault_RAM_completion=str(OUT/'completion.json'),
      current_owner_RAM_sha256=r['RAM_sha256'],current_owner_ZP_sha256=r['ZP_sha256'])
    t.save(mp,marker)
    print('CLOSED2512 CLOCK software:14 cases;real RTC/EEPROM/SPI untouched;F golden;owner restored;RTC eligible;REC>;COM4 free')

if __name__=='__main__':run()
