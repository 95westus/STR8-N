"""Bind the unflashed local-time candidate to its executed model evidence."""
import hashlib,json
from pathlib import Path
from beta4_migration import crc
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-local-time'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    meta=read(OUT/'build.json');assert meta['version']=='2.0b21' and meta['local_time']
    assert meta['clock_version']=='1.6' and max(meta['monitor_bytes'].values())<=3968
    for name,digest in meta['artifacts'].items():assert sha(OUT/name)==digest,name
    for name,size,key in (('boot-status/asset.bin',2560,'status_asset_sha256'),('local-display/asset.bin',1536,'local_asset_sha256')):
        asset=(OUT/name).read_bytes();assert len(asset)==size and crc(asset)==0 and sha(OUT/name)==meta[key]
    assert meta['local_code_bytes']<=1534 and meta['status_code_bytes']<=2558
    assert read(OUT/'clock/build.json')['sha256']==meta['clock_sha256']==sha(OUT/'clock/clock.bin')
    for name in ('local-time-test-results.json','local-time-extra-test-results.json','kernel-test-results.json','quiet-return-test-results.json'):
        report=read(OUT/name);assert report['passed'] and report['artifacts']==meta['artifacts'],name
    local=read(OUT/'local-time-test-results.json')
    assert local['clock_sha256']==meta['clock_sha256'] and local['local_asset_sha256']==meta['local_asset_sha256']
    for name in ('str8n-rtc-component-8000-8fff.bin','str8n-journal-9000-9fff.bin','str8n-v2-recovery-f000-ffff.bin'):
        assert (OUT/name).read_bytes()==(ROOT/'BUILD/v2-combined-display'/name).read_bytes(),name
    report=dict(passed=True,version=meta['version'],artifacts=meta['artifacts'],clock_sha256=meta['clock_sha256'],
        local_asset_sha256=meta['local_asset_sha256'],board_access=False,boards_flashed=False,
        scheduled_beta20_unchanged=True)
    pinned=ROOT/'output/qualification/combined-display-2026-10-08/flash-schedule.json';schedule=read(pinned)
    prior=ROOT/'BUILD/v2-combined-display'
    assert sha(prior/'build.json')==schedule['build_metadata_sha256']
    assert sha(prior/'storage-candidate-check.json')==schedule['candidate_check_sha256']
    (OUT/'local-time-candidate-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS unflashed local-time candidate, CLOCK 1.6, sealed assets, exact model receipts and unchanged scheduled beta20 image')

if __name__=='__main__':main()
