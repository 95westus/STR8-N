"""Portable offline rc1 migration preparation. Live execution remains qualification-gated."""
import argparse,json,hashlib,re
from pathlib import Path
import runtime as r
import legacy_transport as bridge

def safe(root,name):
    root=Path(root).resolve();p=(root/name).resolve()
    r.require(not Path(name).is_absolute() and p.is_relative_to(root),'Escaping file path')
    return p

def verify_kit(kit):
    kit=Path(kit).resolve();manifest=r.read(kit/'kit-manifest.json')
    r.require(manifest['candidate_id']=='rc1' and manifest['version']=='2.0rc1' and manifest['generation']==49,'Wrong kit')
    for name,info in manifest['files'].items():
        p=safe(kit,name);data=p.read_bytes();r.require(len(data)==info['bytes'] and r.sha(data)==info['sha256'],'Changed kit file: '+name)
    return manifest

def capture_identity(m):
    board_identity(m['board'])
    if m['schema']==1:
        r.require(m['repeat_verified'] is True,'A repeated preserving capture is required')
    else:
        r.require(m['schema']==2 and m['repeat_verified'] is False and m['assumed_erased_banks']==[0,1,2]
            and m['independently_repeated_banks']==[3] and m['device_full_bank_preflight_required'] is True,
            'Unsupported guarded empty-bank source admission')
    return m

def capture(path):
    path=Path(path).resolve();m=r.read(path/'capture.json')
    capture_identity(m)
    for name,info in m['files'].items():
        p=safe(path,name);data=p.read_bytes();r.require(len(data)==info['bytes'] and r.sha(data)==info['sha256'],'Capture mismatch: '+name)
    banks=[]
    for n in range(4):
        name=f'b{n}.bin';repeat=f'b{n}-repeat.bin';r.require(name in m['files'] and repeat in m['files'],'Missing complete repeated bank capture')
        data=(path/name).read_bytes();r.require(len(data)==32768 and data==(path/repeat).read_bytes(),'Bank capture mismatch');banks.append(data)
        if m['schema']==2 and n<3:r.require(data==b'\xff'*32768,'Guarded source assumes only fully erased B0/B1/B2')
    return m,banks

