"""Direct exact-profile WDC-to-rc1 bootstrap planning; no vendor bytes in this module.

Outputs are owner-local captures/plans, never public release assets. No ports.
"""
import json
from pathlib import Path
import runtime as r
import migrate as m
import legacy_transport as wire


def profile_for(banks,kit):
    digest=r.sha(banks[3]);profiles=r.read(kit/'profiles.json')
    matches=[p for name,p in profiles.items() if name.startswith('wdcmonv2') and p.get('source_sha256')==digest]
    r.require(len(matches)==1,'Unknown factory WDC source; exact complete source profile required')
    return matches[0]


def place_uchess(banks,record):
    r.require(record[:4]==b'SR\1?' and record[8:24]==b'UCHESS'.ljust(16,b'\0') and len(record)==24+int.from_bytes(record[6:8],'little'),'Bad UCHESS record')
    low=bytes(banks[1][:0x3000]);existing=low.find(record)
    if existing>=0:return None
    for offset in range(0,0x3000-24):
        if low[offset:offset+4]==b'SR\1?' and low[offset+8:offset+24]==b'UCHESS'.ljust(16,b'\0'):
            raise ValueError('Different UCHESS already present; preserve it and resolve explicitly')
    for sector in range(3):
        for offset in range(sector*4096,(sector+1)*4096-len(record)+1,256):
            if low[offset:offset+len(record)]==b'\xff'*len(record):
                banks[1][offset:offset+len(record)]=record
                return (1,0x8000+offset+3)
    raise ValueError('No erased single-sector UCHESS extent; user programs preserved')


def target(source,kit,metadata=None):
    desired=list(map(bytearray,source));desired[3][:]=b'\xff'*32768
    for segment in r.read(kit/'layout.json')['segments']:
        bank,address,size=segment['bank'],segment['address'],segment['bytes'];offset=address-0x8000
        payload=(kit/'payload'/segment['file']).read_bytes()[segment['offset']:segment['offset']+size]
        r.require(len(payload)==size,'Short target payload')
        if bank in (1,2):
            prior=source[bank][offset:offset+size]
            r.require(prior==b'\xff'*size or prior==payload,'Occupied provider destination; preserve user data and refuse')
        desired[bank][offset:offset+size]=payload
    desired[3][0x2000:0x3000]=(kit/'payload/str8n-v2-recovery-slot-a0.bin').read_bytes()
    if metadata is not None:
        r.require(len(metadata)==1024,'Metadata escrow must be 1024 bytes')
        desired[3][0x1c00:0x2000]=metadata
    commit=place_uchess(desired,(kit/'applications/uchess-record.bin').read_bytes())
    return desired,commit


def transaction(source,desired,config,counts,sequence,app_commit):
    r.valid_banks(source);r.valid_banks(desired)
    r.require(source[0]==desired[0],'B0 replacement forbidden')
    r.require(sequence<=0xfffffffd,'Journal sequence exhausted')
    stage_config=bytearray(config);stage_config[7:13]=bytes(6);stage_config[14:]=wire.config_sum(stage_config)
    final_config=r.preference(config,0xa0,49)
    changed=[]
    for bank in range(1,4):
        for sector in range(8,16):
            if bank==3 and sector in (12,13):continue
            offset=(sector-8)*4096
            if source[bank][offset:offset+4096]!=desired[bank][offset:offset+4096]:changed.append((bank,sector))
    order={8:0,9:1,11:2,10:3,14:4,15:5}
    changed.sort(key=lambda pair:(pair[0]==3,pair[0],-pair[1] if pair[0]!=3 else order[pair[1]]))
    erases=[(3,13)]+changed+[(3,12)];reserved=list(counts)
    for bank,sector in erases:
        index=bank*8+sector-8;r.require(reserved[index]<0xffffff,'Wear counter exhausted');reserved[index]+=1
    # Validate count/config representation before any output or device action.
    first=r.record(bytes(stage_config),reserved,sequence+1)+b'\xff'*3968
    final=r.record(final_config,reserved,sequence+2)+b'\xff'*3968
    state=list(map(bytearray,source));operations=[];data=[]
    def append(kind,bank,address,body,commit=None):
        before=r.hashes(state);off=address-0x8000;state[bank][off:off+4096]=body
        operations.append(dict(kind=kind,bank=bank,address=address,commit_address=commit,
            source_sha256=before,after_sha256=r.hashes(state),data_sha256=r.sha(body)))
        data.append(body)
    append('initialize-tracked-journal',3,0xd000,first,0xd07f)
    for bank,sector in changed:
        offset=(sector-8)*4096;body=bytes(desired[bank][offset:offset+4096]);commit=None
        if bank==3 and sector in (10,11) and body[:3]==b'MI\1':commit=(sector<<12)+31
        if body[:4]==b'SR\1?':commit=(sector<<12)+3
        if app_commit and app_commit[0]==bank and app_commit[1]>>12==sector:commit=app_commit[1]
        append('payload-sector',bank,sector<<12,body,commit)
    append('activate-journal',3,0xc000,final,0xc07f)
    r.require(len(operations)<=24,'Too many bootstrap transfers')
    return dict(profile='factory-no-prior-journal',source_sha256=r.hashes(source),expected_sha256=r.hashes(state),
        operations=operations,planned_erase_order=[list(v) for v in erases],counts_before=list(counts),reserved_counts=reserved,
        sequence_before=sequence,sequence_after=sequence+2,source_config=bytes(stage_config).hex(),target_config=final_config.hex(),
        no_lifetime_wear_claim=True,model_only=True,installation_permitted=False),data,list(map(bytes,state))


