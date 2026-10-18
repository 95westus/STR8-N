"""Compose offline variants using the separately qualified RAM helper/wrapper.

No serial launcher. Frozen payload/template files are read only; permission is
always false. Restoration is restricted to receipt-bound prior model states.
"""
from pathlib import Path
import build_beta35_transaction_image as old
j=old.journal;p=old.p
EVIDENCE=p.ROOT/'output/qualification/beta35-prerelease-2026-10-17'

def latest(banks):
    valid=[]
    for off in range(0x4000,0x6000,128):
        r=bytes(banks[3][off:off+128])
        if r[:4]==b'WC\1\0' and r[127]==0 and p.crc(r[:120])==int.from_bytes(r[120:122],'little'):
            valid.append((int.from_bytes(r[4:8],'little'),off,r))
    p.require(bool(valid),'No valid journal')
    seq,off,r=max(valid,key=lambda v:v[0]);p.require(len({v for s,o,v in valid if s==seq})==1,'Ambiguous latest journal')
    return seq,off,r,valid

def compose(tx,data,banks,expected,out):
    p.require(not out.exists(),'New model directory required');out.mkdir(parents=True)
    if tx['no_change']:
        info=dict(transaction=tx,no_change=True,source_sha256=p.bank_hashes(banks),expected_sha256=p.bank_hashes(expected),
            model_only=True,installation_permitted=False,release_qualified=False)
        (out/'plan.json').write_text(old.json.dumps(info,indent=2)+'\n');return info
    cp=p.read(EVIDENCE/'transaction-model-checkpoint.json');buildpath=Path(cp['build_report'])
    p.require(p.sha(buildpath.read_bytes())==cp['build_report_sha256'],'Pinned integration build changed')
    pinned=p.read(buildpath.parent/'2512/plan.json');imagepath=buildpath.parent/'2512/installer-model-only.s19'
    p.require(p.sha(imagepath.read_bytes())==pinned['installer_sha256'],'Pinned integrated RAM image changed')
    image=old.read_s19(imagepath);mf=p.read(p.ROOT/'BUILD/v2-beta35-candidate/migrator/manifest.json')
    p.require(p.sha((p.ROOT/'BUILD/v2-beta35-candidate/migrator/manifest.json').read_bytes())==old.MANIFEST_SHA,'Manifest changed')
    rows=tx['operations'][1:];p.require(0<len(rows)<=mf['max_sectors'],'Invalid row count')
    image[mf['count']]=len(rows);image[mf['commit_after']]=0
    for key,n in [('banks',16),('commits',16),('commit_addresses',64),('table',mf['table_bytes'])]:
        image.update({mf[key]+i:0 for i in range(n)})
    image.update(dict(enumerate(b''.join(old.fnv(b).to_bytes(4,'little') for b in banks),0x3500)))
    image.update(dict(enumerate(tx['operations'][0]['address'].to_bytes(2,'little'),0x3510)))
    page=data[0]+b'\xff'*128;image.update(dict(enumerate(page,0x3600)))
    image.update(dict(enumerate(old.fnv(page).to_bytes(4,'little'),0x3512)))
    state=[bytearray(b) for b in banks];offset=tx['reservation_offset'];state[3][offset:offset+128]=data[0]
    transfers=[]
    for n,(op,body) in enumerate(zip(rows,data[1:])):
        assert p.bank_hashes(state)==op['source_bank_sha256']
        bank=op['bank'];address=op['address'];off=address-0x8000
        transfer=bytearray(body);commit=op['commit_address'] if op['kind']=='payload-sector' else None
        if commit is not None:
            p.require(body[commit-address] in (0,0x3f),'Template supports only monitor/CLOCK commit markers')
            transfer[commit-address]=255;image[mf['commits']+n]=bank+1
            image.update(dict(enumerate(commit.to_bytes(2,'little'),mf['commit_addresses']+4*n)))
        row=bytes([address>>8])+old.fnv(state[bank]).to_bytes(4,'little')+old.fnv(transfer).to_bytes(4,'little')
        image[mf['banks']+n]=bank;image.update(dict(enumerate(row,mf['table']+9*n)))
        state[bank][off:off+4096]=body
        assert p.bank_hashes(state)==op['proposed_bank_sha256'];transfers.append(bytes(transfer))
    assert [bytes(b) for b in state]==expected
    raw=bytes(image[i] for i in range(0x2000,0x3700));program=old.s19(raw,0x2000,0x2000)
    (out/'installer-model-only.s19').write_bytes(program)
    for n,b in enumerate(transfers):(out/f'transfer-{n:02d}.bin').write_bytes(b)
    for n,b in enumerate(expected):(out/f'expected-b{n}.bin').write_bytes(b)
    info=dict(transaction=tx,no_change=False,steps=[[op['bank'],op['address']>>12] for op in rows],
        installer_sha256=p.sha(program),transfer_sha256=[p.sha(b) for b in transfers],source_sha256=p.bank_hashes(banks),
        expected_sha256=p.bank_hashes(expected),pinned_build_report_sha256=cp['build_report_sha256'],
        model_only=True,installation_permitted=False,release_qualified=False,board_access=False)
    (out/'plan.json').write_text(old.json.dumps(info,indent=2)+'\n');return info

