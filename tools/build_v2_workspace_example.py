"""Build the small metadata-cache client for WORK; no board writes."""
import argparse,hashlib,json
from pathlib import Path
from build_v2_spi_resident import assemble
from build_bank_maint_v2 import long_branches
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-spi-resident/workspace/example'
def main():
    global OUT
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,default=ROOT/'BUILD/v2-spi-resident');a=p.parse_args();OUT=a.build.resolve()/'workspace/example'
    wm=json.loads((OUT.parent/'build.json').read_text())
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    src=ROOT/'tools/v2-spi/workspace-example.asm';text=src.read_text().replace('$4006',f'${wm["entry"]+6:04X}').replace('$4003',f'${wm["api"]:04X}')
    if wm['version']=='1.2':text=text.replace('DB "WK",1,1','DB "WK",1,2')
    (stage/src.name).write_text(long_branches(text))
    body,symbols,_=assemble(stage,'workspace-example',0x2000,'APP_END',0x2000)
    assert symbols['APP_END']<=0x2400
    (OUT/'example.bin').write_bytes(body);(OUT/'example.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    (OUT/'build.json').write_text(json.dumps(dict(bytes=len(body),symbols=symbols,sha256=hashlib.sha256(body).hexdigest(),
        source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),cache_bytes=16,request_bytes=32,backing_bytes=64),indent=2)+'\n')
    print('Metadata client:',len(body),'bytes; 16-byte cache for 64-byte workspace table')
if __name__=='__main__':main()
