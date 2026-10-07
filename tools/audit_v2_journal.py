"""Bind journal models, backups, verified installs and real power-cycle evidence."""
import argparse, hashlib, json, re
from pathlib import Path
from qualify_v2_journal_board import records

ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    build=ROOT/'BUILD/v2-rtc-journal';meta=read(build/'build.json');clock=read(ROOT/'BUILD/v2-clock-1.2/build.json')
    for name,digest in meta['artifacts'].items():assert sha((build/name).read_bytes())==digest
    for name in ('kernel-test-results.json','banner-test-results.json','journal-test-results.json'):
        check=read(build/name);assert check['passed']
        assert check.get('artifacts',check.get('kernel_artifacts'))==meta['artifacts']
    cc=read(ROOT/'BUILD/v2-clock-1.2/test-results.json');assert cc['passed'] and cc['sha256']==clock['sha256'] and cc['kernel_artifacts']==meta['artifacts']
    authorization=read(a.root/'allocation-authorization.json')
    result=dict(passed=True,version=meta['version'],clock_version=clock['version'],allocation_authorization=authorization,boards=[])
    for board in ('2512','2205','2609'):
        root=a.root/board;plan=read(root/'upgrade/plan.json');model=read(root/'upgrade/model-check.json')
        initial=read(root/'journal-check/report.json');stage='powercycle-check'
        live=read(root/stage/'report.json')
        assert initial['passed'] and live['passed'] and model['passed']
        maintenance=read(root/'maintenance-check/report.json')
        assert maintenance['passed'] and maintenance['sector_9_refused'] and not maintenance['flash_write_authorized']
        assert not initial['clock_set'] and not live['clock_set'] and not live['trim_written']
        assert model['installer_sha256']==sha((root/'upgrade/installer.s19').read_bytes())==plan['installer_sha256']
        assert model['stale_preimage_refused'] and model['corrupt_payload_refused'] and model['record_commits']==[1,2]
        assert live['final_hashes']==plan['expected_hashes']==model['expected_hashes']
        assert not read(root/'upgrade/install/reset-pending.json')['physical_reset_pending']
        assert read(root/'prior/manifest.json')['repeat_verified']
        for bank in range(4):
            before=(root/f'prior/b{bank}.bin').read_bytes();after=(root/stage/f'final-b{bank}.bin').read_bytes()
            assert before==(root/f'prior/b{bank}-repeat.bin').read_bytes() and sha(before)==plan['prior_hashes'][bank]
            assert after==(root/f'upgrade/expected-b{bank}.bin').read_bytes()
            if bank==0:assert before==after
            if bank==1:assert before[8192:]==after[8192:]
            if bank==2:assert before[8192:]==after[8192:]
            if bank==3:assert before[0x7000:]==after[0x7000:]
        sector=(root/stage/'final-b3.bin').read_bytes()[4096:8192]
        assert sector==(root/'maintenance-check/journal-sector.bin').read_bytes()
        assert sha(sector)==maintenance['journal_sha256']
        evidence=dict(board=board,passed=True,final_hashes=live['final_hashes'])
        if board!='2512':
            data=(root/stage/'eeprom-after.bin').read_bytes();old=(root/'journal-check/eeprom-after.bin').read_bytes()
            assert data[0x80:0x89]==old[0x80:0x89]==(root/'eeprom-prior/status-factory.bin').read_bytes()
            current=records(data[:128]);previous=records(old[:128])
            assert current==live['records'] and previous==initial['records']
            assert max(r['sequence'] for r in current)>max(r['sequence'] for r in previous)
            assert len(current)>=2 and all(r['clearance']==0 for r in current)
            for prior in previous:assert prior in current
            assert live['utc_advancement_verified'] and initial['utc_advancement_verified']
            def rtc_settings(path):
                text=path.read_bytes()
                raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode())
                assert b'Backup enabled: yes' in text and b'Running: yes' in text
                return raw[7:9]
            prior_settings=rtc_settings(root/'prior/rtc-prior.txt')
            assert rtc_settings(root/'journal-check/status-after.txt')==prior_settings
            assert rtc_settings(root/stage/'status-after.txt')==prior_settings
            evidence.update(records=current,factory_status_unchanged=True,next_real_outage_verified=True)
        result['boards'].append(evidence);print('PASS',board,'journal installation, optional-device behavior and retained evidence')
    baseline=read(ROOT/'output/qualification/rtc-utc-sync-2026-10-06/baseline-index.json')
    for b in baseline['boards']:
        assert sha(Path(b['sync_report']).read_bytes())==b['sync_sha256']
        assert sha(Path(b['baseline_report']).read_bytes())==b['baseline_sha256']
    result['original_baselines_preserved']=True
    (a.root/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
