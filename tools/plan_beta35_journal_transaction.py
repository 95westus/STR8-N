"""Semantic-only B35 journal transaction, separate from the frozen installer.

No machine code or hardware launcher is produced. The reservation append must
be implemented and qualified in a separately identified RAM helper before this
transaction can become executable. All permission flags remain false.
"""
from pathlib import Path
import plan_beta35_offline as p

def record(config,counts,sequence):
    p.require(1<=sequence<=0xffffffff,'Journal sequence exhausted')
    r=bytearray(b'\xff'*128);r[:8]=b'WC\x01\0'+sequence.to_bytes(4,'little');r[8:24]=config
    r[24:120]=b''.join(n.to_bytes(3,'little') for n in counts)
    r[120:122]=p.crc(r[:120]).to_bytes(2,'little');r[127]=0
    return bytes(r)

def preference(config,page,generation):
    cfg=bytearray(config);cfg[7:13]=b'P'+bytes([page])+generation.to_bytes(4,'little');cfg[14:]=p.config_checksum(cfg)
    return bytes(cfg)

def transaction(banks,active,payload,backup,*,activation):
    p.require(activation=='select-B35','Explicit offline activation policy select-B35 required')
    logical,desired=p.plan(banks,active,payload,backup)
    config=bytes.fromhex(logical['settings']['configuration_hex'])
    selected=preference(config,0xB0,47)
    common=dict(schema=1,version='2.0b35',generation=47,semantic_plan_only=True,
        execution_permitted=False,installation_permitted=False,release_qualified=False,route_qualified=False,
        board_access=False,journal_history_policy='Reclaim registered WC history; retain original full history in verified private backup',
        counts_policy='Durably reserve all planned erase attempts before any erase; interrupted transactions may overcount unattempted rows',
        startup_and_EDU_bytes_preserved=True,activation_policy=activation,
        linked_reservation_helper_qualified=False,installer_execution_qualified=False,
        physical_interruption_qualified=False,source_bank_sha256=p.bank_hashes(banks),
        logical_planner_sha256=p.sha((p.ROOT/'tools/plan_beta35_offline.py').read_bytes()),
        transaction_planner_sha256=p.sha(Path(__file__).read_bytes()),
        outstanding_gates=['Implement/build RAM reservation writer and all-bank preflight without changing frozen payloads',
            'Execute exact generated installer in instruction model with reservation, commit, corruption and interruption checks',
            'Backup restoration must account for newly attempted erases; copying old wear counters is not qualified restoration',
            'Physical acceptance after protected campaign; A35/legacy/private-ABI routes remain refused'])
    if logical['no_payload_change'] and config==selected:
        return dict(common,no_change=True,operations=[],proposed_bank_sha256=p.bank_hashes(banks)),[],list(banks)
    sequence=logical['settings']['journal_sequence']
    p.require(sequence<=0xffffffff-3,'Three journal sequences unavailable')
    latest_offset=logical['settings']['journal_offset'];retained=(latest_offset//4096+8);staging=25-retained
    for off in range(0x4000,0x6000,128):
        r=bytes(banks[3][off:off+128])
        if r==b'\xff'*128:continue
        p.require(r[:4]==b'WC\x01\0' and r[127]==0 and p.crc(r[:120])==int.from_bytes(r[120:122],'little')
            and r[122:127]==b'\xff'*5,'Unknown, occupied or torn journal record; transaction refused')
    start=(retained-8)*4096
    free=[off for off in range(start,start+4096,128) if banks[3][off:off+128]==b'\xff'*128]
    p.require(bool(free),'No erased reservation record slot in retained journal sector')
    reservation_offset=free[0]
    sectors=[(3,staging)]+[(x['bank'],x['sector']) for x in logical['proposed_payload_sectors']]+[(3,retained)]
    p.require(len(sectors)==len(set(sectors)),'Duplicate planned sector erase')
    counts=list(logical['settings']['erase_counts'])
    for bank,sector in sectors:
        i=bank*8+sector-8;p.require(counts[i]<0xffffff,'Erase-attempt counter exhausted for transaction');counts[i]+=1
    generation=logical['source_identity']['source_generation']
    fallback=preference(config,0xA0,generation)
    # Source A is retained; its generation, not the old preferred B's, is used.
    p.require(bytes(banks[3][0x2008:0x200c])==generation.to_bytes(4,'little'),'Retained A generation mismatch')
    reserve=record(fallback,counts,sequence+1)
    stage=record(fallback,counts,sequence+2)+b'\xff'*(4096-128)
    final=record(selected,counts,sequence+3)+b'\xff'*(4096-128)
    pending=[bytearray(b) for b in banks];operations=[];data=[]
    def append(kind,bank,address,body,*,erase=False,commit=None):
        before=p.bank_hashes(pending);off=address-0x8000
        pending[bank][off:off+len(body)]=body
        operations.append(dict(kind=kind,bank=bank,address=address,bytes=len(body),erase=erase,
            data_sha256=p.sha(body),source_bank_sha256=before,proposed_bank_sha256=p.bank_hashes(pending),
            commit_address=commit,
            record_commit_rule='WC marker byte 127 is programmed only after bytes 0..126 are verified' if 'journal' in kind or kind=='reserve-record' else None))
        data.append(body)
    append('reserve-record',3,reservation_offset+0x8000,reserve,commit=reservation_offset+0x807f)
    append('stage-journal',3,staging<<12,stage,erase=True,commit=(staging<<12)+127)
    for row in logical['proposed_payload_sectors']:
        bank,sector=row['bank'],row['sector'];off=(sector-8)*4096
        commit=0xB003 if (bank,sector)==(1,11) else 0xB01F if (bank,sector)==(3,11) else None
        append('payload-sector',bank,sector<<12,desired[bank][off:off+4096],erase=True,commit=commit)
    append('activate-journal',3,retained<<12,final,erase=True,commit=(retained<<12)+127)
    cfg_after=selected
    p.require(cfg_after[:7]==config[:7] and cfg_after[13]==config[13],'Startup/EDU settings changed')
    p.require(pending[3][0x2000:0x3000]==banks[3][0x2000:0x3000],'Retained A changed')
    result=dict(common,no_change=False,reservation_offset=reservation_offset,
        retained_journal_sector=retained,staging_journal_sector=staging,
        source_configuration_hex=config.hex(),fallback_configuration_hex=fallback.hex(),target_configuration_hex=selected.hex(),
        counts_before=logical['settings']['erase_counts'],reserved_counts=counts,sequence_before=sequence,sequence_after=sequence+3,
        planned_erase_order=[list(x) for x in sectors],operations=operations,
        proposed_bank_sha256=p.bank_hashes(pending),
        journal_reservation_is_required_before_first_erase=True)
    return result,data,[bytes(b) for b in pending]
