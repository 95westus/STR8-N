"""Execute exact-source legacy converters/restoration in an offline CPU model."""
import argparse,ast,json,traceback
from datetime import datetime,timezone
from pathlib import Path
import plan_bf1_2512_legacy as p
import bf1_offline_recovery_model as harness

class Cut(Exception):pass

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--build',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reuse',type=Path);a=ap.parse_args()
    out=a.out.resolve();assert not out.exists();out.mkdir(parents=True)
    model,migration,_,freeze=harness.setup();mf=p.read(a.build/'manifest.json');model.S=mf['symbols'];model.MANIFEST=mf;S=model.S
    original=p.original();checks=[];captured={};executions=0
    def record(name,**kw):
        checks.append(dict(name=name,passed=True,**kw));(out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',name,flush=True)
    def reusable(name,info,tx,banks,stale,corrupt,partial):
        if not a.reuse or stale is not None or corrupt is not None or partial is not None or not (a.reuse/name/'events.json').exists():return False
        old=p.read(a.reuse/name/'plan.json');passed=next((r for r in p.read(a.reuse/'progress.json') if r['name']==name and r.get('outcome')=='complete'),None)
        return bool(passed and old['installer_sha256']==info['installer_sha256'] and old['transaction']==tx and old['source_sha256']==p.hashes(banks))
    def execute(name,banks,tx,data,expected,*,stale=None,corrupt=None,partial=None,capture=False):
        nonlocal executions
        folder=out/name;info=p.compose(a.build,folder,banks,tx,data,expected);initial=list(map(bytearray,banks))
        if stale is not None:initial[stale][0x123]^=1
        allowed={tuple(x) for x in tx['planned_erase_order']};snapshots=[];driver_events=[]
        reservation=tx['operations'][0]['address'];commit_points={(op['bank'],op['commit_address']) for op in tx['operations'] if op['commit_address'] is not None}
        precommit=reservation+max(i for i,v in enumerate(data[0][:127]) if v!=255)
        def publication_check(state,bank,address,value):
            if (bank,address) not in commit_points:return
            if value==0x3f:
                start=address-3-0x8000;header=expected[bank][start:start+24]
                if header[:4]==b'SR\1\x3f':
                    length=24+int.from_bytes(header[6:8],'little');assert bytes(state[bank][start:start+length])==expected[bank][start:start+length], 'SR body not complete before publication'
            if bank==3 and value==0 and address in (0xa01f,0xb01f):
                start=(address&0xf000)-0x8000;assert bytes(state[3][start:start+4096])==expected[3][start:start+4096], 'MI committed before full slot verification'
        if reusable(name,info,tx,banks,stale,corrupt,partial):
            passed=next(r for r in p.read(a.reuse/'progress.json') if r['name']==name and r.get('outcome')=='complete')
            events=p.read(a.reuse/name/'events.json');replay=list(map(bytearray,banks));attempts=[0]*32
            for index,(kind,bank,address,value) in enumerate(events,1):
                off=address-0x8000;assert (bank,address>>12) in allowed or bank==3 and reservation<=address<reservation+128
                if kind=='erase':assert address&4095==0;replay[bank][off:off+4096]=b'\xff'*4096;attempts[bank*8+(address>>12)-8]+=1
                else:assert kind=='program' and replay[bank][off]&value==value;replay[bank][off]=value
                publication_check(replay,bank,address,value)
                row=p.latest(replay)[2];assert all(int.from_bytes(row[24+i*3:27+i*3],'little')>=tx['counts_before'][i]+attempts[i] for i in range(32))
                category=None
                if kind=='program' and bank==3 and address==precommit:category='reservation-before-commit'
                if kind=='program' and bank==3 and address==reservation+127:category='reservation-committed'
                if kind=='erase' and bank in (1,2):category='provider-erase'
                if kind=='program' and bank==3 and address==0xb01f and value==0:category='MON-B-committed'
                if kind=='erase' and bank==3 and address==0xf000:category='fixed-F-erased'
                if kind=='program' and bank==3 and address>=0xfffa:category='fixed-F-final-vector'
                if capture and category and not any(x['category']==category for x in snapshots):snapshots.append(dict(category=category,event_count=index,banks=list(map(bytes,replay)),events=events[:index]))
            assert list(map(bytes,replay))==expected and p.hashes(expected)==passed['bank_sha256']
            assert [[b,address>>12] for kind,b,address,v in events if kind=='erase']==tx['planned_erase_order']
            for n,b in enumerate(expected):assert (a.reuse/name/f'b{n}.bin').read_bytes()==b;(folder/f'b{n}.bin').write_bytes(b)
            (folder/'events.json').write_text(json.dumps(events)+'\n');(folder/'transcript.txt').write_bytes((a.reuse/name/'transcript.txt').read_bytes())
            if capture:captured[name]=dict(source=banks,tx=tx,data=data,expected=expected,snapshots=snapshots,events=events)
            record(name,outcome='complete',mutation_events=len(events),bank_sha256=p.hashes(expected),fresh_CPU_execution=False,reused_from=str((a.reuse/name).resolve()),prior_progress_sha256=p.sha((a.reuse/'progress.json').read_bytes()),equivalence='Identical installer, transaction, source, output and replayed CPU mutation events')
            return expected
        class Memory(model.Memory):
            def __init__(self):
                super().__init__(initial,allowed,{},commit_records={});self.require_maintenance_commit=False;self.attempts=[0]*32
            def mutated(self,kind,address,value):
                super().mutated(kind,address,value)
                publication_check(self.banks,self.bank,address,value)
                if kind=='erase':self.attempts[self.bank*8+(address>>12)-8]+=1
                assert bytes(self.banks[0])==bytes(initial[0]),'B0 changed'
                assert bytes(self.banks[1][:0x3000])==bytes(initial[1][:0x3000]),'User programs changed'
                row=p.latest(self.banks)[2]
                assert row[8:15]==bytes.fromhex(tx['source_config'])[:7] and row[21]==bytes.fromhex(tx['source_config'])[13]
                assert all(int.from_bytes(row[24+i*3:27+i*3],'little')>=tx['counts_before'][i]+self.attempts[i] for i in range(32)), 'Wear reservation lost'
                # Preserve only selected, meaningful cut preimages. Every
                # snapshot is taken during actual CPU execution, not fabricated.
                if capture:
                    category=None
                    if kind=='program' and self.bank==3 and address==precommit:category='reservation-before-commit'
                    if kind=='program' and self.bank==3 and address==reservation+127:category='reservation-committed'
                    if kind=='erase' and self.bank in (1,2):category='provider-erase'
                    if kind=='program' and self.bank==3 and address==0xb01f and value==0:category='MON-B-committed'
                    if kind=='erase' and self.bank==3 and address==0xf000:category='fixed-F-erased'
                    if kind=='program' and self.bank==3 and address>=0xfffa:category='fixed-F-final-vector'
                    if category and not any(x['category']==category for x in snapshots):snapshots.append(dict(category=category,event_count=len(self.events),banks=list(map(bytes,self.banks)),events=list(self.events)))
        memory=Memory();cells,entry=migration.read_s19(folder/'installer-model-only.s19')
        for address,value in cells.items():memory.ram[address]=value
        # Qualify accelerated hash semantics against real opcodes on this build.
        if executions==0:
            memory.ram[0x6000:0x6100]=bytes(range(256));memory.ram[0xe0:0xe2]=b'\0\x60';memory.ram[0x620c]=0x61
            cpu=model.CPU(memory=memory,pc=S['MIG_HASH_RANGE']);memory.cpu=cpu;cpu.accelerate_hash=False;cpu.stPushWord(0x1ff)
            model.run(cpu,lambda:cpu.pc==0x200);assert int.from_bytes(memory.ram[0x6204:0x6208],'little')==migration.fnv(bytes(range(256)))
            record('actual FNV opcodes match accelerated loop',bytes=256)
        cpu=model.CPU(memory=memory,pc=entry);memory.cpu=cpu;memory.rx.extend(b'Y\r');executions+=1;outcome='complete'
        try:
            for n,op in enumerate(tx['operations'][1:]):
                token=f'SEND 4096 BYTES FOR B{op["bank"]}:{op["address"]>>12:X}\r\n'.encode()
                model.run(cpu,lambda:token in bytes(memory.tx) or cpu.pc==S['MIG_HALT'])
                if cpu.pc==S['MIG_HALT']:
                    assert stale is not None and not memory.events and b'REFUSED/FAILED' in memory.tx;outcome='stale source refused before any write';break
                memory.tx.clear();before=len(memory.events);body=bytearray((folder/f'transfer-{n:02d}.bin').read_bytes())
                if corrupt==n:body[100]^=1
                if partial==n:body=body[:2048]
                memory.rx.extend(body)
                if corrupt==n:
                    model.run(cpu,lambda:cpu.pc==S['MIG_HALT']);assert len(memory.events)==before and b'REFUSED/FAILED' in memory.tx;outcome='corrupt transfer refused before row mutation';break
                if partial==n:
                    model.run(cpu,lambda:not memory.rx and cpu.pc==S['V2W_RAW_POLL']);assert len(memory.events)==before;outcome='partial row waits without row mutation';break
            else:
                model.run(cpu,lambda:cpu.pc==S['MIG_HALT']);assert b'MIGRATION VERIFIED' in memory.tx and list(map(bytes,memory.banks))==expected
                assert [[b,address>>12] for kind,b,address,v in memory.events if kind=='erase']==tx['planned_erase_order']
        except BaseException:
            (folder/'failure-transcript.txt').write_bytes(memory.tx)
            for n,b in enumerate(memory.banks):(folder/f'failed-b{n}.bin').write_bytes(b)
            raise
        for n,b in enumerate(memory.banks):(folder/f'b{n}.bin').write_bytes(b)
        (folder/'events.json').write_text(json.dumps(memory.events)+'\n');(folder/'transcript.txt').write_bytes(memory.tx)
        if capture:captured[name]=dict(source=banks,tx=tx,data=data,expected=expected,snapshots=snapshots,events=list(memory.events))
        record(name,outcome=outcome,mutation_events=len(memory.events),erase_attempts=sum(memory.attempts),bank_sha256=p.hashes(memory.banks),fresh_CPU_execution=True)
        return list(map(bytes,memory.banks))
    def boot_target(name,banks,page):
        from test_v2_status import fresh,boot
        from test_v2_sram_store import console
        cpu,m=fresh();m.fast=True
        for n,b in enumerate(banks):m.banks[n][:]=b
        ee=(p.BACKUP/'eeprom.bin').read_bytes();m.bus.ee[:128]=ee[:128];m.bus.ee[0xff]=ee[128];m.bus.ee[0xf0:0xf8]=ee[129:137]
        m.spi.devices[0].data[:]=(p.BACKUP/'sram.bin').read_bytes();m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 00 0C')
        before=(bytes(m.bus.ee),bytes(m.spi.devices[0].data),bytes(m.bus.rtc_regs));injected=[False]
        from test_v2_recovery import B
        def choose(c):
            if c.pc==B['BOOT_RECOVERY_WINDOW'] and not injected[0]:m.rx.extend((b'A' if page==0xa0 else b'B')+b'\r');injected[0]=True
            return False
        boot(cpu,hook=choose);assert m.ram[0x7d30]==page and m.ram[0x7d01]==2
        transcript=bytes(m.tx)+console(cpu,m,b'VERSION\r');assert b'2.0bf1' in transcript
        for cmd in (b'BATCH MAINT;Q\r',b'BATCH R CLOCK;STATUS;Q\r'):
            text=console(cpu,m,cmd,limit=35000000);transcript+=text;assert b'BATCH done' in text and text.endswith(b'B3> '),text[-500:]
            (out/(name+'-in-progress.txt')).write_bytes(transcript)
        # ASM is deliberately not supported inside BATCH. Test that refusal,
        # then launch the assembler through its documented monitor command.
        text=console(cpu,m,b'BATCH ASM;VERSION\r');transcript+=text
        assert b'BATCH stopped: unsupported' in text and text.endswith(b'B3> ')
        text=console(cpu,m,b'ASM\r?\rQUIT\r',limit=35000000);transcript+=text
        (out/(name+'-in-progress.txt')).write_bytes(transcript)
        assert b'ASM> ' in text and text.endswith(b'B3> ')
        assert b'CLOCK 1.11' in transcript
        assert before==(bytes(m.bus.ee),bytes(m.spi.devices[0].data),bytes(m.bus.rtc_regs))
        (out/(name+'.txt')).write_bytes(transcript);record(name,selected_page=page,EEPROM_SRAM_RTC_unchanged=True,fresh_CPU_execution=True)
    try:
        state=original
        for kind in ('wdcmonv2','v2.0b4'):
            key=kind.replace('.','-');cfg=p.latest(state)[2][8:24]
            source_cfg=p.config_without_preference(cfg) if kind=='wdcmonv2' else p.preference(cfg,0xa0,13)
            desired=p.legacy_destination(kind,state);tx,data,source=p.transaction(state,desired,source_cfg,'Stage exact '+kind+' with current wear history')
            execute(key+'-stage-source',state,tx,data,source);identity=p.admit_source(kind,source);record(key+'-exact-source-admitted',**identity)
            desired=p.target_destination(source);target_cfg=p.preference(source_cfg,0xb0,48);tx,data,target=p.transaction(source,desired,target_cfg,kind+' to bf1')
            execute(key+'-convert',source,tx,data,target,capture=True)
            for page in (0xa0,0xb0):
                name=key+'-bf1-'+hex(page);old=next((r for r in p.read(a.reuse/'progress.json') if r['name']==name and r.get('selected_page')==page),None) if a.reuse else None
                if old:
                    def boot_ast(path):
                        node=next(n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n,ast.FunctionDef) and n.name=='boot_target');return ast.dump(node,include_attributes=False)
                    prior_banks=[(a.reuse/(key+'-convert')/f'b{n}.bin').read_bytes() for n in range(4)]
                    assert prior_banks==target and boot_ast(a.reuse/'qualification-source.py')==boot_ast(Path(__file__))
                    (out/(name+'.txt')).write_bytes((a.reuse/(name+'.txt')).read_bytes())
                    record(name,selected_page=page,EEPROM_SRAM_RTC_unchanged=True,fresh_CPU_execution=False,reused_from=str(a.reuse.resolve()),equivalence='Identical four-bank input and identical boot_target AST including synthetic device fixtures',prior_progress_sha256=p.sha((a.reuse/'progress.json').read_bytes()))
                else:boot_target(name,target,page)
            # Restore historical source first, then the actual pre-campaign
            # payload. Both operations retain every newer reserved erase count.
            desired=p.legacy_destination(kind,target);rt,rd,restored=p.transaction(target,desired,source_cfg,'Restore exact '+kind+' payload')
            execute(key+'-restore-historical-source',target,rt,rd,restored);p.admit_source(kind,restored)
            rt,rd,returned=p.transaction(restored,original,p.latest(original)[2][8:24],'Restore original beta35 payload with conservative new wear')
            execute(key+'-restore-original',restored,rt,rd,returned)
            assert all(returned[n]==original[n] for n in (0,1,2)) and returned[3][:0x4000]==original[3][:0x4000] and returned[3][0x6000:]==original[3][0x6000:]
            state=returned
            # Refusals bind all four banks before the reservation write.
            for bank in range(4):execute(key+'-stale-bank-'+str(bank),source,tx,data,target,stale=bank)
            execute(key+'-corrupt-first-row',source,tx,data,target,corrupt=0)
            execute(key+'-partial-first-row',source,tx,data,target,partial=0)
            bad=list(map(bytearray,source));bad[1][0x3000]=0x42
            try:p.admit_source(kind,list(map(bytes,bad)))
            except AssertionError:record(key+'-occupied-destination-refused')
            else:raise AssertionError('Occupied destination accepted')
            bad=list(map(bytearray,source));bad[3][0x7123]^=1
            try:p.admit_source(kind,list(map(bytes,bad)))
            except AssertionError:record(key+'-altered-source-core-refused')
            else:raise AssertionError('Changed historical F accepted')
        # Replay exact CPU-produced cut states and recover with fresh installers.
        for name,ctx in captured.items():
            for cut in ctx['snapshots']:
                if cut['category']=='reservation-before-commit':
                    address=ctx['tx']['operations'][0]['address'];offset=address-0x8000
                    assert cut['banks'][3][offset:offset+127]==ctx['data'][0][:127] and cut['banks'][3][offset+127]==255
                    assert p.latest(cut['banks'])[0]==ctx['tx']['sequence_before']
                    assert ctx['events'][cut['event_count']]==('program',3,address+127,0) or ctx['events'][cut['event_count']]==['program',3,address+127,0]
                replay=list(map(bytearray,ctx['source']));attempts=[0]*32
                for kind,bank,address,value in cut['events']:
                    off=address-0x8000
                    if kind=='erase':replay[bank][off:off+4096]=b'\xff'*4096;attempts[bank*8+(address>>12)-8]+=1
                    else:assert replay[bank][off]&value==value;replay[bank][off]=value
                assert list(map(bytes,replay))==cut['banks']
                assert all(int.from_bytes(p.latest(replay)[2][24+i*3:27+i*3],'little')>=ctx['tx']['counts_before'][i]+attempts[i] for i in range(32))
                tx,data,expected=p.transaction(cut['banks'],ctx['expected'],bytes.fromhex(ctx['tx']['target_config']),name+' cut recovery',attested_cut=True)
                execute(name+'-'+cut['category']+'-recover',cut['banks'],tx,data,expected)
                record(name+'-'+cut['category']+'-replay-attested',cut_event_count=cut['event_count'],CPU_generated_preimage=True,
                    restart_method='RAM re-entry/external programmer required if core or boot path is not intact; not a claim of power-loss-safe conversion')
        result=dict(passed=True,cases=len(checks),checks=checks,observed_utc=datetime.now(timezone.utc).isoformat(),build_manifest_sha256=p.sha((a.build/'manifest.json').read_bytes()),planner_sha256=p.sha(Path(p.__file__).read_bytes()),test_sha256=p.sha(Path(__file__).read_bytes()),backup_report_sha256=p.sha((p.BACKUP/'report.json').read_bytes()),baseline_sha256=p.read(p.Q/'active-rtc-campaign.json')['baseline_index_sha256'],routes=['2512-wdcmonv2-to-bf1','2512-v2.0b4-to-bf1'],offline_CPU_execution=True,hardware_qualified=False,publication_permitted=False,board_access=False,clocks_trims_changed=False,limits=['W65C02 instruction model; no new 65C816 native testing','Core-changing conversion does not promise bootability during mid-erase/program loss','WDC fixture is private exact captured diagnostic/monitor layout, not arbitrary stock firmware','Historical source staging and retained metadata host escrow require their own live receipt admission before hardware use'])
        (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS offline legacy conversion qualification',len(checks),flush=True)
    except BaseException:
        (out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,failure=traceback.format_exc()),indent=2)+'\n');raise
if __name__=='__main__':main()
