"""Serial-disabled A/B and mixed-profile BATCH candidate model checks."""
import argparse,hashlib,json,os,sys,traceback
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text())
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--build',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--resume-completed',type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    build=read(a.build/'build-report.json');assert build['passed'] and build['candidate_id']=='batchfix-r1' and build['generation']==48
    for name,info in build['artifacts'].items():assert sha(a.build/'payload'/name)==info['sha256']
    freeze=read(ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kw):raise RuntimeError('Serial forbidden in separate candidate qualification')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    from test_v2_status import fresh,boot,layout,snapshot,META
    from test_v2_sram_store import console
    from test_v2_spi_resident import k
    symbols=read(a.build/'symbols.json');assert symbols['xip/utilities']['B29_ENGINE']==0xd0ea
    assert symbols['core/monitor-b0']['V2_END']<=0xc000 and symbols['core/monitor-a0']['V2_END']<=0xb000
    candidate=a.build/'payload';baseline=ROOT/'tmp/c35e/payload'
    slotA=(candidate/'str8n-v2-recovery-slot-a0.bin').read_bytes();slotB=(candidate/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    oldA=(ROOT/'BUILD/v2-beta28-b23/str8n-v2-recovery-slot-a0.bin').read_bytes();oldB=(baseline/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    checks=[];transcripts=[];reuse=None
    if a.resume_completed:
        reuse=read(a.resume_completed);assert reuse['passed_completed_cases_only'] and reuse['full_run_passed'] is False and reuse['cases']==18
        assert reuse['source_build_report_sha256']==sha(a.build/'build-report.json')
        folder=a.resume_completed.parent
        for name,key in [('failure.json','original_failure_sha256'),('progress.json','progress_sha256'),('commands.json','commands_sha256')]:assert sha(folder/name)==reuse[key]
        assert sha(Path(reuse['source_harness']))==reuse['harness_sha256']
        checks=[dict(v,reused_from=str(a.resume_completed.resolve())) for v in reuse['completed_checks']]
    def record(name,**kw):
        checks.append(dict(name=name,passed=True,**kw));(a.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',name,flush=True)
    def cmd(cpu,m,line):
        keys=line.encode()+b'\r' if isinstance(line,str) else line;out=console(cpu,m,keys,limit=100000000);transcripts.append(dict(keys=repr(keys),text=out.decode('ascii',errors='replace')));return out
    def fixture(page,*,newA=True,newB=True,old_provider=False,damage=None):
        cpu,m=fresh(primary=layout());m.fast=True;m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2E 17 10 26 80 00')
        source=candidate
        for bank,address,name,count in [(1,0xb000,'clock/storage.bin',12288),(1,0xe000,'assembler/asm-e000.bin',4096),(1,0xf000,'assembler/vectors-f000.bin',4096),
            (2,0x8000,'xip/utilities.bin',22528),(2,0xd800,'boot-status/asset.bin',2560),(2,0xe200,'battery/asset.bin',2560),(2,0xf000,'local-display/asset.bin',1792),(2,0xf800,'version/asset.bin',2048),
            (3,0x8000,'str8n-rtc-component-8000-8fff.bin',4096),(3,0x9000,'str8n-journal-9000-9fff.bin',3072),(3,0xe000,'str8n-v2-recovery-e000-efff.bin',4096),(3,0xf000,'str8n-v2-recovery-f000-ffff.bin',4096)]:
            data=((baseline if old_provider and name=='xip/utilities.bin' else source)/name).read_bytes()[:count];m.banks[bank][address-0x8000:address-0x8000+count]=data
        m.banks[3][0x2000:0x3000]=slotA if newA else oldA;m.banks[3][0x3000:0x4000]=slotB if newB else oldB
        generation=48 if ((page==0xa0 and newA) or (page==0xb0 and newB)) else (40 if page==0xa0 else 47)
        cfg=bytearray(migration.default_config());cfg[7:13]=b'P'+bytes([page])+generation.to_bytes(4,'little');cfg[14:]=migration.config_sum(cfg)
        m.banks[3][0x4000:0x6000]=migration.metadata(cfg,[0]*32,1)+b'\xff'*(8192-128)
        if damage:
            off=0x2000 if page==0xa0 else 0x3000
            if damage=='crc':m.banks[3][off+128]^=1
            elif damage=='uncommitted':m.banks[3][off+31]=255
            elif damage=='provider':m.banks[2][0x100]^=1
        return cpu,m
    def clean(m,before):assert snapshot(m)==before and not m.events and not m.bus.writes
    try:
        for page in ([] if reuse else [0xa0,0xb0]):
            cpu,m=fixture(page);before=snapshot(m);boot(cpu);assert m.ram[0x7d30]==page and m.ram[0x7ef4]==0xba
            assert b'2.0bf1' in cmd(cpu,m,'VERSION');record(f'{page:02X} candidate boot and capability publication')
            trace=[];original_step=cpu.step
            watch={symbols['xip/utilities'][n]:n for n in ['B30_ALIAS','B30_PREFIX','B29_READY','B29_MON_RUN']}
            def traced():
                if m.bank==2 and cpu.pc in watch:trace.append(dict(at=watch[cpu.pc],a=cpu.a,x=cpu.x,y=cpu.y,line=bytes(m.ram[0x7c00:0x7c29]).hex(),provider=m.ram[0x7ee8]))
                return original_step()
            cpu.step=traced
            text=cmd(cpu,m,'BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q');cpu.step=original_step
            (a.out/f'{page:02x}-native-trace.json').write_text(json.dumps(trace,indent=2)+'\n')
            assert b'BATCH done' in text and text.endswith(b'B3> '),text
            clean(m,before);record(f'{page:02X} native four-utility BATCH handoff',persistent_state_unchanged=True)
            text=cmd(cpu,m,'BATCH R CLOCK;STATUS;Q');assert b'CLOCK 1.11' in text and b'BATCH done' in text and text.endswith(b'B3> '),text
            clean(m,before);record(f'{page:02X} CLOCK BATCH query and return',persistent_state_unchanged=True)
            text=cmd(cpu,m,'BATCH SRAM;BOGUS;Q');assert b'BATCH stopped: command failed' in text and text.endswith(b'SRAM> ');cmd(cpu,m,'Q')
            text=cmd(cpu,m,'BATCH R CLOCK;BOGUS;Q');assert b'BATCH stopped: command failed' in text and text.endswith(b'CLOCK> '),text;cmd(cpu,m,'Q')
            clean(m,before);record(f'{page:02X} native and CLOCK errors discard queued return')
            text=cmd(cpu,m,'BATCH MAINT;NAME TEST;Q');assert b'Type YES' in text;assert b'BATCH canceled' in cmd(cpu,m,b'\x1b');cmd(cpu,m,'Q')
            text=cmd(cpu,m,'BATCH R CLOCK;TRIM 1;Q');assert not text.endswith(b'B3> '),text
            text=cmd(cpu,m,b'\x1b');assert b'BATCH canceled' in text,text;cmd(cpu,m,'Q')
            clean(m,before);record(f'{page:02X} native and CLOCK Escape cancel without setting changes')
            text=cmd(cpu,m,'BATCH ASM;VERSION');assert b'BATCH stopped: unsupported' in text and b'ASM>' not in text;clean(m,before);record(f'{page:02X} unsupported ASM batch refused')
            # Exercise compiled predicates directly with bounded synthetic RAM
            # faults. No malformed gate is executed after predicate refusal.
            clock=(candidate/'clock/clock.bin').read_bytes();m.ram[0x2000:0x2000+len(clock)]=clock
            saved={addr:m.ram[addr] for addr in [0x7d30,0x7ef4,0x7c94,0x7c9f]}
            for name,bank,entry in [('native',2,symbols['xip/utilities']['BFX_VALID']),('CLOCK',3,symbols['clock/clock']['B29_CLOCK_VALID'])]:
                for active,magic,want in [(0xa0,0xba,True),(0xb0,0xba,True),(0xb0,0xb9,True),(0xa0,0xb9,False),(0x90,0xba,False),(0xa0,0,False)]:
                    for addr,value in saved.items():m.ram[addr]=value
                    m.ram[0x7d30]=active;m.ram[0x7ef4]=magic;m.bank=bank;assert k.model.call(cpu,entry)==want
                for address in [0x7c94,0x7c9f]:
                    for addr,value in saved.items():m.ram[addr]=value
                    m.ram[address]^=1;m.bank=bank;assert not k.model.call(cpu,entry)
                record(f'{page:02X} {name} predicates validate slots/version/gate and legacy B-only compatibility',predicate_cases=8)
            for addr,value in saved.items():m.ram[addr]=value
            clean(m,before)
        for label,page,options,wanted,magic in [
            ('candidate-A-with-legacy-B',0xa0,dict(newB=False),0xa0,0xba),('candidate-B-with-legacy-A',0xb0,dict(newA=False),0xb0,0xba),
            ('legacy-A-with-new-provider',0xa0,dict(newA=False),0xa0,None),('legacy-B-with-new-provider',0xb0,dict(newB=False),0xb0,0),
            ('new-A-with-old-provider',0xa0,dict(old_provider=True),0xa0,0),('new-B-with-old-provider',0xb0,dict(old_provider=True),0xb0,0),
            ('corrupt-A-falls-back-B',0xa0,dict(damage='crc'),0xb0,0xba),('uncommitted-B-falls-back-A',0xb0,dict(damage='uncommitted'),0xa0,0xba),
            ('corrupt-provider-disables-capability',0xa0,dict(damage='provider'),0xa0,0)]:
            if any(v['name']==label for v in checks):continue
            cpu,m=fixture(page,**options);before=snapshot(m);boot(cpu)
            marker_ok=m.ram[0x7ef4] not in (0xb9,0xba) if magic is None else m.ram[0x7ef4]==magic
            assert m.ram[0x7d30]==wanted and marker_ok,(label,m.ram[0x7d30],m.ram[0x7ef4])
            out=cmd(cpu,m,'D 0200 0200');assert b'0200' in out and out.endswith(b'B3> ');clean(m,before);record(label,persistent_state_unchanged=True)
        # Retain a successful frozen B control as historical evidence, not a
        # fresh test of the separate candidate or a live-board claim.
        cp=read(ROOT/'output/qualification/beta35-prerelease-2026-10-17/a-slot-checkpoint.json');prior=Path(cp['model_report']);assert sha(prior)==cp['model_report_sha256']
    except Exception:
        (a.out/'commands.json').write_text(json.dumps(transcripts,indent=2)+'\n');(a.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    model_sources={}
    for module in list(sys.modules.values()):
        file=Path(getattr(module,'__file__','') or '.')
        if file.is_file() and file.suffix=='.py' and file.resolve().is_relative_to(ws.resolve()):
            name=file.resolve().relative_to(ws).as_posix();digest=sha(file);model_sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    result=dict(passed=True,candidate_id='batchfix-r1',display_version='2.0bf1',generation=48,cases=len(checks),checks=checks,
        source_build_report=str((a.build/'build-report.json').resolve()),source_build_report_sha256=sha(a.build/'build-report.json'),model_sources=model_sources,
        reused_completed_case_count=18 if reuse else 0,fresh_case_count=len(checks)-(18 if reuse else 0),
        completed_case_receipt_sha256=sha(a.resume_completed) if reuse else None,
        historical_A_failure_and_B_control_receipt_sha256=cp['model_report_sha256'],test_sha256=sha(Path(__file__)),
        finished_utc=datetime.now(timezone.utc).isoformat(),model_only=True,serial_disabled=True,board_access=False,persistent_model_devices_unchanged=True,
        electrical_native_or_hardware_qualified=False,installation_permitted=False,release_qualified=False)
    (a.out/'commands.json').write_text(json.dumps(transcripts,indent=2)+'\n');(a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'candidate model checks')
if __name__=='__main__':main()
