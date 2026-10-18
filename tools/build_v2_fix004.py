"""Separate, unflashed APPS fix; retain the local-only TIME candidate."""
import hashlib,json,shutil,sys
from pathlib import Path
import build_v2_config as compiler
from beta4_migration import crc,s19

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'BUILD/v2-time-local';OUT=ROOT/'BUILD/v2-fix004'
NAME='str8n-v2-recovery-e000-efff'

def patch(text):
    before='''                       LDY #$00
                       LDA (V2_PTR),Y
                        BEQ AP_LIST_NEXT'''
    after='''                       JSR AP_LIST_NAME_OK
                       NOP
                        BCC AP_LIST_NEXT'''
    assert text.count(before)==1;text=text.replace(before,after,1)
    before='''AP_LIST_STATE:         LDY #$1E
                       LDA (V2_PTR),Y
                       CMP #$3F
                        BNE AP_LIST_MISSING'''
    after='''AP_LIST_STATE:         JSR AP_LIST_INSTALLED
                        BCC AP_LIST_MISSING
                       NOP
                       NOP
                       NOP'''
    assert text.count(before)==1;text=text.replace(before,after,1)
    assert text.count('AP_END:')==1
    return text.replace('AP_END:','                       INCLUDE "app-list-check.inc"\nAP_END:',1)

def main():
    shutil.copytree(OLD,OUT,dirs_exist_ok=True)
    # Remove inherited qualification receipts: they describe the parent image.
    for p in OUT.glob('*test-results.json'):p.unlink()
    summary=OUT/'qualification-summary.json'
    if summary.exists():summary.unlink()
    stage=OUT/'apps-source';shutil.copytree(OLD/'asm',stage,dirs_exist_ok=True)
    path=stage/'launcher.asm';path.write_text(patch(path.read_text()))
    shutil.copyfile(ROOT/'src/v2-beta4-launcher/app-list-check.inc',stage/'app-list-check.inc')
    compiler.OUT=OUT;compiler.SOURCE=stage
    cells,symbols=compiler.assemble('launcher',0xE000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    body=compiler.dense_image(cells,0xE000,symbols['AP_END'])
    meta=json.loads((OLD/'build.json').read_text())
    assert len(body)<=0x6E0,('launcher capacity',len(body))
    # Every existing private entry remains fixed, including the service kernel.
    for name,address in meta['launcher'].items():
        if name not in ('AP_END','_END_CODE'):
            assert symbols[name]==address,('private symbol moved',name,address,symbols.get(name))
    image=bytearray((OLD/(NAME+'.bin')).read_bytes());image[:len(body)]=body
    assert image[0x6F0:0x6F4]==b'AT\x01\x08'
    assert image[0x6F4:0x7F4]==b'\xff'*256,'unexpected configured native applications'
    image[0x6F4:0x7F4]=bytes(256)
    image[0x7FE:0x800]=crc(image[:0x7FE]).to_bytes(2,'big')
    image[-2:]=crc(image[:-2]).to_bytes(2,'big')
    assert crc(image[:0x800])==crc(image)==0
    prior=(OLD/(NAME+'.bin')).read_bytes()
    assert image[0x800:0xFFE]==prior[0x800:0xFFE], 'saved-program/status code changed'
    (OUT/(NAME+'.bin')).write_bytes(image)
    (OUT/(NAME+'.s19')).write_bytes(s19(dict(enumerate(image,0xE000)),0xF004))
    # Preserve the exact F/A/B, RTC, CLOCK, storage, status and TIME binaries.
    for name in meta['artifacts']:
        if name!=NAME+'.bin':assert (OUT/name).read_bytes()==(OLD/name).read_bytes(),name
    meta.update(launcher=symbols,launcher_bytes=len(body),apps_listing_fixed=True,
        apps_table_empty=True,apps_installed_validated=True,asset_only_candidate=False,
        hardware_tested=False,board_access=False,boards_flashed=False,
        fixes=sorted(set(meta.get('fixes',[])+['STR8N-004'])))
    meta['artifacts']={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in meta['artifacts']}
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('UNFLASHED STR8N-004: launcher',len(body),'/1760; empty descriptor rows initialized; private ABI and other binaries unchanged',flush=True)

def audit():
    meta=json.loads((OUT/'build.json').read_text());receipts={}
    for name,digest in meta['artifacts'].items():
        assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest,name
    for prefix,folder in (('local','local-display'),('status','boot-status')):
        assert hashlib.sha256((OUT/folder/'asset.bin').read_bytes()).hexdigest()==meta[prefix+'_asset_sha256']
    for name in ('apps','time-local','startup-fifo','compact-boot','board-name-power-fail','storage'):
        path=OUT/(name+'-test-results.json');report=json.loads(path.read_text())
        assert report['passed'] and report['artifacts']==meta['artifacts'],name
        for field in ('local_asset_sha256','status_asset_sha256'):
            if field in report:assert report[field]==meta[field],(name,field)
        receipts[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    image=(OUT/(NAME+'.bin')).read_bytes();assert crc(image)==crc(image[:2048])==0
    summary=dict(passed=True,artifacts=meta['artifacts'],receipts=receipts,
        local_asset_sha256=meta['local_asset_sha256'],status_asset_sha256=meta['status_asset_sha256'],
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            ROOT/'tools/build_v2_fix004.py',ROOT/'tools/test_v2_fix004.py',
            OUT/'apps-source/launcher.asm',OUT/'apps-source/app-list-check.inc')},
        board_access=False,boards_flashed=False,hardware_tested=False)
    (OUT/'qualification-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PASS six exact-image receipts and asset/core hashes; no hardware qualification claimed',flush=True)

if __name__=='__main__':audit() if '--audit' in sys.argv else main()
