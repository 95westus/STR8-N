"""Public unknown-history/no-private-escrow route and bounded recovery CPU inputs."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';KIT=ROOT/'output/releases/rc1-2026-10-18-r1/migration';OUT=Q/'rc1-empty-models'
sys.path.insert(0,str(KIT));import runtime as r;import migrate as m;import factory_wdc as f;import recover
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def capture(path,banks,board,guarded=False):
    path.mkdir();files={}
    for n,body in enumerate(banks):
        for suffix in ('','-repeat'):
            name=f'b{n}{suffix}.bin';(path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
    obj=dict(schema=2 if guarded else 1,board=board,repeat_verified=not guarded,model_fixture=True,files=files)
    if guarded:obj.update(assumed_erased_banks=[0,1,2],independently_repeated_banks=[3],device_full_bank_preflight_required=True)
    (path/'capture.json').write_text(json.dumps(obj,indent=2)+'\n')

def main():
    assert not OUT.exists();OUT.mkdir();prior=Q/'bf1-empty-bank-tests-2026-10-18-r1'
    for board,name in [('2609','2609-WDC-to-full-bf1'),('2604','2604-beta4-to-full-bf1')]:
        source=[(prior/name/f'source-b{n}.bin').read_bytes() for n in range(4)];cap=OUT/(board+'-source');capture(cap,source,board,True)
        if board=='2609':f.prepare(cap,KIT,OUT/name,accept_unknown_history=True);f.validate_plan(OUT/name,KIT)
        else:m.prepare_beta4(cap,KIT,OUT/name);m.validate_beta4_plan(OUT/name,KIT)
    folder=OUT/'2609-WDC-to-full-bf1';plan=r.read(folder/'plan.json')
    target=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    source=[(folder/f'source-b{n}.bin').read_bytes() for n in range(4)];current=list(map(bytearray,source))
    # Cut after F/provider/monitor commit but before final preferred-journal activation.
    for n,op in enumerate(plan['transaction']['operations'][:-1]):
        bank,address=op['bank'],op['address'];body=bytearray((folder/f'transfer-{n:02d}.bin').read_bytes())
        if op['commit_address'] is not None:body[op['commit_address']-address]=target[bank][op['commit_address']-0x8000]
        current[bank][address-0x8000:address-0x8000+4096]=body
    cap=OUT/'late-cut-capture';capture(cap,list(map(bytes,current)),'2609')
    recover.prepare_recovery('prepare-forward',KIT,folder,cap,OUT/'2609-factory-late-forward-recovery')
    names=['2609-WDC-to-full-bf1','2604-beta4-to-full-bf1','2609-factory-late-forward-recovery']
    receipt=dict(passed=True,board_access=False,kit_manifest_sha256=sha(KIT/'kit-manifest.json'),
        no_private_history_or_metadata_required=True,plans={n:sha(OUT/n/'plan.json') for n in names},CPU_execution_qualified=False)
    (OUT/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS public empty-bank/no-escrow plans and exact late factory recovery prepared; fresh CPU execution pending')

if __name__=='__main__':main()
