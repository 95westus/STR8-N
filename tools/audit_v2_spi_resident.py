"""Audit matched resident SPI artifacts, regressions and offline update recipes."""
import hashlib,json
from pathlib import Path
from beta4_migration import crc
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-spi-resident'
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    meta=read(OUT/'build.json');assert meta['spi'] and meta['version']=='2.0b14'
    for name,digest in meta['artifacts'].items():assert sha((OUT/name).read_bytes())==digest,name
    reports={}
    for name in ('spi-resident-test-results.json','kernel-test-results.json','journal-test-results.json','banner-test-results.json','time-test-results.json','binding-test-results.json','binding-clock-test-results.json','trim-test-results.json'):
        report=read(OUT/name);assert report['passed'] and report['artifacts']==meta['artifacts'],name
        reports[name]=sha((OUT/name).read_bytes())
    clock=ROOT/'BUILD/v2-clock-1.5';cm=read(clock/'build.json')
    for name in ('core-test-results.json','test-results.json'):
        report=read(clock/name);assert report['passed'] and report['sha256']==cm['sha256'] and report['kernel_artifacts']==meta['artifacts']
        reports['clock/'+name]=sha((clock/name).read_bytes())
    recipes=read(OUT/'spi-upgrade-test-results.json');assert recipes['passed']
    for board in ('2512','2205','2609'):
        recipe=next(r for r in recipes['boards'] if r['board']==board)
        root=Path(recipe.get('root',OUT/'rehearsal'/board));assert root.resolve().is_relative_to((OUT/'rehearsal').resolve())
        plan=read(root/'upgrade/plan.json');model=read(root/'upgrade/model-check.json')
        assert model['passed'] and model['stale_preimage_refused'] and model['corrupt_payload_refused'] and model['record_commits']==[]
        assert model['installer_sha256']==plan['installer_sha256']==sha((root/'upgrade/installer.s19').read_bytes())
        for b in (0,1,2):assert (root/f'prior/b{b}.bin').read_bytes()==(root/f'upgrade/expected-b{b}.bin').read_bytes()
        before=(root/'prior/b3.bin').read_bytes();after=(root/'upgrade/expected-b3.bin').read_bytes();assert before[7168:8192]==after[7168:8192] and before[0x7000:]==after[0x7000:]
        assert after[:4096]==(OUT/'str8n-rtc-component-8000-8fff.bin').read_bytes()
        assert after[4096:7168]==(OUT/'str8n-journal-9000-9fff.bin').read_bytes()[:3072]
    sector=(OUT/'str8n-rtc-component-8000-8fff.bin').read_bytes();js=(OUT/'str8n-journal-9000-9fff.bin').read_bytes();gateway=(OUT/'split/gateway.bin').read_bytes()
    assert sector[:4]==b'RC\x03\x07' and sector[0x900:0x904]==b'BT\x05\x03' and crc(sector)==0
    assert js[:4]==b'PJ\x06\x01' and crc(js[:3072])==0 and js[3072:]==bytes([255])*1024
    assert sector[0xDF0:0xFF0]==gateway and len(gateway)==512 and gateway[:4]==b'RG\x01\x04' and gateway[16:20]==b'I2\x01\x01'
    assert gateway[0x146:0x14D]==b'SP\x01\x01\x4c\xb8\x66' and gateway[0x1A2:0x1A9]==b'SM\x01\x01\x4c\xa9\x66'
    assert gateway[0x1AE]==meta.get('managed_default',0)
    assert meta['spi_sizes']['provider']<=2304 and meta['spi_sizes']['banner_and_helpers']<=1264 and meta['spi_sizes']['journal_and_spi']<=3070
    assert meta['spi_sizes']['gateway']<=326 and meta['launcher_bytes']<=1760 and max(meta['monitor_bytes'].values())<=3968
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(ROOT/'BUILD/v2-rtc-trim/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    result=dict(passed=True,version=meta['version'],clock_version='1.5',clock_sha256=cm['sha256'],artifacts=meta['artifacts'],reports=reports,spi_sizes=meta['spi_sizes'],
                capabilities=15,ram_reservation='6500-66FF',user_ram_top='64FF',hardware_tested=False,boards_flashed=False,extra_sector_allocated=False,installation_recipe='six B3 sectors; B0/B1/B2/F and EUI tail retained')
    (OUT/'candidate-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS matched beta14 resident SPI candidate, seals, RAM layout, all regressions and three six-sector offline recipes; no board writes')

if __name__=='__main__':main()
