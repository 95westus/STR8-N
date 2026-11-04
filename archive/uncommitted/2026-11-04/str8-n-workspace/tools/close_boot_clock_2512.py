"""Close the approved BOOT/CLOCK metadata scope from receipts only; no ports."""
import json,sys
from pathlib import Path
import trial_boot_clock_2512 as trial

t=trial.t;Q=trial.Q;SCOPE=trial.SCOPE;OUT=trial.OUT

def run():
    p=trial.approved();path=OUT/'report.json';r=json.loads(path.read_text())
    assert r['passed'] and r['NVM_verified'] and r['preservation_NVM_verified']
    assert r['erase_requests']==3 and len(r['policy_committed'])==6 and len(r['metadata_committed'])==3
    assert r['direct_erase_requests']==[[0,0x90],[3,0x90]] and r['native_D_erase_requested']
    assert r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['EEPROM_preserved'] and r['COM4_released']
    assert not r.get('error') and not r.get('cleanup_error') and not r['fixture_dirty'] and not r['metadata_dirty']
    assert all(r[n]==0 for n in ('F_writes','MON_writes','RTC_SET','trim_writes','PF_ACK','EEPROM_writes','SPI_data_writes','resets','power_cuts','automatic_mutation_retries'))
    before=(OUT/'B3-before.bin').read_bytes();after=(OUT/'B3-after.bin').read_bytes()
    assert before==(SCOPE/'B3-original.bin').read_bytes() and after==(SCOPE/'B3-expected-final.bin').read_bytes()
    assert before[:0x4000]==after[:0x4000] and before[0x6000:]==after[0x6000:]
    j=t.classify_journal(after);assert (j['sequence'],j['valid_records'],j['default'])==(1177,20,'B')
    assert j['counts']==p['counts_after'] and j['counts'][28:]==[57,38,37,24]
    from nf_migrate import valid_snapshot
    old=[];retained=[]
    for at in range(0x4000,0x6000,256):
        if valid_snapshot(before[at:at+256]):
            old.append(at)
            if before[at:at+256]==after[at:at+256]:retained.append(at)
    assert len(old)==27 and len(retained)==11 and all(at<0x5000 for at in retained)
    assert (SCOPE/'boot-wear-history-original.bin').read_bytes()==before[0x4000:0x6000]
    latest=max((after[at:at+256] for at in range(0x4000,0x6000,256) if valid_snapshot(after[at:at+256])),key=lambda b:int.from_bytes(b[8:12],'little'))
    assert latest[7]==ord('B') and latest[12:30]==before[0x4A0C:0x4A1E]
    assert (OUT/'B0-9000-precleanup.bin').read_bytes()==(SCOPE/'B0-9000-fixture.bin').read_bytes()
    assert (OUT/'B0-9000-restored.bin').read_bytes()==(SCOPE/'B0-9000-original.bin').read_bytes()==b'\xff'*4096
    assert (OUT/'B3-9000-trial-metadata.bin').read_bytes()==(SCOPE/'B3-9000-trial-metadata.bin').read_bytes()
    assert (OUT/'B3-9000-restored.bin').read_bytes()==before[0x1000:0x2000]
    assert (OUT/'EEPROM-00-7F-after.bin').read_bytes()==(SCOPE/'EEPROM-00-7F-original.bin').read_bytes()
    for record in p['metadata_records']:
        at=int(record['address'].split(':')[1],16)
        assert (OUT/f'metadata-{at:04X}.bin').read_bytes()==bytes.fromhex(record['hex'])
    for name,key in [('owner-ram.bin','RAM_sha256'),('owner-zp.bin','ZP_sha256')]:
        assert t.sha((OUT/name).read_bytes())==r[key]
    assert t.sha(after[-4096:])==p['F_sha256']
    import rtc_fleet as fleet
    marker=fleet.admission('2512')  # host eligibility only, no board connection
    assert marker['monitor_generation']==marker['default_monitor_generation']=='00000010'
    assert marker['current_journal_sequence']==1177 and marker['current_journal_valid_records']==20
    assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
    assert not marker['boot_clock_trial_pending'] and not marker['physical_reset_pending']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    completion=dict(status='ACCEPTED_2512_BOOT_AND_CLOCK_METADATA_POSITIVES',passed=True,board='2512',
        receipt=str(path),receipt_sha256=t.sha(path.read_bytes()),image_erases=2,native_D_rotation_erases=1,total_erases=3,
        boot_policy_appends=6,wear_reservations=2,peer_intents=1,total_journal_appends=9,metadata_appends=3,
        old_rows_archived_on_host=27,old_D_rows_replaced_on_chip=16,old_C_rows_retained_exact=11,
        final_sequence=1177,final_valid_records=20,counts_CD_E_F=[57,38,37,24],F_sha256=p['F_sha256'],
        gates_closed=['BOOT OFF and disabled RUN refusal','BOOT DELAY0B/0A legacy-byte commits and invalid9 refusal',
            'BOOT RUN flash marker/public HOLD return to MON B','real CLOCK EUI acceptance and no-op repeat',
            'real CLOCK offset write and no-op repeat','real CLOCK battery limits write without date change'],
        restored=['original boot fields/default B-g10','exact B0:9 all-FF image','exact B3:9 provider and14 original metadata rows',
            'original unbound EUI,-06 offset,battery12/24','all128 EEPROM bytes and unchanged live PF timestamps',
            'fresh owner RAM0200-66FF/ZP00-DF'],
        RTC_SET=0,trim_writes=0,PF_ACK=0,EEPROM_writes=0,SPI_data_writes=0,resets=0,power_cuts=0,
        firmware_rebuilds=0,F_writes=0,MON_writes=0,RTC_collection_eligible=True,baseline_or_collector_changes=0,
        owner_RAM_restored=True,owner_ZP_restored=True,final_prompt='REC>',COM4_released=True,
        remaining=['latched SET/ACK and changed-trim isolated RAM cases','FLASH help must label DELAY as legacy-only before shipping',
            'physical terminal keys/extracted-kit and targeted held816 checks remain separate'],
        limits=['BASE1 chooser stays fixed3s; only legacy delay field storage proved','no physical battery replacement/date test claimed',
            'no manufactured outage or real RTC/EEPROM data write','other boards and published downloads untouched'],
        allowance='All3 erases/9 boot-wear appends/3 metadata appends spent; no further NVM allowance')
    destination=SCOPE/'completion.json';assert not destination.exists();t.save(destination,completion)
    print('CLOSED2512 BOOT/CLOCK:OFF/DELAY-store/RUN and3 CLOCK writers;exact restores;F golden;RTC eligible;REC>;COM4 free',flush=True)

if __name__=='__main__':run()
