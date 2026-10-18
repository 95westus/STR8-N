"""Rebuild only the sealed beta24 local helper; preserve frozen original build."""
import hashlib,json,shutil
from pathlib import Path
from build_v2_spi_resident import assemble
from beta4_migration import crc

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'BUILD/v2-board-name'
OUT=ROOT/'BUILD/v2-board-name-fix006'

def main():
    shutil.copytree(OLD,OUT)
    path=OUT/'local-display/source/local-display.asm'
    text=path.read_text();assert text.count('        JSR BN_SHOW\n')==1
    text=text.replace('        JSR BN_SHOW\n','        JSR BN_READ\n        LDA BN_LENGTH\n        BEQ BN_BOOT_DONE\n        JSR $7E7F\n        JSR BN_SHOW\n',1)
    path.write_text(text)
    body,symbols,_=assemble(path.parent,'local-display',0x6700,'APP_END',0x6707)
    assert len(body)<=1790
    asset=body+b'\xff'*(1790-len(body));asset+=crc(asset).to_bytes(2,'big');assert crc(asset)==0
    (OUT/'local-display/asset.bin').write_bytes(asset)
    meta=json.loads((OUT/'build.json').read_text())
    meta.update(local_symbols=symbols,local_code_bytes=len(body),local_asset_sha256=hashlib.sha256(asset).hexdigest(),fixes=['STR8N-006'])
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    for name in meta['artifacts']:assert (OUT/name).read_bytes()==(OLD/name).read_bytes(),name
    for name in ('boot-status/asset.bin','clock/clock.bin','maint/board-name.bin'):
        assert (OUT/name).read_bytes()==(OLD/name).read_bytes(),name
    print('FIX006 sealed helper',len(body),'bytes; all other firmware/storage unchanged',flush=True)

if __name__=='__main__':main()
