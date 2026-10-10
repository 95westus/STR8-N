"""Read-only audit of the isolated, unflashed boot/EDU display candidate."""
import hashlib,json
from pathlib import Path
from beta4_migration import crc
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-status'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())
def main():
    m=read(OUT/'build.json');assert m['version']=='2.0b16' and m['status_banner'] and m['edu_mode']
    for name,digest in m['artifacts'].items():assert sha((OUT/name).read_bytes())==digest,name
    asset=(OUT/'boot-status/asset.bin').read_bytes();assert len(asset)==1024 and asset[:4]==b'BS\x01\x01' and crc(asset)==0 and sha(asset)==m['status_asset_sha256']
    assert m['status_code_bytes']<=1022 and m['status_asset_address']==0xC900 and m['status_ram']=='7000-73FF temporary staging'
    e=(OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes();assert crc(e)==0 and crc(e[:0x800])==0 and e[0xE92:0xE96]==b'ED\x01\x02'
    assert m['edu_boot_bytes']<=110 and m['edu_hook_bytes']<=254 and m['launcher_bytes']<=1760 and max(m['monitor_bytes'].values())<=3968
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(ROOT/'BUILD/v2-spi-resident/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    reports={}
    for name in ('status-test-results.json','kernel-test-results.json','spi-resident-test-results.json','banner-test-results.json','journal-test-results.json','time-test-results.json','binding-test-results.json','binding-clock-test-results.json','trim-test-results.json'):
        r=read(OUT/name);assert r['passed'] and r['artifacts']==m['artifacts'],name;reports[name]=sha((OUT/name).read_bytes())
    status=read(OUT/'status-test-results.json');assert status['asset_sha256']==sha(asset) and not status['board_access'] and not status['boards_flashed']
    em=read(OUT/'edu/build.json');assert em['version']=='1.1' and em['sha256']==sha((OUT/'edu/edu.bin').read_bytes())==status['edu_sha256']
    assert em['bytes']+24<=0x300 and em['end']<=0x2400
    for name in ('core-test-results.json','test-results.json'):
        r=read(OUT/'clock'/name);assert r['passed'] and r['kernel_artifacts']==m['artifacts'] and r['sha256']==read(OUT/'clock/build.json')['sha256']
    wm=read(OUT/'workspace/build.json')
    for name in ('test-results.json','guard-test-results.json','format-test-results.json','integration-test-results.json','console-test-results.json'):
        r=read(OUT/'workspace'/name);assert r['passed'] and r['workspace_sha256']==wm['sha256'] and r['resident_artifacts']==m['artifacts'],name
    hc=read(OUT/'hardware-client/test-results.json');assert hc['passed'] and hc['resident_artifacts']==m['artifacts']
    sources=('tools/v2-spi/boot-status.asm','tools/v2-spi/status-mode-init.asm','tools/v2-spi/status-loader.asm','tools/v2-spi/edu.asm','tools/build_v2_status.py','tools/build_v2_edu_utility.py')
    result=dict(passed=True,version=m['version'],edu_version=em['version'],artifacts=m['artifacts'],asset_sha256=sha(asset),edu_sha256=em['sha256'],sources={name:sha((ROOT/name).read_bytes()) for name in sources},reports=reports,
        board_access=False,boards_flashed=False,new_sector_allocated=False,permanent_user_ram_added=0,asset_bytes=len(asset),status_code_bytes=m['status_code_bytes'],edu_bytes=em['bytes'],staging_ram=m['status_ram'])
    (OUT/'status-candidate-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS isolated beta16/EDU1.1 status candidate, seals/placement, exact format, read-only metadata/epoch/transfer buffers and all matched regressions; no board access/flashing')
if __name__=='__main__':main()
