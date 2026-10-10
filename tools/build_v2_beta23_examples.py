"""Build readable beta23 65C02 application examples; no board access."""
import argparse,hashlib,json
from pathlib import Path
from beta4_migration import s19,s_record
from build_bank_maint_v2 import long_branches
from build_v2_spi_resident import assemble

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'BUILD/beta23-examples');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'examples/beta23';reports={}
    for name in ('read-time','read-spisram','work-area'):
        folder=out/name;stage=folder/'source';stage.mkdir(parents=True,exist_ok=True)
        (stage/(name+'.asm')).write_text(long_branches((source/(name+'.asm')).read_text()))
        (stage/'example-abi.inc').write_text(long_branches((source/'example-abi.inc').read_text()).replace('BM_LONG_','EXABI_LONG_'))
        body,symbols,_=assemble(stage,name,0x2000,'APP_END',0x2000)
        assert symbols['START']==0x2000 and symbols['APP_END']<=0x3000
        records=s19(dict(enumerate(body,0x2000)),0x2000).splitlines()
        records[0]=s_record('0',0,('STR8-N beta23 example: '+name).encode()).encode()
        image=folder/(name+'.s19');image.write_bytes(b'\n'.join(records)+b'\n');(folder/(name+'.bin')).write_bytes(body)
        report=dict(entry=0x2000,end=symbols['APP_END'],bytes=len(body),symbols=symbols,sha256=hashlib.sha256(body).hexdigest(),s19_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),source_sha256=hashlib.sha256((source/(name+'.asm')).read_bytes()).hexdigest())
        (folder/'build.json').write_text(json.dumps(report,indent=2)+'\n');reports[name]=report
        print('BUILT',name,len(body),'bytes; G 2000',flush=True)
    (out/'build.json').write_text(json.dumps(dict(target='2.0b23 generation 32',examples=reports,shared_source_sha256=hashlib.sha256((source/'example-abi.inc').read_bytes()).hexdigest(),board_access=False),indent=2)+'\n')

if __name__=='__main__':main()
