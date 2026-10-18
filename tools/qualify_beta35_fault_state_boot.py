"""Cold-boot saved integrated fault states in fake devices only."""
import argparse,json,os,sys,traceback
from pathlib import Path
from datetime import datetime,timezone
import beta35_model_transactions as c
p=c.p

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
    prior=p.read(a.source);assert prior['passed'] and prior['integrated_flash_fault_model_passed']
    a.out.mkdir(parents=True,exist_ok=False)
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kw):raise RuntimeError('Serial forbidden in fault-state boot model')
    serial.Serial=forbidden
    import beta4_migration
    beta4_migration.Link=forbidden
    from test_v2_status import fresh,boot,layout,snapshot
    from test_v2_sram_store import console
    cp=p.read(c.EVIDENCE/'cut-boot-recovery-checkpoint.json');cache={};proofs={}
    for key in ['new_state_boot','recovered_state_boot']:
        proof=cp['reports'][key];path=Path(proof['path']);assert p.sha(path.read_bytes())==proof['sha256']
        report=p.read(path);assert report['passed'] and report['virtual_rtc']=='2026-10-17T19:53:15';proofs[str(path)]=proof['sha256']
        for check in report['checks']:
            if check.get('persistent_state_unchanged'):
                # Recovered-state receipt fixes B0/gen46 for all inputs; its
                # reused checks omit the redundant selected_page field.
                page=check.get('selected_page')
                if page is None:
                    assert key=='recovered_state_boot' and report['recovered_state_boot_model_passed'];page=0xb0
                cache[tuple(check['input_bank_sha256'])]=dict(report=str(path),check=check['name'],page=page)
    checks=[];fresh_count=0;reuse_count=0
    try:
        for case in prior['checks']:
            label=case['name'];source=a.source.parent/label;folder=a.out/label;folder.mkdir()
            banks=[(source/f'b{i}.bin').read_bytes() for i in range(4)];hashes=p.bank_hashes(banks);assert hashes==case['bank_sha256']
            cfg=c.latest(banks)[2][8:24];page=cfg[8];generation=int.from_bytes(cfg[9:13],'little');assert page==case['selected_page'] and generation==case['selected_generation']
            key=tuple(hashes)
            if key in cache:
                proof=cache[key];assert proof['page']==page;reuse_count+=1
                result=dict(name=label,passed=True,reused_from=proof,input_bank_sha256=hashes,selected_page=page,selected_generation=generation,persistent_state_unchanged=True)
            else:
                cpu,m=fresh(primary=layout());m.fast=True;m.banks=list(map(bytearray,banks));m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2E 17 10 26 80 00')
                binding=bytes(m.banks[3][0x1c00:0x1c20])
                if binding[:3]==b'EI\1' and binding[31]==0 and p.crc(binding[:28])==int.from_bytes(binding[28:30],'little'):m.bus.ee[0xf2:0xf8]=binding[8:14]
                before=snapshot(m)
                try:
                    boot(cpu);(folder/'boot.txt').write_bytes(m.tx)
                    assert m.ram[0x7d30]==page and bytes(m.tx).endswith(b'B3> ')
                    version={40:b'2.0b28',46:b'2.0b34',47:b'2.0b35'}[generation];assert b'STR8-N '+version in m.tx
                    reply=console(cpu,m,b'D 0200 0200\r',limit=10000000);(folder/'monitor-read.txt').write_bytes(reply)
                    assert b'0200' in reply and b'5A' in reply and reply.endswith(b'B3> ')
                    assert snapshot(m)==before and not m.events and not m.bus.writes
                except Exception:
                    (folder/'failure-boot.txt').write_bytes(m.tx)
                    for i,b in enumerate(m.banks):(folder/f'failed-b{i}.bin').write_bytes(b)
                    raise
                fresh_count+=1;cache[key]=dict(report=str(a.out/'report.json'),check=label,page=page)
                result=dict(name=label,passed=True,fresh_cpu_execution=True,input_bank_sha256=hashes,selected_page=page,selected_generation=generation,persistent_state_unchanged=True)
            checks.append(result);(a.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',label,'boot',flush=True)
    except Exception:
        (a.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    sources={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(ws.resolve()):
            name=path.resolve().relative_to(ws).as_posix();digest=p.sha(path.read_bytes());sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    for path,digest in proofs.items():
        for name,expected in p.read(Path(path))['model_sources'].items():
            if name in sources:assert sources[name]==expected
    result=dict(passed=True,cases=len(checks),checks=checks,fresh_boot_cpu_cases=fresh_count,reused_identical_boot_cases=reuse_count,
        fault_state_boot_model_passed=True,source_report=str(a.source.resolve()),source_report_sha256=p.sha(a.source.read_bytes()),prior_boot_reports=proofs,
        finished_utc=datetime.now(timezone.utc).isoformat(),test_sha256=p.sha(Path(__file__).read_bytes()),model_sources=sources,
        virtual_rtc='2026-10-17T19:53:15',serial_disabled=True,board_access=False,physical_power_cycle_tested=False,route_qualified=False,release_qualified=False,installation_permitted=False)
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'fault-state boot checks')
if __name__=='__main__':main()
