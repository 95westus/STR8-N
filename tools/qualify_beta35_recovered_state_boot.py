"""Boot receipt-bound recovered images; fake devices only, serial forbidden."""
import argparse,json,os,sys,traceback
from pathlib import Path
from datetime import datetime,timezone
import beta35_model_transactions as c
p=c.p
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    cp=p.read(c.EVIDENCE/'cut-boot-recovery-checkpoint.json');proof=cp['reports']['interrupted_restore_recovery'];source=Path(proof['path'])
    assert p.sha(source.read_bytes())==proof['sha256'];prior=p.read(source);assert prior['passed'] and prior['restoration_from_interrupted_restoration_tested']
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kw):raise RuntimeError('Serial access forbidden in recovered boot model')
    serial.Serial=forbidden
    import beta4_migration
    beta4_migration.Link=forbidden
    from test_v2_status import fresh,boot,layout,snapshot
    from test_v2_sram_store import console
    checks=[];cache={};fresh_count=0;reuse_count=0;noops=[]
    try:
        for case in prior['checks']:
            if not case['name'].endswith('-recovered'):continue
            label=case['name'];folder=a.out/label;folder.mkdir();sourcefolder=source.parent/label
            if 'bank_sha256' not in case:
                info=p.read(sourcefolder/'plan.json');assert info['no_change'] and info['source_sha256']==info['expected_sha256']
                noops.append(dict(name=label,reason='Recovery is exact no-op; unchanged parent state covered by new-state boot receipt'))
                continue
            banks=[(sourcefolder/f'b{i}.bin').read_bytes() for i in range(4)];hashes=p.bank_hashes(banks);assert hashes==case['bank_sha256']
            cfg=c.latest(banks)[2][8:24];page=cfg[8];assert cfg[7:8]==b'P' and page==0xb0 and cfg[9:13]==(46).to_bytes(4,'little')
            key=tuple(hashes)
            if key in cache:
                reuse_count+=1;result=dict(name=label,passed=True,reused_from=cache[key],input_bank_sha256=hashes,persistent_state_unchanged=True)
            else:
                cpu,m=fresh(primary=layout());m.fast=True;m.banks=list(map(bytearray,banks));m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2E 17 10 26 80 00')
                binding=bytes(m.banks[3][0x1c00:0x1c20])
                if binding[:3]==b'EI\1' and binding[31]==0 and p.crc(binding[:28])==int.from_bytes(binding[28:30],'little'):
                    m.bus.ee[0xf2:0xf8]=binding[8:14]
                before=snapshot(m)
                try:
                    boot(cpu);(folder/'boot.txt').write_bytes(m.tx)
                    assert m.ram[0x7d30]==page and b'STR8-N 2.0b34' in m.tx and bytes(m.tx).endswith(b'B3> ')
                    reply=console(cpu,m,b'D 0200 0200\r',limit=10000000);(folder/'monitor-read.txt').write_bytes(reply)
                    assert b'0200' in reply and b'5A' in reply and reply.endswith(b'B3> ')
                    assert snapshot(m)==before and not m.events and not m.bus.writes
                except Exception:
                    (folder/'boot-failure.txt').write_bytes(m.tx)
                    for i,b in enumerate(m.banks):(folder/f'failed-b{i}.bin').write_bytes(b)
                    raise
                fresh_count+=1;cache[key]=label
                result=dict(name=label,passed=True,fresh_cpu_execution=True,input_bank_sha256=hashes,selected_page=page,generation=46,persistent_state_unchanged=True)
            checks.append(result);(a.out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',label,'boot',flush=True)
    except Exception:
        (a.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    sources={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(ws.resolve()):
            name=path.resolve().relative_to(ws).as_posix();digest=p.sha(path.read_bytes());sources[name]=digest
            if name in freeze['source_files']:assert digest==freeze['source_files'][name]
    result=dict(passed=True,cases=len(checks),checks=checks,no_op_parent_cases=noops,fresh_boot_cpu_cases=fresh_count,
        reused_identical_boot_cases=reuse_count,recovered_state_boot_model_passed=True,source_report=str(source),source_report_sha256=proof['sha256'],
        finished_utc=datetime.now(timezone.utc).isoformat(),test_sha256=p.sha(Path(__file__).read_bytes()),model_sources=sources,
        virtual_rtc='2026-10-17T19:53:15',serial_disabled=True,board_access=False,physical_power_cycle_tested=False,
        route_qualified=False,release_qualified=False,installation_permitted=False)
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'recovered-state boot checks')
if __name__=='__main__':main()
