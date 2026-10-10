"""Bind the unflashed startup candidate to its executed model receipts."""
import hashlib,json
from pathlib import Path
from beta4_migration import crc

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'BUILD/v2-spi-startup'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    meta=read(BUILD/'build.json')
    assert meta['version']=='2.0b22' and meta['generation']==31
    assert meta['spi_startup_disabled_cb_ack'] and meta['local_time'] and meta['quiet_monitor_return']
    checks={}
    for name in ('spi-startup-test-results.json','spi-startup-integration-test-results.json','local-time-test-results.json','local-time-extra-test-results.json','quiet-return-test-results.json','kernel-test-results.json'):
        r=read(BUILD/name)
        assert r['passed'] and r['artifacts']==meta['artifacts'],name
        if 'status_asset_sha256' in r:assert r['status_asset_sha256']==meta['status_asset_sha256']
        checks[name]=sha(BUILD/name)
    for name,digest in meta['artifacts'].items():assert sha(BUILD/name)==digest,name
    for name,key,size in (('boot-status/asset.bin','status_asset_sha256',2560),('local-display/asset.bin','local_asset_sha256',1536)):
        body=(BUILD/name).read_bytes()
        assert len(body)==size and crc(body)==0 and sha(BUILD/name)==meta[key]
    assert meta['status_code_bytes']<=2558
    for name in ('clock/clock.bin','local-display/asset.bin'):
        assert (BUILD/name).read_bytes()==(ROOT/'BUILD/v2-local-time'/name).read_bytes(),name
    report=dict(passed=True,version=meta['version'],candidate_installed=False,build_sha256=sha(BUILD/'build.json'),model_report_hashes=checks,artifacts=meta['artifacts'],status_asset_sha256=meta['status_asset_sha256'],clock_sha256=meta['clock_sha256'],local_asset_sha256=meta['local_asset_sha256'],board_access=False,hardware_qualification_pending=True)
    (BUILD/'spi-startup-candidate-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS startup candidate artifact/model hashes, sealed assets and unchanged CLOCK/local-display; unflashed')

if __name__=='__main__':main()