def board_identity(board):
    r.require(isinstance(board,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',board),
              'Explicit board identity required (1-64 ASCII letters/digits/._-)')
    return board

def admit_beta4(banks,kit):
    profile=r.read(kit/'profiles.json')['beta4']
    for first,last,key in ((0,0x2000,'maintenance_sha256'),(0x2000,0x3000,'monitor_A_sha256'),(0x3000,0x4000,'monitor_B_sha256'),(0x6000,0x7000,'E_sha256'),(0x7000,0x8000,'F_sha256')):
        r.require(r.sha(banks[3][first:last])==profile[key],'Not the exact published beta4 core/monitor/MAINT profile')
    for s in r.read(kit/'layout.json')['segments']:
        if s['bank'] in (1,2):
            start=s['address']-0x8000;r.require(banks[s['bank']][start:start+s['bytes']]==b'\xff'*s['bytes'],'Occupied provider destination; preserve user data and refuse')
    _,_,row,_=r.clean_journal(banks);cfg=row[8:24]
    # Empty published preference or a valid beta4 A/B preference only.
    r.require(cfg[7:13]==bytes(6) or cfg[7:13] in (b'P\xa0\x0d\0\0\0',b'P\xb0\x0d\0\0\0'),'Unknown beta4 monitor preference')
    return cfg

def beta4_target(banks,kit,escrow=None):
    cfg=admit_beta4(banks,kit);desired=list(map(bytearray,banks))
    for s in r.read(kit/'layout.json')['segments']:
        start=s['address']-0x8000;body=(kit/'payload'/s['file']).read_bytes();desired[s['bank']][start:start+s['bytes']]=body[s['offset']:s['offset']+s['bytes']]
    desired[3][0x2000:0x3000]=(kit/'payload/str8n-v2-recovery-slot-a0.bin').read_bytes()
    if escrow is not None:
        r.require(len(escrow)==1024,'Metadata escrow length');desired[3][0x1c00:0x2000]=escrow
    from factory_wdc import place_uchess
    place_uchess(desired,(kit/'applications/uchess-record.bin').read_bytes())
    return cfg,list(map(bytes,desired))

def prepare_beta4(capture_root,kit,out,metadata_escrow=None):
    verify_kit(kit);identity,banks=capture(capture_root)
    escrow=Path(metadata_escrow).read_bytes() if metadata_escrow is not None else None
    cfg,desired=beta4_target(banks,kit,escrow)
    tx,data,expected=r.transaction(banks,list(map(bytes,desired)),r.preference(cfg,0xb0,49),'Portable published beta4 to rc1')
    info=r.compose(kit/'template',out,banks,tx,data,expected);info.update(route='beta4-to-rc1',capture_manifest_sha256=r.sha((Path(capture_root)/'capture.json').read_bytes()),kit_manifest_sha256=r.sha((kit/'kit-manifest.json').read_bytes()),board=identity['board'],live_execution_qualified=False)
    (out/'source-capture.json').write_bytes((Path(capture_root)/'capture.json').read_bytes())
    info['binding_schema']=1
    info['metadata_escrow']=None
    if escrow is not None:
        (out/'metadata-escrow.bin').write_bytes(escrow)
        info['metadata_escrow']=dict(file='metadata-escrow.bin',bytes=1024,sha256=r.sha(escrow))
    (out/'plan.json').write_text(json.dumps(info,indent=2)+'\n');(out/'.gitignore').write_text('*\n');return info

def validate_beta4_plan(plan_root,kit):
    """Re-derive admitted target/transaction; saved plan hashes alone are insufficient."""
    verify_kit(kit);plan_root=Path(plan_root).resolve();plan=r.read(plan_root/'plan.json')
    r.require(plan['binding_schema']==1 and plan['route']=='beta4-to-rc1','Unsupported or unbound original plan')
    board_identity(plan['board'])
    r.require(plan['live_execution_qualified'] is False and plan['installation_permitted'] is False,
              'Prototype plan must not claim live installation qualification')
    r.require(plan['kit_manifest_sha256']==r.sha((kit/'kit-manifest.json').read_bytes()),'Recovery kit differs from original plan')
    original=(plan_root/'source-capture.json').read_bytes()
    r.require(r.sha(original)==plan['capture_manifest_sha256'],'Changed original capture identity/manifest')
    identity=capture_identity(json.loads(original));r.require(identity['board']==plan['board'],
                                          'Original capture/plan board identity mismatch')
    source=[(plan_root/f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected=[(plan_root/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    r.valid_banks(source);r.valid_banks(expected)
    r.require(r.hashes(source)==plan['source_sha256']==plan['transaction']['source_sha256'],'Changed source escrow')
    for n,body in enumerate(source):
        if identity['schema']==2 and n<3:r.require(body==b'\xff'*32768,'Guarded source bank changed')
        for suffix in ('','-repeat'):
            info=identity['files'][f'b{n}{suffix}.bin']
            r.require(info['bytes']==32768 and info['sha256']==r.sha(body),'Original capture/source mismatch')
    escrow=None
    if plan['metadata_escrow'] is not None:
        info=plan['metadata_escrow'];escrow=safe(plan_root,info['file']).read_bytes()
        r.require(info['bytes']==1024 and len(escrow)==1024 and r.sha(escrow)==info['sha256'],'Changed metadata escrow')
    cfg,desired=beta4_target(source,kit,escrow)
    tx,data,replayed=r.transaction(source,desired,r.preference(cfg,0xb0,49),'Portable published beta4 to rc1')
    r.require(plan['transaction']==tx,'Saved transaction differs from admitted route')
    r.require(expected==replayed and r.hashes(expected)==plan['expected_sha256'],'Saved target differs from admitted route')
    r.require(plan['template_manifest_sha256']==r.sha((kit/'template/manifest.json').read_bytes()),'Changed template binding')
    r.require(plan['installer_sha256']==r.sha((plan_root/'installer-model-only.s19').read_bytes()),'Changed saved installer')
    for index,(op,body) in enumerate(zip(tx['operations'][1:],data[1:])):
        transfer=bytearray(body)
        if op['commit_address'] is not None:transfer[op['commit_address']-op['address']]=255
        r.require((plan_root/f'transfer-{index:02d}.bin').read_bytes()==bytes(transfer),'Changed saved transfer')
    return plan,source,expected

def inspect_wdc(capture_root,kit):
    from factory_wdc import profile_for
    verify_kit(kit);identity,banks=capture(capture_root);profile=profile_for(banks,kit)
    return dict(board=identity['board'],source='wdcmonv2',source_cpu=profile['cpu'],source_sha256=r.sha(banks[3]),requested_target='2.0rc1',direct_migration_required=True,direct_migration_qualified=False,board_access=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('verify-kit','prepare-beta4','inspect-wdc'));p.add_argument('--kit',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--capture',type=Path);p.add_argument('--out',type=Path);p.add_argument('--metadata-escrow',type=Path);a=p.parse_args();verify_kit(a.kit)
    if a.command=='verify-kit':print('PASS kit hashes; no port opened');return
    r.require(a.capture,'--capture is required')
    if a.command=='inspect-wdc':print(json.dumps(inspect_wdc(a.capture,a.kit),indent=2));return
    r.require(a.out,'A new --out is required');result=prepare_beta4(a.capture,a.kit,a.out,a.metadata_escrow);print(json.dumps(result,indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as error:raise SystemExit('REFUSED: '+str(error))
