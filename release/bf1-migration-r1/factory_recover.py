"""Exact-boundary forward recovery for a saved direct-WDC plan; no ports."""
import json
from pathlib import Path
import runtime as r
import migrate as m
import factory_wdc as f

def prepare(kit,original,capture,out):
    plan,source,expected=f.validate_plan(original,kit);identity,current=m.capture(capture)
    r.require(identity['board']==plan['board'],'Factory recovery capture belongs to another board')
    state=list(map(bytearray,source));matches=[]
    def match(name):
        if list(map(bytes,state))==current:matches.append(name)
    match('original-source')
    for n,op in enumerate(plan['transaction']['operations']):
        body=bytearray((original/f'transfer-{n:02d}.bin').read_bytes());bank=op['bank'];offset=op['address']-0x8000
        state[bank][offset:offset+4096]=b'\xff'*4096;match(f'row-{n}-erased')
        state[bank][offset:offset+4096]=body;match(f'row-{n}-before-commit')
        if op['commit_address'] is not None:state[bank][op['commit_address']-0x8000]=expected[bank][op['commit_address']-0x8000]
        match(f'row-{n}-complete')
    r.require(list(map(bytes,state))==expected,'Factory recovery replay differs from target')
    r.require(matches,'Unknown partial factory state; retain evidence and use external programmer recovery')
    info=dict(route='factory-forward-recovery',board=identity['board'],admitted_boundaries=matches,
        original_plan_sha256=r.sha((original/'plan.json').read_bytes()),capture_manifest_sha256=r.sha((capture/'capture.json').read_bytes()),
        kit_manifest_sha256=r.sha((kit/'kit-manifest.json').read_bytes()),installation_permitted=False,model_only=True,
        live_execution_qualified=False,board_access=False)
    if current==expected:
        r.require(not out.exists(),'Output already exists');out.mkdir(parents=True)
        info.update(write_required=False,status='already-complete',transaction=None)
    else:
        # The generic preserving recovery requires a valid bf1 A/B fallback and
        # an extant tracked journal. Early WDC cuts with neither are refused;
        # do not disguise programmer-only recovery as a safe serial operation.
        tx,data,target=r.transaction(current,expected,bytes.fromhex(plan['transaction']['target_config']),
            'Bound factory forward recovery with valid bf1 fallback',attested_cut=True)
        composed=r.compose(kit/'template',out,current,tx,data,target);info.update(composed,write_required=True)
        info['route']='factory-forward-recovery';info['board']=identity['board']
    (out/'plan.json').write_text(json.dumps(info,indent=2)+'\n');(out/'.gitignore').write_text('*\n')
    return info
