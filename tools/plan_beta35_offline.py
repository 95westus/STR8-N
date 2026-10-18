"""Non-executable beta35 B-target payload plan from archived bytes only.

No serial imports, installers, device writes, settings changes or activation.
This prerequisite does not plan the wear-journal transaction or prove erase,
program, commit or physical recovery behavior. It never permits installation.
"""
import argparse,binascii,hashlib,json
from pathlib import Path
from inspect_beta35_source import identify,require,ROOT

PACKAGE=ROOT/'release/beta35-prerelease'
SOURCE_SHA='35e17b958c5290b88aad002c1c830776452e0df8dc39a0ead12691a07872e4d0'
DESTINATION_SHA='20e9cf10ce326714a47862626371ad5011cf8728c16650df6f5bf822eaa959a7'
sha=lambda b:hashlib.sha256(b).hexdigest()
crc=lambda b:binascii.crc_hqx(b,0xffff)
read=lambda p:json.loads(p.read_text())

def load_inputs(payload):
    srcpath=PACKAGE/'source-catalog.json';dstpath=PACKAGE/'destination-catalog.json'
    require(sha(srcpath.read_bytes())==SOURCE_SHA,'Source catalog integrity mismatch')
    require(sha(dstpath.read_bytes())==DESTINATION_SHA,'Destination catalog integrity mismatch')
    source=read(srcpath);destination=read(dstpath)
    mp=ROOT/'release/beta35/release.json';lp=ROOT/'release/beta35/layout.json'
    require(sha(mp.read_bytes())==destination['target_metadata_sha256'],'Target metadata integrity mismatch')
    require(sha(lp.read_bytes())==destination['target_layout_sha256'],'Target layout integrity mismatch')
    meta=read(mp);layout=read(lp)
    require(meta['version']=='2.0b35' and meta['generation']==47,'Wrong target version/generation')
    files={}
    for name,info in meta['expected'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Unsafe target filename')
        data=(payload/name).read_bytes()
        require(len(data)==info['bytes'] and sha(data)==info['sha256'],'Target payload integrity mismatch: '+name)
        files[name]=data
    require(len(layout['segments'])==len(destination['ranges'])==13,'Unexpected owned range count')
    return source,destination,layout,files

def config_checksum(cfg):
    a=b=0
    for v in cfg[:14]:a=(a+v)&255;b=(b+a)&255
    return bytes((a,b))

def settings(banks,identity):
    records=[]
    for off in range(0x4000,0x6000,128):
        r=bytes(banks[3][off:off+128])
        if r[:4]==b'WC\x01\0' and r[127]==0 and crc(r[:120])==int.from_bytes(r[120:122],'little'):
            records.append((int.from_bytes(r[4:8],'little'),off,r))
    require(bool(records),'No valid configuration/wear journal snapshot; conversion required')
    sequence,offset,r=max(records,key=lambda x:x[0])
    require(sequence>0,'Invalid journal sequence')
    require(len({v for seq,off,v in records if seq==sequence})==1,'Ambiguous latest journal sequence')
    cfg=r[8:24]
    require(cfg[0]==1 and cfg[1]<=1 and cfg[2]<=3 and cfg[5]>=10 and cfg[6]<=1
            and cfg[13] in (0,0xA5) and cfg[14:]==config_checksum(cfg),'Invalid stored startup settings')
    address=int.from_bytes(cfg[3:5],'little');top=0x66ff if cfg[13]==0xA5 else 0x64ff
    require(cfg[6]==1 or address<0xe0 or 0x200<=address<=top or address>=0x8000,
            'Stored startup address conflicts with protected RAM')
    preference=cfg[7:13]
    if preference!=bytes(6):
        require(preference[0]==ord('P') and preference[1] in (0xA0,0xB0),'Invalid monitor preference')
        slot=identity['monitors'][f'{preference[1]:02X}']
        require(slot is not None and slot['generation']==int.from_bytes(preference[2:],'little'),
                'Stale monitor preference/generation')
    return dict(configuration_hex=cfg.hex(),configuration_sha256=sha(cfg),
        journal_sequence=sequence,journal_offset=offset,
        erase_counts=[int.from_bytes(r[24+i*3:27+i*3],'little') for i in range(32)],
        configuration_and_journal_preserved_byte_exact=True,
        boot_preference_policy='Preserve exactly in this logical plan; activation behavior is not qualified')

def bank_hashes(banks):
    require(len(banks)==4 and all(len(b)==32768 for b in banks),'Four complete 32768-byte banks required')
    return [sha(b) for b in banks]

def write_backup(directory,banks):
    hashes=bank_hashes(banks);require(not directory.exists(),'Backup directory must be new')
    directory.mkdir(parents=True)
    for i,b in enumerate(banks):(directory/f'b{i}.bin').write_bytes(b)
    manifest=dict(schema=1,meaning='Offline archived full-bank backup; not device restoration qualification',
        banks=[dict(name=f'b{i}.bin',bytes=32768,sha256=d) for i,d in enumerate(hashes)])
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    require(bank_hashes(read_backup(directory))==hashes,'Backup round-trip mismatch')

def read_backup(directory):
    meta=read(directory/'manifest.json')
    require(meta.get('schema')==1 and len(meta.get('banks',[]))==4,'Invalid backup manifest')
    banks=[]
    for i,record in enumerate(meta['banks']):
        require(record['name']==f'b{i}.bin' and record['bytes']==32768,'Invalid backup member')
        data=(directory/record['name']).read_bytes()
        require(len(data)==32768 and sha(data)==record['sha256'],'Backup member integrity mismatch')
        banks.append(data)
    return banks

def validate_preimages(plan,banks):
    require(bank_hashes(banks)==plan['source_bank_sha256'],'Stale archived bank preimage; replan required')

def plan(banks,active,payload,backup):
    original=bank_hashes(banks)
    require(bank_hashes(backup)==original,'Verified full-bank backup does not match source')
    source,destination,layout,files=load_inputs(payload)
    identity=identify(banks,active,source)
    require(identity['layout']=='AB','Legacy conversion is not qualified for beta35')
    require(active==0xA0,'Active B requires an unqualified A35 target (QA35-004); route refused')
    require(identity['validator_address']==0xF30D,'Private ABI conversion is not qualified for beta35')
    require(bytes(banks[3][0x7000:])==files['str8n-v2-recovery-f000-ffff.bin'],
            'Source F conversion is not qualified for beta35')
    require(bytes(banks[3][0x6000:0x7000])==files['str8n-v2-recovery-e000-efff.bin'],
            'Source E conversion is not qualified for beta35')
    saved=settings(banks,identity)
    expected=[bytearray(b) for b in banks];coverage=[bytearray(32768) for _ in range(4)]
    ownership=[]
    for segment,registered in zip(layout['segments'],destination['ranges']):
        for key in ('bank','address','bytes','file'):require(segment[key]==registered[key],'Owned range catalog/layout disagreement')
        bank=segment['bank'];off=segment['address']-0x8000;n=segment['bytes']
        require(0<=bank<4 and off>=0 and off+n<=32768,'Owned range outside bank')
        require(not any(coverage[bank][off:off+n]),'Overlapping owned ranges')
        old=bytes(banks[bank][off:off+n]);new=files[segment['file']][segment['offset']:segment['offset']+n]
        require(len(new)==n,'Incomplete target range')
        require(sha(old) in registered['accepted_sha256'] or old==b'\xff'*n,
                'Unknown or occupied owned destination: '+segment['file'])
        coverage[bank][off:off+n]=b'\1'*n;expected[bank][off:off+n]=new
        ownership.append(dict(bank=bank,address=segment['address'],bytes=n,source_sha256=sha(old),target_sha256=sha(new)))
    changed=[]
    for bank in range(4):
        for s in range(8,16):
            off=(s-8)*4096
            before=bytes(banks[bank][off:off+4096]);after=bytes(expected[bank][off:off+4096])
            if before!=after:changed.append((bank,s))
        require(all(x==y for i,(x,y) in enumerate(zip(banks[bank],expected[bank])) if not coverage[bank][i]),
                'Unowned bytes changed')
    # CLOCK's first sector follows its tails; monitor activation is last.
    changed.sort(key=lambda row:(2 if row==(3,11) else 1 if row==(1,11) else 0,row[0],-row[1]))
    if changed:
        require(saved['journal_sequence']<0xffffffff,'Journal sequence exhausted')
        for bank,s in changed:require(saved['erase_counts'][bank*8+s-8]<0xffffff,'Erase-attempt counter exhausted')
    steps=[]
    for bank,s in changed:
        off=(s-8)*4096
        steps.append(dict(bank=bank,sector=s,preimage_sha256=sha(bytes(banks[bank][off:off+4096])),
            proposed_committed_sha256=sha(bytes(expected[bank][off:off+4096])),
            shared_sector_unowned_bytes_preserved=True))
    result=dict(schema=1,version='2.0b35',generation=47,planning_only=True,
        execution_permitted=False,installation_permitted=False,release_qualified=False,route_qualified=False,
        board_access=False,source_identity=identity,source_bank_sha256=original,
        verified_backup_sha256=bank_hashes(backup),proposed_bank_sha256=bank_hashes(expected),
        settings=saved,owned_ranges=ownership,proposed_payload_sectors=steps,no_payload_change=not changed,
        retained_A_sha256=sha(bytes(banks[3][0x2000:0x3000])),
        unowned_bytes_preserved=True,journal_transaction_planned=False,
        source_catalog_sha256=SOURCE_SHA,destination_catalog_sha256=DESTINATION_SHA,
        target_metadata_sha256=destination['target_metadata_sha256'],
        outstanding_gates=['Qualified journal/wear transaction and commit staging',
            'Activation policy for the preserved monitor preference/generation',
            'Generated exact-image installer model: refusal, interruptions, backup restoration',
            'Physical acceptance after protected campaign',
            'A35 and legacy/private-ABI conversion routes remain refused'],
        proposed_images_are_not_installation_payloads=True)
    cfg=bytes.fromhex(saved['configuration_hex'])
    if cfg[7]==ord('P'):
        off=(cfg[8]-0x80)*256
        result['preferred_generation_matches_proposal']=cfg[9:13]==expected[3][off+8:off+12]
    else:result['preferred_generation_matches_proposal']=None
    return result,[bytes(b) for b in expected]

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('backup');b.add_argument('--banks-dir',required=True,type=Path);b.add_argument('--prefix',default='b');b.add_argument('--out',required=True,type=Path)
    q=sub.add_parser('plan');q.add_argument('--banks-dir',required=True,type=Path);q.add_argument('--prefix',default='b')
    q.add_argument('--backup-dir',required=True,type=Path);q.add_argument('--payload-dir',required=True,type=Path)
    q.add_argument('--active',choices=['A','B'],required=True);q.add_argument('--out',required=True,type=Path)
    a=p.parse_args();require('/' not in a.prefix and '\\' not in a.prefix and ':' not in a.prefix,'Invalid bank filename prefix')
    banks=[(a.banks_dir/f'{a.prefix}{i}.bin').read_bytes() for i in range(4)]
    if a.command=='backup':write_backup(a.out,banks);print('Verified offline full-bank backup');return
    require(not a.out.exists(),'Choose a new plan output path')
    result,_=plan(banks,{'A':0xA0,'B':0xB0}[a.active],a.payload_dir,read_backup(a.backup_dir))
    result['planner_sha256']=sha(Path(__file__).read_bytes())
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Offline logical payload plan saved; journal/installer/route qualification remain pending')

if __name__=='__main__':main()
