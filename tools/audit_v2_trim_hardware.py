"""Audit beta13/CLOCK1.5 installs, preserved state and complete readbacks."""
import argparse,hashlib,json
from pathlib import Path
from beta4_migration import journal,crc
from qualify_v2_journal_board import records
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    build=ROOT/'BUILD/v2-rtc-trim';meta=read(build/'build.json');candidate=read(build/'candidate-check.json')
    assert candidate['passed'] and candidate['artifacts']==meta['artifacts']
    assert all(sha((build/n).read_bytes())==h for n,h in meta['artifacts'].items())
    result=dict(passed=True,version=meta['version'],clock_version='1.5',boards=[],clock_set=False,trim_adjusted=False)
    for board in ('2512','2205','2609'):
        root=a.root/board;pending=read(root/'upgrade/install/reset-pending.json');stage=pending.get('qualification_stage','trim-check')
        plan=read(root/'upgrade/plan.json');model=read(root/'upgrade/model-check.json');live=read(root/stage/'report.json')
        assert live['passed'] and model['passed'] and model['record_commits']==[2]
        assert model['stale_preimage_refused'] and model['corrupt_payload_refused']
        assert model['installer_sha256']==plan['installer_sha256']==sha((root/'upgrade/installer.s19').read_bytes())
        assert live['installed_hashes']==live['final_hashes']==plan['expected_hashes']==model['expected_hashes']
        assert not any(live[k] for k in ('clock_set','trim_changed','identity_accepted','powerfail_acknowledged'))
        assert not read(root/'upgrade/install/reset-pending.json')['physical_reset_pending']
        assert read(root/'prior/manifest.json')['repeat_verified'] and read(root/'eeprom-prior/report.json')['passed']
        for bank in range(4):
            before=(root/f'prior/b{bank}.bin').read_bytes();after=(root/stage/f'final-b{bank}.bin').read_bytes()
            assert before==(root/f'prior/b{bank}-repeat.bin').read_bytes() and sha(before)==plan['prior_hashes'][bank]
            assert after==(root/f'upgrade/expected-b{bank}.bin').read_bytes()==(root/stage/f'installed-b{bank}.bin').read_bytes()
            if bank in (0,1):assert before==after
            if bank==2:assert before[8192:]==after[8192:]
            if bank==3:
                assert before[7168:8192]==after[7168:8192] and before[0x5000:0x6000]==after[0x5000:0x6000] and before[0x7000:]==after[0x7000:]
                assert after[4096:4100]==b'PJ\x05\x01' and crc(after[4096:7168])==0
                r=journal(after);assert r[8:24].hex()==plan['config']
                assert [int.from_bytes(r[24+i*3:27+i*3],'little') for i in range(32)]==plan['counts_after']
        if board!='2512':
            e0=(root/stage/'eeprom-final-0.bin').read_bytes();assert e0==(root/stage/'eeprom-final-1.bin').read_bytes()
            prior_ee=(root/'eeprom-prior/array.bin').read_bytes()
            assert e0[0x80:0x89]==(root/'eeprom-prior/status-factory.bin').read_bytes()
            if live['eeprom_unchanged']:assert e0[:128]==prior_ee
            else:
                assert board=='2609' and live['boot_powerfail_logged_and_acked']
                old=records(prior_ee);current=records(e0[:128]);last=max((r['sequence'] for r in old),default=0)
                new=[r for r in current if r['sequence']>last];assert new==live['new_outage_records'] and len(new)==1 and new[0]['sequence']==last+1
                for i in range(4):
                    if i!=new[0]['slot']-1:assert e0[i*32:(i+1)*32]==prior_ee[i*32:(i+1)*32]
            assert live['control_trim']=='8000'
        result['boards'].append(dict(board=board,final_hashes=live['final_hashes'],eui=live.get('eui'),control_trim=live.get('control_trim'),checks=live['checks'],eeprom_unchanged=live['eeprom_unchanged'],new_outage_records=live.get('new_outage_records',[])))
        print('PASS',board,'verified beta13/CLOCK1.5; current B0/B1/F, EUI tail, EEPROM and trim preserved')
    baseline=read(ROOT/'output/qualification/rtc-utc-sync-2026-10-06/baseline-index.json')
    for b in baseline['boards']:
        assert sha(Path(b['sync_report']).read_bytes())==b['sync_sha256'] and sha(Path(b['baseline_report']).read_bytes())==b['baseline_sha256']
    result['original_drift_baselines_preserved']=True
    (a.root/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
