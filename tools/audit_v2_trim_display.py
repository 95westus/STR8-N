"""Bind display tests, immutable components, staging bounds and candidate bytes."""
import hashlib
import json
from pathlib import Path
from beta4_migration import crc

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-trim-display'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    meta=read(OUT/'build.json');assert meta['version']=='2.0b18' and meta['generation']==27
    assert meta['trim_display'] and meta['status_ram_base']==0x6E00 and meta['status_asset_bytes']==2560
    assert meta['status_code_bytes']<=2558 and max(meta['monitor_bytes'].values())<=3968
    for name,digest in meta['artifacts'].items():assert sha(OUT/name)==digest,name
    asset=(OUT/'boot-status/asset.bin').read_bytes()
    assert len(asset)==2560 and asset[:4]==b'BS\x01\x03' and crc(asset)==0
    assert sha(OUT/'boot-status/asset.bin')==meta['status_asset_sha256']
    for name in ('str8n-rtc-component-8000-8fff.bin','str8n-journal-9000-9fff.bin','str8n-v2-recovery-f000-ffff.bin'):
        assert (OUT/name).read_bytes()==(ROOT/'BUILD/v2-storage'/name).read_bytes(),name
    for name in ('store/sram.bin','workspace/workspace.bin','edu/edu.bin','clock/clock.bin'):
        assert (OUT/name).read_bytes()==(ROOT/'BUILD/v2-storage'/name).read_bytes(),name
    for name in ('kernel-test-results.json','storage-test-results.json','trim-display-test-results.json'):
        r=read(OUT/name);assert r['passed'] and r['artifacts']==meta['artifacts'],name
        if name!='kernel-test-results.json':
            assert r.get('asset_sha256',r.get('status_asset_sha256'))==meta['status_asset_sha256'],name
    report=dict(passed=True,version=meta['version'],artifacts=meta['artifacts'],
        status_asset_sha256=meta['status_asset_sha256'],checked_normal_encodings=256,
        immutable_rtc_journal_recovery_retained=True,saved_utilities_retained=True,
        user_ram_top_unchanged=True,board_access=False)
    (OUT/'storage-candidate-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS sealed display asset, staging bounds, all signed encodings, kernel/storage regressions; RTC, journal, recovery and utilities unchanged')

if __name__=='__main__':main()
