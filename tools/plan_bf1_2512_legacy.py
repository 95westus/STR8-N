"""Exact-source 2512 legacy conversion candidate. Offline plans only, no ports."""
import hashlib,json
import zipfile
from pathlib import Path
import beta4_migration as migration
from beta35_model_transactions import latest
from plan_beta35_journal_transaction import record,preference
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
BACKUP=Q/'bf1-2512-pre-migration-backup-2026-10-17-r1'
STOCK=Q/'board-2512-layout-2026-09-24/b0-final.bin'
KIT=ROOT/'BUILD/v2-beta4/kit';PAYLOAD=ROOT/'tmp/bfx5/payload'
sha=lambda data:hashlib.sha256(data).hexdigest()
hashes=lambda banks:[sha(bytes(b)) for b in banks]
read=lambda p:json.loads(p.read_text())

def original():
    audit=Q/'bf1-2512-migration-input-audit-2026-10-17-r1.json';a=read(audit)
    assert a['passed'] and sha((BACKUP/'report.json').read_bytes())==a['backup_report_sha256']
    report=read(BACKUP/'report.json');assert report['passed'] and report['application_ram_restored']
    for name,info in report['files'].items():assert sha((BACKUP/name).read_bytes())==info['sha256']
    return [(BACKUP/f'b{n}.bin').read_bytes() for n in range(4)]

def config_without_preference(cfg):
    result=bytearray(cfg);result[7:13]=bytes(6);result[14:]=migration.config_sum(result);return bytes(result)

def masks():
    mask=[bytearray(32768) for _ in range(4)]
    for segment in read(ROOT/'release/beta35/layout.json')['segments']:
        bank=segment['bank'];offset=segment['address']-0x8000;n=segment['bytes'];mask[bank][offset:offset+n]=b'\1'*n
    # Both monitors and the explicit source-owned B3 system layout are replaced.
    mask[3][:]=b'\1'*32768
    return mask

def legacy_destination(kind,banks):
    assert kind in ('wdcmonv2','v2.0b4');result=list(map(bytearray,banks));mask=masks()
    for bank in (1,2):
        for i,value in enumerate(mask[bank]):
            if value:result[bank][i]=255
    if kind=='wdcmonv2':
        data=STOCK.read_bytes();assert sha(data)=='2f0000c74eceec809a814e31f822702977d7bfed5ee6f3bc4869627864ca59a8';result[3][:]=data
    else:
        intake=read(Q/'bf1-2512-migration-route-preparation-2026-10-17-r1/intake.json')['source_fixtures']['published_beta4']
        archive=Path(intake['path']);assert sha(archive.read_bytes())==intake['sha256']
        with zipfile.ZipFile(archive) as z:
            manifest=json.loads(z.read('manifest.json'));assert manifest['version']=='2.0b4' and manifest['generation']==13
            for name,digest in manifest['artifacts'].items():assert sha(z.read(name))==digest and (KIT/name).read_bytes()==z.read(name)
        result[3][:]=b'\xff'*32768;result[3][:8192]=migration.maintenance_storage(KIT)
        for offset,name in [(0x2000,'slot-a'),(0x3000,'slot-b'),(0x6000,'e000-efff'),(0x7000,'f000-ffff')]:
            result[3][offset:offset+4096]=(KIT/f'str8n-v2-b4-{name}.bin').read_bytes()
    return list(map(bytes,result))

def target_destination(banks):
    result=list(map(bytearray,banks));pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json')
    for name,info in pin['artifacts'].items():assert sha((PAYLOAD/name).read_bytes())==info['sha256']
    for s in read(ROOT/'release/beta35/layout.json')['segments']:
        offset=s['address']-0x8000;result[s['bank']][offset:offset+s['bytes']]=(PAYLOAD/s['file']).read_bytes()[s['offset']:s['offset']+s['bytes']]
    result[3][0x2000:0x3000]=(PAYLOAD/'str8n-v2-recovery-slot-a0.bin').read_bytes()
    # Historical source staging uses this region for the old monitor/MAINT.
    # Restore the current board's exact mutable identity/policy/history preimage
    # from its verified host escrow, never from another board or a clean image.
    result[3][0x1c00:0x2000]=original()[3][0x1c00:0x2000]
    return list(map(bytes,result))

