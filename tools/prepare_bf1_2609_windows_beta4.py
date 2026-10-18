"""Prepare the owner-authorized 2609 beta4 fixture/upgrade; offline only."""
import argparse,json,sys,hashlib,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit',required=True,type=Path)
    p.add_argument('--source-plan',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();sys.path.insert(0,str(a.kit.resolve()))
    import runtime as r
    import migrate
    import legacy_transport as wire
    migrate.verify_kit(a.kit)
    source_info=r.read(a.source_plan/'plan.json')
    banks=[(a.source_plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    r.require(r.hashes(banks)==source_info['expected_sha256'],'Changed prior expected state')
    r.require(not a.out.exists(),'Fresh output directory required');a.out.mkdir(parents=True)
    archive=ROOT/'output/release/str8n-v2-b4.zip'
    r.require(sha(archive.read_bytes())=='4c25bc576cbc32efd04aeea4fe80c68544a50b80685d12bfcf1e44122bacbc14','Published beta4 archive changed')
    desired=list(map(bytearray,banks))
    for s in r.read(a.kit/'layout.json')['segments']:
        if s['bank'] in (1,2):
            start=s['address']-0x8000
            desired[s['bank']][start:start+s['bytes']]=b'\xff'*s['bytes']
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('manifest.json'))
        r.require(manifest['version']=='2.0b4' and manifest['generation']==13,'Wrong historical source')
        for name,digest in manifest['artifacts'].items():
            r.require(sha(z.read(name))==digest,'Historical component digest differs')
        desired[3][:]=b'\xff'*32768
        # Published maintenance storage includes its exact SR header and body.
        from beta4_migration import maintenance_storage
        desired[3][:8192]=maintenance_storage(ROOT/'BUILD/v2-beta4/kit')
        for offset,name in ((0x2000,'slot-a'),(0x3000,'slot-b'),(0x6000,'e000-efff'),(0x7000,'f000-ffff')):
            desired[3][offset:offset+4096]=z.read(f'str8n-v2-b4-{name}.bin')
    _,_,row,_=r.clean_journal(banks)
    tx,data,staged=r.transaction(banks,list(map(bytes,desired)),r.preference(row[8:24],0xa0,13),'2609 owner-local published beta4 staging')
    stage=a.out/'stage-beta4';info=r.compose(a.kit/'template',stage,banks,tx,data,staged)
    info.update(board='2609',route='private-beta4-fixture',source_plan_sha256=sha((a.source_plan/'plan.json').read_bytes()))
    (stage/'plan.json').write_text(json.dumps(info,indent=2)+'\n')
    cap=a.out/'model-only-beta4-capture';cap.mkdir();files={}
    for n,b in enumerate(staged):
        for suffix in ('','-repeat'):
            name=f'b{n}{suffix}.bin';(cap/name).write_bytes(b);files[name]=dict(bytes=len(b),sha256=sha(b))
    (cap/'capture.json').write_text(json.dumps(dict(schema=1,board='2609',model_fixture=True,repeat_verified=True,files=files),indent=2)+'\n')
    escrow=a.out/'private-metadata-escrow.bin';escrow.write_bytes(banks[3][0x1c00:0x2000])
    forward=a.out/'beta4-to-bf1';up=migrate.prepare_beta4(cap,a.kit,forward,escrow)
    migrate.validate_beta4_plan(forward,a.kit)
    # uChess/user areas are outside provider ranges and must survive both legs.
    for bank in (1,2):
        owned=bytearray(32768)
        for s in r.read(a.kit/'layout.json')['segments']:
            if s['bank']==bank:
                off=s['address']-0x8000;owned[off:off+s['bytes']]=b'\1'*s['bytes']
        final=(forward/f'expected-b{bank}.bin').read_bytes()
        r.require(all(owned[i] or banks[bank][i]==staged[bank][i]==final[i] for i in range(32768)),'Unowned content changed')
    receipt=dict(passed=True,preparation_only=True,CPU_execution_qualified=False,hardware_qualified=False,board_access=False,board='2609',
        stage_plan_sha256=sha((stage/'plan.json').read_bytes()),forward_plan_sha256=sha((forward/'plan.json').read_bytes()),
        kit_manifest_sha256=sha((a.kit/'kit-manifest.json').read_bytes()),historical_source_not_for_distribution=True,
        unowned_content_preserved=True,pending=['fresh exact CPU/flash staging and upgrade tests','successful preceding WDC route hardware check','Windows beta4 staging and migration hardware acceptance'])
    (a.out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS exact beta4 staging/portable upgrade preparation, binding and unowned-content preservation; CPU/hardware gates pending')

if __name__=='__main__':main()
