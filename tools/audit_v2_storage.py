"""Read-only final candidate/model audit. Never opens a board port."""
import hashlib,json,re,subprocess,zipfile
from pathlib import Path
from beta4_migration import crc
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-storage'
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def backup_path(name):
    p=name.lower().replace('\\','/');base=p.rsplit('/',1)[-1]
    return any('/'+part+'/' in '/'+p for part in ('backups','board-backups','qualification','prior')) or bool(re.fullmatch(r'(?:b[0-3](?:-repeat)?|(?:before|after|prior|final|baseline|installed|expected)-b[0-3]|all-banks|full-flash)\.(?:bin|s19)',base)) or base.endswith(('-backup.bin','-readback.bin','-backup.s19','-readback.s19'))

def main():
    meta=read(OUT/'build.json');assert meta['version']=='2.0b17' and meta['storage_services']
    for name,digest in meta['artifacts'].items():assert sha((OUT/name).read_bytes())==digest,name
    e=(OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes();assert crc(e)==crc(e[:0x800])==0 and e[0xE92:0xE96]==b'ED\x01\x03'
    assert max(meta['monitor_bytes'].values())<=3968 and meta['launcher_bytes']<=1760
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(ROOT/'BUILD/v2-spi-resident/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    asset=(OUT/'boot-status/asset.bin').read_bytes();assert len(asset)==2048 and crc(asset)==0 and asset[:4]==b'BS\x01\x02'
    assert sha(asset)==meta['status_asset_sha256'] and meta['status_asset_address']==0xC800 and meta['status_code_bytes']<=2046
    wm=read(OUT/'workspace/build.json');sm=read(OUT/'store/build.json');em=read(OUT/'edu/build.json');mm=read(OUT/'maint/manifest.json')
    assert wm['version']=='1.2' and wm['entry']==0x5000 and wm['api']==0x5003 and wm['end']==0x648B and wm['bytes']==5259
    assert sm['version']=='1.2' and sm['streams'] and sm['relocated_end']<0x7800 and sm['data_bytes']<=256
    body=(OUT/'store/sram.bin').read_bytes();assert crc(body)==0 and sha(body)==sm['sha256']
    assert sm['symbols']['SOURCE_BYTE']==0x7B90 and meta['worker']['V2W_END']<=0x7B90
    assert sm['symbols']['TRANSFER']>=0x6C06
    assert mm['version']=='1.8' and mm['end']<=0x5000 and mm['storage_bytes']==12288
    stored=(OUT/mm['storage_file']).read_bytes();n=int.from_bytes(stored[6:8],'little');assert n==mm['bytes'] and sha(stored[24:24+n])==mm['program_sha256'] and sha(stored)==mm['storage_sha256']
    assert em['version']=='1.2' and em['bytes']+24<=0x280 and em['sha256']==sha((OUT/'edu/edu.bin').read_bytes())
    assert wm['sha256']==sha((OUT/'workspace/workspace.bin').read_bytes())
    reports={}
    for name in ('storage-test-results.json','status-test-results.json','kernel-test-results.json','spi-resident-test-results.json','trim-test-results.json','journal-test-results.json','banner-test-results.json','time-test-results.json','binding-test-results.json','binding-clock-test-results.json'):
        r=read(OUT/name);assert r['passed'] and r['artifacts']==meta['artifacts'],name;reports[name]=sha((OUT/name).read_bytes())
    r=read(OUT/'storage-test-results.json');assert len(r['checks'])>=9 and r['maint_sha256']==mm['program_sha256'] and r['store_sha256']==sm['sha256'] and r['asset_sha256']==sha(asset)
    assert '$0200-$64FF' in r['checks'][0]
    assert not r['board_access'] and not r['boards_flashed']
    assert read(OUT/'status-test-results.json')['edu_sha256']==em['sha256']
    r=read(OUT/'store/test-results.json');assert r['passed'] and r['artifacts']==meta['artifacts'] and r['store_sha256']==sm['sha256']
    for name in ('test-results.json','guard-test-results.json','format-test-results.json','integration-test-results.json','console-test-results.json'):
        r=read(OUT/'workspace'/name);assert r['passed'] and r['workspace_sha256']==wm['sha256'] and r['resident_artifacts']==meta['artifacts'],name
    r=read(OUT/'hardware-client/test-results.json');assert r['passed'] and r['resident_artifacts']==meta['artifacts']
    assert any(x['operation']=='query_with_full_lower_application' for x in read(OUT/'workspace/integration-test-results.json')['measurements'])
    cm=read(OUT/'clock/build.json')
    for name in ('core-test-results.json','test-results.json'):
        r=read(OUT/'clock'/name);assert r['passed'] and r['kernel_artifacts']==meta['artifacts'] and r['sha256']==cm['sha256'],name
    # Proposed paired record layout, including two existing demo reservations.
    ranges=[(1,0x8000,0xB000,'MAINT'),(2,0xA000,0xA000+24+sm['bytes'],'SRAM'),(2,0xB000,0xB000+24+wm['bytes'],'WORK'),(2,0xC540,0xC572,'DEMO2'),(2,0xC580,0xC580+24+em['bytes'],'EDU'),(2,0xC800,0xD000,'asset'),(2,0xAF80,0xAF9E,'relocated SDEMO')]
    for i,a in enumerate(ranges):
        for b in ranges[i+1:]:assert a[0]!=b[0] or a[2]<=b[1] or b[2]<=a[1],(a,b)
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0');assert not [p for p in tracked if backup_path(p)]
    history=subprocess.check_output(['git','log','--all','--name-only','--pretty=format:'],cwd=ROOT).decode().splitlines();assert not [p for p in history if backup_path(p)]
    for p in (ROOT/'output/release').glob('*.zip'):
        with zipfile.ZipFile(p) as z:assert not [n for n in z.namelist() if backup_path(n)],p.name
    subprocess.run(['git','check-ignore','--quiet','BUILD/v2-storage/build.json'],cwd=ROOT,check=True)
    sources=['tools/build_v2_storage.py','tools/build_v2_status.py','tools/build_v2_storage_maint.py','tools/build_v2_sram_store.py','tools/build_v2_workspace.py','tools/build_v2_edu_utility.py','tools/v2-spi/storage-maint.inc','tools/v2-spi/storage-services.inc','tools/v2-spi/sram-stream.asm']
    result=dict(passed=True,version=meta['version'],artifacts=meta['artifacts'],reports=reports,sources={p:sha((ROOT/p).read_bytes()) for p in sources},work_sha256=wm['sha256'],store_sha256=sm['sha256'],maint_sha256=mm['program_sha256'],asset_sha256=sha(asset),proposed_ranges=ranges,board_access=False,boards_flashed=False,permanent_ram_added=0,backups_in_index_history_or_release=False)
    (OUT/'storage-candidate-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS beta17 matched storage/WORK/SRAM/status/RTCC models, placements and seals; fixed F preserved; no board access or tracked backups')

if __name__=='__main__':main()
