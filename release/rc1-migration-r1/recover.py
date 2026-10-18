"""Portable recovery preparation. Exact-state admission only; no live serial execution."""
import argparse,json
from pathlib import Path
import runtime as r
from migrate import capture,verify_kit,admit_beta4,validate_beta4_plan

def admit_boundary(plan_root,current):
    plan=r.read(plan_root/'plan.json');source=[(plan_root/f'source-b{n}.bin').read_bytes() for n in range(4)];expected=[(plan_root/f'expected-b{n}.bin').read_bytes() for n in range(4)];tx=plan['transaction']
    r.require(r.hashes(source)==plan['source_sha256']==tx['source_sha256'],'Changed source escrow');r.require(r.hashes(expected)==plan['expected_sha256'],'Changed target escrow')
    state=list(map(bytearray,source));candidates=[('before-reservation',list(map(bytes,state)))];erase_count=0
    for index,op in enumerate(tx['operations']):
        bank,address=op['bank'],op['address'];offset=address-0x8000
        if index==0:body=r.record(bytes.fromhex(tx['source_config']),tx['reserved_counts'],tx['sequence_before']+1)
        else:
            body=bytearray((plan_root/f'transfer-{index-1:02d}.bin').read_bytes())
            if op['commit_address'] is not None:body[op['commit_address']-address]=expected[bank][op['commit_address']-0x8000]
            body=bytes(body);r.require(len(body)==4096,'Transfer size')
        r.require(r.sha(body)==op['data_sha256'],'Changed recovery transfer')
        if index:
            state[bank][offset:offset+4096]=b'\xff'*4096;erase_count+=1;candidates.append((f'row-{index}-erased',list(map(bytes,state))))
        state[bank][offset:offset+len(body)]=body
        if op['commit_address'] is not None:
            pending=list(map(bytearray,state));pending[bank][op['commit_address']-0x8000]=255;candidates.append((f'row-{index}-before-commit',list(map(bytes,pending))))
        candidates.append((f'row-{index}-complete',list(map(bytes,state))))
    r.require(list(map(bytes,state))==expected,'Recovery transaction replay mismatch')
    matches=[name for name,banks in candidates if banks==current];r.require(matches,'Unexplained/partial flash state; retain evidence and use the documented programmer route, never force a guessed recovery')
    return plan,source,expected,matches

def prepare_recovery(command,kit,plan_root,capture_root,out):
    r.require(command in ('prepare-forward','prepare-restore-beta4'),'Unknown recovery operation')
    if r.read(plan_root/'plan.json')['route']=='direct-wdcmonv2-to-rc1':
        r.require(command=='prepare-forward','Vendor restoration is not a beta4 restoration; retain original private backups for programmer recovery')
        from factory_recover import prepare
        return prepare(kit,plan_root,capture_root,out)
    plan,source,expected=validate_beta4_plan(plan_root,kit)
    identity,current=capture(capture_root)
    r.require(identity['board']==plan['board'],'Recovery capture belongs to another board')
    _,_,_,matches=admit_boundary(plan_root,current)
    if command=='prepare-forward' and current==expected:
        # A verified complete target needs a durable receipt, not another pair
        # of journal erases merely because the recovery command was requested.
        r.clean_journal(current)
        r.require(not out.exists(),'Recovery output already exists')
        info=dict(route=command,board=identity['board'],status='already-complete',write_required=False,
                  transaction=None,source_sha256=r.hashes(current),expected_sha256=r.hashes(expected),
                  original_plan_sha256=r.sha((plan_root/'plan.json').read_bytes()),
                  current_capture_manifest_sha256=r.sha((capture_root/'capture.json').read_bytes()),
                  kit_manifest_sha256=r.sha((kit/'kit-manifest.json').read_bytes()),
                  admitted_boundaries=matches,live_execution_qualified=False,model_only=True,
                  board_access=False,installation_permitted=False)
        out.mkdir(parents=True);(out/'plan.json').write_text(json.dumps(info,indent=2)+'\n');(out/'.gitignore').write_text('*\n')
        return info
    if command=='prepare-restore-beta4':
        r.require(current==expected,'Source restoration requires a fully completed target, not an interrupted conversion');cfg=admit_beta4(source,kit);desired=source
    else:cfg=bytes.fromhex(plan['transaction']['target_config']);desired=expected
    tx,data,target=r.transaction(current,desired,cfg,'Portable '+command,attested_cut=True);info=r.compose(kit/'template',out,current,tx,data,target);info.update(route=command,board=identity['board'],write_required=True,original_plan_sha256=r.sha((plan_root/'plan.json').read_bytes()),current_capture_manifest_sha256=r.sha((capture_root/'capture.json').read_bytes()),kit_manifest_sha256=r.sha((kit/'kit-manifest.json').read_bytes()),admitted_boundaries=matches,live_execution_qualified=False);(out/'plan.json').write_text(json.dumps(info,indent=2)+'\n');(out/'.gitignore').write_text('*\n');return info

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('prepare-forward','prepare-restore-beta4'));p.add_argument('--kit',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--plan',type=Path,required=True);p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare_recovery(a.command,a.kit,a.plan,a.capture,a.out),indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as error:raise SystemExit('REFUSED: '+str(error))
