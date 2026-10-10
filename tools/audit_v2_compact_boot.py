"""Bind compact boot candidate to executed display, RTC and SPI models."""
import hashlib,json
from pathlib import Path
from beta4_migration import crc
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-compact-boot'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    meta=read(OUT/'build.json')
    assert meta['version']=='2.0b23' and meta['generation']==32 and meta['compact_boot_local']
    assert meta['spi_startup_disabled_cb_ack'] and meta['quiet_monitor_return']
    reports={}
    for name in ('compact-boot-test-results.json','reset-notice-test-results.json','local-time-test-results.json','quiet-return-test-results.json','kernel-test-results.json','spi-resident-test-results.json','journal-test-results.json','spi-startup-test-results.json','spi-startup-integration-test-results.json'):
        r=read(OUT/name);assert r['passed'] and r['artifacts']==meta['artifacts'],name
        if 'status_asset_sha256' in r:assert r['status_asset_sha256']==meta['status_asset_sha256'],name
        reports[name]=sha(OUT/name)
    for name,digest in meta['artifacts'].items():assert sha(OUT/name)==digest,name
    for name,key,size in (('boot-status/asset.bin','status_asset_sha256',2560),('local-display/asset.bin','local_asset_sha256',1536)):
        body=(OUT/name).read_bytes();assert len(body)==size and crc(body)==0 and sha(OUT/name)==meta[key]
    assert meta['status_code_bytes']<=2558 and meta['local_code_bytes']<=1534
    assert (OUT/'clock/clock.bin').read_bytes()==(ROOT/'BUILD/v2-spi-startup/clock/clock.bin').read_bytes()
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(ROOT/'BUILD/v2-spi-startup/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    report=dict(passed=True,version=meta['version'],generation=meta['generation'],build_sha256=sha(OUT/'build.json'),artifacts=meta['artifacts'],model_report_hashes=reports,clock_sha256=meta['clock_sha256'],status_asset_sha256=meta['status_asset_sha256'],local_asset_sha256=meta['local_asset_sha256'],board_access=False,boards_flashed=False,hardware_qualification_pending=True)
    (OUT/'compact-boot-candidate-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS compact boot candidate, exact model receipts, unchanged CLOCK/recovery and sealed assets; unflashed')

if __name__=='__main__':main()
