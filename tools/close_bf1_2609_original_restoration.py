"""Close actual two-stage restoration evidence; never claim power-loss qualification."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import plan_bf1_2609_route as route
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';G=Q/'bf1-2609-physical-gate-2026-10-17-r1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    output=G/'original-restoration-checkpoint.json';assert not output.exists()
    phases={}
    for name,case in [('restore-A40','restore-A40-retain-Bbf1'),('restore-B35','restore-original-B35-complete')]:
        transaction=G/name;checks=G/(name+'-checks');r=read(checks/'report.json');tx=read(transaction/'report.json')
        assert tx['passed'] and r['passed'] and r['case']==case and tx['case']==case
        assert r['full_flash_verified'] and r['initial_checks_passed'] and r['application_ram_restored'] and r['ports_released']
        assert r['transaction_report_sha256']==sha(transaction/'report.json')
        assert not read(transaction/'restore-needed.json')['needed'] and not read(checks/'restore-needed.json')['needed']
        assert not read(transaction/'activation-completed.json')['physical_reset_pending']
        for bank,digest in enumerate(tx['expected_hashes']):assert sha(checks/f'after-checks-b{bank}.bin')==digest
        for mode in (r['cpu_mode_before'],r['cpu_mode_after']):
            assert mode['emulation_mode_before_probe'] and mode['dbr']==mode['pbr']==mode['direct_page']==0
        phases[name]=dict(transaction_sha256=sha(transaction/'report.json'),hardware_report_sha256=sha(checks/'report.json'))
    original=Q/'2609-return-backup-2026-10-17-1931Z';final=G/'restore-B35-checks'
    banks=[(final/f'after-checks-b{i}.bin').read_bytes() for i in range(4)]
    before=[(original/f'b{i}.bin').read_bytes() for i in range(4)]
    for bank in range(4):
        assert all(x==y for offset,(x,y) in enumerate(zip(banks[bank],before[bank])) if not(bank==3 and 0x4000<=offset<0x6000))
    old=route.c.latest(before);new=route.c.latest(banks)
    assert new[0]>old[0]
    oldrow,newrow=old[2],new[2]
    assert oldrow[8:24]==newrow[8:24]
    counts_old=[int.from_bytes(oldrow[24+i*3:27+i*3],'little') for i in range(32)]
    counts_new=[int.from_bytes(newrow[24+i*3:27+i*3],'little') for i in range(32)]
    assert all(y>=x for x,y in zip(counts_old,counts_new))
    assert (final/'eeprom-after.bin').read_bytes()==(original/'eeprom.bin').read_bytes()
    assert (final/'sram-after.bin').read_bytes()==(original/'sram.bin').read_bytes()
    active=read(Q/'active-rtc-campaign.json');assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    result=dict(passed=True,board='2609',observed_utc=datetime.now(timezone.utc).isoformat(),phases=phases,
                original_payload_restoration_hardware_passed=True,original_payload_bytes_equal_outside_wear_journals=True,
                original_configuration_restored=True,journal_sequence_before=old[0],journal_sequence_after=new[0],
                conservative_counts_before=counts_old,conservative_counts_after=counts_new,
                EEPROM_and_full_SRAM_unchanged=True,application_RAM_restored=True,processor_runtime='65C816 E=1',
                clock_trim_changed=False,baseline_sha256=active['baseline_index_sha256'],
                physical_power_interruption_performed=False,physical_power_interruption_qualified=False,
                remaining='Fresh backup and re-admission from restored B35/new wear history, then owner-controlled bounded power-interruption/recovery tests and return to pinned bf1',
                release_qualified=False,installation_permitted=False,publication_permitted=False)
    publish(output,result)
    publish(Q/'bf1-2609-original-restoration-current.json',dict(checkpoint=str(output.resolve()),checkpoint_sha256=sha(output)))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
