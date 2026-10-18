"""Qualify the owner-requested final 2512 bf1 load after both legacy route restorations. Derived from the legacy CPU harness; no serial access."""
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
    source_root=p.Q/'bf1-2512-legacy-offline-2026-10-17-r6/v2-0b4-restore-original'; source_info=p.read(source_root/'plan.json'); original=[(source_root/f'expected-b{n}.bin').read_bytes() for n in range(4)]; assert p.hashes(original)==source_info['expected_sha256']; checks=[];captured={};executions=0
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
        cfg=p.latest(original)[2][8:24]
        desired=p.target_destination(original)
        tx,data,target=p.transaction(original,desired,p.preference(cfg,0xb0,48),'Owner final complete bf1 on 2512')
        execute('final-bf1',original,tx,data,target)
        for page in (0xa0,0xb0):boot_target('final-bf1-'+hex(page),target,page)
        for bank in range(4):execute('final-stale-bank-'+str(bank),original,tx,data,target,stale=bank)
        execute('final-corrupt-first-row',original,tx,data,target,corrupt=0)
        execute('final-partial-first-row',original,tx,data,target,partial=0)
        result=dict(passed=True,cases=len(checks),checks=checks,observed_utc=datetime.now(timezone.utc).isoformat(),build_manifest_sha256=p.sha((a.build/'manifest.json').read_bytes()),planner_sha256=p.sha(Path(p.__file__).read_bytes()),test_sha256=p.sha(Path(__file__).read_bytes()),backup_report_sha256=p.sha((p.BACKUP/'report.json').read_bytes()),baseline_sha256=p.read(p.Q/'active-rtc-campaign.json')['baseline_index_sha256'],routes=['2512-owner-final-bf1'],offline_CPU_execution=True,hardware_qualified=False,publication_permitted=False,board_access=False,clocks_trims_changed=False,limits=['W65C02 instruction model; no new 65C816 native testing','Core-changing conversion does not promise bootability during mid-erase/program loss','WDC fixture is private exact captured diagnostic/monitor layout, not arbitrary stock firmware','Historical source staging and retained metadata host escrow require their own live receipt admission before hardware use'])
        (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS offline final bf1 load qualification',len(checks),flush=True)
    except BaseException:
        (out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,failure=traceback.format_exc()),indent=2)+'\n');raise
if __name__=='__main__':main()
