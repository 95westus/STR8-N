"""Qualify direct WDCMONV2/beta4 -> v1g; vendor fixtures remain private."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();pkg=args.package.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    sys.path[:0]=[str(pkg),str(pkg/'engine')]
    import uniform_upgrade as u
    import bootstrap_routes as b
    import runtime as r
    from rc1_uniform_cpu_model import execute
    protected_sources={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (Path(__file__),ROOT/'tools/rc1_uniform_cpu_model.py')}
    manifest=u.package(pkg);kit,m,f=b.modules(pkg);checks=[]
    def passed(name,**values):
        assert values.pop('passed',True)
        checks.append(dict(name=name,passed=True,**values));print('PASS',name,flush=True)
    def refuse(name,action):
        try:action()
        except (ValueError,KeyError):passed(name)
        else:raise AssertionError('Accepted '+name)
    def capture(path,banks):
        path.mkdir();files={}
        for n,body in enumerate(banks):
            for suffix in ('','-repeat'):
                name=f'b{n}{suffix}.bin';(path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
        ram=bytes(n%251 for n in range(25344))
        for name,body in [('application-ram.bin',ram),('restore-application-ram.s19',r.migration.s19(dict(enumerate(ram,0x200)),0x200))]:
            (path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
        u.legacy.save(path/'capture.json',dict(schema=1,board='MODEL',usb_serial='MODEL-USB',repeat_verified=True,files=files))
    cases=[]
    metadata=out/'private-metadata-escrow.bin'
    metadata.write_bytes((Q/'rc1-v1g-register-edits-qualification-r1-2026-10-20-225008Z/2604-before/b3.bin').read_bytes()[0x1c00:0x2000])
    for cpu,sourcefile in [('65C02',Q/'board-2512-layout-2026-09-24/b0-final.bin'),
                           ('65C816',Q/'bf1-2609-windows-offline-2026-10-18-r1/model-only-WDC-capture/b3.bin')]:
        banks=[b'\xff'*32768]*3+[sourcefile.read_bytes()]
        assert b.identify(pkg,banks)=='wdcmonv2-'+cpu
        name='wdcmonv2-'+cpu;cap=out/(name+'-capture');capture(cap,banks)
        refuse(name+' requires honest tracked-wear acknowledgement',lambda:u.prepare(pkg,cap,out/(name+'-no-ack')))
        plan=out/(name+'-plan');info=u.prepare(pkg,cap,plan,accept_unknown_wear_history=True);u.verify(pkg,plan)
        expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        assert u.identify(pkg,manifest,expected)=='v1g' and expected[0]==banks[0]
        assert info['transaction']['no_lifetime_wear_claim'] and info['intermediate_generation49'] is False
        assert len(info['transaction']['operations'])==23
        passed(name+' direct 23-transfer v1g plan, no intermediate49, exact target')
        cases.append((name,plan,banks,cpu=='65C816',True))
        config=bytearray([1,0,3,7,240,10,0]+[0]*9);config=r.preference(config,0xb0,50)
        history=out/(name+'-history.json');u.legacy.save(history,dict(schema=1,board='MODEL',config=config.hex(),counts=list(range(100,132)),sequence=100))
        owned=out/(name+'-escrow-plan');owned_info=u.prepare(pkg,cap,owned,history=history,metadata_escrow=metadata);u.verify(pkg,owned)
        target=[(owned/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        assert target[3][0x1c00:0x2000]==metadata.read_bytes() and r.latest(target)[2][8:24]==config
        passed(name+' board-bound history/metadata preserves owner preference/data and conservative counts')
        cases.append((name+'-escrow',owned,banks,cpu=='65C816',True))
    base=[bytearray(b'\xff'*32768) for _ in range(4)];b4=ROOT/'BUILD/v2-beta4/kit'
    base[3][:8192]=(b4/'str8n-v2-b4-maint-8000-9fff.bin').read_bytes()
    for offset,name in [(0x2000,'slot-a'),(0x3000,'slot-b'),(0x6000,'e000-efff'),(0x7000,'f000-ffff')]:
        base[3][offset:offset+4096]=(b4/f'str8n-v2-b4-{name}.bin').read_bytes()
    cfg=bytearray([1,0,3,7,240,10,0]+[0]*9);cfg[14:]=r.migration.config_sum(cfg)
    base[1][0x1f00:0x1f08]=b'USERDATA'
    for page in (0xa0,0xb0):
        banks=list(map(bytearray,base));config=r.preference(cfg,page,13)
        banks[3][0x4000:0x4080]=r.record(config,list(range(50,82)),100)
        banks=list(map(bytes,banks));name=f'beta4-{page:x}';cap=out/(name+'-capture');capture(cap,banks)
        plan=out/(name+'-plan');info=u.prepare(pkg,cap,plan,metadata_escrow=metadata);u.verify(pkg,plan)
        expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        assert u.identify(pkg,manifest,expected)=='v1g' and expected[0]==banks[0]
        assert expected[1][0x1f00:0x1f08]==b'USERDATA' and r.latest(expected)[2][8:17]==config[:9]
        assert expected[3][0x1c00:0x2000]==metadata.read_bytes()
        assert len(info['transaction']['operations'])-1==23 and not info['intermediate_generation49']
        passed(name+' direct 23-transfer v1g plan preserves user flash/startup/preference')
        for is816 in (False,True):cases.append((name,plan,banks,is816,False))
        bad=list(map(bytearray,banks));bad[1][0x2000]=0;badcap=out/(name+'-conflict');capture(badcap,bad)
        refuse(name+' occupied debugger destination preserved/refused',lambda:u.prepare(pkg,badcap,out/(name+'-bad-plan')))
    for name,plan,banks,is816,stock in cases:
        result=execute(pkg,plan,banks,is816=is816,stock=stock)
        passed(name+' '+result['CPU']+' actual linked installer',**result)
    for name,plan,banks,is816,stock in (cases[0],cases[2],cases[4],cases[-1]):
        for fault in ('stale','corrupt'):
            result=execute(pkg,plan,banks,is816=is816,stock=stock,fault=fault)
            passed(name+(' 816' if is816 else ' 02')+' '+fault+' device refusal',**result)
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in protected_sources.items()),'Model source changed while executing'
    u.legacy.save(out/'report.json',dict(passed=True,board_access=False,checks=checks,groups=len(checks),actual_complete_installer_executions=len(cases),
        native_debugging=False,RTC_drift_in_release_qualification=False,intermediate_generation49=False,
        vendor_images_exported=False,hash_ranges_accelerated=True,electrical_timing_tested=False,
        uniform_manifest_sha256=r.sha((pkg/'uniform-manifest.json').read_bytes()),source_sha256=protected_sources,
        test_sha256=protected_sources[str(Path(__file__))],model_sha256=protected_sources[str(ROOT/'tools/rc1_uniform_cpu_model.py')]))


if __name__=='__main__':main()
