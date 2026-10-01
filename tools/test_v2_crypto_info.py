"""Emulate assembled probe: exact command traffic, bounded failures, VIA restore."""
import json
import os, sys
from types import SimpleNamespace
from pathlib import Path
for directory in sorted(Path("BUILD").glob("v*/local/test-deps"), reverse=True):
    if (directory/"py65").is_dir(): sys.path.insert(0,str(directory))
from py65.devices.mpu65c02 import MPU
harness=SimpleNamespace(MPU=MPU)
def ret(cpu): cpu.pc=(cpu.stPopWord()+1)&65535
harness.ret=ret
class Memory(list):
    def __init__(self,pins):
        super().__init__([0]*65536); self.pins=pins; self.writes=[]
        self[0x2000:0x2000+len(harness.IMAGE)]=harness.IMAGE
        self[0x7e60:0x7e64]=b"RA\x01\x0d"
        self[0x7fc3]=0x36; self[0x7fcf]=0x24
    def __getitem__(self,key):
        if key==0x7fcf:
            ddr=super().__getitem__(0x7fc3)
            return (super().__getitem__(key)&ddr)|(self.pins&~ddr)
        return super().__getitem__(key)
    def __setitem__(self,key,value):
        if isinstance(key,int): self.writes.append((key,value))
        super().__setitem__(key,value)
harness.Memory=Memory
from build_v2_crypto_info import OUT, NAME, crc, commands
R=json.loads((OUT/'build.json').read_text()); S=R['symbols']
harness.IMAGE=(OUT/(NAME+'.bin')).read_bytes()
def run(kind='good',pins=0x81):
    mem=harness.Memory(pins); cpu=harness.MPU(memory=mem,pc=0x2000)
    out=bytearray(); tx=[]; response=[]; reads=0
    for step in range(200000):
        pc=cpu.pc
        if pc==0x7e67: break
        if pc in (0x7e6d,0x7e7c,0x7e7f):
            out.extend(bytes([cpu.a]) if pc==0x7e6d else f'{cpu.a:02X}'.encode() if pc==0x7e7c else b'\r\n'); harness.ret(cpu)
        elif pc==S['DELAY']: harness.ret(cpu)
        elif kind!='physical' and pc==S['I2WRITE']:
            tx.append(cpu.a); cpu.p |= 1; harness.ret(cpu)
        elif kind!='physical' and pc==S['I2READ']:
            if not response:
                wake=reads%2==0
                response=list(bytes.fromhex('04113343') if wake else bytes.fromhex('0700006002')+crc(bytes.fromhex('0700006002')))
                if kind=='badwake' and wake: response[-1]^=1
                if kind=='badcount' and not wake: response=[255]
                reads+=1
            cpu.a=response.pop(0); harness.ret(cpu)
        else: cpu.step()
    else: raise AssertionError('unbounded execution')
    assert mem[0x7fc3]==0x36 and mem[0x7fcf]&0x36==0x24
    assert all(a<0x7000 or a in (0x7fc3,0x7fcf,0x7e60,0x7e61,0x7e62,0x7e63) for a,v in mem.writes)
    return out.decode(),tx
assert crc(bytes.fromhex('0411'))==bytes.fromhex('3343')
out,tx=run()
expected=[]
for row in commands(): expected += [0xc1,0xc0,3,*bytes.fromhex(row['packet']),0xc1,0xc0,1]
assert tx==expected
assert 'CRYPTO INFO DONE' in out and len(out.splitlines())==70
for kind in ('badwake','badcount'): assert 'TRANSPORT FAIL' in run(kind)[0]
for pins in (0x81,0,1,0x80): assert 'TRANSPORT FAIL' in run('physical',pins)[0]
(OUT/'test-results.json').write_text(json.dumps({'sha256':R['sha256'],'passed':True,'electrical_timing_emulated':False},indent=2)+'\n')
print('PASS: exact 69-command traffic; bad wake/count; absent/stuck bus; bounded return; VIA restoration')
