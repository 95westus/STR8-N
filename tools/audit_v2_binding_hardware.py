"""Bind beta12 installation, physical checks, identity acceptance and archives."""
import argparse,hashlib,json,binascii
from pathlib import Path
from beta4_migration import journal,crc
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    build=ROOT/'BUILD/v2-rtc-binding';candidate=read(build/'candidate-check.json');meta=read(build/'build.json');assert candidate['passed']
    assert all(sha((build/n).read_bytes())==h for n,h in meta['artifacts'].items())
    result=dict(passed=True,version='2.0b12',clock_version='1.4',boards=[],no_clock_set=True)
    for board in ('2512','2205','2609'):
        root=a.root/board;plan=read(root/'upgrade/plan.json');model=read(root/'upgrade/model-check.json');live=read(root/'binding-check/report.json')
        assert live['passed'] and model['passed'] and model['record_commits']==[2]
        assert model['stale_preimage_refused'] and model['corrupt_payload_refused']
        assert model['installer_sha256']==plan['installer_sha256']==sha((root/'upgrade/installer.s19').read_bytes())
        assert live['installed_hashes']==plan['expected_hashes']==model['expected_hashes']
        assert not live['clock_set'] and not live['trim_written'] and not read(root/'upgrade/install/reset-pending.json')['physical_reset_pending']
        assert read(root/'prior/manifest.json')['repeat_verified'] and read(root/'eeprom-prior/report.json')['passed']
        for bank in range(4):
            before=(root/f'prior/b{bank}.bin').read_bytes();installed=(root/f'binding-check/installed-b{bank}.bin').read_bytes();final=(root/f'binding-check/final-b{bank}.bin').read_bytes()
            assert before==(root/f'prior/b{bank}-repeat.bin').read_bytes() and sha(before)==plan['prior_hashes'][bank]
            assert installed==(root/f'upgrade/expected-b{bank}.bin').read_bytes() and sha(final)==live['final_hashes'][bank]
            if bank in (0,1):assert before==installed==final
            if bank==2:assert installed==final and before[8192:]==final[8192:]
            if bank==3:
                assert before[0x7000:]==installed[0x7000:]==final[0x7000:] and installed[:7168]==final[:7168] and installed[8192:]==final[8192:]
                assert crc(final[4096:7168])==0 and final[4096:4100]==b'PJ\x04\x01'
                record=journal(final);assert record[8:24].hex()==plan['config']
                assert [int.from_bytes(record[24+i*3:27+i*3],'little') for i in range(32)]==plan['counts_after']
                if board=='2512':assert installed==final and final[7168:8192]==bytes([255])*1024 and not live['identity_accepted']
                else:
                    r=final[7168:7200];sf=(root/'eeprom-prior/status-factory.bin').read_bytes()
                    assert r[:4]==b'EI\x01\0' and r[4:8]==(1).to_bytes(4,'little') and r[8:14]==sf[3:9]
                    assert binascii.crc_hqx(r[:28],0xffff)==int.from_bytes(r[28:30],'little') and r[31]==0
                    assert final[7200:8192]==bytes([255])*992 and live['identity_accepted']
        if board!='2512':
            e0=(root/'binding-check/eeprom-final-0.bin').read_bytes();e1=(root/'binding-check/eeprom-final-1.bin').read_bytes()
            assert e0==e1 and e0[0x80:0x89]==(root/'eeprom-prior/status-factory.bin').read_bytes()
            if live['eeprom_unchanged']:assert e0[:128]==(root/'eeprom-prior/array.bin').read_bytes()
        result['boards'].append(dict(board=board,eui=live.get('eui'),identity_accepted=live['identity_accepted'],eeprom_unchanged=live.get('eeprom_unchanged'),final_hashes=live['final_hashes']))
        print('PASS',board,'backups, verified update, TIME/EUI/identity qualification, history and exact final images')
    baseline=read(ROOT/'output/qualification/rtc-utc-sync-2026-10-06/baseline-index.json')
    for b in baseline['boards']:
        assert sha(Path(b['sync_report']).read_bytes())==b['sync_sha256'] and sha(Path(b['baseline_report']).read_bytes())==b['baseline_sha256']
    result['original_drift_baselines_preserved']=True
    (a.root/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
