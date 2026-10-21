"""Linked RC1 RAM installer model shared by direct and legacy route tests.

Only flash busy timing, transport pacing and hash-range loops are accelerated.
The first FNV call is separately checked with real instructions. Native mode
is never entered, and this is not electrical interruption qualification.
"""
import ast
from collections import deque
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def execute(pkg,plan,initial,*,is816,stock=False,fault=None,private_fixture=False):
    import runtime as r
    import legacy_transport as wire
    import install_transport as transport
    pkg,plan=Path(pkg),Path(plan);info=r.read(plan/'plan.json')
    source=(ROOT/'tools/test_v2_recovery.py').read_text();tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Memory')
    scope={'deque':deque};exec(compile(ast.Module(body=[node],type_ignores=[]),'inherited-flash-model','exec'),scope)
    BaseMemory=scope['Memory'];symbols=r.read(ROOT/'tmp/blg4/manifest.json')['symbols']
    template=pkg/'migration/factory-template' if stock else pkg/'engine/template'
    original=ROOT/'tmp/bwf1/manifest.json' if stock else ROOT/'tmp/blg4/manifest.json'
    assert r.read(original)['integrated_sha256']==r.read(template/'manifest.json')['integrated_sha256']
    sys.path[:0]=[str(ROOT/'BUILD/v1.30/local/test-deps'),str(ROOT/'BUILD/test-deps-816')]
    from py65.devices.mpu65c02 import MPU as CPU02
    from py65816.devices.mpu65c816 import MPU as CPU816
    from fetch_rc1_debugger_816_model import MODEL_SHA256
    assert r.sha(Path(sys.modules[CPU816.__module__].__file__).read_bytes())==MODEL_SHA256
    class Memory(BaseMemory):
        def __init__(self):
            super().__init__(initial);self.ram[0x7fec]=0xee;self.id_mode=False;self.erases=[0]*32;self.reservation_verified=False
            self.allowed={(o['bank'],o['address']&0xf000) for o in info['transaction']['operations']}
        def __getitem__(self,address):
            assert 0<=address<=65535
            if self.id_mode and address in (0x8000,0x8001):return 0xbf if address==0x8000 else 0xb5
            return super().__getitem__(address)
        def __setitem__(self,address,value):
            assert 0<=address<=65535
            if address==0xd555 and value==0x90 and self.unlock==2:self.id_mode=True;self.unlock=0;return
            if self.id_mode and address==0x8000 and value==0xf0:self.id_mode=False;return
            super().__setitem__(address,value)
        def mutated(self,kind,address,value):
            assert (self.bank,address&0xf000) in self.allowed
            if kind=='erase':self.erases[self.bank*8+(address>>12)-8]+=1
            try:_,_,row,_=r.latest(self.banks)
            except ValueError:
                # Factory conversion has no old wear journal. Only its first
                # declared journal initialization may precede a valid row.
                if private_fixture:
                    assert info['private_vendor_payload'] and self.reservation_verified and self.bank==3
                    assert address>>12 in (info['transaction']['retained_journal_sector'],15)
                else:
                    assert stock and self.erases==[0]*29+[1,0,0]
                    assert self.bank==3 and 0xd000<=address<=0xdfff
            else:
                if int.from_bytes(row[4:8],'little')>=info['transaction']['sequence_before']+1:self.reservation_verified=True
                for i,n in enumerate(self.erases):
                    assert int.from_bytes(row[24+3*i:27+3*i],'little')>=info['transaction']['counts_before'][i]+n
            self.events.append((kind,self.bank,address,value))
    class CPU(CPU816 if is816 else CPU02):
        accelerate=True
        def step(self):
            if is816:assert self.mode==1 and (self.dpr,self.dbr,self.pbr)==(0,0,0)
            if not is816 and self.pc==0x2001 and self.memory[self.pc]==0xfb:self.pc+=1;return self
            if self.accelerate and self.pc==symbols['MIG_HASH_RANGE']:
                first=int.from_bytes(self.memory.ram[0xe0:0xe2],'little');stop=self.memory.ram[0x620c]
                value=wire.fnv(bytes(self.memory[x] for x in range(first,(stop<<8) if stop else 65536)))
                self.memory.ram[0x6204:0x6208]=value.to_bytes(4,'little');self.memory.ram[0xe0:0xe2]=bytes([0,stop])
                self.a,self.x=stop,0;self.p|=self.CARRY|self.ZERO;self.pc=(self.stPopWord()+1)&65535;return self
            return super().step()
    def run(cpu,predicate,limit=40000000):
        for _ in range(limit):
            if predicate():return
            assert cpu.pc<0x8000;cpu.step()
        raise AssertionError(('timeout',hex(cpu.pc),bytes(cpu.memory.tx[-180:])))
    memory=Memory();cells,entry=wire.read_s19(plan/'installer-model-only.s19')
    for address,value in cells.items():memory.ram[address]=value
    cpu=CPU(memory=memory,pc=entry);cpu.pc=entry;memory.cpu=cpu
    if is816:cpu.b=0xa5
    # Actual FNV opcodes, on both CPUs, before using the acceleration.
    memory.ram[0x6000:0x6100]=bytes(range(256));memory.ram[0xe0:0xe2]=b'\0\x60';memory.ram[0x620c]=0x61
    cpu.pc=symbols['MIG_HASH_RANGE'];cpu.accelerate=False;cpu.stPushWord(0x1ff)
    run(cpu,lambda:cpu.pc==0x200);assert int.from_bytes(memory.ram[0x6204:0x6208],'little')==wire.fnv(bytes(range(256)))
    cpu.pc=entry;cpu.accelerate=True
    if fault=='stale':memory.banks[0][0]^=1
    operations=info['transaction']['operations'] if stock else info['transaction']['operations'][1:]
    class Endpoint:
        def monitor_load(self,path):assert path==plan/'installer-model-only.s19'
        def stock_load(self,body,start):assert body==cells and start==entry
        def send(self,data):
            if fault=='corrupt' and len(data)==64 and not getattr(self,'corrupted',False):
                data=bytes([data[0]^1])+data[1:];self.corrupted=True
            memory.rx.extend(data)
        def until(self,token,seconds=45):
            run(cpu,lambda:token in memory.tx or cpu.pc==symbols['MIG_HALT'])
            if token not in memory.tx:raise ValueError('device refused: '+bytes(memory.tx[-160:]).decode('ascii','replace'))
            end=memory.tx.index(token)+len(token);reply=bytes(memory.tx[:end]);del memory.tx[:end];return reply
    with patch.object(transport.time,'sleep',return_value=None):
        if fault:
            try:transport.execute(Endpoint(),plan,stock=stock)
            except ValueError:
                assert b'REFUSED/FAILED' in memory.tx
                if fault=='stale' or stock:assert not memory.events
                return dict(passed=True,fault=fault,mutation_events=len(memory.events),native_debugging=False)
            raise AssertionError('Fault was accepted')
        result=transport.execute(Endpoint(),plan,stock=stock)
    run(cpu,lambda:cpu.pc==symbols['MIG_HALT'])
    expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    assert list(map(bytes,memory.banks))==expected
    assert [[e[1],e[2]>>12] for e in memory.events if e[0]=='erase']==info['transaction']['planned_erase_order']
    assert expected[0]==bytes(initial[0])
    return dict(passed=True,transfers=result['transfers_completed'],erases=sum(memory.erases),mutation_events=len(memory.events),
                CPU='65C816 E=1' if is816 else '65C02',native_debugging=False,linked_FNV_checked=True,exact_all_four_bank_target=True)
