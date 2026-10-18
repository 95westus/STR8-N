"""Offline linked variant/restoration models; never constructs serial access."""
import argparse,json,os,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
import beta35_model_transactions as c
import plan_beta35_attested_restoration as attested
import plan_beta35_restore_recovery as recovery
p=c.p;j=c.j

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase',choices=['variants','restoration','recovery'],required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');workspace=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(workspace/'BUILD/test-deps'));sys.path.insert(0,str(workspace/'tools'))
    import serial
    def forbidden(*args,**kwargs):raise RuntimeError('Serial access forbidden in offline qualification')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    import test_v2_rtc_upgrade as model
    manifest=p.read(workspace/'BUILD/v2-beta35-candidate/migrator/manifest.json');S=manifest['symbols'];model.S=S;model.MANIFEST=manifest
    cp=p.read(c.EVIDENCE/'transaction-model-checkpoint.json');priorpath=Path(cp['report'])
    assert p.sha(priorpath.read_bytes())==cp['report_sha256'];prior=p.read(priorpath);buildpath=Path(cp['build_report']).parent
    checks=[];cuts=0;mutations=0;current=None;cache={};reused=0
    class Cut(Exception):pass
    def record(label,**data):
        checks.append(dict(name=label,passed=True,**data));(a.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',label,flush=True)
    def invariant(m):
        seq,off,r,valid=c.latest(m.banks);cfg=r[8:24];original_cfg=bytes.fromhex(m.txplan['source_configuration_hex'])
        assert cfg[:7]==original_cfg[:7] and cfg[13]==original_cfg[13] and cfg[14:]==p.config_checksum(cfg)
        counts=[int.from_bytes(r[24+i*3:27+i*3],'little') for i in range(32)]
        assert all(counts[i]>=m.txplan['counts_before'][i]+m.attempts[i] for i in range(32))
        assert cfg[7:8]==b'P' and cfg[8] in (0xa0,0xb0)
        offset=(cfg[8]-0x80)*256;slot=m.banks[3][offset:offset+4096]
        assert slot[:4]==b'MI\1'+cfg[8:9] and slot[31]==0 and slot[8:12]==cfg[9:13]
        assert p.crc(slot[:18]+slot[32:])==int.from_bytes(slot[18:20],'little')
        if cfg==bytes.fromhex(m.txplan['target_configuration_hex']):
            assert bytes(m.banks[1])==m.expected[1] and bytes(m.banks[2])==m.expected[2]
            assert bytes(m.banks[3][0x3000:0x4000])==m.expected[3][0x3000:0x4000]
        assert bytes(m.banks[0])==m.original[0] and bytes(m.banks[3][0x2000:0x3000])==m.original[3][0x2000:0x3000]
        assert bytes(m.banks[3][0x6000:])==m.original[3][0x6000:]
    class Memory(model.Memory):
        def __init__(self,banks,info,expected,cut):
            super().__init__(banks,set(map(tuple,info['steps'])),{},commit_records={});self.require_maintenance_commit=False
            self.original=list(map(bytes,banks));self.expected=expected;self.txplan=info['transaction'];self.attempts=[0]*32;self.cut=cut
        def mutated(self,kind,address,value):
            super().mutated(kind,address,value)
            if kind=='erase':self.attempts[self.bank*8+(address>>12)-8]+=1
            invariant(self)
            if self.cut==len(self.events):raise Cut()
    def execute(label,banks,tx,data,expected,*,cut=None,corrupt=None,partial=None,stale=None):
        nonlocal current,cuts,mutations,reused
        folder=a.out/label;info=c.compose(tx,data,banks,expected,folder);current=folder
        if tx['no_change']:
            assert banks==expected and not data and not (folder/'installer-model-only.s19').exists()
            record(label,outcome='exact no-op; no RAM installer emitted',mutation_events=0);return None
        key=json.dumps([info['source_sha256'],info['installer_sha256'],info['transfer_sha256'],info['expected_sha256'],tx['counts_before']],sort_keys=True)
        reusable=cut is None and corrupt is None and partial is None and stale is None
        if a.phase in ('restoration','recovery') and reusable and key in cache:
            m,origin=cache[key];assert [bytes(b) for b in m.banks]==expected
            for i,b in enumerate(m.banks):(folder/f'b{i}.bin').write_bytes(b)
            reused+=1
            record(label,outcome='complete; reused byte-identical CPU model inputs',reused_from=origin,
                input_equivalence='All source banks, complete RAM installer, every transfer, expected banks and initial count bounds hash-identical',
                bank_sha256=p.bank_hashes(m.banks),mutation_events_reused=len(m.events))
            return m
        initial=list(map(bytearray,banks))
        if stale is not None:initial[stale][123]^=1
        m=Memory(initial,info,expected,cut);cells,entry=migration.read_s19(folder/'installer-model-only.s19')
        for address,value in cells.items():m.ram[address]=value
        cpu=model.CPU(memory=m,pc=entry);m.cpu=cpu;m.rx.extend(b'Y\r');outcome='complete'
        try:
            for n,(bank,sector) in enumerate(info['steps']):
                token=f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode()
                model.run(cpu,lambda:token in bytes(m.tx) or cpu.pc==S['MIG_HALT'])
                if cpu.pc==S['MIG_HALT']:
                    assert stale is not None and not m.events and b'REFUSED/FAILED' in m.tx;outcome='stale source refused';break
                m.tx.clear();before=len(m.events);body=bytearray((folder/f'transfer-{n:02d}.bin').read_bytes())
                if corrupt==n:body[127]^=1
                if partial==n:body=body[:2048]
                m.rx.extend(body)
                if corrupt==n:
                    model.run(cpu,lambda:cpu.pc==S['MIG_HALT']);assert len(m.events)==before and b'REFUSED/FAILED' in m.tx
                    outcome='corrupt row refused before mutation';break
                if partial==n:
                    model.run(cpu,lambda:not m.rx and cpu.pc==S['V2W_RAW_POLL']);assert len(m.events)==before
                    outcome='partial row waits without mutation';break
            else:
                model.run(cpu,lambda:cpu.pc==S['MIG_HALT'])
                assert b'MIGRATION VERIFIED' in m.tx and [bytes(b) for b in m.banks]==expected
                assert [[e[1],e[2]>>12] for e in m.events if e[0]=='erase']==tx['planned_erase_order']
                assert m.events[-1]==('program',3,(tx['retained_journal_sector']<<12)+127,0)
                assert c.latest(m.banks)[2][8:24]==bytes.fromhex(tx['target_configuration_hex'])
        except Cut:
            assert len(m.events)==cut;cuts+=1;outcome='mutation-boundary cut'
        except Exception:
            for i,b in enumerate(m.banks):(folder/f'failed-b{i}.bin').write_bytes(b)
            (folder/'failure-transcript.txt').write_bytes(m.tx);raise
        if stale is None:invariant(m)
        for i,b in enumerate(m.banks):(folder/f'b{i}.bin').write_bytes(b)
        (folder/'events.json').write_text(json.dumps(m.events)+'\n');(folder/'transcript.txt').write_bytes(m.tx)
        mutations+=len(m.events)
        record(label,outcome=outcome,mutation_events=len(m.events),erase_attempts=sum(m.attempts),bank_sha256=p.bank_hashes(m.banks),
            counts_after=[int.from_bytes(c.latest(m.banks)[2][24+i*3:27+i*3],'little') for i in range(32)])
        if reusable and outcome=='complete':cache[key]=(m,label)
        return m
    def schedule(m,tx):
        points={1}
        for n,(kind,bank,address,value) in enumerate(m.events,1):
            if kind=='erase' or kind=='program' and (bank,address) in [(3,tx['operations'][0]['commit_address']),
                    (3,(tx['staging_journal_sector']<<12)+127),(3,(tx['retained_journal_sector']<<12)+127),(3,0xb01f),(1,0xb003)]:
                points.add(n)
                if n>1:points.add(n-1)
        return sorted(points)
    try:
        if a.phase=='recovery':
            parentcp=p.read(c.EVIDENCE/'variants-restoration-checkpoint.json');parentpath=Path(parentcp['restore_instruction_report'])
            assert p.sha(parentpath.read_bytes())==parentcp['restore_instruction_report_sha256']
            parent=p.read(parentpath);assert parent['passed'];representative=None
            for case in parent['checks']:
                if not case['name'].startswith(('restoration-cut-','restoration-corrupt-','restoration-partial-')):continue
                name=case['name'];folder=parentpath.parent/name
                banks=[(folder/f'b{i}.bin').read_bytes() for i in range(4)]
                backupdir=a.out/(name+'-verified-backup');p.write_backup(backupdir,c.old.fixture('2512'));backup=p.read_backup(backupdir)
                tx,data,expected=recovery.context(name,banks,backup)
                before_counts=[int.from_bytes(c.latest(banks)[2][24+i*3:27+i*3],'little') for i in range(32)]
                execute(name+'-recovered',banks,tx,data,expected)
                final=c.latest(expected)[2];after_counts=[int.from_bytes(final[24+i*3:27+i*3],'little') for i in range(32)]
                assert all(after_counts[i]>=before_counts[i] for i in range(32))
                assert all(expected[i]==backup[i] for i in (0,1,2)) and expected[3][:0x4000]==backup[3][:0x4000] and expected[3][0x6000:]==backup[3][0x6000:]
                assert final[8:24]==c.latest(backup)[2][8:24]
                if name=='restoration-cut-123':representative=(name,banks,backup,tx,data,expected)
            name,banks,backup,tx,data,expected=representative
            for bank in range(4):execute(f'recovery-stale-{bank}',banks,tx,data,expected,stale=bank)
            for failure in ('unknown-case','changed-preimage','wrong-backup'):
                b=list(map(bytearray,banks));bk=list(map(bytearray,backup));label=name
                if failure=='unknown-case':label='fabricated-interruption'
                elif failure=='changed-preimage':b[0][0]^=1
                else:bk[0][0]^=1
                try:recovery.context(label,b,bk)
                except ValueError as e:record(failure+'-refused',reason=str(e))
                else:raise AssertionError('Unregistered recovery input admitted')
        elif a.phase=='variants':
            for board in ['2512','2205','2604','2609']:
                original=c.old.fixture(board)
                reverse=list(map(bytearray,original));reverse[3][0x4000:0x5000],reverse[3][0x5000:0x6000]=original[3][0x5000:0x6000],original[3][0x4000:0x5000]
                reverse=list(map(bytes,reverse));tx,data,expected=j.transaction(reverse,0xa0,p.ROOT/'tmp/c35e/payload',reverse,activation='select-B35')
                m=execute(board+'-reverse-complete',reverse,tx,data,expected)
                if board=='2512':
                    for n in schedule(m,tx):execute(f'reverse-cut-{n}',reverse,tx,data,expected,cut=n)
                    for bank in range(4):execute(f'reverse-stale-{bank}',reverse,tx,data,expected,stale=bank)
                existing=[(buildpath/board/f'expected-b{i}.bin').read_bytes() for i in range(4)]
                activation=list(map(bytearray,existing));seq,off,row,valid=c.latest(activation)
                cfg=j.preference(row[8:24],0xa0,int.from_bytes(original[3][0x2008:0x200c],'little'))
                activation[3][off:off+128]=j.record(cfg,[int.from_bytes(row[24+i*3:27+i*3],'little') for i in range(32)],seq)
                activation=list(map(bytes,activation));tx,data,expected=j.transaction(activation,0xa0,p.ROOT/'tmp/c35e/payload',activation,activation='select-B35')
                assert len(tx['operations'])==3 and len(tx['planned_erase_order'])==2
                m=execute(board+'-activation-complete',activation,tx,data,expected)
                if board=='2512':
                    for n in schedule(m,tx):execute(f'activation-cut-{n}',activation,tx,data,expected,cut=n)
                    for n in range(2):
                        execute(f'activation-corrupt-{n}',activation,tx,data,expected,corrupt=n)
                        execute(f'activation-partial-{n}',activation,tx,data,expected,partial=n)
                tx,data,expected=j.transaction(existing,0xa0,p.ROOT/'tmp/c35e/payload',existing,activation='select-B35')
                execute(board+'-no-op',existing,tx,data,expected)
        else:
            representative=None
            for case in prior['checks']:
                label=case['name'];board=label.split('-')[0] if label.endswith('-complete') else '2512'
                original=c.old.fixture(board);info=p.read(buildpath/board/'plan.json')
                folder=priorpath.parent/label;banks=[(folder/f'b{i}.bin').read_bytes() for i in range(4)];events=p.read(folder/'events.json')
                backupdir=a.out/(label+'-verified-backup');p.write_backup(backupdir,original);backup=p.read_backup(backupdir)
                if label.startswith('stale-bank-'):
                    try:attested.restoration(banks,backup,certificate=case,events=events,upgrade_plan=info)
                    except ValueError as e:record(label+'-restore-refused',reason=str(e))
                    else:raise AssertionError('Unknown stale preimage admitted to restoration')
                    continue
                tx,data,expected=attested.restoration(banks,backup,certificate=case,events=events,upgrade_plan=info)
                m=execute(label+'-restored',banks,tx,data,expected)
                # Original payload/unowned bytes restored; new journal counts
                # and sequence are intentionally retained rather than copied.
                assert all(expected[i]==backup[i] for i in (0,1,2))
                assert expected[3][:0x4000]==backup[3][:0x4000] and expected[3][0x6000:]==backup[3][0x6000:]
                if label=='2512-complete':representative=(banks,backup,case,events,info,tx,data,expected,m)
            banks,backup,case,events,info,tx,data,expected,m=representative
            for n in schedule(m,tx):execute(f'restoration-cut-{n}',banks,tx,data,expected,cut=n)
            for bank in range(4):execute(f'restoration-stale-{bank}',banks,tx,data,expected,stale=bank)
            for n in range(len(tx['operations'])-1):
                execute(f'restoration-corrupt-{n}',banks,tx,data,expected,corrupt=n)
                execute(f'restoration-partial-{n}',banks,tx,data,expected,partial=n)
            for label,bad,back,cert in [('altered-preimage',[bytearray(b) for b in banks],backup,case),
                    ('wrong-backup',banks,[bytearray(b) for b in backup],case)]:
                if label=='altered-preimage':bad[0][0]^=1
                else:back[0][0]^=1
                try:attested.restoration(bad,back,certificate=cert,events=events,upgrade_plan=info)
                except ValueError as e:record(label+'-refused',reason=str(e))
                else:raise AssertionError('Unsafe restoration accepted')
    except Exception:
        (a.out/'failure.json').write_text(json.dumps(dict(passed=False,phase=a.phase,checks=checks,current=str(current),error=traceback.format_exc()),indent=2)+'\n');raise
    sources={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(workspace.resolve()):
            name=path.resolve().relative_to(workspace).as_posix();digest=p.sha(path.read_bytes());sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    report=dict(passed=True,phase=a.phase,cases=len(checks),checks=checks,mutation_boundary_cut_cases=cuts,
        mutations_checked=mutations,reused_identical_complete_cases=reused,finished_utc=datetime.now(timezone.utc).isoformat(),
        source_report_sha256=cp['report_sha256'],composer_sha256=p.sha(Path(c.__file__).read_bytes()),
        test_sha256=p.sha(Path(__file__).read_bytes()),model_sources=sources,serial_disabled=True,board_access=False,
        attested_restoration_sha256=p.sha(Path(attested.__file__).read_bytes()),
        recovery_admission_sha256=p.sha(Path(recovery.__file__).read_bytes()),
        full_instruction_execution=True,hash_range_loops_accelerated=True,
        prior_unchanged_linked_hash_equivalence_receipt=str(priorpath.parent/'fnv-proof.json'),
        cold_boot_after_these_new_cases_tested=False,restoration_from_interrupted_restoration_tested=a.phase=='recovery',
        physical_interruption_qualified=False,wear_aware_restoration_qualified=False,
        route_qualified=False,release_qualified=False,installation_permitted=False)
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(checks),a.phase,'offline checks')
if __name__=='__main__':main()
