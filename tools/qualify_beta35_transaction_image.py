"""Execute separate integrated transaction images with serial disabled.

Mutation-boundary cuts are emulator snapshots, not electrical interruption or
physical restoration. Preserve every failed/cut state for later recovery work.
"""
import argparse,json,os,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
import build_beta35_transaction_image as builder
p=builder.p

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--build',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);build=p.read(args.build/'build-report.json');assert build['passed']
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');workspace=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'));sys.path.insert(0,str(workspace/'tools'))
    import serial
    def forbidden(*a,**k):raise RuntimeError('Serial access forbidden in integrated transaction model')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    import test_v2_rtc_upgrade as model
    manifest=workspace/'BUILD/v2-beta35-candidate/migrator/manifest.json';mf=p.read(manifest);S=mf['symbols'];model.S=S;model.MANIFEST=mf
    assert p.sha(manifest.read_bytes())==builder.MANIFEST_SHA
    checks=[];successful={}
    class Cut(Exception):pass
    def latest(banks):
        good=[]
        for off in range(0x4000,0x6000,128):
            r=bytes(banks[3][off:off+128])
            if r[:4]==b'WC\x01\0' and r[127]==0 and p.crc(r[:120])==int.from_bytes(r[120:122],'little'):
                good.append((int.from_bytes(r[4:8],'little'),r))
        assert good,'No valid journal record';return max(good,key=lambda x:x[0])[1]
    def invariant(m):
        row=latest(m.banks);cfg=row[8:24];sourcecfg=bytes.fromhex(m.info['transaction']['source_configuration_hex'])
        assert cfg[:7]==sourcecfg[:7] and cfg[13]==sourcecfg[13] and cfg[14:]==p.config_checksum(cfg)
        counts=[int.from_bytes(row[24+i*3:27+i*3],'little') for i in range(32)]
        before=m.info['transaction']['counts_before'];assert all(c>=before[i]+m.attempts[i] for i,c in enumerate(counts))
        assert cfg[7:8]==b'P' and cfg[8] in (0xA0,0xB0)
        off=(cfg[8]-0x80)*256;slot=m.banks[3][off:off+4096]
        assert slot[:4]==b'MI\1'+cfg[8:9] and slot[31]==0 and cfg[9:13]==slot[8:12]
        assert p.crc(slot[:18]+slot[32:])==int.from_bytes(slot[18:20],'little')
        if cfg[8]==0xB0 and cfg[9:13]==(47).to_bytes(4,'little'):
            assert m.monitor_committed
            assert bytes(m.banks[1])==m.expected[1] and bytes(m.banks[2])==m.expected[2]
        assert bytes(m.banks[0])==m.original[0]
        assert bytes(m.banks[3][0x2000:0x3000])==m.original[3][0x2000:0x3000]
        assert bytes(m.banks[3][0x6000:])==m.original[3][0x6000:]
    class Memory(model.Memory):
        def __init__(self,initial,original,info,expected,cut=None):
            super().__init__(initial,set(map(tuple,info['steps'])),{},commit_records={})
            # This is not MAINT relocation: B2's existing MAINT remains exact.
            self.require_maintenance_commit=False
            self.original=original;self.info=info;self.expected=expected;self.cut=cut
            self.attempts=[0]*32;self.monitor_committed=False;self.activation_committed=False
        def mutated(self,kind,address,value):
            super().mutated(kind,address,value)
            if kind=='erase':self.attempts[self.bank*8+(address>>12)-8]+=1
            if self.bank==1 and address==0xB003 and value==0x3F:
                assert bytes(self.banks[1])==self.expected[1]
            if self.bank==3 and address==0xB01F and value==0:
                assert bytes(self.banks[1])==self.expected[1] and bytes(self.banks[2])==self.expected[2]
                assert bytes(self.banks[3][0x3000:0x4000])==self.expected[3][0x3000:0x4000]
                assert latest(self.banks)[16]==0xA0
                self.monitor_committed=True
            if kind=='program' and self.bank==3 and address==(self.info['transaction']['retained_journal_sector']<<12)+127 and value==0:
                self.activation_committed=True
            # Check durable journal/selection invariants after every modeled mutation.
            invariant(self)
            if self.cut==len(self.events):raise Cut()
    def load(board,*,stale=None,cut=None):
        folder=args.build/board;info=p.read(folder/'plan.json')
        row=next(x for x in build['boards'] if x['board']==board);assert p.sha((folder/'plan.json').read_bytes())==row['plan_sha256']
        assert p.sha((folder/'installer-model-only.s19').read_bytes())==info['installer_sha256']==row['installer_sha256']
        original=builder.fixture(board);expected=[(folder/f'expected-b{i}.bin').read_bytes() for i in range(4)]
        assert p.bank_hashes(original)==info['source_sha256'] and p.bank_hashes(expected)==info['expected_sha256']
        transfers=[(folder/f'transfer-{i:02d}.bin').read_bytes() for i in range(len(info['steps']))]
        assert [p.sha(x) for x in transfers]==info['transfer_sha256']
        initial=[bytearray(b) for b in original]
        if stale is not None:initial[stale][123]^=1
        m=Memory(initial,original,info,expected,cut);cells,entry=migration.read_s19(folder/'installer-model-only.s19')
        for a,v in cells.items():m.ram[a]=v
        cpu=model.CPU(memory=m,pc=entry);m.cpu=cpu;m.rx.extend(b'Y\r')
        return m,cpu,info,transfers
    def save_case(label,m,outcome):
        folder=args.out/label;folder.mkdir()
        for i,b in enumerate(m.banks):(folder/f'b{i}.bin').write_bytes(b)
        (folder/'transcript.txt').write_bytes(m.tx)
        (folder/'events.json').write_text(json.dumps(m.events)+'\n')
        result=dict(name=label,passed=True,outcome=outcome,mutation_events=len(m.events),erase_events=sum(m.attempts),
            monitor_committed=m.monitor_committed,activation_committed=m.activation_committed,bank_sha256=p.bank_hashes(m.banks))
        checks.append(result);(args.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',label,flush=True)
    def execute(label,board='2512',*,stale=None,corrupt=None,partial=None,cut=None):
        m,cpu,info,transfers=load(board,stale=stale,cut=cut)
        outcome='complete'
        try:
            for n,(bank,sector) in enumerate(info['steps']):
                token=f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode()
                model.run(cpu,lambda:token in bytes(m.tx) or cpu.pc==S['MIG_HALT'])
                if cpu.pc==S['MIG_HALT']:
                    assert stale is not None and not m.events and b'REFUSED/FAILED' in m.tx
                    outcome='stale source refused before any mutation';break
                m.tx.clear();prior=len(m.events);data=bytearray(transfers[n])
                if corrupt==n:data[127]^=1
                if partial==n:data=data[:2048]
                m.rx.extend(data)
                if corrupt==n:
                    model.run(cpu,lambda:cpu.pc==S['MIG_HALT'])
                    assert len(m.events)==prior and not m.activation_committed and b'REFUSED/FAILED' in m.tx
                    outcome='corrupt payload refused before row mutation';break
                if partial==n:
                    model.run(cpu,lambda:not m.rx and cpu.pc==S['V2W_RAW_POLL'])
                    assert len(m.events)==prior and not m.activation_committed
                    outcome='partial payload waiting; row untouched';break
            else:
                model.run(cpu,lambda:cpu.pc==S['MIG_HALT'])
                assert b'MIGRATION VERIFIED' in m.tx and not b'REFUSED/FAILED' in m.tx
                assert [bytes(b) for b in m.banks]==m.expected
                assert [(e[1],e[2]>>12) for e in m.events if e[0]=='erase']==list(map(tuple,info['steps']))
                assert m.monitor_committed and m.activation_committed
                assert m.events[-1]==('program',3,(info['transaction']['retained_journal_sector']<<12)+127,0)
                assert latest(m.banks)[8:24]==bytes.fromhex(info['transaction']['target_configuration_hex'])
                successful[board]=list(m.events)
        except Cut:
            assert cut==len(m.events);outcome='injected mutation-boundary cut'
        if stale is None:invariant(m)
        save_case(label,m,outcome)
        return m
    try:
        m,cpu,info,_=load('2512');sample=bytes(range(256));m.ram[0x6000:0x6100]=sample
        m.ram[0xE0:0xE2]=b'\0\x60';m.ram[0x620C]=0x61;cpu.pc=S['MIG_HASH_RANGE'];cpu.accelerate_hash=False;cpu.stPushWord(0x1ff)
        model.run(cpu,lambda:cpu.pc==0x200);assert int.from_bytes(m.ram[0x6204:0x6208],'little')==migration.fnv(sample)
        (args.out/'fnv-proof.json').write_text(json.dumps(dict(passed=True,linked_instructions=True,bytes=256))+'\n')
        for board in ['2512','2205','2604','2609']:execute(board+'-complete',board)
        for bank in range(4):execute('stale-bank-'+str(bank),stale=bank)
        for n in range(8):execute('corrupt-row-'+str(n),corrupt=n)
        for n in range(8):execute('partial-row-'+str(n),partial=n)
        events=successful['2512'];positions={1,123}
        info=p.read(args.build/'2512/plan.json');stage=(info['transaction']['staging_journal_sector']<<12)+127
        final=(info['transaction']['retained_journal_sector']<<12)+127
        for n,event in enumerate(events,1):
            kind,bank,address,value=event
            if kind=='erase' or (kind=='program' and ((bank==3 and address in (stage,final,0xB01F)) or (bank==1 and address==0xB003))):
                positions.add(n)
                if n>1:positions.add(n-1)
        (args.out/'cut-schedule.json').write_text(json.dumps(sorted(positions))+'\n')
        for n in sorted(positions):execute('cut-after-event-'+str(n),cut=n)
    except Exception:
        (args.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    sources={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(workspace.resolve()):
            name=path.resolve().relative_to(workspace).as_posix();digest=p.sha(path.read_bytes());sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    report=dict(passed=True,cases=len(checks),checks=checks,mutation_boundary_cut_cases=len(positions),
        finished_utc=datetime.now(timezone.utc).isoformat(),build_report_sha256=p.sha((args.build/'build-report.json').read_bytes()),
        test_sha256=p.sha(Path(__file__).read_bytes()),model_sources=sources,serial_disabled=True,board_access=False,
        hash_opcode_equivalence_checked=True,hash_range_loops_accelerated=True,
        full_transaction_model_passed=True,actual_boot_after_cut_tested=False,
        wear_aware_restoration_qualified=False,physical_interruption_qualified=False,
        route_qualified=False,installation_permitted=False,release_qualified=False,
        legacy_MAINT_relocation_guard_disabled='Existing B2 MAINT is retained; exact final banks and own CLOCK/monitor/journal commit invariants are checked instead',
        scope='Eight-sector reservation/staged journal/payload/activation instruction model; no electrical cuts, cold-boot-after-cut or qualified restoration')
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(checks),'integrated transaction scenarios; recovery/restoration/hardware gates remain open')

if __name__=='__main__':main()
