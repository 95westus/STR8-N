"""Exhaustive linked $82 IDs and $84 count/limit regressions. Offline only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
EXTRA=r'''
    groups=[];failures=[]
    states={
        'uninitialized':(0,bytes([0x5A])*80),
        'empty':(0xA5,bytes(80)),
        'partial-with-hole':(0xA5,bytes([0xA1,0,5,0])+bytes(12)+bytes(4)+bytes([0xC1,0,5,0])+bytes(52)+bytes([0xFE,0,5,0])),
        'full':(0xA5,b''.join(bytes([i,0,5,0]) for i in range(0xA0,0xA4))+b''.join(bytes([i,0,5,0]) for i in range(0xC0,0xD0))),
        'system-only':(0xA5,b''.join(bytes([i,0,5,0]) for i in range(0xA0,0xA4))+bytes(64))}
    def mismatch(label,expected,observed):
        if expected!=observed:failures.append(dict(name=label,expected=expected,observed=observed))
    # Observe the actual memory bus at the first byte beyond the selected RAM
    # limit, rather than inferring absence of an overread from the printed text.
    original_get=Memory.__getitem__
    def watched_get(self,address):
        if isinstance(address,int) and address==getattr(self,'forbidden_read',None):self.forbidden_reads+=1
        return original_get(self,address)
    Memory.__getitem__=watched_get
    for slot in ('A','B'):
        for state,(valid,table) in states.items():
            assert len(table)==80
            cpu,m=fixture(slot,1)
            for ident in range(256):
                m.ram[0x7BFF]=valid;m.ram[0x7C30:0x7C80]=table
                p=(0x24,0x25,0x64,0xE7)[ident%4];before=bytes([0x34,0x12,ident,0x22,0x33,p,0xFF]);m.ram[0x7000:0x7007]=before
                cpu.pc=sy['DBG_UNREGISTER'];cpu.sp=255;run(cpu,lambda:cpu.pc==sy['DBG_FUNCTION_RETURN'])
                expected_table=bytearray(table);found=None
                if valid==0xA5 and 0xC0<=ident<0xFF:
                    found=next((i for i in range(16,80,4) if table[i]==ident),None)
                success=found is not None
                if success:expected_table[found]=0
                expected=bytearray(before);expected[2]=0 if success else 1;expected[5]=(p|1) if success else (p&0xFE)
                mismatch(f'{slot} unregister {ident:02X} {state}',dict(context=expected.hex(),table=bytes(expected_table).hex()),
                         dict(context=bytes(m.ram[0x7000:0x7007]).hex(),table=bytes(m.ram[0x7C30:0x7C80]).hex()))
                assert not m.writes
                if is816:assert cpu.mode==1 and cpu.b==0xA5 and cpu.native_detector_steps==0
            groups.append(dict(name=f'{slot} all 256 unregister IDs: {state}',cases=256))
        for end,released in ((0x64FF,False),(0x66FF,True)):
            cpu,m=fixture(slot,1);m.ram[0x7D0C]=0 if released else 255;m.ram[0x7D0A:0x7D0C]=end.to_bytes(2,'little')
            m.forbidden_read=end+1
            cases=[(end-count+1,count,True) for count in range(256)]
            cases.extend([(0x200,1,True),(0x200,255,True),(0x23FF,2,True),(0x23FE,255,True),
                          (0x1FF,1,False),(end,2,False),(end-1,3,False),(end+1,1,False),(0xFFFF,255,False),
                          (0xFFFF,0,True),(0,0,True)])
            for index,(pointer,count,valid) in enumerate(cases):
                if valid and count:m.ram[pointer:pointer+count]=b'Z'*count
                p=(0x24,0x25,0x64,0xE7)[index%4];before=bytes([0x34,0x12,pointer&255,pointer>>8,count,p,0xFF]);m.ram[0x7000:0x7007]=before
                m.tx.clear();m.forbidden_reads=0;cpu.pc=sy['DBG_TRACE_TEXT'];cpu.sp=255
                run(cpu,lambda:cpu.pc==sy['DBG_FUNCTION_RETURN'])
                expected=bytearray(before)
                if not valid:expected[2]=1;expected[5]&=0xFE
                mismatch(f'{slot} text {pointer:04X}+{count} end {end:04X}',dict(context=expected.hex(),output_hex=(b'Z'*count if valid else b'').hex(),overreads=0),
                         dict(context=bytes(m.ram[0x7000:0x7007]).hex(),output_hex=bytes(m.tx).hex(),overreads=m.forbidden_reads))
                assert not m.writes
                if is816:assert cpu.mode==1 and cpu.b==0xA5 and cpu.native_detector_steps==0
            groups.append(dict(name=f'{slot} all 256 text counts at RAM end {end:04X}, zero/invalid/wrapping/page-crossing ranges',cases=len(cases)))
    proof=dict(passed=not failures,board_access=False,native_debugging=False,native_applications_tested=False,
        CPU='65C816 E=1' if is816 else '65C02',firmware_sha256=hashlib.sha256(image).hexdigest(),groups=groups,
        cases=sum(g['cases'] for g in groups),failures=failures)
    path=Path(__file__).with_name('brk-regressions-816.json' if is816 else 'brk-regressions-02.json')
    path.write_text(json.dumps(proof,indent=2)+'\n')
    print('REGRESSIONS',proof['CPU'],proof['cases'],'cases;',len(failures),'failures;',path)
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
'''

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--build',type=Path,required=True);a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    source=(ROOT/'tools/test_rc1_debugger.py').read_text();prefix,marker,_=source.partition("    rows={r['opcode']")
    assert marker and 'def fixture(' in prefix and 'def direct(' in prefix
    prefix=prefix.replace("ROOT=Path(__file__).resolve().parents[1]",'ROOT=Path('+repr(str(ROOT))+')')
    harness=out/'harness.py';harness.write_text(prefix+EXTRA)
    pins=dict(fixture_source_sha256=hashlib.sha256((ROOT/'tools/test_rc1_debugger.py').read_bytes()).hexdigest(),harness_sha256=hashlib.sha256(harness.read_bytes()).hexdigest(),board_access=False)
    (out/'source-pin.json').write_text(json.dumps(pins,indent=2)+'\n')
    results=[]
    for cpu in ('65c02','65c816-e'):
        result=subprocess.run([sys.executable,str(harness),'--build',str(a.build.resolve()),'--cpu',cpu],capture_output=True,text=True)
        (out/(cpu+'.log')).write_text(result.stdout+result.stderr);print(result.stdout.strip(),flush=True)
        if result.returncode:print(result.stderr,file=sys.stderr)
        results.append(result.returncode)
    if any(results):raise SystemExit(1)

if __name__=='__main__':main()