def restoration(banks,backup,*,certificate,events,upgrade_plan):
    """Plan restoration only for a proven saved interruption of this upgrade.

    Certificate hashes and replayed events bind the exact archived state. This
    is not a general damaged-flash recovery planner or a hardware tool.
    """
    p.require(p.bank_hashes(banks)==certificate['bank_sha256'],'Unrecognized interrupted preimage')
    p.require(p.bank_hashes(backup)==upgrade_plan['source_sha256'],'Backup does not match original upgrade source')
    replay=[bytearray(b) for b in backup];attempts=[0]*32;erases=[]
    allowed=set(map(tuple,upgrade_plan['steps']));reserve=upgrade_plan['transaction']['reservation_offset']+0x8000
    for kind,bank,address,value in events:
        p.require(0<=bank<4 and 0x8000<=address<=0xffff,'Invalid event')
        sector=address>>12;off=address-0x8000
        if kind=='erase':
            p.require(address&0xfff==0,'Unaligned erase event')
            erases.append([bank,sector]);p.require(erases==upgrade_plan['steps'][:len(erases)],'Unexpected erase order')
            replay[bank][off:off+4096]=b'\xff'*4096;attempts[bank*8+sector-8]+=1
        else:
            p.require(kind=='program' and ((bank,sector) in allowed or bank==3 and reserve<=address<reserve+128),'Event outside transaction')
            p.require(replay[bank][off]&value==value,'Invalid flash program transition');replay[bank][off]=value
    p.require([bytes(b) for b in replay]==list(map(bytes,banks)),'Event replay does not match interrupted state')
    seq,off,r,valid=latest(banks);bseq,boff,br,bvalid=latest(backup)
    p.require(seq<=0xffffffff-3,'Restoration sequence exhausted')
    # Exact protected/unowned preservation; only package-owned payload and C/D
    # may differ, and only within a replayed, receipt-bound upgrade.
    _,_,layout,_=p.load_inputs(p.ROOT/'tmp/c35e/payload');coverage=[bytearray(32768) for _ in range(4)]
    for seg in layout['segments']:
        start=seg['address']-0x8000;coverage[seg['bank']][start:start+seg['bytes']]=b'\1'*seg['bytes']
    coverage[3][0x4000:0x6000]=b'\1'*8192
    p.require(all(a==b for bank in range(4) for i,(a,b) in enumerate(zip(banks[bank],backup[bank])) if not coverage[bank][i]),'Protected/unowned bytes changed')
    config=br[8:24];p.require(config[14:]==p.config_checksum(config),'Backup settings invalid')
    fallback=j.preference(config,0xA0,int.from_bytes(backup[3][0x2008:0x200c],'little'))
    p.require(r[8:15]==config[:7] and r[21]==config[13],'Source startup/EDU settings disagree with backup')
    counts=[max(int.from_bytes(v[24+i*3:27+i*3],'little') for s,o,v in valid+bvalid) for i in range(32)]
    oldcounts=[int.from_bytes(br[24+i*3:27+i*3],'little') for i in range(32)]
    p.require(all(counts[i]>=oldcounts[i]+attempts[i] for i in range(32)),'Durable counts below replayed attempted erases')
    changed=[]
    for bank in range(4):
        for sector in range(8,16):
            if bank==3 and sector in (12,13):continue
            start=(sector-8)*4096
            if banks[bank][start:start+4096]!=backup[bank][start:start+4096]:changed.append((bank,sector))
    changed.sort(key=lambda x:(2 if x==(3,11) else 1 if x==(1,11) else 0,x[0],-x[1]))
    # A healthy already-restored image is an exact device-write no-op.
    clean=True
    for start in range(0x4000,0x6000,128):
        page=bytes(banks[3][start:start+128])
        if page!=b'\xff'*128 and not any(o==start for s,o,v in valid):clean=False
    common=dict(mode='receipt-bound-wear-aware-restoration',model_only=True,route_qualified=False,
        installation_permitted=False,release_qualified=False,board_access=False,counts_before=list(counts),
        backup_erase_counts=oldcounts,prior_replayed_attempts=attempts,source_configuration_hex=r[8:24].hex(),
        target_configuration_hex=config.hex(),source_bank_sha256=p.bank_hashes(banks))
    if not changed and r[8:24]==config and clean:
        return dict(common,no_change=True,operations=[],proposed_bank_sha256=p.bank_hashes(banks)),[],list(map(bytes,banks))
    retained=off//4096+8;staging=25-retained;start=(retained-8)*4096
    free=[n for n in range(start,start+4096,128) if banks[3][n:n+128]==b'\xff'*128]
    p.require(bool(free),'No safe erased restoration reservation slot')
    sectors=[(3,staging)]+changed+[(3,retained)]
    for bank,sector in sectors:
        i=bank*8+sector-8;p.require(counts[i]<0xffffff,'Restoration erase counter exhausted');counts[i]+=1
    state=[bytearray(b) for b in banks];ops=[];data=[]
    def append(kind,bank,address,body,commit):
        before=p.bank_hashes(state);offset=address-0x8000;state[bank][offset:offset+len(body)]=body
        ops.append(dict(kind=kind,bank=bank,address=address,bytes=len(body),erase=kind!='reserve-record',
            commit_address=commit,data_sha256=p.sha(body),source_bank_sha256=before,proposed_bank_sha256=p.bank_hashes(state)));data.append(body)
    append('reserve-record',3,free[0]+0x8000,j.record(fallback,counts,seq+1),free[0]+0x807f)
    append('stage-journal',3,staging<<12,j.record(fallback,counts,seq+2)+b'\xff'*3968,(staging<<12)+127)
    for bank,sector in changed:
        start=(sector-8)*4096;body=bytes(backup[bank][start:start+4096]);commit=None
        if (bank,sector)==(3,11):commit=0xb01f
        elif (bank,sector)==(1,11) and body[3]==0x3f:commit=0xb003
        append('payload-sector',bank,sector<<12,body,commit)
    append('activate-journal',3,retained<<12,j.record(config,counts,seq+3)+b'\xff'*3968,(retained<<12)+127)
    result=dict(common,no_change=False,reservation_offset=free[0],retained_journal_sector=retained,
        staging_journal_sector=staging,reserved_counts=list(counts),planned_erase_order=[list(s) for s in sectors],
        operations=ops,proposed_bank_sha256=p.bank_hashes(state),backup_journal_not_replayed=True)
    return result,data,[bytes(b) for b in state]
