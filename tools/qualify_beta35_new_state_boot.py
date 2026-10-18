"""Boot saved variant/restoration states without hardware access.

Reuse prior results only for identical complete flash and identical virtual
device inputs; preserve the receipt chain and distinguish reuse from fresh CPU
execution. No board resets or serial constructors are permitted.
"""
import argparse,json,os,sys,traceback
from pathlib import Path
from datetime import datetime,timezone
import beta35_model_transactions as c
p=c.p
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    cp=p.read(c.EVIDENCE/'variants-restoration-checkpoint.json');inputs=[]
    for name in ['variants_report','restore_instruction_report']:
        path=Path(cp[name]);assert p.sha(path.read_bytes())==cp[name+'_sha256'];inputs.append((path,p.read(path)))
    oldcp=p.read(c.EVIDENCE/'interrupted-boot-checkpoint.json');oldpath=Path(oldcp['report']);assert p.sha(oldpath.read_bytes())==oldcp['report_sha256']
    old=p.read(oldpath);assert old['passed'] and old['virtual_rtc']=='2026-10-17T19:53:15'
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kw):raise RuntimeError('No serial access in new cut-state boot model')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    from test_v2_status import fresh,boot,layout,snapshot
    from test_v2_sram_store import console
    import test_v2_rtc_upgrade as installer
    mf=p.read(ws/'BUILD/v2-beta35-candidate/migrator/manifest.json');installer.S=mf['symbols'];installer.MANIFEST=mf
    # The prior proof used this exact fixture, boot path and foreground read.
    cache={}
    for check in old['checks']:
        if check.get('persistent_state_unchanged'):
            cache[tuple(check['source_bank_sha256'])]=dict(report=str(oldpath),check=check['name'],selected_page=check['selected_page'])
    checks=[];excluded=[];fresh_count=0;reuse_count=0;reentries=0
    def record(label,**kw):
        checks.append(dict(name=label,passed=True,**kw));print('PASS',label,flush=True)
        (a.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n')
    try:
        for path,report in inputs:
            assert report['passed']
            for case in report['checks']:
                label=path.parent.name+'--'+case['name']
                if 'bank_sha256' not in case:
                    excluded.append(dict(name=label,reason='No mutated image: exact no-op or pre-planning refusal'));continue
                source=path.parent/case['name'];banks=[(source/f'b{i}.bin').read_bytes() for i in range(4)]
                hashes=p.bank_hashes(banks);assert hashes==case['bank_sha256'];folder=a.out/label;folder.mkdir()
                cfg=c.latest(banks)[2][8:24];assert cfg[7:8]==b'P';page=cfg[8];key=tuple(hashes)
                if key in cache:
                    proof=cache[key];assert proof['selected_page']==page;reuse_count+=1
                    record(label+' boot',reused_from=proof,input_bank_sha256=hashes,selected_page=page,persistent_state_unchanged=True)
                else:
                    cpu,m=fresh(primary=layout());m.fast=True;m.banks=list(map(bytearray,banks))
                    m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2E 17 10 26 80 00')
                    binding=bytes(m.banks[3][0x1c00:0x1c20])
                    if binding[:3]==b'EI\1' and binding[31]==0 and p.crc(binding[:28])==int.from_bytes(binding[28:30],'little'):
                        m.bus.ee[0xf2:0xf8]=binding[8:14]
                    before=snapshot(m)
                    try:
                        boot(cpu);(folder/'boot.txt').write_bytes(m.tx)
                        assert m.ram[0x7d30]==page and bytes(m.tx).endswith(b'B3> ')
                        reply=console(cpu,m,b'D 0200 0200\r',limit=10000000);(folder/'monitor-read.txt').write_bytes(reply)
                        assert b'0200' in reply and b'5A' in reply and reply.endswith(b'B3> ')
                        assert snapshot(m)==before and not m.events and not m.bus.writes
                    except Exception:
                        (folder/'boot-failure.txt').write_bytes(m.tx)
                        for i,b in enumerate(m.banks):(folder/f'failed-b{i}.bin').write_bytes(b)
                        raise
                    fresh_count+=1;record(label+' boot',fresh_cpu_execution=True,input_bank_sha256=hashes,selected_page=page,persistent_state_unchanged=True)
                    cache[key]=dict(report=str(a.out/'report.json'),check=label+' boot',selected_page=page)
                # Re-entry is tied to each distinct RAM image/source plan,
                # independent of whether its boot evidence was reused.
                info=p.read(source/'plan.json');program=source/'installer-model-only.s19'
                assert p.sha(program.read_bytes())==info['installer_sha256']
                cells,entry=migration.read_s19(program);mem=installer.Memory(banks,set(map(tuple,info['steps'])),{},commit_records={});mem.require_maintenance_commit=False
                for address,value in cells.items():mem.ram[address]=value
                cpu=installer.CPU(memory=mem,pc=entry);mem.cpu=cpu;mem.rx.extend(b'Y\r')
                installer.run(cpu,lambda:cpu.pc==mf['symbols']['MIG_HALT'])
                (folder/'reentry.txt').write_bytes(mem.tx)
                assert b'REFUSED/FAILED' in mem.tx and not mem.events and [bytes(b) for b in mem.banks]==banks
                reentries+=1;record(label+' stale re-entry',mutation_events=0,installer_sha256=info['installer_sha256'])
    except Exception:
        (a.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    sources={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(ws.resolve()):
            name=path.resolve().relative_to(ws).as_posix();digest=p.sha(path.read_bytes());sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    for name,digest in old['model_sources'].items():
        if name in sources:assert sources[name]==digest
    result=dict(passed=True,cases=len(checks),fresh_boot_cpu_cases=fresh_count,reused_identical_boot_cases=reuse_count,
        stale_installer_reentry_cases=reentries,checks=checks,excluded_no_image_cases=excluded,
        finished_utc=datetime.now(timezone.utc).isoformat(),test_sha256=p.sha(Path(__file__).read_bytes()),
        source_reports={str(path):p.sha(path.read_bytes()) for path,r in inputs},prior_boot_report=str(oldpath),prior_boot_report_sha256=oldcp['report_sha256'],
        model_sources=sources,virtual_rtc='2026-10-17T19:53:15',serial_disabled=True,board_access=False,
        new_cut_state_boot_model_passed=True,physical_power_cycle_tested=False,route_qualified=False,installation_permitted=False,release_qualified=False)
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'new-state boot/re-entry checks')
if __name__=='__main__':main()
