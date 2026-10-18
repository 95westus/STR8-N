"""Close first bounded hardware cut and seal current bytes for the A route."""
import json,hashlib,shutil
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
import plan_bf1_2609_route as route
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';G=Q/'bf1-2609-physical-gate-2026-10-17-r1';CUT=G/'power-cut-1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    destination=CUT/'checkpoint.json';assert not destination.exists()
    checks=CUT/'recovery-checks';r=read(checks/'report.json');tx=CUT/'recovery/report.json'
    assert r['passed'] and r['physical_interruption_recovery_completed'] and r['pre_interruption_RAM_restored'] and r['ports_released']
    assert r['transaction_report_sha256']==sha(tx) and r['reset_confirmation_sha256']==sha(CUT/'recovery-reset-confirmation.json')
    for folder in (CUT,CUT/'recovery',checks):assert not read(folder/'restore-needed.json')['needed'] and read(folder/'restore-needed.json')['verified']
    assert read(CUT/'recovery/activation-completed.json')['hardware_report_sha256']==sha(checks/'report.json')
    assert all(c['passed'] for c in r['checks'])
    for k in ('cpu_mode_before','cpu_mode_after_batch','cpu_mode_after'):
        m=r[k];assert m['emulation_mode_before_probe'] and m['dbr']==m['pbr']==m['direct_page']==0 and m['entry_decimal_clear'] and m['entry_irq_disabled']
    recovery=read(tx);banks=[]
    for i,digest in enumerate(recovery['expected_hashes']):
        assert sha(checks/f'before-checks-b{i}.bin')==sha(checks/f'after-checks-b{i}.bin')==digest
        banks.append((checks/f'after-checks-b{i}.bin').read_bytes())
    admission=CUT/'recovery-admission.json';a=read(admission);assert a['passed']
    returned=CUT/'return-capture';precut=G/'post-restoration-backup'
    for name in ('eeprom','sram'):assert (checks/(name+'-after.bin')).read_bytes()==(returned/(name+'.bin')).read_bytes()
    assert (checks/'sram-after.bin').read_bytes()==(precut/'sram.bin').read_bytes()
    plan_path=G/'stable-boundary-proof-r2/stable-boundary-recovery/plan.json';plan=read(plan_path)
    row=route.c.latest(banks)[2];counts=[int.from_bytes(row[24+i*3:27+i*3],'little') for i in range(32)]
    assert counts==plan['transaction']['reserved_counts'] and row[8:24].hex()==plan['transaction']['target_configuration_hex']
    active=read(Q/'active-rtc-campaign.json');assert sha(Path(active['baseline_index']))==active['baseline_index_sha256'] and active['powered_off_boards']==['2205']
    refs={'admission':admission,'return_capture':returned/'report.json','recovery':tx,'hardware':checks/'report.json','off':CUT/'owner-power-off-confirmation.json','on':CUT/'owner-power-on-confirmation.json','reset':CUT/'recovery-reset-confirmation.json'}
    cp=dict(passed=True,board='2609',observed_utc=datetime.now(timezone.utc).isoformat(),case='First stable transfer boundary with A40 fallback',
            hardware_power_interruption_and_recovery_passed=True,actual_cut_state_exactly_modeled=True,
            fallback='A40 2.0b28 on 65C816 E=1',recovered='bf1 B generation 48',recovered_B_frequency_or_trim_not_adjusted=True,
            utility_CLOCK_BATCH_passed=True,SRAM_unchanged=True,EEPROM_expected_PF_event=a['EEPROM_expected_PF_event'],
            pre_interruption_RAM_restored=True,conservative_counts_after=counts,
            refs={k:dict(path=str(p.resolve()),sha256=sha(p)) for k,p in refs.items()},baseline_sha256=active['baseline_index_sha256'],
            qualification_scope='Owner-controlled power loss while waiting for the second transfer after a verified first journal transfer; exact fallback/cut readback and recovery. Not mid-erase/program or arbitrary byte timing.',
            deferred=['native 816 applications/tests','ACIA','crypto'],release_qualified=False,installation_permitted=False,publication_permitted=False)
    publish(destination,cp);publish(Q/'bf1-2609-power-recovery-current.json',dict(checkpoint=str(destination.resolve()),checkpoint_sha256=sha(destination)))
    out=G/'post-cut-1-backup';assert not out.exists();sources={}
    for i in range(4):sources[f'b{i}.bin']=checks/f'after-checks-b{i}.bin';sources[f'b{i}-repeat.bin']=checks/f'before-checks-b{i}.bin'
    for name in ('eeprom','sram'):sources[name+'.bin']=checks/(name+'-after.bin');sources[name+'-repeat.bin']=returned/(name+'.bin')
    for name in ('application-ram-original.bin','restore-application-ram.s19'):sources[name]=precut/name
    sources['version.txt']=checks/'version.txt';assert b'2.0bf1' in sources['version.txt'].read_bytes()
    out.mkdir()
    for name,path in sources.items():shutil.copyfile(path,out/name)
    publish(out/'restore-needed.json',dict(needed=False,verified=True,sha256=sha(precut/'application-ram-original.bin')))
    receipt=dict(passed=True,board='2609',port=recovery['port'],usb_serial='A10MPQXCA',active_page=0xb0,
                 flash_repeat_verified=True,eeprom_repeat_verified=True,sram_repeat_verified=True,application_ram_restored=True,ports_released=True,
                 capture_kind='Sealed actual before/after recovery-check flash readbacks and independent retained-device comparisons spanning flash-only recovery; no new reads by sealer',
                 parent_checkpoint_sha256=sha(destination),hardware_report_sha256=sha(checks/'report.json'),
                 source_readbacks={n:dict(path=str(p.resolve()),sha256=sha(p)) for n,p in sources.items()},
                 files={n:dict(bytes=(out/n).stat().st_size,sha256=sha(out/n)) for n in sources},board_access=False,clock_set=False,trim_changed=False)
    publish(out/'report.json',receipt)
    campaign_path=Path(active['campaign_state']);campaign=read(campaign_path);campaign['2609_physical_gate'].update(state='First bounded hardware power-cut/recovery passed with pre-interruption RAM restored; preparing later A-slot boundary',first_case_checkpoint=str(destination.resolve()),first_case_checkpoint_sha256=sha(destination),physical_interruption_recovery_completed=True);publish(campaign_path,campaign)
    print('PASS first hardware power-cut/recovery checkpoint and receipt-bound current bf1 B backup',flush=True)
if __name__=='__main__':main()
