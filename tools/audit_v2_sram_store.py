"""Bind SRAM utility qualification to the linked images and resident candidate."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-spi-resident';STORE=OUT/'store'
read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    meta=read(STORE/'build.json');test=read(STORE/'test-results.json');resident=read(OUT/'build.json')
    qualified=read(OUT/'candidate-check.json')
    assert qualified['passed'] and qualified['artifacts']==resident['artifacts']
    assert test['passed'] and test['artifacts']==resident['artifacts'] and test['store_sha256']==meta['sha256']
    assert meta['source_sha256']==sha((ROOT/'tools/v2-spi/sram-store.asm').read_bytes())
    image=(STORE/'sram.bin').read_bytes();core=(STORE/'store-core.bin').read_bytes();data=(STORE/'store-data.bin').read_bytes()
    pages=(len(core)+255)//256
    assert sha(image)==meta['sha256'] and image[64:64+len(core)]==core
    assert image[64+pages*256:64+pages*256+len(data)]==data
    if meta.get('aux_bytes'):
        aux=(STORE/'store-layout.bin').read_bytes()
        assert len(aux)==meta['aux_bytes']<=256 and image[64+pages*256+256:64+pages*256+256+len(aux)]==aux
        assert meta['aux_source_sha256']==sha((ROOT/'tools/v2-spi/sram-layout.asm').read_bytes())
    assert len(core)==meta['core_bytes']<=3072 and len(data)==meta['data_bytes']<=256
    assert meta['entry']==0x4000 and meta['load_end']<0x6500 and meta['relocated_end']<0x7800
    assert resident['managed_default']==1 and (OUT/'split/gateway.bin').read_bytes()[0x1AE]==1
    result=dict(passed=True,store_sha256=meta['sha256'],resident_artifacts=resident['artifacts'],
        test_report_sha256=sha((STORE/'test-results.json').read_bytes()),core_bytes=len(core),data_bytes=len(data),
        saved_bytes=len(image),flash_record_bytes=len(image)+24,program_payload_bytes=63488,workspace_bytes=65504,
        max_stack_bytes=test['max_stack_bytes'],board_access=False,boards_flashed=False)
    (STORE/'candidate-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS matched named SRAM utility and protected resident candidate; no board access')

if __name__=='__main__':main()
