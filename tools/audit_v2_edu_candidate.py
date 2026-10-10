"""Bind beta15 tests and fresh board recipes before any flashing."""
import argparse,hashlib,json
from pathlib import Path
from build_v2_spi_resident import OUT
from beta4_migration import crc
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();meta=read(OUT/'build.json')
    assert meta['version']=='2.0b15' and meta['edu_mode'] and max(meta['monitor_bytes'].values())<=3968 and meta['launcher_bytes']<=1760
    for name,digest in meta['artifacts'].items():assert sha((OUT/name).read_bytes())==digest,name
    reports={}
    for name in ('edu-mode-test-results.json','kernel-test-results.json','spi-resident-test-results.json','journal-test-results.json','banner-test-results.json','time-test-results.json','binding-test-results.json','binding-clock-test-results.json','trim-test-results.json'):
        r=read(OUT/name);assert r['passed'] and r['artifacts']==meta['artifacts'],name;reports[name]=sha((OUT/name).read_bytes())
    cm=read(ROOT/'BUILD/v2-clock-1.5/build.json')
    for name in ('core-test-results.json','test-results.json'):
        r=read(ROOT/'BUILD/v2-clock-1.5'/name);assert r['passed'] and r['sha256']==cm['sha256'] and r['kernel_artifacts']==meta['artifacts']
    wm=read(OUT/'workspace/build.json');assert wm['version']=='1.1' and sha((OUT/'workspace/workspace.bin').read_bytes())==wm['sha256']
    for name in ('test-results.json','guard-test-results.json','format-test-results.json','integration-test-results.json','console-test-results.json'):
        r=read(OUT/'workspace'/name);assert r['passed'] and r['workspace_sha256']==wm['sha256'] and r['resident_artifacts']==meta['artifacts'],name
    utility=read(OUT/'edu/build.json');assert utility['sha256']==read(OUT/'edu-mode-test-results.json')['utility_sha256']==sha((OUT/'edu/edu.bin').read_bytes())
    client=read(OUT/'hardware-client/test-results.json');assert client['passed'] and client['resident_artifacts']==meta['artifacts']
    for b in ('2512','2205','2609'):
        root=a.root/b;plan=read(root/'upgrade/plan.json');check=read(root/'upgrade/model-check.json')
        assert check['passed'] and check['stale_preimage_refused'] and check['corrupt_payload_refused'] and check['record_commits']==[2]
        assert check['expected_hashes']==plan['expected_hashes'] and check['installer_sha256']==plan['installer_sha256']==sha((root/'upgrade/installer.s19').read_bytes())
        assert plan['edu_mode']==('OFF' if b=='2512' else 'ON')
        for bank in (0,1):assert (root/f'prior/b{bank}.bin').read_bytes()==(root/f'upgrade/expected-b{bank}.bin').read_bytes()
        before=(root/'prior/b3.bin').read_bytes();after=(root/'upgrade/expected-b3.bin').read_bytes()
        assert before[:8192]==after[:8192] and before[0x7000:]==after[0x7000:]
        if b!='2512':assert read(root/'sram-prior/report.json')['passed'] and (root/'sram-prior/array-0.bin').read_bytes()==(root/'sram-prior/array-1.bin').read_bytes()
    e=(OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes();assert crc(e)==0 and crc(e[:0x800])==0 and e[0xE94:0xE98]==b'ED\x01\x01'
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(a.root/'source-beta14/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    result=dict(passed=True,version=meta['version'],clock_sha256=cm['sha256'],artifacts=meta['artifacts'],reports=reports,boards_flashed=False,board_access=False,edu_mode=True,root=str(a.root),workspace_sha256=wm['sha256'],utility_sha256=utility['sha256'])
    (OUT/'candidate-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS beta15 EDU modes, all matched regressions, WORK1.1 and 3 exact-source commit-last installers; no board writes')
if __name__=='__main__':main()
