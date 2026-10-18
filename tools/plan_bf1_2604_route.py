"""2604 receipt-bound bf1 route; offline only, no serial imports or launcher."""
import json
from pathlib import Path
import beta35_model_transactions as c
import inspect_beta35_source as inspection
p=c.p;j=c.j;ROOT=p.ROOT
def compose(tx,data,banks,expected,out,helper_build):
    info=c.compose(tx,data,banks,expected,out)
    helper=p.read(helper_build/'build-report.json');body=(helper_build/'reservation.bin').read_bytes()
    p.require(helper['passed'] and len(body)<0x300 and p.sha(body)==helper['binary_sha256'],'Invalid separate bf1 route helper')
    p.require(p.sha((ROOT/'release/candidates/batchfix-route-r1/source/reservation.asm').read_bytes())==helper['source_sha256'],'Helper source changed')
    cells=c.old.read_s19(out/'installer-model-only.s19');cells.update(dict(enumerate(body,0x3000)))
    program=c.old.s19(bytes(cells[i] for i in range(0x2000,0x3700)),0x2000,0x2000);(out/'installer-model-only.s19').write_bytes(program)
    info.update(installer_sha256=p.sha(program),separate_route_helper_build_sha256=p.sha((helper_build/'build-report.json').read_bytes()),separate_route_helper_sha256=p.sha(body))
    (out/'plan.json').write_text(json.dumps(info,indent=2)+'\n');return info
def inputs(backup,build,*,allow_restoring=False):
    receipt=p.read(backup/'report.json')
    complete=receipt['passed'] and receipt.get('sram_repeat_verified') and receipt.get('application_ram_restored')
    p.require(receipt['board']=='2604' and receipt['flash_repeat_verified'] and receipt['eeprom_repeat_verified'] and not receipt.get('failure') and (complete or allow_restoring),'Completed backup required unless explicitly modeling verified reads while RAM restoration continues')
    for name,item in receipt['files'].items():
        data=(backup/name).read_bytes();p.require(len(data)==item['bytes'] and p.sha(data)==item['sha256'],'Backup hash mismatch: '+name)
    banks=[(backup/f'b{i}.bin').read_bytes() for i in range(4)]
    p.require(all(banks[i]==(backup/f'b{i}-repeat.bin').read_bytes() for i in range(4)),'Repeated flash mismatch')
    for name,size in [('eeprom',137),('sram',131072)]:
        first=(backup/(name+'.bin')).read_bytes();second=(backup/(name+'-repeat.bin')).read_bytes();p.require(first==second and len(first)==size,'Repeated retained memory mismatch: '+name)
    meta=p.read(build/'build-report.json');p.require(meta['passed'] and meta['candidate_id']=='batchfix-r1' and meta['generation']==48,'Wrong candidate build')
    files={name:(build/'payload'/name).read_bytes() for name in meta['artifacts']}
    for name,data in files.items():p.require(p.sha(data)==meta['artifacts'][name]['sha256'],'Candidate artifact changed: '+name)
    catalog=p.read(inspection.CATALOG);identity=inspection.identify(banks,receipt['active_page'],catalog)
    p.require(identity['source_version']=='2.0b35' and identity['active_page']==0xB0 and identity['validator_address']==0xF30D,'This route requires exact captured active B35/F30D profile')
    p.require(banks[3][0x6000:0x7000]==files['str8n-v2-recovery-e000-efff.bin'] and banks[3][0x7000:]==files['str8n-v2-recovery-f000-ffff.bin'],'E/F conversion refused')
    settings=p.settings(banks,identity)
    return banks,files,identity,settings

