"""Offline debugger board-package planning and actual RAM installer rehearsal.

Runs the packaged transport against CPU/flash endpoints; no serial import or
port access. Flash busy timing and FNV range loops are accelerated. Before that
shortcut, the linked FNV instructions are compared with Python on each CPU.
"""
import argparse
import ast
from contextlib import contextmanager
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--build',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();pkg=args.package.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(pkg));sys.path.insert(0,str(pkg/'engine'))
    import board_plan as p
    import install_transport as engine
    import legacy_transport as wire
    import runtime as r
    manifest=p.package(pkg);checks=[]
    def passed(name,**extra):checks.append(dict(name=name,passed=True,**extra));print('PASS',name,flush=True)
    def capture(path,banks):
        path.mkdir();files={}
        for n,body in enumerate(banks):
            for suffix in ('','-repeat'):
                name=f'b{n}{suffix}.bin';(path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
        body=bytes(i%251 for i in range(0x6500));(path/'application-ram.bin').write_bytes(body)
        (path/'restore-application-ram.s19').write_bytes(wire.s19(dict(enumerate(body,0x200)),0x200))
        for name in ('application-ram.bin','restore-application-ram.s19'):
            body=(path/name).read_bytes();files[name]=dict(bytes=len(body),sha256=r.sha(body))
        p.save(path/'capture.json',dict(schema=1,board='OFFLINE-ONLY',usb_serial='SIMULATED',repeat_verified=True,files=files))
    def refuse(name,action):
        try:action()
        except (ValueError,AssertionError):passed(name)
        else:raise AssertionError('Accepted '+name)

    # Deterministic rc1 fixture, with nonzero wear and owner data outside targets.
    image=(args.build/'firmware.bin').read_bytes()
    banks=[bytearray(b'\xff'*32768)]+[bytearray(image[i:i+32768]) for i in range(0,len(image),32768)]
    for row in manifest['sectors']:
        off=row['address']-0x8000;banks[row['bank']][off:off+4096]=(pkg/row['baseline']).read_bytes()
    banks[0][123]=0x42;banks[1][0x1100:0x1108]=b'PRESERVE'
    _,_,record,_=r.latest(banks);cfg=r.preference(record[8:24],0xA0,49)
    banks[3][0x4000:0x6000]=b'\xff'*8192;banks[3][0x4000:0x4080]=r.record(cfg,list(range(100,132)),1000)
    original=list(map(bytes,banks));capture(out/'before',original)
    install=p.prepare(pkg,out/'before',out/'install','install');p.verify(pkg,out/'install')
    passed('fresh repeated capture creates exact declared-sector install, preserves other sectors/data/settings and counts erases')
    target=[(out/'install'/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    current=list(map(bytearray,target));seq,_,latest,_=r.latest(current)
    cfg=bytearray(r.preference(latest[8:24],0xB0,50));cfg[6]^=1;cfg[14:]=wire.config_sum(cfg)
    counts=[int.from_bytes(latest[24+3*i:27+3*i],'little') for i in range(32)]
    current[3][0x4080:0x4100]=r.record(cfg,counts,seq+1);current[1][0x1100]=0x23
    capture(out/'after',list(map(bytes,current)))
    rollback=p.prepare(pkg,out/'after',out/'rollback','rollback',out/'install');p.verify(pkg,out/'rollback')
    restored=[(out/'rollback'/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    seq2,_,last,_=r.latest(restored)
    assert seq2>seq and last[8:15]==cfg[:7] and last[15:21]==b'P\xA0'+(49).to_bytes(4,'little')
    assert restored[1][0x1100]==0x23 and restored[1][0x2000:0x3000]==b'\xff'*4096
    assert all(v>=old for v,old in zip(rollback['transaction']['reserved_counts'],install['transaction']['reserved_counts']))
    passed('fresh-capture rollback restores original firmware/preference while retaining newer settings/data and advancing wear')
    bad=list(map(bytearray,original));bad[1][0x2000]=0;capture(out/'occupied',bad)
    refuse('occupied debugger destination refused',lambda:p.prepare(pkg,out/'occupied',out/'must-not-exist','install'))
    bad=list(map(bytearray,original));bad[3][0x7000]^=1;capture(out/'wrong-firmware',bad)
    refuse('unrecognized resident F refused',lambda:p.prepare(pkg,out/'wrong-firmware',out/'must-not-exist','install'))
    path=out/'install/transfer-02.bin';before=path.read_bytes();path.write_bytes(bytes([before[0]^1])+before[1:])
    refuse('changed transfer refused before any port',lambda:p.verify(pkg,out/'install'));path.write_bytes(before)
    path=out/'install/installer-model-only.s19';before=path.read_bytes()
    cells,entry=wire.read_s19(path);cells[0x2000]^=1;path.write_bytes(wire.s19(cells,entry))
    saved=r.read(out/'install/plan.json');changed=dict(saved,installer_sha256=r.sha(path.read_bytes()));p.save(out/'install/plan.json',changed)
    refuse('edited installer refused even with its saved SHA updated',lambda:p.verify(pkg,out/'install'))
    path.write_bytes(before);p.save(out/'install/plan.json',saved)
    import board_link
    command=argparse.Namespace(operation='execute',plan=out/'install',board='OFFLINE-ONLY',usb_serial='SIMULATED',experimental=False)
    refuse('execute without experimental flag refuses before serial import',lambda:board_link.run(command))

    # Exercise the explicit-port orchestration against RAM endpoints and the
    # real CPU-model smoke transcripts. No serial module is imported.
    transcript=r.read(args.build/'debugger-transcripts-65c816-e.json')
    replies=[row for row in transcript if row.get('smoke') and row['slot']=='A']
    class RAMEendpoint:
        def __init__(self,ram_end=0x66FF,fault=False):
            self.ram=bytearray(32768);self.ram[0x7D0A:0x7D0C]=ram_end.to_bytes(2,'little')
            self.loaded=0;self.row=0;self.fault=fault;self.entry=0x200
        def dump(self,first,last,prompt=b'\r\nB3> '):return bytes(self.ram[first:last+1])
        def send(self,data):
            raw=bytes.fromhex(data.strip()[2:].decode());address=int.from_bytes(raw[1:3],'big')
            if data.startswith(b'S1'):
                self.ram[address:address+len(raw[3:-1])]=raw[3:-1];self.loaded+=len(raw[3:-1])
            elif data.startswith(b'S9'):self.entry=address
        def until(self,token,seconds=45):return f'Entry {self.entry:04X}\r\nB3> '.encode()
        def command(self,text,prompt=b'\r\nB3> '):
            if text=='':return prompt
            if text=='VERSION':return b'STR8-N 2.0rc1 65C02 Board: OFFLINE-ONLY\r\nMONITOR A gen 00000032 VALID\r\nMONITOR B gen 00000032 VALID\r\nB3> '
            if text=='L':return b'S19'
            row=replies[self.row];self.row+=1;assert row['command']==text
            if text=='X' and self.fault:self.ram[0x200]^=1
            return row['output'].encode()
    def orchestrate(operation,name,endpoint):
        output=out/name
        @contextmanager
        def connect(args,where):where.mkdir();yield endpoint
        ns=argparse.Namespace(operation=operation,plan=None,board='OFFLINE-ONLY',usb_serial='SIMULATED',
                              archive=out/'before',out=output,expected_generation=50)
        with patch.object(board_link,'connection',connect),patch.object(board_link.time,'sleep',return_value=None):board_link.run(ns)
        return r.read(output/'report.json')
    endpoint=RAMEendpoint();report=orchestrate('smoke','smoke-host',endpoint)
    assert report['passed'] and report['breakpoint_hits_verified']==16 and report['smoke_program_bytes_restored']
    passed('board smoke orchestration checks exact CPU transcripts and post-HOLD/X code readbacks')
    refuse('leftover breakpoint patch rejected by host smoke',lambda:orchestrate('smoke','smoke-host-fault',RAMEendpoint(fault=True)))
    endpoint=RAMEendpoint();report=orchestrate('restore-ram','restore-host',endpoint)
    assert report['RAM_restoration_host_verified'] and endpoint.ram[0x200:0x6700]==(out/'before/application-ram.bin').read_bytes()
    passed('original full application RAM archive is loaded, read back and never executed')
    endpoint=RAMEendpoint(ram_end=0x64FF)
    refuse('RAM restore into an owned 6500-66FF service area refused',lambda:orchestrate('restore-ram','restore-host-refusal',endpoint))
    assert endpoint.loaded==0

    # Reuse the established flash/FT245 model class without importing its board
    # launchers or build-time side effects. Mutations have route-specific checks.
    source=(ROOT/'tools/test_v2_recovery.py').read_text();tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Memory')
    scope={'deque':deque};exec(compile(ast.Module(body=[node],type_ignores=[]),'existing-flash-model','exec'),scope)
    BaseMemory=scope['Memory']
    model_manifest=r.read(ROOT/'tmp/blg4/manifest.json');symbols=model_manifest['symbols']
    assert model_manifest['integrated_sha256']==r.read(pkg/'engine/template/manifest.json')['integrated_sha256']
    sys.path.insert(0,str(ROOT/'BUILD/v1.30/local/test-deps'))
    sys.path.insert(0,str(ROOT/'BUILD/test-deps-816'))
    from py65.devices.mpu65c02 import MPU as CPU02
    from py65816.devices.mpu65c816 import MPU as CPU816
    from fetch_rc1_debugger_816_model import MODEL_SHA256
    assert r.sha(Path(sys.modules[CPU816.__module__].__file__).read_bytes())==MODEL_SHA256

    for is816,base in ((False,CPU02),(True,CPU816)):
        label='816 E=1' if is816 else '65C02'
        class Memory(BaseMemory):
            def __init__(self,initial,info):
                super().__init__(initial);self.ram[0x7FEC]=0xEE;self.info=info;self.id_mode=False
                self.allowed={(op['bank'],op['address']&0xF000) for op in info['transaction']['operations']}
                self.erases=[0]*32
            def __getitem__(self,address):
                assert 0<=address<=0xFFFF
                if self.id_mode and address in (0x8000,0x8001):return 0xBF if address==0x8000 else 0xB5
                return super().__getitem__(address)
            def __setitem__(self,address,value):
                assert 0<=address<=0xFFFF
                if address==0xD555 and value==0x90 and self.unlock==2:self.id_mode=True;self.unlock=0;return
                if self.id_mode and address==0x8000 and value==0xF0:self.id_mode=False;return
                super().__setitem__(address,value)
            def mutated(self,kind,address,value):
                assert (self.bank,address&0xF000) in self.allowed
                if kind=='erase':
                    i=self.bank*8+(address>>12)-8;self.erases[i]+=1
                    _,_,row,_=r.latest(self.banks);count=int.from_bytes(row[24+3*i:27+3*i],'little')
                    assert count>=self.info['transaction']['counts_before'][i]+self.erases[i],'Erase before durable wear reservation'
                self.events.append((kind,self.bank,address,value))
        class CPU(base):
            accelerate=True
            def step(self):
                if is816:assert self.mode==1 and (self.dpr,self.dbr,self.pbr)==(0,0,0)
                if not is816 and self.pc==0x2001 and self.memory[self.pc]==0xFB:self.pc+=1;return self
                if self.accelerate and self.pc==symbols['MIG_HASH_RANGE']:
                    start=int.from_bytes(self.memory.ram[0xE0:0xE2],'little');stop=self.memory.ram[0x620C]
                    value=wire.fnv(bytes(self.memory[a] for a in range(start,(stop<<8) if stop else 0x10000)))
                    self.memory.ram[0x6204:0x6208]=value.to_bytes(4,'little');self.memory.ram[0xE0:0xE2]=bytes([0,stop])
                    self.a,self.x=stop,0;self.p|=self.CARRY|self.ZERO;self.pc=(self.stPopWord()+1)&65535;return self
                return super().step()
        def run(cpu,predicate,limit=20000000):
            for _ in range(limit):
                if predicate():return
                assert cpu.pc<0x8000,'Installer executed flash';cpu.step()
            raise AssertionError(('installer timeout',hex(cpu.pc),bytes(cpu.memory.tx[-200:])))
        def fresh(folder,initial):
            info=r.read(folder/'plan.json');m=Memory(initial,info);cells,entry=wire.read_s19(folder/'installer-model-only.s19')
            for address,value in cells.items():m.ram[address]=value
            cpu=CPU(memory=m,pc=entry);cpu.pc=entry;m.cpu=cpu
            if is816:cpu.b=0xA5
            return cpu,m
        cpu,m=fresh(out/'install',original);sample=bytes(range(256));m.ram[0x6000:0x6100]=sample
        m.ram[0xE0:0xE2]=b'\0\x60';m.ram[0x620C]=0x61
        cpu.pc=symbols['MIG_HASH_RANGE'];cpu.accelerate=False;cpu.stPushWord(0x1FF)
        run(cpu,lambda:cpu.pc==0x200)
        assert int.from_bytes(m.ram[0x6204:0x6208],'little')==wire.fnv(sample)
        passed(label+' linked FNV instruction check before enabling range acceleration')
        for direction,initial in (('install',original),('rollback',list(map(bytes,current)))):
            folder=out/direction;info=r.read(folder/'plan.json');cpu,m=fresh(folder,initial)
            class Endpoint:
                def monitor_load(self,path):assert path==folder/'installer-model-only.s19'
                def send(self,data):m.rx.extend(data)
                def until(self,token,seconds=45):
                    run(cpu,lambda:token in m.tx or cpu.pc==symbols['MIG_HALT'])
                    assert token in m.tx,bytes(m.tx[-200:]);end=m.tx.index(token)+len(token)
                    result=bytes(m.tx[:end]);del m.tx[:end];return result
            with patch.object(engine.time,'sleep',return_value=None):result=engine.execute(Endpoint(),folder)
            run(cpu,lambda:cpu.pc==symbols['MIG_HALT'])
            expected=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
            assert list(map(bytes,m.banks))==expected and result['transfers_completed']==len(manifest['sectors'])+2
            assert [[e[1],e[2]>>12] for e in m.events if e[0]=='erase']==info['transaction']['planned_erase_order']
            if is816:assert cpu.mode==1 and cpu.b==0xA5
            passed(label+' actual packaged transport + RAM '+direction+' reaches exact targets',erase_attempts=sum(m.erases))
        initial=list(map(bytearray,original));initial[0][0]^=1;cpu,m=fresh(out/'install',initial);m.rx.extend(b'Y\r')
        run(cpu,lambda:cpu.pc==symbols['MIG_HALT'])
        assert not m.events and b'REFUSED/FAILED' in m.tx
        passed(label+' stale full-bank source refuses before any flash mutation')
        cpu,m=fresh(out/'install',original);m.rx.extend(b'Y\r')
        first=install['transaction']['operations'][1]
        token=f'SEND 4096 BYTES FOR B{first["bank"]}:{first["address"]>>12:X}\r\n'.encode()
        run(cpu,lambda:token in m.tx or cpu.pc==symbols['MIG_HALT']);assert token in m.tx
        before=len(m.events);body=bytearray((out/'install/transfer-00.bin').read_bytes());body[127]^=1
        m.rx.extend(body);run(cpu,lambda:cpu.pc==symbols['MIG_HALT'])
        assert len(m.events)==before and b'REFUSED/FAILED' in m.tx
        passed(label+' corrupted transfer refused before its sector erase/program')
    p.save(out/'report.json',dict(passed=True,board_access=False,native_debugging=False,checks=checks,
             package_manifest_sha256=r.sha((pkg/'board-test-manifest.json').read_bytes()),
             flash_model_sha256=hashlib.sha256(source.encode()).hexdigest(),
             actual_installer_instructions=True,hash_ranges_accelerated=True,electrical_timing_tested=False))


if __name__=='__main__':main()
