"""Build the W65C02S workspace library/utility; no board access."""
import argparse,hashlib,json
from pathlib import Path
from build_v2_spi_resident import assemble
from build_bank_maint_v2 import long_branches
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-spi-resident/workspace'

def main():
    global OUT
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,default=ROOT/'BUILD/v2-spi-resident');p.add_argument('--base',type=lambda v:int(v,0),default=0x4000);a=p.parse_args()
    OUT=a.build.resolve()/'workspace';base=a.base;assert base in (0x4000,0x5000)
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    src=ROOT/'tools/v2-spi/workspace.asm'
    text=src.read_text().replace('CMP #$40','CMP #>START');version='1.2' if base==0x5000 else '1.1'
    if version=='1.2':text=text.replace('DB "WK",1,1','DB "WK",1,2').replace('TITLE DB "WORK 1.1"','TITLE DB "WORK 1.2"')
    (stage/src.name).write_text(long_branches(text))
    body,symbols,_=assemble(stage,'workspace',base,'APP_END',base+6)
    assert symbols['APP_END']<=0x6500,hex(symbols['APP_END'])
    (OUT/'workspace.bin').write_bytes(body);(OUT/'workspace.s19').write_bytes(s19(dict(enumerate(body,base)),base))
    meta=dict(version=version,entry=base,api=base+3,end=symbols['APP_END'],bytes=len(body),symbols=symbols,
        sha256=hashlib.sha256(body).hexdigest(),source_sha256=hashlib.sha256(src.read_bytes()).hexdigest())
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('WORK '+version+':',len(body),'bytes; API',hex(base+3),'; end',hex(symbols['APP_END']-1))

if __name__=='__main__':main()