def render_installer(kit,source,tx,data,expected,cpu):
    r.require(cpu in ('65C02','65C816'),'Unsupported source CPU')
    template=kit/'factory-template';mf=r.read(template/'manifest.json');raw=(template/'bootstrap-template.s19').read_bytes()
    r.require(mf['passed'] and r.sha(raw)==mf['integrated_sha256'],'Changed factory template')
    image=wire.read_s19(template/'bootstrap-template.s19')[0]
    image[mf['count']]=len(tx['operations']);image[mf['commit_after']]=0
    for key,size in [('banks',24),('commits',24),('commit_addresses',96),('commit_values',24),('table',216)]:
        image.update({mf[key]+i:0 for i in range(size)})
    image.update(dict(enumerate(b''.join(wire.fnv(b).to_bytes(4,'little') for b in source),0x3500)))
    image.update({a:0 for a in range(0x3600,0x3700)})
    image.update(dict(enumerate(wire.fnv(bytes(256)).to_bytes(4,'little'),0x3512)))
    transfers=[]
    for index,(op,body) in enumerate(zip(tx['operations'],data)):
        r.require((r.hashes(source) if index==0 else r.hashes(prior))==op['source_sha256'],'Bootstrap preimage chain mismatch')
        transfer=bytearray(body);commit=op['commit_address']
        if commit is not None:
            image[mf['commits']+index]=op['bank']+1;image[mf['commit_values']+index]=body[commit-op['address']]
            image.update(dict(enumerate(commit.to_bytes(2,'little'),mf['commit_addresses']+4*index)))
            transfer[commit-op['address']]=255
        image[mf['banks']+index]=op['bank']
        row=bytes([op['address']>>8])+wire.fnv(source[op['bank']] if index==0 else prior[op['bank']]).to_bytes(4,'little')+wire.fnv(transfer).to_bytes(4,'little')
        image.update(dict(enumerate(row,mf['table']+9*index)));transfers.append(bytes(transfer))
        if index==0:prior=list(map(bytearray,source))
        offset=op['address']-0x8000;prior[op['bank']][offset:offset+4096]=body
    r.require(list(map(bytes,prior))==expected,'Bootstrap replay mismatch')
    entry=mf['entry_65C816'] if cpu=='65C816' else mf['entry_65C02']
    return wire.s19(image,entry),transfers,entry


def compose(kit,out,source,tx,data,expected,cpu):
    installer,transfers,entry=render_installer(kit,source,tx,data,expected,cpu)
    r.require(not out.exists(),'Output directory already exists');out.mkdir(parents=True)
    (out/'installer-model-only.s19').write_bytes(installer)
    for index,body in enumerate(transfers):(out/f'transfer-{index:02d}.bin').write_bytes(body)
    for index,body in enumerate(source):(out/f'source-b{index}.bin').write_bytes(body)
    for index,body in enumerate(expected):(out/f'expected-b{index}.bin').write_bytes(body)
    return dict(route='direct-wdcmonv2-to-rc1',transaction=tx,installer_sha256=r.sha(installer),
        source_sha256=r.hashes(source),expected_sha256=r.hashes(expected),entry=entry,source_cpu=cpu,
        factory_template_manifest_sha256=r.sha((kit/'factory-template/manifest.json').read_bytes()),
        kit_manifest_sha256=r.sha((kit/'kit-manifest.json').read_bytes()),live_execution_qualified=False,
        model_only=True,board_access=False,installation_permitted=False)


def history_seed(identity,seed,accept_unknown_history):
    if seed is None:
        r.require(accept_unknown_history,'Factory source has no rc1 wear history; explicit new tracked-baseline acknowledgement required')
        config=wire.default_config() if hasattr(wire,'default_config') else bytes([1,0,3,7,240,10,0]+[0]*9)
        config=bytearray(config);config[14:]=wire.config_sum(config);config=bytes(config);counts=[0]*32;sequence=0
        origin='Tracked migration attempts only; previous physical erase history is unknown'
    else:
        r.require(seed['schema']==1 and seed['board']==identity['board'],'History belongs to another board')
        config=bytes.fromhex(seed['config']);counts=seed['counts'];sequence=seed['sequence']
        r.record(config,counts,max(1,sequence));origin='Owner-local conservative tracked history, not lifetime physical wear'
    r.require(type(sequence) is int and 0<=sequence<=0xfffffffd,'Invalid tracked-history sequence')
    return config,counts,sequence,origin