def admit_source(kind,banks):
    assert len(banks)==4 and all(len(b)==32768 for b in banks)
    expected=legacy_destination(kind,banks)
    assert banks[3][:0x4000]==expected[3][:0x4000] and banks[3][0x6000:]==expected[3][0x6000:], 'Unknown/altered historical source'
    # Upper provider destinations must be erased, not merely recognisable by name.
    for bank in (1,2):
        assert banks[bank]==expected[bank], 'Occupied legacy conversion destination'
    clean_journal(banks)
    cfg=latest(banks)[2][8:24]
    assert cfg==config_without_preference(cfg) if kind=='wdcmonv2' else cfg==preference(cfg,0xa0,13)
    return dict(kind=kind,source_sha256=hashes(banks),host_escrow_report_sha256=sha((BACKUP/'report.json').read_bytes()))

def clean_journal(banks):
    seq,off,row,valid=latest(banks)
    for i in range(0x4000,0x6000,128):
        r=bytes(banks[3][i:i+128]);assert r==b'\xff'*128 or any(o==i and bytes(v)==r for _,o,v in valid), 'Torn or unknown wear record'
    assert row[8:24][14:]==migration.config_sum(row[8:24])
    return seq,off,row,valid

def transaction(banks,destination,target_config,label,*,attested_cut=False):
    banks=list(map(bytes,banks));destination=list(map(bytes,destination));assert banks[0]==destination[0], 'B0 replacement forbidden'
    seq,offset,row,valid=latest(banks)
    if not attested_cut:clean_journal(banks)
    assert seq<=0xfffffffc and target_config[:7]==row[8:15] and target_config[13]==row[21]
    assert target_config[14:]==migration.config_sum(target_config)
    retained=offset//4096+8;staging=25-retained;start=(retained-8)*4096
    free=[i for i in range(start,start+4096,128) if banks[3][i:i+128]==b'\xff'*128];assert free,'No erased reservation slot'
    counts=[max(int.from_bytes(r[24+i*3:27+i*3],'little') for _,_,r in valid) for i in range(32)]
    changed=[]
    for bank in range(1,4):
        for sector in range(8,16):
            if bank==3 and sector in (12,13):continue
            off=(sector-8)*4096
            if banks[bank][off:off+4096]!=destination[bank][off:off+4096]:changed.append((bank,sector))
    # All provider bodies before their headers; fixed recovery F is the last
    # payload, followed only by durable selection/configuration activation.
    b3_order={8:0,9:1,11:2,10:3,14:4,15:5}
    if destination[3][:4]==b'SR\1\x3f':
        # Published beta4 MAINT spans B3:8/9. Finish its tail before
        # publishing the header; this also applies to source restoration.
        b3_order[9],b3_order[8]=0,1
    changed.sort(key=lambda x:(x[0]==3,x[0],-x[1] if x[0]!=3 else b3_order[x[1]]))
    erases=[(3,staging)]+changed+[(3,retained)];reserved=list(counts)
    for bank,sector in erases:
        i=bank*8+sector-8;assert reserved[i]<0xffffff,'Wear counter exhausted';reserved[i]+=1
    state=list(map(bytearray,banks));operations=[];data=[]
    def append(kind,bank,address,body,commit=None):
        before=hashes(state);off=address-0x8000;state[bank][off:off+len(body)]=body
        operations.append(dict(kind=kind,bank=bank,address=address,commit_address=commit,source_sha256=before,after_sha256=hashes(state),data_sha256=sha(body)));data.append(body)
    cfg=row[8:24]
    if attested_cut:
        # A conversion cut may have replaced the old preferred monitor. A new
        # recovery reservation must describe a slot which actually exists, or
        # an empty legacy preference, before the helper will admit it.
        pages=[p for p in (0xa0,0xb0) if migration.slot_valid(banks[3][(p-0x80)*256:(p-0x80)*256+4096],p)]
        cfg=preference(cfg,pages[-1],int.from_bytes(banks[3][(pages[-1]-0x80)*256+8:(pages[-1]-0x80)*256+12],'little')) if pages else config_without_preference(cfg)
    append('reserve-record',3,free[0]+0x8000,record(cfg,reserved,seq+1),free[0]+0x807f)
    append('stage-journal',3,staging<<12,record(cfg,reserved,seq+2)+b'\xff'*3968)
    for bank,sector in changed:
        off=(sector-8)*4096;body=destination[bank][off:off+4096];commit=None
        if bank==3 and sector in (10,11) and body[:3]==b'MI\1' and body[31]==0:commit=(sector<<12)+31
        if body[:4]==b'SR\1\x3f':commit=(sector<<12)+3
        append('payload-sector',bank,sector<<12,body,commit)
    append('activate-journal',3,retained<<12,record(target_config,reserved,seq+3)+b'\xff'*3968)
    assert len(operations)-1<=24
    return dict(label=label,source_sha256=hashes(banks),expected_sha256=hashes(state),operations=operations,counts_before=counts,reserved_counts=reserved,sequence_before=seq,sequence_after=seq+3,reservation_offset=free[0],planned_erase_order=[list(x) for x in erases],source_config=cfg.hex(),target_config=target_config.hex(),model_only=True,installation_permitted=False),data,list(map(bytes,state))

