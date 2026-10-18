"""Execute exact 2604-derived bf1 install/recovery instruction models offline."""
import argparse,json,os,sys,traceback
from pathlib import Path
from datetime import datetime,timezone
import plan_bf1_2604_route as route
c=route.c;p=route.p;j=route.j
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--build',type=Path,required=True);ap.add_argument('--helper-build',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--allow-capture-restoring',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    intake=p.read(a.backup/'report.json');(a.out/'backup-intake.json').write_text(json.dumps(intake,indent=2)+'\n')
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory']);os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kwargs):raise RuntimeError('Serial forbidden in bf1 route model')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    import test_v2_rtc_upgrade as model
    mf=p.read(ws/'BUILD/v2-beta35-candidate/migrator/manifest.json');S=mf['symbols'];model.S=S;model.MANIFEST=mf
    checks=[]
    def record(name,**kw):
        checks.append(dict(name=name,passed=True,**kw));(a.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',name,flush=True)
    def invariants(m):
        _,_,r,valid=c.latest(m.banks);cfg=r[8:24];original=bytes.fromhex(m.info['transaction']['source_configuration_hex']);tx=m.info['transaction']
        assert cfg[:7]==original[:7] and cfg[13]==original[13] and cfg[14:]==p.config_checksum(cfg)
        counts=[int.from_bytes(r[24+i*3:27+i*3],'little') for i in range(32)];assert all(counts[i]>=tx['counts_before'][i]+m.attempts[i] for i in range(32))
        assert cfg[7:8]==b'P' and cfg[8] in (0xa0,0xb0);off=(cfg[8]-0x80)*256;slot=m.banks[3][off:off+4096]
        assert slot[:4]==b'MI\1'+cfg[8:9] and slot[31]==0 and slot[8:12]==cfg[9:13] and p.crc(slot[:18]+slot[32:])==int.from_bytes(slot[18:20],'little')
        fallback=tx['fallback_page'];fo=(fallback-0x80)*256
        assert bytes(m.banks[3][fo:fo+4096])==m.original[3][fo:fo+4096]
        assert bytes(m.banks[0])==m.original[0] and bytes(m.banks[3][0x6000:])==m.original[3][0x6000:]
    class Cut(Exception):pass
    class Memory(model.Memory):
        def __init__(self,banks,info,expected,cut):
            super().__init__(banks,set(map(tuple,info['steps'])),{},commit_records={});self.require_maintenance_commit=False;self.original=list(map(bytes,banks));self.info=info;self.expected=expected;self.attempts=[0]*32;self.cut=cut
        def mutated(self,kind,address,value):
            super().mutated(kind,address,value)
            if kind=='erase':self.attempts[self.bank*8+(address>>12)-8]+=1
            invariants(self)
            if len(self.events)==self.cut:raise Cut()
    def execute(name,banks,tx,data,expected,*,cut=None,stale=None,corrupt=None):
        folder=a.out/name;info=route.compose(tx,data,banks,expected,folder,a.helper_build);initial=list(map(bytearray,banks))
        if stale is not None:initial[stale][123]^=1
        m=Memory(initial,info,expected,cut);cells,entry=migration.read_s19(folder/'installer-model-only.s19')
        for addr,value in cells.items():m.ram[addr]=value
        cpu=model.CPU(memory=m,pc=entry);m.cpu=cpu;m.rx.extend(b'Y\r');outcome='complete'
        try:
          for n,(bank,sector) in enumerate(info['steps']):
            token=f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode();model.run(cpu,lambda:token in bytes(m.tx) or cpu.pc==S['MIG_HALT'])
            if cpu.pc==S['MIG_HALT']:
                assert stale is not None and not m.events and b'REFUSED/FAILED' in m.tx;outcome='stale source refused';break
            m.tx.clear();prior=len(m.events);body=bytearray((folder/f'transfer-{n:02d}.bin').read_bytes())
            if corrupt==n:body[127]^=1
            m.rx.extend(body)
            if corrupt==n:
                model.run(cpu,lambda:cpu.pc==S['MIG_HALT']);assert len(m.events)==prior and b'REFUSED/FAILED' in m.tx;outcome='corrupt transfer refused before row mutation';break
          else:
            model.run(cpu,lambda:cpu.pc==S['MIG_HALT']);assert b'MIGRATION VERIFIED' in m.tx and list(map(bytes,m.banks))==expected
            assert [[e[1],e[2]>>12] for e in m.events if e[0]=='erase']==tx['planned_erase_order']
        except Cut:outcome='instruction-model mutation-boundary cut'
        if stale is None:invariants(m)
        for i,b in enumerate(m.banks):(folder/f'b{i}.bin').write_bytes(b)
        (folder/'events.json').write_text(json.dumps(m.events)+'\n');(folder/'transcript.txt').write_bytes(m.tx)
        record(name,outcome=outcome,mutation_events=len(m.events),erase_attempts=sum(m.attempts),bank_sha256=p.bank_hashes(m.banks));return m,info
    def bootcheck(name,banks,expected_page,*,batch=False):
        from test_v2_status import fresh,boot
        from test_v2_sram_store import console
        cpu,m=fresh();m.fast=True
        for i,b in enumerate(banks):m.banks[i][:]=b
        ee=(a.backup/'eeprom.bin').read_bytes();m.bus.ee[:128]=ee[:128];m.bus.ee[0xff]=ee[128];m.bus.ee[0xf0:0xf8]=ee[129:137]
        m.spi.devices[0].data[:]=(a.backup/'sram.bin').read_bytes();m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 00 0C')
        before_ee=bytes(m.bus.ee);before_sram=bytes(m.spi.devices[0].data);before_rtc=bytes(m.bus.rtc_regs)
        boot(cpu);assert m.ram[0x7d30]==expected_page,(name,bytes(m.tx)[-1000:])
        if batch:
            text=console(cpu,m,b'BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q\r',limit=100000000);assert b'BATCH done' in text and text.endswith(b'B3> '),text
            text+=console(cpu,m,b'BATCH R CLOCK;STATUS;Q\r',limit=100000000);assert b'CLOCK 1.11' in text and b'BATCH done' in text and text.endswith(b'B3> '),text
        else:text=bytes(m.tx)
        assert bytes(m.bus.ee)==before_ee and bytes(m.spi.devices[0].data)==before_sram and bytes(m.bus.rtc_regs)==before_rtc
        # The boot policy may append BA records. Archive and constrain them;
        # the RTC/EEPROM/SRAM themselves remain byte exact in this model.
        differences=[(bank,i) for bank in range(4) for i,(x,y) in enumerate(zip(banks[bank],m.banks[bank])) if x!=y]
        assert all(bank==3 and 0x1d00<=i<0x2000 for bank,i in differences),differences[:10]
        (a.out/(name+'.txt')).write_bytes(text);record(name,selected_page=expected_page,batch=batch,boot_BA_changed_bytes=len(differences),modeled_eeprom_sram_rtc_unchanged=True)
    try:
        banks,tx,data,expected,files,identity=route.prepare(a.backup,a.build,allow_restoring=a.allow_capture_restoring);record('fresh double-read data and exact source/destination admission',identity=identity,application_ram_restoration_complete_at_intake=bool(intake.get('application_ram_restored')))
        # Execute the linked helper's configuration validator directly for
        # both exact monitor generations and malformed preference records.
        helper=p.read(a.helper_build/'build-report.json');binary=(a.helper_build/'reservation.bin').read_bytes()
        for page,generation,valid in [(0xa0,40,True),(0xb0,47,True),(0xa0,47,False),(0xb0,40,False),(0x90,40,False)]:
            mem=model.Memory(banks,set(),{},commit_records={});mem.ram[0x3000:0x3000+len(binary)]=binary
            cfg=j.preference(c.latest(banks)[2][8:24],page,generation);mem.ram[0x3600:0x3680]=j.record(cfg,[0]*32,1)
            cpu=model.CPU(memory=mem,pc=helper['symbols']['R_CONFIG']);mem.cpu=cpu;cpu.stPushWord(0x1ff)
            model.run(cpu,lambda:cpu.pc==0x200);assert bool(cpu.p&cpu.CARRY)==valid and not mem.events
        record('separate linked reservation validator A/B generations and invalid page refusal',cases=5,helper_bytes=len(binary))
        complete,info=execute('install-B-complete',banks,tx,data,expected);bootcheck('installed-B-native-CLOCK-BATCH',expected,0xb0,batch=True)
        second=list(map(bytearray,expected));second[3][0x2000:0x3000]=files['str8n-v2-recovery-slot-a0.bin']
        cfg=c.latest(expected)[2][8:24];atx,ad,afinal=route.transaction(expected,second,fallback_page=0xb0,target_config=j.preference(cfg,0xa0,48),label='A bf1 after verified coherent B bf1')
        am,ai=execute('install-A-after-B-complete',expected,atx,ad,afinal);bootcheck('installed-A-native-CLOCK-BATCH',afinal,0xa0,batch=True)
        # Restore A40 first while retaining coherent B bf1. Then restore the
        # original B/assets with A40 retained and original settings selected.
        reverseA=list(map(bytearray,afinal));reverseA[3][0x2000:0x3000]=banks[3][0x2000:0x3000]
        rtx,rd,re=route.transaction(afinal,reverseA,fallback_page=0xb0,target_config=j.preference(c.latest(afinal)[2][8:24],0xb0,48),label='Restore original A40, retain bf1 B')
        execute('restore-A40-retain-Bbf1',afinal,rtx,rd,re)
        btx,bd,be=route.transaction(re,banks,fallback_page=0xa0,target_config=c.latest(banks)[2][8:24],label='Restore original B35/assets; preserve new wear counts')
        execute('restore-original-B35-complete',re,btx,bd,be);bootcheck('restored-original-B35-boot',be,0xb0)
        assert all(be[i]==banks[i] for i in (0,1,2)) and be[3][:0x4000]==banks[3][:0x4000] and be[3][0x6000:]==banks[3][0x6000:]
        for bank in range(4):execute(f'stale-bank-{bank}',banks,tx,data,expected,stale=bank)
        for n in (0,len(info['steps'])-1):execute(f'corrupt-transfer-{n}',banks,tx,data,expected,corrupt=n)
        # Representative cuts exercise a durable reservation, monitor erase,
        # monitor commit and final activation; evidence bound to exact events.
        points={123}
        for n,(kind,bank,address,value) in enumerate(complete.events,1):
            if kind=='erase' and (bank,address)==(3,0xb000) or kind=='program' and bank==3 and address in (0xb01f,(tx['retained_journal_sector']<<12)+127):points.add(n)
        for n in sorted(points):
            m,cutinfo=execute(f'B-cut-{n}',banks,tx,data,expected,cut=n);current=list(map(bytes,m.banks));cfg=c.latest(current)[2][8:24];bootcheck(f'B-cut-{n}-boot',current,cfg[8])
            route.attest_recovery(current,banks,events=m.events,info=cutinfo,certificate=p.bank_hashes(current))
            restoretx,restoredata,restoreexpected=route.transaction(current,banks,fallback_page=0xa0,target_config=c.latest(banks)[2][8:24],label='Receipt-bound B cut restoration',attestation=p.bank_hashes(current))
            execute(f'B-cut-{n}-restored',current,restoretx,restoredata,restoreexpected)
        # Altered preimage must be rejected by receipt-bound recovery.
        altered=list(map(bytearray,current));altered[0][0]^=1
        try:route.attest_recovery(altered,banks,events=m.events,info=cutinfo,certificate=p.bank_hashes(current))
        except ValueError:record('altered recovery preimage refused')
        else:raise AssertionError('Changed recovery preimage admitted')
        report=dict(passed=True,candidate_id='batchfix-r1',board='2604',checks=checks,cases=len(checks),backup=str(a.backup.resolve()),backup_intake_sha256=p.sha((a.out/'backup-intake.json').read_bytes()),backup_completion_requires_separate_final_checkpoint=True,candidate_build_report_sha256=p.sha((a.build/'build-report.json').read_bytes()),finished_utc=datetime.now(timezone.utc).isoformat(),serial_disabled=True,board_access=False,installation_permitted=False,release_qualified=False,route_qualified=False,physical_interruption_qualified=False,physical_restoration_qualified=False,scope='Fresh-byte B-first then A bf1 instruction-model route, wear-aware two-phase original-payload restoration, representative B cuts/boot/recovery and bounded refusals. Not exhaustive cuts, electrical or native CPU acceptance.',sources={str(f):p.sha(f.read_bytes()) for f in [Path(__file__),Path(route.__file__),Path(c.__file__)]})
        (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(checks),'2604 bf1 offline route checks',flush=True)
    except BaseException:
        (a.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
if __name__=='__main__':main()
