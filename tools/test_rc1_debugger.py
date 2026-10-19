"""Execute the debugger candidate offline; no serial/network/board access.

Uses py65's 65C02 or py65816's 65C816 model plus bank/FT245 behavior. Actual debugger,
monitor D/M, assembler, RAM vectors and worker instructions execute unchanged.
The board's timing delay is skipped. Native applications/debugging and interrupt
timing are out of scope; only rc1's existing reset CPU detector may exchange E.
"""
import argparse
import binascii
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from fetch_rc1_debugger_816_model import COMMIT, MODEL_SHA256, SOURCE

ROOT=Path(__file__).resolve().parents[1]


def s19(path):
    cells={}
    for line in path.read_text().splitlines():
        if line.startswith('S1'):
            r=bytes.fromhex(line[2:]);assert sum(r)&255==255
            a=int.from_bytes(r[1:3],'big')
            cells.update({a+i:v for i,v in enumerate(r[3:-1])})
    return cells


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build',type=Path,required=True)
    ap.add_argument('--deps',type=Path,default=ROOT/'BUILD/v1.30/local/test-deps')
    ap.add_argument('--cpu',choices=('65c02','65c816-e'),default='65c02')
    ap.add_argument('--deps-816',type=Path,default=ROOT/'BUILD/test-deps-816')
    ap.add_argument('--smoke-package',type=Path,help='rehearse the exact packaged board smoke images and command expectations')
    ap.add_argument('--manuals',type=Path,help='assemble and execute marked examples from ASM_GUIDE.md and ABI_REFERENCE.md offline')
    ap.add_argument('--skip-boot',action='store_true',help='development subset; report records omitted boot coverage')
    a=ap.parse_args();out=a.build.resolve()
    harness_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    sys.path.insert(0,str(a.deps))
    is816=a.cpu=='65c816-e'
    model_hash=None
    if is816:
        sys.path.insert(0,str(a.deps_816))
        from py65816.devices.mpu65c816 import MPU as BaseMPU
        model_hash=hashlib.sha256(Path(sys.modules[BaseMPU.__module__].__file__).read_bytes()).hexdigest()
        assert model_hash==MODEL_SHA256,model_hash
    else:
        from py65.devices.mpu65c02 import MPU as BaseMPU
    report=json.loads((out/'debugger-build.json').read_text());sy=report['debugger_symbols']
    allsy=json.loads((out/'symbols.json').read_text());image=(out/'firmware.bin').read_bytes()
    checks=[];transcripts=[]
    boot=allsy['core/str8n-v2-boot']
    xce=boot['BOOT_XCE'];restore=boot['BOOT_XCE_RESTORE']
    detector_native_pcs=(xce+1,xce+2,xce+4,restore-1,restore)
    boot_results=[]

    class Memory:
        def __init__(self):
            self.ram=bytearray(32768);self.bank=3
            self.banks=[bytearray(b'\xff'*32768)]+[bytearray(image[i:i+32768]) for i in range(0,len(image),32768)]
            self.ram[0x7FEC]=0xEE;self.ram[0x7FE0]=0x0C
            self.rx=deque();self.tx=bytearray();self.writes=[];self.reads=[]
        def __getitem__(self,address):
            if isinstance(address,slice):return [self[i] for i in range(*address.indices(65536))]
            assert 0<=address<=65535,('nonzero 816 bank access',hex(address))
            if 0x6500<=address<0x6700:self.reads.append(address)
            if address>=0x8000:return self.banks[self.bank][address-0x8000]
            if address==0x7FE0:return self.ram[address]&~0x23 | (0 if self.rx else 2)
            if address==0x7FE1 and not self.ram[0x7FE3]:return self.rx[0] if self.rx else 0
            return self.ram[address]
        def __setitem__(self,address,value):
            assert 0<=address<=65535,('nonzero 816 bank write',hex(address))
            value &=255
            if address>=0x8000:
                self.writes.append((self.bank,address,value))
                raise AssertionError(('unexpected flash command',self.writes[-1]))
            old=self.ram[address];self.ram[address]=value
            if address==0x7FEC:
                assert value&0xEE in (0xCC,0xCE,0xEC,0xEE),hex(value)
                self.bank=(1 if value&2 else 0)|(2 if value&0x20 else 0)
            elif address==0x7FE0 and not old&8 and value&8 and self.rx:self.rx.popleft()
            elif address==0x7FE3 and value==255 and self.ram[0x7FE0]&4:self.tx.append(self.ram[0x7FE1])

    class MPU(BaseMPU):
        def __init__(self,memory,pc):
            super().__init__(memory=memory,pc=pc)
            self.pc=pc # py65816 resets via the hardware vector regardless of pc.
            self.native_detector_steps=0
            self.allow_reset_detector=pc==0xF004
        def step(self):
            op=self.memory[self.pc]
            if not is816 and op&15==15: # WDC bit branches, absent from py65.
                zp=self.memory[(self.pc+1)&65535];offset=self.memory[(self.pc+2)&65535]
                bit=(op>>4)&7;test=bool(self.memory[zp]&(1<<bit))
                taken=test if op&128 else not test
                self.pc=(self.pc+3+(offset if offset<128 else offset-256 if taken else 0))&65535 if taken else (self.pc+3)&65535
                return self
            return super().step()

    def run(cpu,predicate,limit=2000000):
        trace=deque(maxlen=24)
        for _ in range(limit):
            if predicate():return
            if cpu.pc==0x7AF8:cpu.pc=(cpu.stPopWord()+1)&65535
            else:
                trace.append((cpu.memory.bank,cpu.pc,cpu.memory[cpu.pc],cpu.sp))
                if is816:
                    # rc1's existing reset detector briefly exchanges E/C.
                    # Permit only its exact instructions; no native application
                    # or debugger execution is admitted by this test runner.
                    if not cpu.mode:
                        assert cpu.allow_reset_detector and cpu.memory.bank==3,list(trace)
                        assert cpu.native_detector_steps<len(detector_native_pcs),list(trace)
                        assert cpu.pc==detector_native_pcs[cpu.native_detector_steps],list(trace)
                        cpu.native_detector_steps+=1
                    assert (cpu.pbr,cpu.dbr,cpu.dpr)==(0,0,0),list(trace)
                try:cpu.step()
                except Exception as exc:
                    raise AssertionError(('CPU exception',list(trace))) from exc
        raise AssertionError(('timeout',hex(cpu.pc),cpu.memory.bank,bytes(cpu.memory.tx[-250:]),
                              bytes(cpu.memory.ram[0x7000:0x7020]).hex()))

    def fixture(slot='A',bank=3):
        m=Memory();page=0xA0 if slot=='A' else 0xB0
        # B0 is deliberately absent from the release. A RAM program may use
        # B0 only if that bank supplies compatible hardware interrupt vectors.
        m.banks[0][-32:]=m.banks[3][-32:]
        for file in ('str8n-v2-worker','str8n-v2-vectors'):
            for address,v in s19(out/'s/core'/f'{file}.s19').items():m.ram[address]=v
        for address,v in s19(out/'s/batch/batch-gate.s19').items():m.ram[address]=v
        m.ram[0x7D00]=3;m.ram[0x7D01]=0x16 if is816 else 2;m.ram[0x7D30]=page
        m.ram[0x7D0C]=255;m.ram[0x7D0A:0x7D0C]=b'\xff\x64'
        m.ram[0xF3]=bank
        cpu=MPU(memory=m,pc=page*256+0x48);cpu.p=0x24;cpu.sp=255
        reset=allsy['core/monitor-'+slot.lower()+'0']['V2_RESET']
        run(cpu,lambda:cpu.pc==reset)
        assert m.ram[0x7E02:0x7E04]==b'\x81\x7B'
        if is816:cpu.b=0xA5
        m[0x7FEC]=(0xCC,0xCE,0xEC,0xEE)[bank]
        return cpu,m

    def stopped(cpu):
        return cpu.pc==sy['DBG_READ_CHAR'] and not cpu.memory.rx

    def command(cpu,line):
        m=cpu.memory;start=len(m.tx);m.rx.extend(line.encode()+b'\r')
        run(cpu,lambda:stopped(cpu))
        result=bytes(m.tx[start:]);transcripts.append(dict(command=line,output=result.decode('ascii')))
        if is816:assert cpu.mode==1 and cpu.b==0xA5,('816 E/hidden B changed',line,cpu.mode,cpu.b)
        return result

    def begin(code,slot='A',bank=3,sp=255):
        cpu,m=fixture(slot,bank)
        m.ram[0x200:0x200+len(code)]=code
        cpu.pc=0x200;cpu.a=0x11;cpu.x=0x22;cpu.y=0x33;cpu.sp=sp;cpu.p=0x2D
        run(cpu,lambda:stopped(cpu))
        return cpu,m

    def passed(text):checks.append(text);print('PASS',text,flush=True)

    def direct(cpu,entry,limit=2000000):
        cpu.sp=255;cpu.stPushWord(0x5FFF);cpu.pc=entry
        run(cpu,lambda:cpu.pc==0x6000,limit)
        if is816:assert cpu.mode==1 and cpu.b==0xA5

    rows={r['opcode']:r for r in json.loads((ROOT/'release/candidates/rc1/source/assembler/opcodes.json').read_text())}
    if is816:
        # Exercise the imported model itself before it becomes our oracle.
        for sp in (0,1,2,0xFE,0xFF):
            for p in (0x24,0x2D,0xED):
                m=Memory();m.banks[3][0x7FFE:]=b'\x00\x50'
                m.ram[0x200:0x202]=b'\x00\x80';m.ram[0x5000]=0x40
                cpu=MPU(memory=m,pc=0x200);cpu.sp=sp;cpu.p=p;cpu.b=0xA5
                cpu.step()
                assert cpu.pc==0x5000 and cpu.sp==(sp-3)&255 and cpu.mode==1
                assert [m.ram[0x100+((sp-i)&255)] for i in range(3)]==[2,2,p|0x30]
                assert not cpu.p&8 and cpu.p&4 and cpu.b==0xA5
                cpu.step()
                assert (cpu.pc,cpu.sp,cpu.p,cpu.b,cpu.mode)==(0x202,sp,p|0x30,0xA5,1)
        for code,length in ((bytes.fromhex('07 10'),2),(bytes.fromhex('0F 00 04 00'),4)):
            m=Memory();m.ram[0x200:0x200+len(code)]=code
            m.ram[0x10:0x13]=bytes.fromhex('00 04 00');m.ram[0x400]=0x42
            cpu=MPU(memory=m,pc=0x200);cpu.a=1;cpu.b=0xA5;cpu.step()
            assert (cpu.pc,cpu.a,cpu.b,cpu.mode)==(0x200+length,0x43,0xA5,1)
        passed('independent 816 model: E=1 BRK/RTI frames, decimal clearing, five stack positions, hidden B and repurposed opcodes')

    for slot in ('A','B'):
        for bank in range(4):
            cpu,m=begin(bytes.fromhex('00 01 E8 00 02 EA 4C 04 02'),slot,bank)
            assert m.ram[0x7000:0x7007]==bytes.fromhex('02 02 11 22 33 3D FF'),m.ram[0x7000:0x7007].hex()
            assert b'PC=0202' in m.tx and m.bank==1
            result=command(cpu,'S')
            assert m.ram[0x7000:0x7007]==bytes.fromhex('03 02 11 23 33 3D FF'),m.ram[0x7000:0x7007].hex()
            assert m.ram[0x203]==0
            assert not m.writes
    passed('automatic BRK entry and single ordinary instruction in MON A/B with all four original banks')
    cpu,m=begin(bytes.fromhex('00 01 EA EA 00 02'))
    assert b'0202:' in command(cpu,'D 0202 0205')
    assert b'PC=0202' in command(cpu,'R')
    command(cpu,'M 0202 E8')
    assert m.ram[0x202]==0xE8
    command(cpu,'S');assert m.ram[0x7003]==0x23
    passed('shared monitor D/M returns to DBG and edited code executes')
    for slot in ('A','B'):
        cpu,m=begin(bytes.fromhex('00 01 E8 E0 25 D0 FB 00 02 EA'),slot)
        original=bytes(m.ram[0x200:0x20A])
        command(cpu,'B 0202')
        for x in (0x23,0x24):
            command(cpu,'C')
            assert m.ram[0x7000:0x7002]==b'\x02\x02'
            assert m.ram[0x7003]==x
            assert m.ram[0x7043]==1
            assert bytes(m.ram[0x200:0x20A])==original
        command(cpu,'M 0202 CA')
        assert m.ram[0x202]==0xCA
        command(cpu,'S');assert m.ram[0x7003]==0x23
        command(cpu,'BC 0202');assert not m.ram[0x7043]
    passed('persistent breakpoint rearming on C, original-byte restoration while paused, edit and clear in MON A/B')
    call=bytes.fromhex('00 01 20 10 02 E8 00 02')+bytes(8)+bytes.fromhex('E8 E8 60')
    cpu,m=begin(call)
    for pc,x,sp in ((0x210,0x22,0xFD),(0x211,0x23,0xFD),(0x212,0x24,0xFD),(0x205,0x24,0xFF)):
        command(cpu,'S')
        assert int.from_bytes(m.ram[0x7000:0x7002],'little')==pc
        assert m.ram[0x7003]==x and m.ram[0x7006]==sp
    cpu,m=begin(call);command(cpu,'N')
    assert m.ram[0x7000:0x7002]==b'\x05\x02' and m.ram[0x7003]==0x24 and m.ram[0x7006]==255
    command(cpu,'N');assert m.ram[0x7000:0x7002]==b'\x06\x02' and m.ram[0x7003]==0x25
    cpu,m=begin(call);command(cpu,'B 0211');command(cpu,'N')
    assert m.ram[0x7000:0x7002]==b'\x11\x02' and m.ram[0x7006]==0xFD
    command(cpu,'C');assert m.ram[0x7000:0x7002]==b'\x08\x02' and m.ram[0x7003]==0x25
    passed('S enters and returns from RAM calls; N steps over; persistent breakpoint inside N takes precedence')
    cpu,m=begin(bytes.fromhex('00 01 80 FE'))
    command(cpu,'S');assert m.ram[0x7000:0x7002]==b'\x02\x02'
    command(cpu,'B 0202');command(cpu,'C');assert m.ram[0x7000:0x7002]==b'\x02\x02'
    cpu,m=begin(bytes.fromhex('00 01 A5 10 00 02'))
    command(cpu,'M 0010 7F');assert m.ram[0x7210]==0x7F
    assert b'0010: 7F' in command(cpu,'D 0010')
    command(cpu,'S');assert m.ram[0x7002]==0x7F
    passed('self-loop stepping and persistent self-loop breakpoints; logical application zero-page D/M')
    for sp in (0,1,2,0xFE,0xFF):
        cpu,m=begin(call,sp=sp)
        command(cpu,'S');assert m.ram[0x7006]==(sp-2)&255
        command(cpu,'S');command(cpu,'S');command(cpu,'S')
        assert m.ram[0x7006]==sp and m.ram[0x7000:0x7002]==b'\x05\x02'
    passed('BRK capture, S JSR/RTS and application page-one stack wrapping')
    recursive=bytes.fromhex('00 01 20 10 02 EA 00 02')+bytes(8)+bytes.fromhex('CA F0 03 20 10 02 60')
    cpu,m=begin(recursive);command(cpu,'R X=03')
    command(cpu,'S');command(cpu,'S');command(cpu,'S')
    assert m.ram[0x7000:0x7002]==b'\x13\x02'
    command(cpu,'N')
    assert m.ram[0x7000:0x7002]==b'\x16\x02' and m.ram[0x7006]==0xFD and m.ram[0x7003]==0
    passed('N ignores recursive return-site hits until the original stack depth returns')
    cpu,m=begin(bytes.fromhex('00 01 20 6D 7E EA 00 02'))
    before=bytes(m.ram[0x7000:0x7007]);assert b'?' in command(cpu,'S')
    assert bytes(m.ram[0x7000:0x7007])==before
    command(cpu,'R A=41');assert b'A' in command(cpu,'N')
    assert m.ram[0x7000:0x7002]==b'\x05\x02' and m.ram[0x7006]==255
    passed('S refuses a firmware call without changing saved state; N executes the RAM console ABI call')
    cpu,m=begin(bytes.fromhex('00 01 EA 00 02'))
    for address in range(0x1000,0x1008):command(cpu,f'B {address:04X}')
    assert sum(bool(m.ram[0x7043+4*i]) for i in range(8))==8
    assert b'?' in command(cpu,'B 1008')
    command(cpu,'BC *');assert all(m.ram[0x7043+4*i]==0 for i in range(8))
    before=bytes(m.ram[0x6400:0x6500]);assert b'Protected' in command(cpu,'M 64FF 11 22')
    assert bytes(m.ram[0x6400:0x6500])==before
    assert b'Protected' in command(cpu,'D 7F00')
    assert b'?' in command(cpu,'S JUNK')
    assert b'?' in command(cpu,'C JUNK')
    assert b'?' in command(cpu,'M 0202 '+('11 '*30))
    assert m.ram[0x202]==0xEA
    command(cpu,'R PC=7F00');assert b'?' in command(cpu,'S')
    command(cpu,'R PC=0202')
    m.ram[0x64FE:0x6500]=b'\xAD\x12';m.reads.clear()
    result=command(cpu,'U 64FE 01')
    assert b'.BYTE $AD' in result and not m.reads,(result,m.reads)
    for opcode in (0xCB,0xDB,0x02):
        m.ram[0x202]=opcode;before=bytes(m.ram[0x7000:0x7007])
        assert b'?' in command(cpu,'S')
        assert bytes(m.ram[0x7000:0x7007])==before
    passed('eight-slot limit, clearing, atomic edit rejection, I/O refusal, malformed input and bounded disassembly/stepping')
    for slot in ('A','B'):
        cpu,m=begin(bytes.fromhex('00 01 E8 4C 67 7E'),slot)
        command(cpu,'B 0202')
        m.rx.extend(b'C\r')
        reenter=allsy['core/monitor-'+slot.lower()+'0']['V2_REENTER']
        run(cpu,lambda:cpu.pc==reenter,10000000)
        assert not m.ram[0x7BFC] and not m.ram[0x7BFD] and m.ram[0x202]==0xE8
        cpu,m=begin(bytes.fromhex('00 01 EA'),slot);command(cpu,'B 0202')
        m.rx.extend(b'X\r');run(cpu,lambda:cpu.pc==reenter,10000000)
        assert not m.ram[0x7BFC] and m.ram[0x202]==0xEA
    passed('normal application HOLD and X clean up patches/registrations before MON A/B reentry')
    w=allsy['core/str8n-v2-worker']
    for entry,physical,selected,carry in ((w['V2W_MUTATE'],3,1,True),
                                        (w['V2W_BYTE'],1,3,False),
                                        (w['V2W_ERASE_RAW'],1,3,False)):
        cpu,m=fixture(bank=physical);m.ram[0xF3]=selected;m.ram[0xEE]=0xA0
        m.ram[0xE4:0xE6]=b'\x12\xA0';m.ram[0xF0]=0x55
        m.ram[0x6800:0x7800]=b'\x96'*4096
        direct(cpu,entry)
        assert not m.writes and m.ram[0xF6]==3 and bool(cpu.p&1)==carry
        assert m.ram[0x6800:0x7800]==b'\x96'*4096
    cpu,m=fixture();m.ram[0x400:0x417]=bytes([1,0,0xA0,0,2,1,2])+b'TEST'.ljust(16,b'\0')
    m.ram[0x6800:0x7800]=b'\x96'*4096;cpu.a=0;cpu.x=4
    direct(cpu,0xE811)
    assert not cpu.p&1 and cpu.a==1 and not m.writes
    assert m.ram[0x6800:0x7800]==b'\x96'*4096
    passed('S/R/T and all resident flash write/erase paths refuse B1:A000-AFFF before mutation, preserving staging')
    # Execute the new ASM BRK syntax through the actual two-pass assembler.
    asm=allsy['assembler/asm-app']
    for lines,wanted,error in ((['ORG $0200','BRK $12','BRK','BRK #$FE','END'],bytes.fromhex('00 12 00 00 00 FE'),0),
                               (['BRK $100'],None,5)):
        cpu,m=fixture(bank=1);packed=bytearray()
        for n,line in enumerate(lines,1):packed+=n.to_bytes(2,'little')+bytes([len(line),0])+line.encode()
        m.ram[0x3300:0x3300+len(packed)]=packed
        m.ram[asm['SRC_END']:asm['SRC_END']+2]=(0x3300+len(packed)).to_bytes(2,'little')
        direct(cpu,asm['ASM_ASSEMBLE'],10000000)
        assert m.ram[asm['ERROR']]==error,(m.ram[asm['ERROR']],error)
        if wanted is not None:assert m.ram[0x200:0x200+len(wanted)]==wanted
    assert asm['OUTPUT_END']==0x3300 and asm['SOURCE_END']==0x4F00 and asm['SYMBOL_END']==0x6300 and asm['STATE_END']==0x6500
    passed('actual ASM BRK operands, bare BRK, immediate spelling and out-of-range signature; all ASM RAM buffers unchanged')
    # Registration/function dispatch executes actual BRK and user RTS paths.
    cpu,m=fixture();m.ram[0x400:0x404]=bytes.fromhex('C1 00 05 00')
    m.ram[0x500:0x506]=bytes.fromhex('A9 42 8D 02 70 60')
    program=bytes.fromhex('A9 00 A2 04 00 81 00 C1 00 01')
    m.ram[0x200:0x200+len(program)]=program;cpu.pc=0x200;cpu.sp=255
    run(cpu,lambda:stopped(cpu));assert m.ram[0x7002]==0x42
    assert m.ram[0x7C40:0x7C44]==bytes.fromhex('C1 00 05 00')
    assert b'C1 0500' in command(cpu,'F')
    cpu,m=fixture(bank=1);m.ram[0x400:0x404]=bytes.fromhex('A1 00 05 00')
    m.ram[0x500:0x506]=bytes.fromhex('A9 66 8D 02 70 60');cpu.a=0;cpu.x=4
    direct(cpu,sy['DBG_SYSTEM_REGISTER']);assert cpu.p&1 and cpu.a==0
    m.ram[0x200:0x204]=bytes.fromhex('00 A1 00 01');cpu.pc=0x200
    run(cpu,lambda:stopped(cpu));assert m.ram[0x7002]==0x66
    passed('separate user/system registration tables and RTS callback result through saved context')
    for signature in (0x80,0x81,0x83,0x84):
        cpu,m=fixture();m.ram[0x400:0x404]=bytes.fromhex('80 00 05 00')
        m.ram[0x200:0x209]=bytes([0xA9,0,0xA2,4,0xA0,4,0,signature,0xEA])
        m.ram[0x209:0x20B]=b'\x00\x01';cpu.pc=0x200;cpu.p=0x25
        run(cpu,lambda:stopped(cpu))
        if signature==0x80:assert m.ram[0x7002:0x7005]==bytes([1,16,4])
        if signature==0x81:assert m.ram[0x7002]==1 and not m.ram[0x7005]&1
        if signature in (0x83,0x84):assert m.ram[0x7002:0x7005]==bytes([0,4,4])
    passed('BRK query, protected system signature rejection and register-preserving trace services')
    for step in ('S','N'):
        cpu,m=begin(bytes.fromhex('00 01 00 80 EA 00 02'))
        command(cpu,step)
        assert m.ram[0x7000:0x7002]==b'\x04\x02' and m.ram[0x7002:0x7005]==bytes([1,16,4])
    passed('S and N over a BRK service stop immediately after that service returns')
    cpu,m=fixture();program=bytearray()
    for i in range(17):
        address=0x400+4*i
        m.ram[address:address+4]=bytes([0xC0+i,0,5,0])
        program+=bytes([0xA9,address&255,0xA2,address>>8,0,0x81])
    program+=bytes.fromhex('00 01 A9 C3 00 82 00 01')
    m.ram[0x500]=0x60;m.ram[0x200:0x200+len(program)]=program;cpu.pc=0x200
    run(cpu,lambda:stopped(cpu));assert m.ram[0x7002]==1 and not m.ram[0x7005]&1
    assert sum(bool(m.ram[0x7C40+4*i]) for i in range(16))==16
    command(cpu,'C');assert m.ram[0x7002]==0 and m.ram[0x7005]&1
    assert sum(bool(m.ram[0x7C40+4*i]) for i in range(16))==15
    for address,flags in ((0x1FF,0),(0x64FE,0),(0x400,1)):
        cpu,m=fixture();m.ram[address:address+4]=bytes([0xC1,0,5,flags])
        m.ram[0x200:0x208]=bytes([0xA9,address&255,0xA2,address>>8,0,0x81,0,1]);cpu.pc=0x200
        run(cpu,lambda:stopped(cpu));assert m.ram[0x7002]==1 and not m.ram[0x7005]&1
    passed('16 user registration slots, full-table error, unregister, and request/flags bounds')
    cpu,m=fixture();m.ram[0x400:0x404]=bytes.fromhex('C1 00 05 00')
    m.ram[0x500:0x506]=bytes.fromhex('00 83 8D 02 70 60')
    program=bytes.fromhex('A9 00 A2 04 00 81 00 C1 00 01')
    m.ram[0x200:0x200+len(program)]=program;cpu.pc=0x200
    run(cpu,lambda:stopped(cpu));assert m.ram[0x7002]==9
    passed('nested BRK callback refuses reentry without losing the application context')
    # Integration-level branch cases cover all condition flags through S.
    for opcode,mask,taken_when_set in ((0x10,128,False),(0x30,128,True),(0x50,64,False),(0x70,64,True),
                                     (0x90,1,False),(0xB0,1,True),(0xD0,2,False),(0xF0,2,True)):
        for is_set in (False,True):
            cpu,m=begin(bytes([0,1,opcode,2,0xEA,0xEA,0xEA]))
            p=(m.ram[0x7005]&~mask)|(mask if is_set else 0)
            command(cpu,f'R P={p:02X}');command(cpu,'S')
            target=0x206 if is_set==taken_when_set else 0x204
            assert int.from_bytes(m.ram[0x7000:0x7002],'little')==target
    passed('all eight conditional branch tests, taken and not taken, through the integrated S command')
    instruction_cases=0
    if is816:
        # These are RMB/SMB/BBR/BBS on a 65C02, and different 816 opcodes.
        # This debugger shares ASM's common subset; do not invent 65C02 semantics.
        for opcode in range(256):
            if opcode in rows and opcode&7!=7:continue
            cpu,m=begin(bytes([0,1,opcode,0x10,0x02,0]))
            before=bytes(m.ram[0x7000:0x7007])
            for step in ('S','N'):
                assert b'?' in command(cpu,step),(opcode,step)
                assert bytes(m.ram[0x7000:0x7007])==before
            assert f'.BYTE ${opcode:02X}'.encode() in command(cpu,'U 0202 01')
        passed('all 76 opcodes outside the common subset, including 32 repurposed 65C02 bytes, refuse S/N and disassemble as bytes on 816 E=1')
        # Compare the firmware's saved result with one direct CPU-model step.
        # This checks actual resume/capture for ordinary instructions, plus
        # the debugger's emulated transfers against the independent 816 core.
        supported=[op for op in rows if op&7!=7 and op not in (0,0xCB,0xDB)]
        for opcode in sorted(supported):
            cpu,m=begin(bytes([0,1,opcode,0x42,0x04,0xEA]),sp=0xE0)
            for address in (0x42,0x64):m.ram[0x7200+address:0x7202+address]=b'\x00\x05'
            for address in (0x442,0x464,0x475,0x500,0x533):m.ram[address]=0x55
            # A valid return frame for RTS/RTI and pointer for JMP (abs,X).
            m.ram[0x71E1:0x71E5]=bytes.fromhex('3D 10 02 00')
            if opcode==0x60:m.ram[0x71E1:0x71E3]=bytes.fromhex('0F 02')
            if opcode in (0x6C,0x7C):
                pointer=0x442+(0x22 if opcode==0x7C else 0)
                m.ram[pointer:pointer+2]=b'\x10\x02'
            reference=Memory();reference.ram[:]=m.ram
            reference.ram[:256]=m.ram[0x7200:0x7300]
            reference.ram[0x100:0x200]=m.ram[0x7100:0x7200]
            ref=MPU(memory=reference,pc=0x202)
            ref.a,ref.x,ref.y,ref.p,ref.sp=m.ram[0x7002:0x7007];ref.b=0xA5
            ref.step()
            command(cpu,'S')
            actual=(int.from_bytes(m.ram[0x7000:0x7002],'little'),*m.ram[0x7002:0x7005],m.ram[0x7005]&0xCF,m.ram[0x7006])
            expected=(ref.pc,ref.a,ref.x,ref.y,ref.p&0xCF,ref.sp)
            assert actual==expected,(f'{opcode:02X}',rows[opcode],actual,expected)
            assert ref.mode==1 and ref.b==0xA5
            assert m.ram[0x200:0x6500]==reference.ram[0x200:0x6500],f'{opcode:02X} application RAM differs'
            assert m.ram[0x7200:0x72E0]==reference.ram[:0xE0],f'{opcode:02X} application zero page differs'
            # Compare allocated stack bytes. Entry legitimately uses the free
            # bytes below SP for the hardware frame, register saves and SELECT.
            for offset in range(ref.sp+1,256):
                assert m.ram[0x7100+offset]==reference.ram[0x100+offset],(f'{opcode:02X} stack differs',offset)
            instruction_cases+=1
        passed(f'{instruction_cases} common opcodes: integrated S result matches direct 816 E=1 execution, including JMP/JSR/RTS/RTI and decimal ALU')
    lengths=dict(imp=1,acc=1,imm=2,zpg=2,zpx=2,zpy=2,abs=3,abx=3,aby=3,inx=2,iny=2,zpi=2,ind=3,iax=3,rel=2,zpr=3)
    decoder_cases=0
    cpu,m=fixture(bank=1)
    for pc in (0x02FE,0x0300):
        for opcode in range(256):
            low,high=0x80,0xFE
            m.ram[pc:pc+3]=bytes([opcode,low,high])
            m.ram[0x7020:0x7022]=pc.to_bytes(2,'little');start=len(m.tx)
            direct(cpu,sy['DISASM'])
            if opcode not in rows or (is816 and opcode&7==7):length,text=1,f'.BYTE ${opcode:02X}'
            else:
                r=rows[opcode];mode='zpg' if opcode==0 else r['mode'];length=lengths[mode]
                byte=f'${low:02X}';word=f'${high:02X}{low:02X}'
                rel=f'${(pc+length-128)&65535:04X}';rel2=f'${(pc+length-2)&65535:04X}'
                operand=dict(imp='',acc=' A',imm=' #'+byte,zpg=' '+byte,zpx=' '+byte+',X',zpy=' '+byte+',Y',
                             abs=' '+word,abx=' '+word+',X',aby=' '+word+',Y',inx=' ('+byte+',X)',iny=' ('+byte+'),Y',
                             zpi=' ('+byte+')',ind=' ('+word+')',iax=' ('+word+',X)',rel=' '+rel,zpr=' '+byte+','+rel2)[mode]
                text=r['name']+operand
            raw=''.join(f'{v:02X} ' for v in (opcode,low,high)[:length]).ljust(9)
            expected=f'{pc:04X} '+raw+text+'\r\n'
            assert bytes(m.tx[start:]).decode()==expected,(opcode,bytes(m.tx[start:]),expected)
            assert int.from_bytes(m.ram[0x7020:0x7022],'little')==pc+length
            decoder_cases+=1
    passed('linked disassembler: 512 cases cover every opcode byte, all ASM addressing modes and page-boundary targets')
    smoke_cases=0;smoke_suite_hash=None;smoke_images={}
    if a.smoke_package:
        folder=a.smoke_package.resolve();suite_path=folder/'smoke/scenarios.json'
        suite=json.loads(suite_path.read_text());smoke_suite_hash=hashlib.sha256(suite_path.read_bytes()).hexdigest()
        spec=importlib.util.spec_from_file_location('debugger_smoke_checks',folder/'smoke_checks.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for slot in ('A','B'):
            for test in suite['tests']:
                cpu,m=fixture(slot,3);path=folder/test['image'];cells=s19(path)
                smoke_images[test['image']]=hashlib.sha256(path.read_bytes()).hexdigest()
                assert path.read_text().splitlines()[-1]=='S9030200FA'
                assert min(cells)==0x200 and max(cells)<0x6500
                for address,value in cells.items():m.ram[address]=value
                for step in test['steps']:
                    start=len(m.tx)
                    if step['command'].startswith('G '):
                        cpu.pc=test['entry'];run(cpu,lambda:stopped(cpu));result=bytes(m.tx[start:])
                    elif step['prompt']=='MON':
                        m.rx.extend(step['command'].encode()+b'\r')
                        run(cpu,lambda:cpu.pc==allsy['core/monitor-'+slot.lower()+'0']['V2_REENTER'])
                        result=bytes(m.tx[start:])
                        assert not m.ram[0x7BFC] and not m.ram[0x7BFD]
                        assert all(m.ram[address]==value for address,value in cells.items()),'Patches left in smoke program'
                    else:result=command(cpu,step['command'])
                    module.check(step,result)
                    transcripts.append(dict(smoke=test['name'],slot=slot,command=step['command'],output=result.decode('ascii')))
                    if is816:assert cpu.mode==1 and cpu.b==0xA5
                assert not m.writes
                smoke_cases+=1
        passed('exact packaged board smoke in MON A/B: BRK, shared D/M/U, C/S/N, all eight persistent breakpoints twice, ninth refusal, clears, X and query')
    manual_cases=0;manual_sources={};manual_images={}
    if a.manuals:
        examples={}
        for name in ('ASM_GUIDE.md','ABI_REFERENCE.md'):
            path=a.manuals/name;body=path.read_text(encoding='utf-8')
            manual_sources[name]=hashlib.sha256(path.read_bytes()).hexdigest()
            for label,block in re.findall(r'<!-- debugger-example: ([\w-]+) -->\s*```asm\n(.*?)```',body,re.S):
                assert label not in examples,label
                examples[label]=block.strip().splitlines()
        assert set(examples)=={'steps','eight-breakpoints','user-registration','system-registration'}
        def leave_manual(cpu,m,slot):
            m.rx.extend(b'C\r');reenter=allsy['core/monitor-'+slot.lower()+'0']['V2_REENTER']
            run(cpu,lambda:cpu.pc==reenter,10000000)
            assert not m.ram[0x7BFC] and not m.ram[0x7BFD] and not m.ram[0x7BFF]
            assert not m.writes
        for slot in ('A','B'):
            for label,lines in examples.items():
                cpu,m=fixture(slot,1);packed=bytearray()
                for line in lines:
                    number,text=line.split(maxsplit=1);encoded=text.encode('ascii')
                    packed+=int(number).to_bytes(2,'little')+bytes([len(encoded),0])+encoded
                m.ram[0x3300:0x3300+len(packed)]=packed
                m.ram[asm['SRC_END']:asm['SRC_END']+2]=(0x3300+len(packed)).to_bytes(2,'little')
                direct(cpu,asm['ASM_ASSEMBLE'],10000000)
                assert not m.ram[asm['ERROR']],(label,m.ram[asm['ERROR']])
                size=int.from_bytes(m.ram[asm['RESULT_LEN']:asm['RESULT_LEN']+2],'little')
                emitted=bytes(m.ram[0x200:0x200+size]);assert size
                manual_images[label]=dict(bytes=size,sha256=hashlib.sha256(emitted).hexdigest())
                cpu.pc=0x200;cpu.sp=255;cpu.p=0x24
                run(cpu,lambda:stopped(cpu))
                transcripts.append(dict(manual=label,slot=slot,assembled_hex=emitted.hex(),output=bytes(m.tx).decode('ascii')))
                if label=='steps':
                    y=m.ram[0x7004]
                    for cmd,pc,x,sp in (('S',0x207,1,255),('S',0x213,1,253),('S',0x214,2,253),('S',0x20A,2,255),('N',0x20B,2,255),('N',0x20E,3,255),('C',0x210,3,255)):
                        command(cpu,cmd)
                        assert (int.from_bytes(m.ram[0x7000:0x7002],'little'),m.ram[0x7003],m.ram[0x7006])==(pc,x,sp)
                    assert m.ram[0x7004]==(y+1)&255
                elif label=='eight-breakpoints':
                    for address in range(0x209,0x211):command(cpu,f'B {address:04X}')
                    assert b'?' in command(cpu,'B 0600')
                    for hit in range(16):
                        command(cpu,'C')
                        assert (int.from_bytes(m.ram[0x7000:0x7002],'little'),m.ram[0x7003],m.ram[0x7004])==(0x209+hit%8,hit,hit//8)
                        assert m.ram[0x209:0x211]==b'\xE8'*8
                    command(cpu,'C');assert m.ram[0x7000:0x7002]==b'\x18\x02' and m.ram[0x7003:0x7005]==b'\x10\x02'
                    command(cpu,'BC 020C');assert b'020C' not in command(cpu,'B');command(cpu,'BC *')
                elif label=='user-registration':
                    assert m.ram[0x7002]==0x42 and b'C1 ' in command(cpu,'F')
                    command(cpu,'C');assert m.ram[0x7002]==0 and m.ram[0x7005]&1 and b'C1 ' not in command(cpu,'F')
                else:
                    assert m.ram[0x7002]==0x66 and m.ram[0x7C30]==0xA1 and b'A1 ' in command(cpu,'F')
                leave_manual(cpu,m,slot);manual_cases+=1
        passed('exact manual ASM examples assembled/executed in MON A/B: C/S/N, eight breakpoints, user register/unregister and system pointer registration')
    # Complete boot from the candidate image, including provider/status paths.
    for slot in (() if a.skip_boot else ('A','B')):
        m=Memory();m.ram[0x200:0x6700]=b'\x96'*(0x6700-0x200)
        if slot=='B':m.banks[3][0x201F]=255
        flash_before=[bytes(b) for b in m.banks]
        cpu=MPU(memory=m,pc=0xF004);cpu.p=0x24
        mon=allsy['core/monitor-'+slot.lower()+'0']
        run(cpu,lambda:cpu.pc==mon['V2_LINE_BYTE'] and m.tx.endswith(b'B3> '),20000000)
        assert m.ram[0x7D01]==(0x16 if is816 else 2)
        if is816:
            assert cpu.mode==1 and cpu.native_detector_steps==len(detector_native_pcs)
            cpu.allow_reset_detector=False;cpu.b=0xA5
        assert m.ram[0x7D30]==(0xA0 if slot=='A' else 0xB0)
        assert m.ram[0x7E02:0x7E04]==b'\x81\x7B'
        assert m.ram[0x7D0A:0x7D0C]==b'\xFF\x66'
        assert m.ram[0x200:0x6700]==b'\x96'*(0x6700-0x200)
        m.ram[0x200:0x204]=b'\x00\x01\xEA\xEA'
        m.rx.extend(b'G 0200\r');run(cpu,lambda:stopped(cpu),10000000)
        assert m.ram[0x7000:0x7002]==b'\x02\x02'
        assert [bytes(b) for b in m.banks]==flash_before and not m.writes
        if is816:assert cpu.mode==1 and cpu.b==0xA5
        boot_results.append(dict(slot=slot,cpu_id=m.ram[0x7D01],reset_detector_native_steps=cpu.native_detector_steps))
    if not a.skip_boot:passed('full candidate boot selects MON A/B, preserves all application RAM, and G launches automatic BRK debugging without enable commands')
    component=(out/'payload/debugger-a000.bin').read_bytes()
    assert len(component)==4096 and binascii.crc_hqx(component,65535)==0
    assert report['debugger_code_bytes']<=4094
    suffix=('-65c816-e' if is816 else '')+('-subset' if a.skip_boot else '')+('-manuals' if a.manuals else '')
    (out/f'debugger-test{suffix}.json').write_text(json.dumps(dict(passed=True,checks=checks,check_groups=len(checks),decoder_cases=decoder_cases,
      direct_instruction_comparison_cases=instruction_cases,
      board_smoke_cases=smoke_cases,smoke_suite_sha256=smoke_suite_hash,smoke_images_sha256=smoke_images,
      manual_example_cases=manual_cases,manual_sources_sha256=manual_sources,manual_images=manual_images,
      board_access=False,full_boot_tested=not a.skip_boot,native_816_tested=False,
      test_harness_sha256=harness_hash,
      processor_model='py65816 65C816 E=1' if is816 else 'py65 65C02',model_sha256=model_hash,
      model_commit=COMMIT if is816 else None,model_source=SOURCE if is816 else None,
      emulation_816_tested=is816,reset_cpu_detector_exception=is816 and not a.skip_boot,
      boots=boot_results,
      B0_test_precondition='matching STR8-N hardware vectors supplied in the fixture; B0 is absent from candidate image',
      instruction_timing_tested=False,flash_write_attempts=0,
      firmware_sha256=hashlib.sha256(image).hexdigest()),indent=2)+'\n')
    (out/f'debugger-transcripts{suffix}.json').write_text(json.dumps(transcripts,indent=2)+'\n')


if __name__=='__main__':main()
