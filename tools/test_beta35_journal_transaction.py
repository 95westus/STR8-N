"""Semantic byte-state proof only; does not execute linked installer instructions."""
import argparse,json,traceback
from datetime import datetime,timezone
from pathlib import Path
import plan_beta35_journal_transaction as j
p=j.p

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True,type=Path);args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);checks=[];payload=p.ROOT/'tmp/c35e/payload'
    def fixture(board,after=False):
        if after:folder=p.ROOT/f'output/qualification/beta35-fleet-2026-10-16/{board}';prefix='expected-b'
        else:
            base=p.ROOT/'output/qualification/beta34-fleet-2026-10-16';folder=base/'fresh/2512' if board=='2512' else base/board/'hardware'
            prefix='flash-1-b' if board=='2512' else 'final-b'
        return [(folder/f'{prefix}{i}.bin').read_bytes() for i in range(4)]
    def clone(b):return [bytearray(x) for x in b]
    def latest(banks):
        rows=[]
        for off in range(0x4000,0x6000,128):
            r=bytes(banks[3][off:off+128])
            if r[:4]==b'WC\x01\0' and r[127]==0 and p.crc(r[:120])==int.from_bytes(r[120:122],'little'):
                rows.append((int.from_bytes(r[4:8],'little'),r))
        assert rows;return max(rows,key=lambda x:x[0])[1]
    def passed(label,**info):checks.append(dict(name=label,passed=True,**info));print('PASS',label,flush=True)
    def compile(b,**kw):return j.transaction(b,0xA0,payload,b,activation=kw.get('activation','select-B35'))
    def refuse(label,b,contains,**kw):
        try:compile(b,**kw)
        except ValueError as e:assert contains in str(e),(label,str(e));passed(label,refusal=str(e))
        else:raise AssertionError('Unsafe transaction accepted: '+label)
    def mutate_latest(b,fn):
        b=clone(b);source,_,_,_=p.load_inputs(payload);saved=p.settings(b,p.identify(b,0xA0,source));off=saved['journal_offset']
        r=bytearray(b[3][off:off+128]);fn(r);r[120:122]=p.crc(r[:120]).to_bytes(2,'little');b[3][off:off+128]=r;return b
    def prove(label,banks):
        plan,data,wanted=compile(banks);assert len(plan['planned_erase_order'])==8 and len(plan['operations'])==9
        state=clone(banks);actual=[0]*32;events=0;checked=0;payload_verified=0
        config=bytes.fromhex(plan['source_configuration_hex']);before_counts=plan['counts_before']
        def invariant():
            nonlocal checked
            r=latest(state);cfg=r[8:24]
            assert cfg[:7]==config[:7] and cfg[13]==config[13] and cfg[14:]==p.config_checksum(cfg)
            counts=[int.from_bytes(r[24+i*3:27+i*3],'little') for i in range(32)]
            assert all(c>=before_counts[i]+actual[i] for i,c in enumerate(counts)),(label,'durable counts',events)
            if cfg[7:8]==b'P':
                off=(cfg[8]-0x80)*256;slot=state[3][off:off+4096]
                assert slot[:4]==b'MI\1'+cfg[8:9] and slot[31]==0
                assert cfg[9:13]==slot[8:12] and p.crc(slot[:18]+slot[32:])==int.from_bytes(slot[18:20],'little')
                if cfg[8]==0xB0 and cfg[9:13]==(47).to_bytes(4,'little'):
                    assert payload_verified==6,'New B selected before all payload verification'
            assert state[3][0x2000:0x3000]==banks[3][0x2000:0x3000]
            assert state[3][0x6000:]==banks[3][0x6000:]
            checked+=1
        invariant()
        for step,body in zip(plan['operations'],data):
            assert p.bank_hashes(state)==step['source_bank_sha256']
            bank=step['bank'];off=step['address']-0x8000
            if step['erase']:
                state[bank][off:off+4096]=b'\xff'*4096;actual[bank*8+(step['address']>>12)-8]+=1;events+=1;invariant()
            commit=None if step['commit_address'] is None else step['commit_address']-step['address']
            order=[i for i,v in enumerate(body) if v!=255 and i!=commit]
            if commit is not None:order.append(commit)
            for i in order:
                assert state[bank][off+i]==255
                state[bank][off+i]=body[i];events+=1;invariant()
            assert state[bank][off:off+len(body)]==body
            if step['kind']=='payload-sector':payload_verified+=1
            assert p.bank_hashes(state)==step['proposed_bank_sha256']
        assert [bytes(x) for x in state]==wanted and p.bank_hashes(state)==plan['proposed_bank_sha256']
        assert latest(state)[8:24]==bytes.fromhex(plan['target_configuration_hex'])
        assert [before_counts[i]+actual[i] for i in range(32)]==plan['reserved_counts']
        out=args.out/label;out.mkdir();(out/'transaction.json').write_text(json.dumps(plan,indent=2)+'\n')
        for n,body in enumerate(data):(out/f'operation-{n:02d}.bin').write_bytes(body)
        for n,b in enumerate(wanted):(out/f'proposed-b{n}.bin').write_bytes(b)
        passed(label+' all semantic byte states preserve boot preference, settings, A/F and durable erase-count bounds',
               semantic_states_checked=checked,erase_operations=sum(actual),byte_mutations=events-sum(actual),
               instruction_execution=False)
    try:
        for board in ['2205','2512','2604','2609']:
            prove(board,fixture(board))
            existing=fixture(board,True);plan,data,expected=compile(existing)
            assert plan['no_change'] and not data and expected==existing
            passed(board+' already selected B35 is exact no-op even when manually running A')
        before=fixture('2512');reverse=clone(before);reverse[3][0x4000:0x5000],reverse[3][0x5000:0x6000]=before[3][0x5000:0x6000],before[3][0x4000:0x5000]
        prove('reverse-journal-sectors',reverse)
        refuse('activation policy must be explicit',before,'Explicit offline activation policy',activation='retain-old-preference')
        for location in (0x4080,0x5000):
            unknown=clone(before);unknown[3][location]=0
            refuse('unknown journal bytes '+hex(location),unknown,'Unknown, occupied or torn journal')
            torn=clone(before);torn[3][location:location+128]=b'WC\x01\0'+b'\xff'*124
            refuse('torn journal '+hex(location),torn,'Unknown, occupied or torn journal')
        reserved=mutate_latest(before,lambda r:r.__setitem__(122,0));refuse('unknown reserved journal byte',reserved,'Unknown, occupied or torn journal')
        for remaining in (0,1,2):
            b=mutate_latest(before,lambda r,remaining=remaining:r.__setitem__(slice(4,8),(0xffffffff-remaining).to_bytes(4,'little')))
            message='Journal sequence exhausted' if remaining==0 else 'Three journal sequences unavailable'
            refuse('sequence space '+str(remaining),b,message)
        for index in (28,29):
            b=mutate_latest(before,lambda r,index=index:r.__setitem__(slice(24+index*3,27+index*3),b'\xff'*3))
            refuse('journal sector erase count exhausted '+str(index),b,'Erase-attempt counter exhausted for transaction')
        full=clone(before);r=latest(full);counts=[int.from_bytes(r[24+i*3:27+i*3],'little') for i in range(32)]
        seq=int.from_bytes(r[4:8],'little')
        for n in range(32):full[3][0x4000+n*128:0x4080+n*128]=j.record(r[8:24],counts,seq+n)
        refuse('full retained journal needs qualified compaction',full,'No erased reservation record slot')
        # All payload images stay exactly frozen; only C/D and the declared code ranges differ.
        plan,data,expected=compile(before)
        for n in range(4):assert before[n]==fixture('2512')[n]
        assert expected[0]==before[0] and expected[3][0x1000:0x3000]==before[3][0x1000:0x3000]
        passed('source arrays immutable and unowned service records retained')
        for label,tag,mode in [('EDU-OFF',0xA5,0),('native-mode',0,1)]:
            def config(r,tag=tag,mode=mode):r[21]=tag;r[14]=mode;r[22:24]=p.config_checksum(r[8:24])
            b=mutate_latest(before,config);plan,data,expected=compile(b)
            old=bytes.fromhex(plan['source_configuration_hex']);new=bytes.fromhex(plan['target_configuration_hex'])
            assert old[:7]==new[:7] and old[13]==new[13]
            passed(label+' startup/EDU settings preserved; no CPU execution claim')
    except Exception:
        (args.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    report=dict(passed=True,cases=len(checks),checks=checks,finished_utc=datetime.now(timezone.utc).isoformat(),
        semantic_byte_states=sum(c.get('semantic_states_checked',0) for c in checks),
        scope='Abstract journal/activation state transitions; not execution of the linked installer or electrical cuts',
        transaction_planner_sha256=p.sha((p.ROOT/'tools/plan_beta35_journal_transaction.py').read_bytes()),
        logical_planner_sha256=p.sha((p.ROOT/'tools/plan_beta35_offline.py').read_bytes()),test_sha256=p.sha(Path(__file__).read_bytes()),
        board_access=False,linked_reservation_helper_qualified=False,installer_execution_qualified=False,
        physical_interruption_qualified=False,physical_restoration_qualified=False,route_qualified=False,
        installation_permitted=False,release_qualified=False)
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(checks),'semantic journal scenarios;',report['semantic_byte_states'],'byte states; linked helper/installer unqualified')

if __name__=='__main__':main()