def prepare(capture_root,kit,out,history=None,metadata=None,accept_unknown_history=False):
    m.verify_kit(kit);identity,source=m.capture(capture_root);profile=profile_for(source,kit)
    seed=r.read(history) if history is not None else None
    config,counts,sequence,origin=history_seed(identity,seed,accept_unknown_history)
    tail=Path(metadata).read_bytes() if metadata is not None else None
    desired,app_commit=target(source,kit,tail);tx,data,expected=transaction(source,desired,config,counts,sequence,app_commit)
    info=compose(kit,out,source,tx,data,expected,profile['cpu']);info.update(board=identity['board'],wear_baseline_origin=origin,
        capture_manifest_sha256=r.sha((capture_root/'capture.json').read_bytes()),app_record_sha256=r.sha((kit/'applications/uchess-record.bin').read_bytes()),
        binding_schema=1,accept_unknown_wear_history=bool(accept_unknown_history),source_history=None,metadata_escrow=None)
    (out/'source-capture.json').write_bytes((capture_root/'capture.json').read_bytes())
    if history is not None:
        body=Path(history).read_bytes();(out/'source-history.json').write_bytes(body)
        info['source_history']=dict(file='source-history.json',bytes=len(body),sha256=r.sha(body))
    if tail is not None:
        (out/'metadata-escrow.bin').write_bytes(tail)
        info['metadata_escrow']=dict(file='metadata-escrow.bin',bytes=len(tail),sha256=r.sha(tail))
    (out/'plan.json').write_text(json.dumps(info,indent=2)+'\n');(out/'.gitignore').write_text('*\n')
    return info


def validate_plan(plan_root,kit):
    """Re-derive the exact factory transaction, installer and every transfer."""
    m.verify_kit(kit);plan_root=Path(plan_root).resolve();plan=r.read(plan_root/'plan.json')
    r.require(plan['binding_schema']==1 and plan['route']=='direct-wdcmonv2-to-rc1','Unbound/unsupported factory plan')
    r.require(plan['live_execution_qualified'] is False and plan['installation_permitted'] is False and plan['model_only'] is True,
              'Prototype factory plan cannot claim live qualification')
    r.require(plan['kit_manifest_sha256']==r.sha((kit/'kit-manifest.json').read_bytes()),'Changed factory kit binding')
    m.board_identity(plan['board']);raw=(plan_root/'source-capture.json').read_bytes()
    r.require(r.sha(raw)==plan['capture_manifest_sha256'],'Changed original capture manifest')
    identity=m.capture_identity(json.loads(raw))
    r.require(identity['board']==plan['board'],
              'Original capture/plan board mismatch')
    source=[(plan_root/f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected=[(plan_root/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    r.valid_banks(source);r.valid_banks(expected)
    r.require(r.hashes(source)==plan['source_sha256']==plan['transaction']['source_sha256'],'Changed factory source escrow')
    for n,body in enumerate(source):
        if identity['schema']==2 and n<3:r.require(body==b'\xff'*32768,'Guarded source bank changed')
        for suffix in ('','-repeat'):
            info=identity['files'][f'b{n}{suffix}.bin']
            r.require(info['bytes']==32768 and info['sha256']==r.sha(body),'Original repeated capture/source mismatch')
    profile=profile_for(source,kit)
    r.require(plan['source_cpu']==profile['cpu'],'Factory source CPU/profile mismatch')
    def bound_file(info):
        if info is None:return None
        body=m.safe(plan_root,info['file']).read_bytes()
        r.require(len(body)==info['bytes'] and r.sha(body)==info['sha256'],'Changed bound factory history/metadata')
        return body
    history=bound_file(plan['source_history']);metadata=bound_file(plan['metadata_escrow'])
    config,counts,sequence,origin=history_seed(identity,json.loads(history) if history is not None else None,
        plan['accept_unknown_wear_history'])
    r.require(plan['wear_baseline_origin']==origin,'Changed wear-history interpretation')
    desired,commit=target(source,kit,metadata)
    tx,data,replayed=transaction(source,desired,config,counts,sequence,commit)
    r.require(plan['transaction']==tx and expected==replayed and r.hashes(expected)==plan['expected_sha256'],
              'Saved factory transaction/target differs from admitted route')
    r.require(plan['factory_template_manifest_sha256']==r.sha((kit/'factory-template/manifest.json').read_bytes()),'Changed factory template binding')
    r.require(plan['app_record_sha256']==r.sha((kit/'applications/uchess-record.bin').read_bytes()),'Changed application binding')
    installer,transfers,entry=render_installer(kit,source,tx,data,expected,profile['cpu'])
    r.require(plan['entry']==entry and (plan_root/'installer-model-only.s19').read_bytes()==installer and r.sha(installer)==plan['installer_sha256'],
              'Changed factory installer or entry')
    names={f'transfer-{n:02d}.bin' for n in range(len(transfers))}
    r.require({p.name for p in plan_root.glob('transfer-*.bin')}==names,'Missing or extra factory transfer')
    for n,body in enumerate(transfers):r.require((plan_root/f'transfer-{n:02d}.bin').read_bytes()==body,'Changed factory transfer')
    return plan,source,expected
