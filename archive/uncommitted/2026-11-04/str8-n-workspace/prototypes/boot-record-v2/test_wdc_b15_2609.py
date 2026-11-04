"""Exact F-only WDC-to-b15 CPU/NOR, transport, interruption and refusal tests.

No serial import or device access. Only repeated FNV calls and UART pacing are
accelerated; the FNV opcodes are separately executed and checked on the CPU.
Every observed flash mutation is checked for preservation of every non-F byte.
"""
import argparse
import copy
import hashlib
import io
import json
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import patch

import wdc_b15_2609 as planning
ROOT,HERE=planning.ROOT,planning.HERE
sys.path[:0]=[str(ROOT/'BUILD/v1.30/local/test-deps'),str(ROOT/'BUILD/test-deps-816'),str(ROOT/'tools')]
from py65816.devices.mpu65c816 import MPU as CPU816
from installer.engine import runtime as r,legacy_transport as wire,install_transport as transport
from installer.flash_model import Memory as BaseMemory
from installer.common import save

class Model:
    def __init__(self,plan,native=True,fault=None,accelerate=True):
        self.plan=Path(plan);self.info=planning.verify(plan);self.tx=self.info['transaction'];self.fault=fault
        self.symbols=r.read(planning.TEMPLATE/'symbols.json')
        self.source=[(self.plan/f'source-b{n}.bin').read_bytes() for n in range(4)]
        self.expected=[(self.plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        self.allowed={(b,a<<12) for b,a in self.tx['planned_erase_order']}
        self.checkpoints=[];self.prefixes=0;self.initialization_prefixes=0;self.durable_prefixes=0
        self.erase_counts=[0]*32;self.record_commits=[];self.guard_entered=False;self.native=native
        model=self
        class Memory(BaseMemory):
            def __init__(self):
                super().__init__(model.source);self.id_mode=False;self.ram[0x7fec]=0xee
                self.last_completed_sector=None;self.drop_commit=False
            def __getitem__(self,address):
                assert 0<=address<=65535,('Unexpected native bank access',hex(address))
                if self.id_mode and address in (0x8000,0x8001):
                    return (0x01 if fault=='wrong-flash' else 0xbf) if address==0x8000 else 0xb5
                return super().__getitem__(address)
            def __setitem__(self,address,value):
                assert 0<=address<=65535
                assert not 0x7fc0<=address<=0x7fcf,'Installer attempted RTC/SPI VIA access'
                if address==0xd555 and value==0x90 and self.unlock==2:self.id_mode=True;self.unlock=0;return
                if self.id_mode and address==0x8000 and value==0xf0:self.id_mode=False;return
                super().__setitem__(address,value)
            def mutated(self,kind,address,value):
                assert (self.bank,address&0xf000) in model.allowed,('Write outside planned B3 sectors',kind,self.bank,hex(address))
                assert self.banks[:3]==list(map(bytearray,model.source[:3])),'B0/B1/B2 changed at a mutation prefix'
                assert self.banks[3][:-4096]==model.source[3][:-4096],'A non-F B3 byte changed at a mutation prefix'
                model.prefixes+=1
                if kind=='erase':
                    model.erase_counts[self.bank*8+(address>>12)-8]+=1
                    model.checkpoints.append(dict(case=f'erase-{address:04X}',banks=list(map(bytes,self.banks))))
                assert not planning.snbt_records(self.banks),'F-only conversion initialized a journal'
                assert model.erase_counts[31]==1 and sum(model.erase_counts)==1
                if fault=='erase-verify' and kind=='erase':self.banks[3][0x7011]=0
                if fault=='program-verify' and kind=='program' and address==0xf000:self.banks[3][0x7000]^=1
                if kind=='program' and address in (0xf000,0xf004,0xf080,0xfffa,0xfffc,0xfffd,0xfffe,0xffff):
                    model.checkpoints.append(dict(case=f'F-program-{address:04X}',banks=list(map(bytes,self.banks))))
                self.events.append((kind,self.bank,address,value))
        class CPU(CPU816):
            def step(self):
                if self.pc==0x2007:model.guard_entered=True
                if model.guard_entered:
                    assert self.mode==1 and (self.dpr,self.dbr,self.pbr)==(0,0,0),'Common worker CPU state not normalized'
                if accelerate and self.pc==model.symbols['MIG_HASH_RANGE']:
                    first=int.from_bytes(self.memory.ram[0xe0:0xe2],'little');stop=self.memory.ram[0x620c]
                    value=wire.fnv(bytes(self.memory[a] for a in range(first,(stop<<8) if stop else 65536)))
                    self.memory.ram[0x6204:0x6208]=value.to_bytes(4,'little');self.memory.ram[0xe0:0xe2]=bytes([0,stop])
                    self.a,self.x=stop,0;self.p|=self.CARRY|self.ZERO;self.pc=(self.stPopWord()+1)&65535;return self
                return super().step()
        self.memory=Memory();cells,entry=wire.read_s19(self.plan/'installer-model-only.s19')
        for a,v in cells.items():self.memory.ram[a]=v
        self.cells,self.entry=cells,entry
        self.cpu=CPU(memory=self.memory,pc=entry);self.memory.cpu=self.cpu
        self.cpu.pc=entry;self.cpu.pbr=0;self.cpu.mode=0 if native else 1
        self.cpu.p=0x08 if native else 0x3c;self.cpu.dpr=0x1234;self.cpu.dbr=0x7d;self.cpu.sp=0x7ef if native else 0xef
        if fault and fault.startswith('stale-'):self.memory.banks[int(fault[-1])][0]^=1
        if fault=='table-corrupt':self.memory.ram[r.read(planning.TEMPLATE/'manifest.json')['banks']]=0
        if fault=='guard-data':self.memory.ram[0x3600]^=1
        if fault=='wrong-flash':pass

    def run(self,predicate,limit=40000000):
        for _ in range(limit):
            if predicate():return
            assert self.cpu.pc<0x8000,'ROM fetch while installer running'
            self.cpu.step()
        raise AssertionError(('CPU limit',hex(self.cpu.pc),bytes(self.memory.tx[-160:])))

    def execute(self):
        model=self
        class Endpoint:
            corruption_done=False;transfers=0
            def stock_load(self,cells,entry):assert cells==model.cells and entry==model.entry==0x3700
            def send(self,body):
                if model.fault=='cancel' and body==b'Y\r':body=b'N\r'
                if model.fault and model.fault.startswith('corrupt-') and len(body)==64:
                    target=int(model.fault.split('-')[1])
                    if self.transfers==target and not self.corruption_done:body=bytes([body[0]^1])+body[1:];self.corruption_done=True
                model.memory.rx.extend(body)
            def until(self,token,seconds=45):
                model.run(lambda:token in model.memory.tx or model.cpu.pc==model.symbols['MIG_HALT'])
                if token not in model.memory.tx:raise ValueError('Device refused: '+bytes(model.memory.tx[-120:]).decode('ascii','replace'))
                if token.startswith(b'SEND 4096'):self.transfers+=1
                end=model.memory.tx.index(token)+len(token);reply=bytes(model.memory.tx[:end]);del model.memory.tx[:end];return reply
        endpoint=Endpoint()
        with patch.object(transport.time,'sleep',return_value=None):
            try:response=transport.execute(endpoint,self.plan,stock=True)
            except ValueError:
                assert self.fault,'Unexpected installer refusal'
                assert b'REFUSED/FAILED' in self.memory.tx
                expected_erasures=0
                if self.fault.startswith('corrupt-'):expected_erasures=int(self.fault.split('-')[1])-1
                elif self.fault in ('erase-verify','program-verify'):expected_erasures=1
                assert sum(self.erase_counts)==expected_erasures,(self.fault,self.erase_counts)
                if not expected_erasures:assert not self.memory.events
                assert bytes(self.memory.banks[0])==self.source[0] or self.fault=='stale-0'
                return dict(passed=True,mode='native' if self.native else 'emulation',fault=self.fault,
                    erase_attempts=sum(self.erase_counts),B0_preserved=True,mutation_prefixes=self.prefixes)
        assert self.fault is None,'Fault accepted'
        self.run(lambda:self.cpu.pc==self.symbols['MIG_HALT'])
        assert list(map(bytes,self.memory.banks))==self.expected
        assert [[b,a>>12] for kind,b,a,v in self.memory.events if kind=='erase']==self.tx['planned_erase_order']
        assert not self.record_commits
        return dict(passed=True,mode='native' if self.native else 'emulation',fault=None,
            transfers=response['transfers_completed'],erases=sum(self.erase_counts),mutation_prefixes=self.prefixes,
            B0_B1_B2_and_nonF_B3_preserved_at_every_prefix=True,CPU_state_normalized=True,
            no_RTC_SPI_VIA_writes=True,exact_all_four_bank_target=True,one_F_sector_only=True)

def check_hash_opcodes(plan):
    h=Model(plan,accelerate=False);c,m=h.cpu,h.memory
    c.mode=1;c.dpr=c.dbr=c.pbr=0;c.p=0x34;c.sp=255
    m.ram[0x6000:0x6100]=bytes(range(256));m.ram[0xe0:0xe2]=b'\0\x60';m.ram[0x620c]=0x61
    c.pc=h.symbols['MIG_HASH_RANGE'];c.stPushWord(0x1ff);h.run(lambda:c.pc==0x200)
    assert int.from_bytes(m.ram[0x6204:0x6208],'little')==wire.fnv(bytes(range(256)))
    return dict(passed=True,case='actual-FNV-opcodes',native_debugging=False)

def check_stock_loader(plan):
    cells,entry=wire.read_s19(Path(plan)/'installer-model-only.s19');first,last=min(cells),max(cells)
    expected=bytes(cells[a] for a in range(first,last+1));checks=[]
    class Endpoint:
        stock_load=wire.Link.stock_load;stock_read=wire.Link.stock_read
        def __init__(self,bad):self.ram=bytearray(0x8000);self.bad=bad;self.go=None
        def protocol(self,command):self.command=command
        def send(self,data):
            if self.command==6:self.go=int.from_bytes(data,'little');return
            address=int.from_bytes(data[:3],'little');count=int.from_bytes(data[3:6],'little')
            assert first<=address and address+count<=last+1 and not address<=0x7ff<address+count
            if self.command==2:self.ram[address:address+count]=data[6:]
            else:
                self.reply=bytearray(self.ram[address:address+count])
                if self.bad:self.reply[0]^=1
        def exact(self,count):return b'\0' if self.command==2 else bytes(self.reply)
    for bad in (False,True):
        endpoint=Endpoint(bad)
        if bad:
            try:endpoint.stock_load(cells,entry)
            except IOError:assert endpoint.go is None
            else:raise AssertionError('Bad RAM readback executed')
        else:
            endpoint.stock_load(cells,entry);assert endpoint.go==entry and endpoint.ram[first:last+1]==expected
        checks.append(dict(passed=True,case='stock-loader-bad-readback-refuses-EXEC' if bad else 'stock-loader-repeated-device-readback-before-EXEC',entry=entry))
    return checks

def host_tampering(plan,out):
    checks=[]
    for name in ('plan.json','installer-model-only.s19','transfer-00.bin','b15-F-4096.bin','expected-b0.bin','source-b3.bin'):
        folder=out/('tamper-'+name.replace('.','-'));shutil.copytree(plan,folder,ignore=shutil.ignore_patterns('proof*','tamper-*'))
        path=folder/name;raw=path.read_bytes()
        if name=='plan.json':
            value=json.loads(raw);value['transaction']['operations'][0]['bank']=0;path.write_text(json.dumps(value))
        else:path.write_bytes(bytes([raw[0]^1])+raw[1:])
        try:planning.verify(folder)
        except (ValueError,AssertionError):pass
        else:raise AssertionError('Tampered '+name+' accepted')
        checks.append(dict(passed=True,case='host-refuses-'+name))
    return checks

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();plan=args.plan.resolve();out=args.out.resolve();assert not out.exists();out.mkdir(parents=True)
    results=[];normal=[]
    def passed(row):
        results.append(row);save(out/'progress.json',dict(passed=True,completed=len(results),checks=results))
        print('PASS',len(results),row.get('case',row.get('mode')),row.get('fault') or '',flush=True)
    passed(check_hash_opcodes(plan))
    for row in check_stock_loader(plan):passed(row)
    for native in (True,False):
        model=Model(plan,native=native);passed(model.execute());normal.append(model)
    faults=['stale-0','stale-1','stale-2','stale-3','table-corrupt','guard-data','wrong-flash','cancel',
            'corrupt-1','erase-verify','program-verify']
    for fault in faults:passed(Model(plan,native=True,fault=fault).execute())
    for row in host_tampering(plan,out):passed(row)
    save(out/'model-proof.json',dict(passed=True,hardware=False,serial_access=False,board_access=False,flashed=False,
        checks=len(results),cases=results,plan_sha256=planning.digest(plan/'plan.json'),
        installer_sha256=planning.digest(plan/'installer-model-only.s19'),test_source_sha256=planning.digest(__file__),
        limits=['CPU/NOR and simulated stock transport only; no electrical power-cut test',
                'No C/D initialization or onboard wear journal write; one F erase is accounted for in host metadata only',
                'Interrupted F programming may require external recovery; every other sector, including B0, remains intact']))
    print('PASS',len(results),'offline checks; no ports opened or board writes',flush=True)

if __name__=='__main__':main()
