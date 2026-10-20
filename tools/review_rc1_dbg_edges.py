"""Offline boundary review using the existing instruction-model fixture. No ports.

Writes a derived harness only in a new review directory. Original firmware,
model receipts and the fixture source remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
EXTRA=r'''
    results=[]
    def record(name,slot,expected,observed):
        results.append(dict(name=name,slot=slot,expected=expected,observed=observed,passed=expected==observed))
    for slot in ('A','B'):
        for ident in (0,0x7F,0x80,0xA1,0xBF,0xC1,0xC2,0xFF):
            cpu,m=fixture(slot);m.ram[0x400:0x404]=bytes.fromhex('C1 00 05 00');m.ram[0x500]=0x60
            code=bytes.fromhex('A9 00 A2 04 00 81')+bytes([0xA9,ident,0,0x82,0,1])
            m.ram[0x200:0x200+len(code)]=code;cpu.pc=0x200;cpu.p=0x24
            run(cpu,lambda:stopped(cpu))
            record(f'unregister {ident:02X} after registering C1',slot,
                   dict(A=0 if ident==0xC1 else 1,carry=ident==0xC1,C1_present=ident!=0xC1),
                   dict(A=m.ram[0x7002],carry=bool(m.ram[0x7005]&1),C1_present=m.ram[0x7C40]==0xC1))
            assert not m.writes
        for ident in (0x9F,0xA0,0xBF,0xC0,0xFF):
            cpu,m=fixture(slot,1);m.ram[0x400:0x404]=bytes([ident,0,5,0]);m.ram[0x500]=0x60;cpu.a=0;cpu.x=4
            direct(cpu,sy['DBG_SYSTEM_REGISTER'])
            ok=0xA0<=ident<=0xBF
            record(f'system ID boundary {ident:02X}',slot,dict(A=0 if ok else 1,carry=ok),dict(A=cpu.a,carry=bool(cpu.p&1)))
        for pointer in (0x1FF,0x64FE):
            cpu,m=fixture(slot,1);m.ram[0x400:0x404]=bytes.fromhex('A1 00 05 00');cpu.a=pointer&255;cpu.x=pointer>>8
            direct(cpu,sy['DBG_SYSTEM_REGISTER'])
            record(f'system request bounds {pointer:04X}',slot,dict(A=1,carry=False),dict(A=cpu.a,carry=bool(cpu.p&1)))
        cpu,m=begin(bytes.fromhex('00 01 EA'),slot,1);context=bytes(m.ram[0x7000:0x7007]);table=bytes(m.ram[0x7C30:0x7C80])
        m.ram[0x400:0x404]=bytes.fromhex('A1 00 05 00');cpu.a=0;cpu.x=4;direct(cpu,sy['DBG_SYSTEM_REGISTER'])
        record('system registration during active session',slot,dict(A=1,carry=False,context_unchanged=True,table_unchanged=True),
               dict(A=cpu.a,carry=bool(cpu.p&1),context_unchanged=bytes(m.ram[0x7000:0x7007])==context,table_unchanged=bytes(m.ram[0x7C30:0x7C80])==table))
        for end,released in ((0x64FF,False),(0x66FF,True)):
            for pointer,count in ((end,1),(end-1,2),(end,2)):
                cpu,m=fixture(slot);m.ram[0x7D0C]=0 if released else 255;m.ram[0x7D0A:0x7D0C]=end.to_bytes(2,'little')
                m.ram[pointer:pointer+2]=b'ZZ';code=bytes([0xA9,pointer&255,0xA2,pointer>>8,0xA0,count,0,0x84,0,1])
                m.ram[0x200:0x200+len(code)]=code;cpu.pc=0x200;cpu.p=0x25
                run(cpu,lambda:stopped(cpu))
                valid=pointer+count-1<=end
                record(f'text range {pointer:04X}+{count} with RAM end {end:04X}',slot,
                       dict(A=pointer&255 if valid else 1,X=pointer>>8,Y=count,carry=valid,printed_bytes=count if valid else 0),
                       dict(A=m.ram[0x7002],X=m.ram[0x7003],Y=m.ram[0x7004],carry=bool(m.ram[0x7005]&1),printed_bytes=m.tx.count(ord('Z'))))
                assert not m.writes
                if is816:assert cpu.mode==1 and cpu.native_detector_steps==0
    output=Path(__file__).with_name('edge-review-816.json' if is816 else 'edge-review-02.json')
    output.write_text(json.dumps(dict(audit_completed=True,passed=all(x['passed'] for x in results),board_access=False,native_debugging=False,
        CPU='65C816 E=1' if is816 else '65C02',firmware_sha256=hashlib.sha256(image).hexdigest(),checks=results),indent=2)+'\n')
    print('REVIEW',len(results),'checks;',sum(not x['passed'] for x in results),'contract/invalid-input discrepancies;',output)

if __name__=='__main__':main()
'''

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--build',type=Path,required=True);a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    source=(ROOT/'tools/test_rc1_debugger.py').read_text()
    prefix,separator,_=source.partition("    rows={r['opcode']")
    assert separator and 'def fixture(' in prefix and 'def direct(' in prefix
    prefix=prefix.replace("ROOT=Path(__file__).resolve().parents[1]",'ROOT=Path('+repr(str(ROOT))+')')
    harness=out/'harness.py';harness.write_text(prefix+EXTRA)
    for cpu in ('65c02','65c816-e'):
        result=subprocess.run([sys.executable,str(harness),'--build',str(a.build.resolve()),'--cpu',cpu],capture_output=True,text=True)
        (out/(cpu+'.log')).write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        print(result.stdout.strip())
    (out/'source-pin.json').write_text(json.dumps(dict(fixture_source_sha256=hashlib.sha256((ROOT/'tools/test_rc1_debugger.py').read_bytes()).hexdigest(),harness_sha256=hashlib.sha256(harness.read_bytes()).hexdigest(),board_access=False),indent=2)+'\n')

if __name__=='__main__':main()
