"""Run the separately linked reservation helper, with hardware access disabled."""
import argparse,json,os,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
import plan_beta35_journal_transaction as journal
p=journal.p

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--build',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);build=p.read(args.build/'build-report.json')
    body=(args.build/'reservation.bin').read_bytes();assert p.sha(body)==build['binary_sha256']
    assert p.sha((p.ROOT/'release/beta35-prerelease/source/reservation.asm').read_bytes())==build['source_sha256']
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');workspace=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'));sys.path.insert(0,str(workspace/'tools'))
    import serial
    def forbidden(*a,**k):raise RuntimeError('Serial access forbidden in helper qualification')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    import test_v2_rtc_upgrade as model
    manifest_path=workspace/'BUILD/v2-beta35-candidate/migrator/manifest.json'
    assert p.sha(manifest_path.read_bytes())==build['frozen_manifest_sha256']
    mf=p.read(manifest_path);model.S=mf['symbols'];model.MANIFEST=mf;S=model.S
    template=workspace/'BUILD/v2-beta35-candidate/migrator/rtc-migrator-2000.s19'
    assert p.sha(template.read_bytes())==mf['sha256'];cells,entry=migration.read_s19(template)
    checks=[];proofs={}
    class Cut(Exception):pass
    class Memory(model.Memory):
        def __init__(self,banks,address,cut=None):
            super().__init__(banks,{(3,12),(3,13)},{},commit_records={});self.address=address;self.cut=cut;self.failure=None;self.verify_calls=0
        def mutated(self,kind,address,value):
            assert kind=='program' and self.bank==3 and self.address<=address<self.address+128
            super().mutated(kind,address,value)
            if len(self.events)==self.cut:raise Cut()
    class CPU(model.CPU):
        def step(self):
            m=self.memory
            if m.failure=='timeout' and self.pc==build['links']['V2W_POLL']:
                self.stPop();self.pc=build['links']['V2W_TIMEOUT'];return self
            if self.pc==build['symbols']['R_VERIFY_PREFIX']:
                m.verify_calls+=1
                if (m.failure=='prefix-readback' and m.verify_calls==1) or (m.failure=='committed-readback' and m.verify_calls==2):
                    m.banks[3][m.address-0x8000]^=1
            return super().step()
    def banks_for(board):
        base=p.ROOT/'output/qualification/beta34-fleet-2026-10-16';folder=base/'fresh/2512' if board=='2512' else base/board/'hardware'
        prefix='flash-1-b' if board=='2512' else 'final-b';return [(folder/f'{prefix}{i}.bin').read_bytes() for i in range(4)]
    def passed(label,**info):checks.append(dict(name=label,passed=True,**info));print('PASS',label,flush=True)
    def latest(banks):
        rows=[]
        for off in range(0x4000,0x6000,128):
            r=bytes(banks[3][off:off+128])
            if r[:4]==b'WC\x01\0' and r[127]==0 and p.crc(r[:120])==int.from_bytes(r[120:122],'little'):
                rows.append((int.from_bytes(r[4:8],'little'),r))
        assert rows;return max(rows,key=lambda x:x[0])[1]
    def prepare(banks,*,stale=None,address=None,alter=None,cut=None,failure=None):
        tx,records,_=journal.transaction(banks,0xA0,p.ROOT/'tmp/c35e/payload',banks,activation='select-B35')
        target=tx['operations'][0]['address'];initial=[bytearray(b) for b in banks]
        if stale is not None:initial[stale][123]^=1
        memory=Memory(initial,target,cut);cpu=CPU(memory=memory,pc=entry);memory.cpu=cpu
        for a,v in cells.items():memory.ram[a]=v
        memory.ram[mf['count']]=1  # Admission only: stop at MIG_NEXT before reading any row.
        memory.rx.extend(b'Y\r');model.run(cpu,lambda:cpu.pc==S['MIG_NEXT'])
        assert not memory.events
        memory.ram[0x3000:0x3000+len(body)]=body
        memory.ram[0x3500:0x3510]=b''.join(migration.fnv(b).to_bytes(4,'little') for b in banks)
        memory.ram[0x3510:0x3512]=(target if address is None else address).to_bytes(2,'little')
        memory.ram[0x3600:0x3700]=records[0]+b'\xff'*128
        if alter:alter(memory)
        if not alter or not getattr(memory,'retain_input_hash',False):
            memory.ram[0x3512:0x3516]=migration.fnv(memory.ram[0x3600:0x3700]).to_bytes(4,'little')
        memory.failure=failure
        return memory,cpu,tx,records[0]
    def execute(memory,cpu):
        cpu.stPushWord(0x1ff);cpu.pc=0x3000
        try:model.run(cpu,lambda:cpu.pc==0x200)
        except Cut:return None
        assert cpu.sp==255 and memory.bank==3
        return bool(cpu.p&cpu.CARRY)
    def refused(label,**kw):
        mem,cpu,tx,r=prepare(sample,**kw);result=execute(mem,cpu)
        assert result is False and mem.ram[0x6236]!=0 and not mem.events,label
        passed(label,mutation_events=0)
    try:
        sample=banks_for('2512')
        # Check the actual linked FNV instructions before enabling the model's shortcut.
        mem,cpu,tx,r=prepare(sample);mem.ram[0x6000:0x6100]=bytes(range(256));mem.ram[0xE0:0xE2]=b'\0\x60';mem.ram[0x620C]=0x61
        cpu.pc=S['MIG_HASH_RANGE'];cpu.accelerate_hash=False;cpu.stPushWord(0x1ff);model.run(cpu,lambda:cpu.pc==0x200)
        assert int.from_bytes(mem.ram[0x6204:0x6208],'little')==migration.fnv(bytes(range(256)))
        passed('actual linked FNV equivalence before hash-loop acceleration')
        for board in ['2205','2512','2604','2609']:
            banks=banks_for(board);mem,cpu,tx,r=prepare(banks);assert execute(mem,cpu) is True and mem.ram[0x6236]==0
            target=tx['operations'][0]['address'];off=target-0x8000
            assert bytes(mem.banks[3][off:off+128])==r and mem.events[-1]==('program',3,target+127,0)
            assert latest(mem.banks)==r
            expected=[bytearray(b) for b in banks];expected[3][off:off+128]=r
            assert mem.banks==expected
            proofs[board]=dict(events=len(mem.events),target=target,final_bank_sha256=p.bank_hashes(mem.banks))
            (args.out/(board+'-events.json')).write_text(json.dumps(mem.events)+'\n')
            passed(board+' actual linked append, readback and commit-last; no erase',events=len(mem.events))
        for bank in range(4):refused('stale bank '+str(bank)+' refused before mutation',stale=bank)
        for address in [0xA080,0xC001,0xE080,0xC0C0,0xC000]:refused('unsafe/occupied destination '+hex(address),address=address)
        def corrupt_input(m):
            m.ram[0x3512:0x3516]=migration.fnv(m.ram[0x3600:0x3700]).to_bytes(4,'little');m.ram[0x3620]^=1;m.retain_input_hash=True
        refused('corrupt input page refuses before mutation',alter=corrupt_input)
        refused('bad record CRC refuses despite repaired input FNV',alter=lambda m:m.ram.__setitem__(0x3678,m.ram[0x3678]^1))
        def alter_record(index,value,*,checksum=False):
            def change(m):
                m.ram[0x3600+index]=value
                if checksum:m.ram[0x3616:0x3618]=p.config_checksum(m.ram[0x3608:0x3618])
                m.ram[0x3678:0x367A]=p.crc(m.ram[0x3600:0x3678]).to_bytes(2,'little')
            return change
        for label,index,value in [('magic',0,0),('commit marker',127,255),('configuration checksum',22,0),('premature B preference',16,0xB0),('wrong A generation',17,0)]:
            refused(label+' refuses with repaired CRC/input FNV',alter=alter_record(index,value))
        for failure in ('timeout','prefix-readback','committed-readback'):
            mem,cpu,tx,r=prepare(sample,failure=failure);assert execute(mem,cpu) is False
            assert latest(mem.banks)==latest(sample) and all(e[0]=='program' for e in mem.events)
            passed(failure+' failure returns safely without erase',mutation_events=len(mem.events))
        # Inject a cut immediately after every actual byte-program event.
        count=proofs['2512']['events'];cut_results=[]
        for n in range(1,count+1):
            mem,cpu,tx,r=prepare(sample,cut=n);assert execute(mem,cpu) is None
            valid=latest(mem.banks)
            assert valid==(r if n==count else latest(sample))
            assert mem.banks[0]==sample[0] and mem.banks[3][0x2000:0x3000]==sample[3][0x2000:0x3000]
            cut_results.append(dict(after_program_event=n,reservation_valid=n==count,erase_events=0))
        (args.out/'program-cut-results.json').write_text(json.dumps(cut_results,indent=2)+'\n')
        passed('cuts after every linked append program event',cut_cases=count,claim='Emulator mutation-boundary cuts; not electrical partial-byte behavior')
    except Exception:
        (args.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    sources={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(workspace.resolve()):
            name=path.resolve().relative_to(workspace).as_posix();digest=p.sha(path.read_bytes());sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    report=dict(passed=True,cases=len(checks),checks=checks,finished_utc=datetime.now(timezone.utc).isoformat(),
        scope='Separate helper append only; full installer integration, staged journals, payload and activation interruption/restore remain unqualified',
        build_report_sha256=p.sha((args.build/'build-report.json').read_bytes()),helper_binary_sha256=build['binary_sha256'],
        test_sha256=p.sha(Path(__file__).read_bytes()),model_sources=sources,serial_disabled=True,board_access=False,
        standalone_helper_model_passed=True,installer_integrated=False,full_transaction_qualified=False,
        physical_interruption_qualified=False,physical_restoration_qualified=False,installation_permitted=False,release_qualified=False,
        hash_opcode_equivalence_checked=True,hash_range_loops_accelerated=True,proofs=proofs)
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(checks),'linked-helper scenarios; full installer remains unqualified')

if __name__=='__main__':main()
