"""Inject bounded polling/readback faults in the linked offline transactions.

No hardware access or electrical timing claim. A late failure can follow an
already-valid journal commit; failure never implies rollback.
"""
import argparse,json,os,sys,traceback
from pathlib import Path
from datetime import datetime,timezone
import beta35_model_transactions as c
p=c.p
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kw):raise RuntimeError('Serial access forbidden in flash-fault model')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    import test_v2_rtc_upgrade as model
    mf=p.read(ws/'BUILD/v2-beta35-candidate/migrator/manifest.json');S=mf['symbols'];model.S=S;model.MANIFEST=mf
    cp=p.read(c.EVIDENCE/'variants-restoration-checkpoint.json');oldcp=p.read(c.EVIDENCE/'transaction-model-checkpoint.json')
    build=Path(oldcp['build_report']);assert p.sha(build.read_bytes())==oldcp['build_report_sha256']
    restore_report=Path(cp['restore_instruction_report']);assert p.sha(restore_report.read_bytes())==cp['restore_instruction_report_sha256']
    forward=build.parent/'2512';restore=restore_report.parent/'2512-complete-restored'
    upgraded=Path(oldcp['report']).parent/'2512-complete'
    contexts=[('forward',forward,c.old.fixture('2512')),
        ('restore',restore,[(upgraded/f'b{i}.bin').read_bytes() for i in range(4)])]
    checks=[];current=None
    def invariant(m):
        r=c.latest(m.banks)[2];cfg=r[8:24];source=bytes.fromhex(m.info['transaction']['source_configuration_hex'])
        assert cfg[:7]==source[:7] and cfg[13]==source[13] and cfg[14:]==p.config_checksum(cfg)
        counts=[int.from_bytes(r[24+i*3:27+i*3],'little') for i in range(32)]
        assert all(counts[i]>=m.info['transaction']['counts_before'][i]+m.attempts[i] for i in range(32))
        assert cfg[7:8]==b'P' and cfg[8] in (0xa0,0xb0)
        offset=(cfg[8]-0x80)*256;slot=m.banks[3][offset:offset+4096]
        assert slot[:4]==b'MI\1'+cfg[8:9] and slot[31]==0 and cfg[9:13]==slot[8:12]
        assert p.crc(slot[:18]+slot[32:])==int.from_bytes(slot[18:20],'little')
        assert bytes(m.banks[0])==m.original[0] and bytes(m.banks[3][0x2000:0x3000])==m.original[3][0x2000:0x3000]
        assert bytes(m.banks[3][0x6000:])==m.original[3][0x6000:]
        if cfg==bytes.fromhex(m.info['transaction']['target_configuration_hex']):
            assert bytes(m.banks[1])==m.expected[1] and bytes(m.banks[2])==m.expected[2]
            assert bytes(m.banks[3][0x3000:0x4000])==m.expected[3][0x3000:0x4000]
    class Memory(model.Memory):
        def __init__(self,banks,info,expected,row,kind):
            super().__init__(banks,set(map(tuple,info['steps'])),{},commit_records={});self.require_maintenance_commit=False
            self.original=list(map(bytes,banks));self.info=info;self.expected=expected;self.target_row=row;self.kind=kind
            self.row=-1;self.last=None;self.injection=None;self.injected_events=None;self.inject_read=None;self.attempts=[0]*32
        def mutated(self,kind,address,value):
            super().mutated(kind,address,value);self.last=(kind,self.bank,address,value)
            if kind=='erase':self.attempts[self.bank*8+(address>>12)-8]+=1
            invariant(self)
        def __getitem__(self,address):
            value=super().__getitem__(address)
            if self.inject_read and address==self.inject_read[1] and self.bank==self.inject_read[0]:
                self.inject_read=None;self.injection=dict(kind=self.kind,bank=self.bank,address=address,expected=value,returned=value^1)
                self.injected_events=len(self.events)
                if self.kind=='persistent-verify':self.banks[self.bank][address-0x8000]^=1
                return value^1
            return value
    class CPU(model.CPU):
        def step(self):
            m=self.memory
            if m.row==m.target_row and m.injection is None:
                if self.pc==S['V2W_POLL'] and m.last:
                    kind,bank,address,value=m.last
                    wanted=(m.kind=='erase-timeout' and kind=='erase') or (m.kind=='program-timeout' and kind=='program')
                    op=m.info['transaction']['operations'][m.target_row+1]
                    wanted |= m.kind=='commit-timeout' and kind=='program' and address==op['commit_address']
                    if wanted:
                        m.injection=dict(kind=m.kind,bank=bank,address=address,actual_mutation=kind)
                        m.injected_events=len(m.events);self.stPop();self.pc=S['V2W_TIMEOUT'];return self
                if self.pc==S['V2W_VERIFY'] and m.kind in ('transient-verify','persistent-verify'):
                    m.inject_read=(m.bank,int.from_bytes(m.ram[0xe4:0xe6],'little'))
            return super().step()
    try:
        for context,folder,banks in contexts:
            info=p.read(folder/'plan.json');assert p.bank_hashes(banks)==info['source_sha256']
            expected=[(folder/f'expected-b{i}.bin').read_bytes() for i in range(4)];assert p.bank_hashes(expected)==info['expected_sha256']
            path=folder/'installer-model-only.s19';assert p.sha(path.read_bytes())==info['installer_sha256'];cells,entry=migration.read_s19(path)
            rows=info['transaction']['operations'][1:]
            tests=[(n,k) for n in range(len(rows)) for k in ['erase-timeout','program-timeout','transient-verify','persistent-verify']
                   if k!='program-timeout' or any(v!=255 for v in (folder/f'transfer-{n:02d}.bin').read_bytes())]
            tests += [(n,'commit-timeout') for n,op in enumerate(rows) if op['commit_address'] is not None]
            for target,kind in tests:
                label=f'{context}-row-{target}-{kind}';out=a.out/label;out.mkdir();current=out
                m=Memory(banks,info,expected,target,kind)
                for address,value in cells.items():m.ram[address]=value
                cpu=CPU(memory=m,pc=entry);m.cpu=cpu;m.rx.extend(b'Y\r')
                try:
                    for n,(bank,sector) in enumerate(info['steps']):
                        token=f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode();model.run(cpu,lambda:token in bytes(m.tx) or cpu.pc==S['MIG_HALT'])
                        assert cpu.pc!=S['MIG_HALT'];m.row=n;m.tx.clear()
                        data=(folder/f'transfer-{n:02d}.bin').read_bytes();assert p.sha(data)==info['transfer_sha256'][n];m.rx.extend(data)
                        if n==target:break
                    model.run(cpu,lambda:cpu.pc==S['MIG_HALT'])
                    assert m.injection is not None and b'REFUSED/FAILED' in m.tx and b'MIGRATION VERIFIED' not in m.tx
                    assert len(m.events)==m.injected_events and m.busy is None and m.ram[0xf4]==0
                    assert m.ram[0xf6]==(1 if 'timeout' in kind else 2)
                    assert sum(m.attempts)==target+1 and cpu.pc<0x8000
                    invariant(m)
                except Exception:
                    for i,b in enumerate(m.banks):(out/f'failed-b{i}.bin').write_bytes(b)
                    (out/'failure-transcript.txt').write_bytes(m.tx);raise
                for i,b in enumerate(m.banks):(out/f'b{i}.bin').write_bytes(b)
                (out/'events.json').write_text(json.dumps(m.events)+'\n');(out/'transcript.txt').write_bytes(m.tx)
                cfg=c.latest(m.banks)[2][8:24]
                item=dict(name=label,passed=True,row=target,injection=m.injection,mutation_events=len(m.events),erase_attempts=sum(m.attempts),
                    events_after_injection=0,bank_on_halt=m.bank,nmi_hold_released=True,flash_busy_cleared=True,
                    halted_in_ram=True,reported_failure=True,success_reported=False,selected_page=cfg[8],
                    selected_generation=int.from_bytes(cfg[9:13],'little'),target_preference_already_committed=cfg==bytes.fromhex(info['transaction']['target_configuration_hex']),
                    bank_sha256=p.bank_hashes(m.banks),installer_sha256=info['installer_sha256'])
                checks.append(item);(a.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',label,flush=True)
    except Exception:
        (a.out/'failure.json').write_text(json.dumps(dict(passed=False,current=str(current),checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    sources={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(ws.resolve()):
            name=path.resolve().relative_to(ws).as_posix();digest=p.sha(path.read_bytes());sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    result=dict(passed=True,cases=len(checks),checks=checks,finished_utc=datetime.now(timezone.utc).isoformat(),
        test_sha256=p.sha(Path(__file__).read_bytes()),model_sources=sources,serial_disabled=True,board_access=False,
        integrated_flash_fault_model_passed=True,scope='Bounded poll-timeout and injected transient/persistent verification faults, not electrical timing or arbitrary damage',
        source_reports={str(build):oldcp['build_report_sha256'],str(restore_report):cp['restore_instruction_report_sha256']},
        physical_interruption_qualified=False,route_qualified=False,installation_permitted=False,release_qualified=False)
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'integrated flash fault cases')
if __name__=='__main__':main()