def transaction(banks,desired,*,fallback_page,target_config,label,attestation=None):
    """Reserve before erase; keep fallback slot immutable until final selection."""
    banks=list(map(bytes,banks));desired=list(map(bytes,desired));seq,offset,row,valid=c.latest(banks);cfg=row[8:24]
    p.require(seq<=0xfffffffc,'Journal sequence exhausted')
    for off in range(0x4000,0x6000,128):
        r=banks[3][off:off+128]
        p.require(r==b'\xff'*128 or (r[:4]==b'WC\1\0' and r[127]==0 and p.crc(r[:120])==int.from_bytes(r[120:122],'little') and r[122:127]==b'\xff'*5) or attestation==p.bank_hashes(banks),'Unknown/torn journal without exact replay attestation; refuse')
    for config in (cfg,target_config):p.require(config[14:]==p.config_checksum(config),'Invalid configuration checksum')
    p.require(cfg[:7]==target_config[:7] and cfg[13]==target_config[13],'Startup/EDU change refused')
    fo=(fallback_page-0x80)*256;slot=banks[3][fo:fo+4096]
    p.require(slot[:4]==b'MI\1'+bytes([fallback_page]) and slot[31]==0 and p.crc(slot[:18]+slot[32:])==int.from_bytes(slot[18:20],'little'),'Invalid fallback')
    p.require(desired[3][fo:fo+4096]==slot,'Fallback replacement in same transaction refused')
    fallback=j.preference(cfg,fallback_page,int.from_bytes(slot[8:12],'little'))
    changed=[]
    for bank in range(4):
      for sector in range(8,16):
        if bank==3 and sector in (12,13):continue
        start=(sector-8)*4096
        if banks[bank][start:start+4096]!=desired[bank][start:start+4096]:changed.append((bank,sector))
    changed.sort(key=lambda r:(2 if r[0]==3 and r[1] in (10,11) else 1 if r==(1,11) else 0,r[0],-r[1]))
    retained=offset//4096+8;staging=25-retained;start=(retained-8)*4096
    free=[off for off in range(start,start+4096,128) if banks[3][off:off+128]==b'\xff'*128];p.require(bool(free),'No safe reservation slot')
    before=[max(int.from_bytes(r[24+i*3:27+i*3],'little') for _,_,r in valid) for i in range(32)];counts=list(before)
    erases=[(3,staging)]+changed+[(3,retained)]
    for bank,sector in erases:
        n=bank*8+sector-8;p.require(counts[n]<0xffffff,'Erase count exhausted');counts[n]+=1
    state=list(map(bytearray,banks));ops=[];data=[]
    def append(kind,bank,address,body,commit):
        original=p.bank_hashes(state);off=address-0x8000;state[bank][off:off+len(body)]=body
        ops.append(dict(kind=kind,bank=bank,address=address,bytes=len(body),erase=kind!='reserve-record',commit_address=commit,data_sha256=p.sha(body),source_bank_sha256=original,proposed_bank_sha256=p.bank_hashes(state)));data.append(body)
    append('reserve-record',3,free[0]+0x8000,j.record(fallback,counts,seq+1),free[0]+0x807f)
    append('stage-journal',3,staging<<12,j.record(fallback,counts,seq+2)+b'\xff'*3968,(staging<<12)+127)
    for bank,sector in changed:
        start=(sector-8)*4096;body=desired[bank][start:start+4096]
        commit=(sector<<12)+31 if bank==3 and sector in (10,11) else 0xb003 if (bank,sector)==(1,11) and body[3]==0x3f else None
        append('payload-sector',bank,sector<<12,body,commit)
    append('activate-journal',3,retained<<12,j.record(target_config,counts,seq+3)+b'\xff'*3968,(retained<<12)+127)
    tx=dict(schema=1,candidate_id='batchfix-r1',version='2.0bf1',generation=48,label=label,no_change=False,reservation_offset=free[0],retained_journal_sector=retained,staging_journal_sector=staging,source_configuration_hex=cfg.hex(),fallback_configuration_hex=fallback.hex(),target_configuration_hex=target_config.hex(),fallback_page=fallback_page,counts_before=before,reserved_counts=counts,sequence_before=seq,sequence_after=seq+3,operations=ops,planned_erase_order=[list(x) for x in erases],source_bank_sha256=p.bank_hashes(banks),proposed_bank_sha256=p.bank_hashes(state),installation_permitted=False,release_qualified=False,route_qualified=False,board_access=False,model_only=True)
    return tx,data,list(map(bytes,state))

def prepare(backup,build,*,allow_restoring=False):
    banks,files,identity,settings=inputs(backup,build,allow_restoring=allow_restoring);layout=p.read(ROOT/'release/beta35/layout.json');catalog=p.read(ROOT/'release/beta35-prerelease/destination-catalog.json');desired=list(map(bytearray,banks));coverage=[bytearray(32768) for _ in range(4)]
    for segment,registered in zip(layout['segments'],catalog['ranges']):
        bank=segment['bank'];start=segment['address']-0x8000;n=segment['bytes'];old=banks[bank][start:start+n];new=files[segment['file']][segment['offset']:segment['offset']+n]
        p.require(p.sha(old) in registered['accepted_sha256'] or old==b'\xff'*n,'Unknown occupied destination '+segment['file'])
        p.require(len(new)==n,'Incomplete target');desired[bank][start:start+n]=new;coverage[bank][start:start+n]=b'\1'*n
    p.require(all(x==y for bank in range(4) for i,(x,y) in enumerate(zip(banks[bank],desired[bank])) if not coverage[bank][i]),'Unowned bytes changed')
    cfg=bytes.fromhex(settings['configuration_hex']);tx,data,expected=transaction(banks,desired,fallback_page=0xa0,target_config=j.preference(cfg,0xb0,48),label='2604 B-first coherent bf1; retain original A40')
    return banks,tx,data,expected,files,identity

def attest_recovery(current,original,*,events,info,certificate):
    """Exact mutation replay binds recovery; reject unknown/changed states."""
    p.require(p.bank_hashes(current)==certificate,'Unrecognized recovery preimage')
    p.require(p.bank_hashes(original)==info['source_sha256'],'Wrong original backup')
    state=list(map(bytearray,original));attempts=[0]*32;erases=[];allowed=set(map(tuple,info['steps']));reserve=info['transaction']['operations'][0]['address']
    for kind,bank,address,value in events:
        p.require(0<=bank<4 and 0x8000<=address<=0xffff,'Invalid recovery event')
        if kind=='erase':
            p.require(address&4095==0,'Unaligned erase');erases.append([bank,address>>12]);p.require(erases==info['steps'][:len(erases)],'Unexpected erase order');state[bank][address-0x8000:address-0x8000+4096]=b'\xff'*4096;attempts[bank*8+(address>>12)-8]+=1
        else:
            p.require(kind=='program' and ((bank,address>>12) in allowed or bank==3 and reserve<=address<reserve+128),'Unexpected write');off=address-0x8000;p.require(state[bank][off]&value==value,'Invalid flash transition');state[bank][off]=value
    p.require(list(map(bytes,state))==list(map(bytes,current)),'Recovery event replay mismatch')
    _,_,row,_=c.latest(current);oldrow=c.latest(original)[2]
    p.require(all(int.from_bytes(row[24+i*3:27+i*3],'little')>=int.from_bytes(oldrow[24+i*3:27+i*3],'little')+attempts[i] for i in range(32)),'Counts below actual attempts')
    return attempts
