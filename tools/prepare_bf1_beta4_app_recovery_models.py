"""New app-complete beta4 forward-cut and historical-restoration CPU plans."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';KIT=ROOT/'tmp/bf1-distribution-r16/migration'
sys.path.insert(0,str(KIT));import runtime as r;import recover
OUT=Q/'bf1-public-beta4-recovery-models-2026-10-18-r1';ORIGINAL=Q/'bf1-public-empty-bank-models-2026-10-18-r1/2604-beta4-to-full-bf1'
def capture(path,banks):
    path.mkdir();files={}
    for n,body in enumerate(banks):
        for suffix in ('','-repeat'):
            name=f'b{n}{suffix}.bin';(path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
    (path/'capture.json').write_text(json.dumps(dict(schema=1,board='2604',repeat_verified=True,model_fixture=True,files=files)))
def main():
    assert not OUT.exists();OUT.mkdir();plan=r.read(ORIGINAL/'plan.json')
    source=[(ORIGINAL/f'source-b{n}.bin').read_bytes() for n in range(4)];target=[(ORIGINAL/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    complete=OUT/'completed-target';capture(complete,target)
    recover.prepare_recovery('prepare-restore-beta4',KIT,ORIGINAL,complete,OUT/'beta4-original-restoration')
    current=list(map(bytearray,source));tx=plan['transaction'];op=tx['operations'][0]
    reserved=r.record(bytes.fromhex(tx['source_config']),tx['reserved_counts'],tx['sequence_before']+1)
    current[op['bank']][op['address']-0x8000:op['address']-0x8000+len(reserved)]=reserved
    op=tx['operations'][1];current[op['bank']][op['address']-0x8000:op['address']-0x8000+4096]=b'\xff'*4096
    cut=OUT/'first-erased-cut';capture(cut,list(map(bytes,current)))
    recover.prepare_recovery('prepare-forward',KIT,ORIGINAL,cut,OUT/'beta4-interrupted-forward')
    names=['beta4-original-restoration','beta4-interrupted-forward']
    (OUT/'preparation.json').write_text(json.dumps(dict(passed=True,board_access=False,plans={n:r.sha((OUT/n/'plan.json').read_bytes()) for n in names}),indent=2)+'\n')
    print('PASS two fresh app-complete beta4 recovery plans prepared')
if __name__=='__main__':main()