def compose(build,out,banks,tx,data,expected):
    assert not out.exists();out.mkdir(parents=True)
    mf=read(build/'manifest.json');assert mf['passed'] and sha((build/'integrated-template.s19').read_bytes())==mf['integrated_sha256']
    image=migration.read_s19(build/'integrated-template.s19')[0];image[mf['count']]=len(tx['operations'])-1;image[mf['commit_after']]=0
    for key,n in [('banks',24),('commits',24),('commit_addresses',96),('commit_values',24),('table',216)]:image.update({mf[key]+i:0 for i in range(n)})
    image.update(dict(enumerate(b''.join(migration.fnv(b).to_bytes(4,'little') for b in banks),0x3500)))
    image.update(dict(enumerate((tx['reservation_offset']+0x8000).to_bytes(2,'little'),0x3510)))
    page=data[0]+b'\xff'*128;image.update(dict(enumerate(page,0x3600)));image.update(dict(enumerate(migration.fnv(page).to_bytes(4,'little'),0x3512)))
    state=list(map(bytearray,banks));state[3][tx['reservation_offset']:tx['reservation_offset']+128]=data[0]
    for n,(op,body) in enumerate(zip(tx['operations'][1:],data[1:])):
        assert hashes(state)==op['source_sha256'];bank=op['bank'];address=op['address'];transfer=bytearray(body);commit=op['commit_address']
        if commit is not None:
            image[mf['commits']+n]=bank+1;image[mf['commit_values']+n]=body[commit-address]
            image.update(dict(enumerate(commit.to_bytes(2,'little'),mf['commit_addresses']+4*n)));transfer[commit-address]=255
        row=bytes([address>>8])+migration.fnv(state[bank]).to_bytes(4,'little')+migration.fnv(transfer).to_bytes(4,'little')
        image[mf['banks']+n]=bank;image.update(dict(enumerate(row,mf['table']+9*n)));state[bank][address-0x8000:address-0x7000]=body
        (out/f'transfer-{n:02d}.bin').write_bytes(transfer)
    assert list(map(bytes,state))==expected
    raw=migration.s19(image,0x2000);(out/'installer-model-only.s19').write_bytes(raw)
    for n,b in enumerate(banks):(out/f'source-b{n}.bin').write_bytes(b)
    for n,b in enumerate(expected):(out/f'expected-b{n}.bin').write_bytes(b)
    info=dict(transaction=tx,installer_sha256=sha(raw),template_manifest_sha256=sha((build/'manifest.json').read_bytes()),source_sha256=hashes(banks),expected_sha256=hashes(expected),board='2512',model_only=True,board_access=False,installation_permitted=False)
    (out/'plan.json').write_text(json.dumps(info,indent=2)+'\n');return info
