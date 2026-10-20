"""Package a qualified debugger build for an explicit future board experiment."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
KIT=ROOT/'release/rc1-migration-r1'
sha=lambda data:hashlib.sha256(data).hexdigest()


def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def scenarios(symbols):
    s=symbols['steps'];b=symbols['breakpoints'];q=symbols['query']
    def action(command,pc=None,x=None,y=None,sp=None,a=None,**extra):
        item=dict(command=command,prompt='DBG',**extra)
        regs={k:v for k,v in (('PC',pc),('A',a),('X',x),('Y',y),('S',sp)) if v is not None}
        if regs:item['registers']=regs
        return item
    first=[action('G 0200',s['STEP_POINT'],0x22,0x33,255,0x11),
           action(f'D {s["STEP_POINT"]:04X} {s["STEP_POINT"]:04X}',contains=[f'{s["STEP_POINT"]:04X}: E8']),
           action('M 0600 A5'),action('D 0600 0600',contains=['0600: A5']),
           action(f'U {s["STEP_POINT"]:04X} 01',contains=['INX']),
           action('S',s['CALL_POINT'],0x23,0x33,255),action('S',s['SUB'],0x23,0x33,0xFD),
           action('S',s['SUB']+1,0x24,0x33,0xFD),action('S',s['SUB_RETURN'],0x25,0x33,0xFD),
           action('S',s['AFTER_CALL'],0x25,0x33,255),action('N',s['SECOND_CALL'],0x25,0x34,255),
           action('N',s['AFTER_OVER'],0x27,0x34,255),action('C',s['DONE'],0x27,0x34,255),
           dict(command='C',prompt='MON')]
    addresses=[b[f'BP{i}'] for i in range(8)]
    setup=[action('G 0200',b['READY'],0,0,255)]+[action(f'B {v:04X}') for v in addresses]
    points=setup+[action('B',breakpoints=addresses),action('B 0600',error=True)]
    for lap in range(2):
        for i,pc in enumerate(addresses):points.append(action('C',pc,lap*8+i,lap,255))
    points += [action('B',breakpoints=addresses),
               action(f'D {addresses[0]:04X} {addresses[-1]:04X}',contains=[' '.join(['E8']*8)]),
               action('C',b['DONE'],16,2,255),action(f'BC {addresses[3]:04X}'),
               action('B',breakpoints=addresses[:3]+addresses[4:]),action('BC *'),action('B',breakpoints=[]),
               dict(command='C',prompt='MON')]
    abort=setup+[dict(command='X',prompt='MON')]
    query=[action('G 0200',q['DONE'],16,4,255,1),dict(command='C',prompt='MON')]
    return dict(schema=1,scope='65C02 and 65C816 E=1 only; native applications/debugging excluded',
                breakpoint_addresses=addresses,breakpoint_hits_expected=16,tests=[
                    dict(name='BRK entry, shared D/M/U, C/S/N and HOLD',image='smoke/steps.s19',entry=0x200,steps=first),
                    dict(name='all eight persistent breakpoints hit twice, ninth refusal, individual/all clear',image='smoke/breakpoints.s19',entry=0x200,steps=points),
                    dict(name='X abort cleans eight active breakpoint records',image='smoke/breakpoints.s19',entry=0x200,steps=abort),
                    dict(name='BRK 80 ABI query returns without stopping until BRK 03',image='smoke/query.s19',entry=0x200,steps=query)])


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--build',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();build=args.build.resolve();out=args.out.resolve()
    assert not out.exists(),out
    image=(build/'firmware.bin').read_bytes();report=json.loads((build/'debugger-build.json').read_text())
    assert sha(image)==report['firmware_sha256'] and len(image)==98304
    proofs=[]
    for name in ('debugger-test.json','debugger-test-65c816-e.json'):
        proof=json.loads((build/name).read_text())
        assert proof['passed'] and proof['full_boot_tested'] and not proof['board_access'] and not proof['native_816_tested']
        assert proof['firmware_sha256']==sha(image)
        assert proof['test_harness_sha256']==sha((ROOT/'tools/test_rc1_debugger.py').read_bytes()),'Re-run tests after changing the harness'
        assert proof.get('board_smoke_cases')==8,'Re-run both CPU suites with --smoke-package'
        proofs.append(proof)
    # Verify the unchanged upstream transaction engine before copying it.
    km=json.loads((KIT/'kit-manifest.json').read_text())
    for name,info in km['files'].items():
        data=(KIT/name).read_bytes();assert sha(data)==info['sha256'] and len(data)==info['bytes'],name
    out.mkdir(parents=True)
    for directory in ('engine/template','sectors','baseline','qualification','smoke'):(out/directory).mkdir(parents=True)
    for name in ('runtime.py','legacy_transport.py','install_transport.py'):
        shutil.copyfile(KIT/name,out/'engine'/name)
    shutil.copyfile(ROOT/'tools/serial_test_coordination.py',out/'engine/serial_test_coordination.py')
    for name in ('manifest.json','integrated-template.s19'):shutil.copyfile(KIT/'template'/name,out/'engine/template'/name)
    for name in ('board_plan.py','board_link.py','smoke_checks.py','BOARD_TEST.md','BRK_ABI.md'):
        shutil.copyfile(HERE/name,out/name)
    for name in ('debugger-build.json','debugger-test.json','debugger-test-65c816-e.json'):
        shutil.copyfile(build/name,out/'qualification'/name)
    rows=[(1,0xA000,'debugger-a000.bin'),(1,0xE000,'assembler/asm-e000.bin'),(1,0xF000,'assembler/vectors-f000.bin'),
          (3,0xA000,'str8n-v2-recovery-slot-a0.bin'),(3,0xB000,'str8n-v2-recovery-slot-b0.bin'),
          (3,0xE000,'str8n-v2-recovery-e000-efff.bin'),(3,0xF000,'str8n-v2-recovery-f000-ffff.bin'),
          (2,0x8000,'xip/utilities.bin'),(2,0xD000,'xip/utilities.bin')]
    sectors=[]
    for bank,address,name in rows:
        filename=f'b{bank}-{address:04x}.bin';offset=address-0x8000 if bank==2 else 0
        if bank==2:
            # Utilities end at D7FF; the rest of D000 contains unchanged XIP
            # data. Bind the complete sector, including that preserved tail.
            first=(bank-1)*32768+address-0x8000
            target=image[first:first+4096]
            legacy=(KIT/'payload'/name).read_bytes()[offset:offset+4096]
            before=legacy+target[len(legacy):]
        else:
            target=(build/'payload'/name).read_bytes()[:4096]
            before=(KIT/'payload'/name).read_bytes()[:4096] if address!=0xA000 or bank!=1 else b'\xff'*4096
        assert len(target)==len(before)==4096
        offset=(bank-1)*32768+address-0x8000;assert image[offset:offset+4096]==target
        (out/'sectors'/filename).write_bytes(target);(out/'baseline'/filename).write_bytes(before)
        sectors.append(dict(bank=bank,address=address,target='sectors/'+filename,baseline='baseline/'+filename))
    symbols={}
    for name in ('steps','breakpoints','query'):
        stem='smoke-'+name;shutil.copyfile(HERE/(stem+'.asm'),out/'smoke'/(stem+'.asm'))
        for command in ([shutil.which('wdc02as'),'-G','-L','-S','-W',stem+'.asm'],
                        [shutil.which('wdcln'),'-g','-s','-t','-c0200','-hm19','-j','-o',name+'.s19',stem+'.obj']):
            result=subprocess.run(command,cwd=out/'smoke',capture_output=True,text=True)
            if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        symbols[name]={n:int(v,16) for v,n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',(out/'smoke'/(name+'.map')).read_text(),re.M)}
        assert symbols[name]['START']==0x200
        # WDCLN defaults S9 to 0000; publish the actual RAM program entry.
        path=out/'smoke'/(name+'.s19');lines=path.read_text().splitlines()
        assert lines[-1].startswith('S9');lines[-1]='S9030200FA'
        path.write_text('\n'.join(lines)+'\n')
    save(out/'smoke/scenarios.json',scenarios(symbols));save(out/'smoke/symbols.json',symbols)
    for proof in proofs:
        assert proof['smoke_suite_sha256']==sha((out/'smoke/scenarios.json').read_bytes()),'Untested smoke scenarios'
        for name,digest in proof['smoke_images_sha256'].items():assert sha((out/name).read_bytes())==digest,'Untested smoke image'
    files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(out.rglob('*')) if p.is_file()}
    save(out/'board-test-manifest.json',dict(schema=1,candidate='rc1-debugger-v1',generation=50,
         board_access=False,hardware_qualified=False,native_debugging=False,firmware_sha256=sha(image),
         debugger_code_bytes=report['debugger_code_bytes'],remaining_sector_bytes=report['remaining_bytes'],
         install_method='exact-source standalone RAM transaction; nine firmware sectors; eleven 4K transfers',
         sectors=sectors,files=files))
    print('PASS prepared experimental board package:',out,'; no ports opened')


if __name__=='__main__':main()
