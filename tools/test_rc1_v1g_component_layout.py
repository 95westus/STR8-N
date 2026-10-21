"""Model exact v1g component removal/dependencies. Never opens board ports.

These are altered model flash fixtures, not hardware erase or uninstall proofs.
No native application/debugging or RTC drift qualification is performed.
"""
import argparse
from collections import deque
import binascii
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
IMAGE='6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();assert a.out.resolve().is_relative_to(ROOT/'output/qualification') and not a.out.exists()
    sys.path[:0]=[str(ROOT/'BUILD/v1.30/local/test-deps'),str(ROOT/'BUILD/test-deps-816'),str(ROOT/'tools')]
    import serial
    def forbidden(*args,**kw):raise AssertionError('Hardware/network forbidden in component models')
    serial.Serial=forbidden;socket.socket=forbidden;socket.create_connection=forbidden
    helper=module(ROOT/'tools/test_rc1_dbg_register_edits_cpu.py','component_definitions')
    full=module(ROOT/'tools/test_rc1_dbg_full_soak_cpu.py','component_full_model')
    assert SHA(ROOT/'tools/test_rc1_dbg_full_soak_cpu.py')==helper.FULL_MODEL_SHA
    build=ROOT/'BUILD/rc1-debugger-v1g';image=(build/'firmware.bin').read_bytes();assert SHA(build/'firmware.bin')==IMAGE
    symbols=json.loads((build/'symbols.json').read_text());boot=symbols['core/str8n-v2-boot']
    EEPROM,SPI=full.peripheral_classes();results=[]
    inputs=[Path(__file__),ROOT/'tools/test_rc1_dbg_register_edits_cpu.py',ROOT/'tools/test_rc1_dbg_full_soak_cpu.py',build/'firmware.bin',build/'symbols.json']
    pins={str(p.relative_to(ROOT)):SHA(p) for p in inputs}
    for is816 in (False,True):
        if is816:
            from py65816.devices.mpu65c816 import MPU as BaseMPU
            assert SHA(sys.modules[BaseMPU.__module__].__file__)==helper.MODEL_816_SHA
        else:
            from py65.devices.mpu65c02 import MPU as BaseMPU
        for variant in ('full','no-UCHESS','no-ASM-E','no-DBG1','opaque-lower-banks','F-only'):
            altered=bytearray(image)
            erased=[]
            if variant=='no-UCHESS':erased=[(1,0x8000)]
            if variant=='no-ASM-E':erased=[(1,0xe000)]
            if variant=='no-DBG1':erased=[(1,0xa000)]
            if variant=='opaque-lower-banks':altered[:65536]=b'\x5a'*65536
            if variant=='F-only':altered[:0x17000]=b'\xff'*0x17000
            for bank,address in erased:
                first=(bank-1)*32768+address-0x8000;altered[first:first+4096]=b'\xff'*4096
            for slot in ('A',):
                print('MODEL', '65C816 E=1' if is816 else '65C02',slot,variant,flush=True)
                space=dict(BaseMPU=BaseMPU,deque=deque,is816=is816,image=bytes(altered),metadata=full.metadata,
                    EEPROM=EEPROM,SPI=SPI,hashlib=hashlib,binascii=binascii,
                    detector=tuple(boot[n]+delta for n,delta in [('BOOT_XCE',1),('BOOT_XCE',2),('BOOT_XCE',4),('BOOT_XCE_RESTORE',-1),('BOOT_XCE_RESTORE',0)]))
                helper.definitions(ROOT/'tools/test_rc1_dbg_full_soak_cpu.py',('Memory','MPU','run','snapshot'),space)
                class MissingDependency(Exception):pass
                class GuardedCPU(space['MPU']):
                    def step(self):
                        if variant in ('no-DBG1','opaque-lower-banks','F-only') and self.memory.bank==1 and 0xa000<=self.pc<0xb000:
                            raise MissingDependency('Monitor/BRK hook attempts to execute absent B1:A debugger')
                        return super().step()
                memory=space['Memory'](slot);cpu=GuardedCPU(memory);memory.cpu=memory.spi.cpu=cpu;cpu.p=0x24
                if variant=='F-only':
                    # Memory's metadata seed is a full-system fixture convenience;
                    # a real F-only layout has neither journal sector nor slot.
                    memory.banks[3][0x4000:0x6000]=b'\xff'*8192
                mon=symbols['core/monitor-'+slot.lower()+'0'];run=space['run'];logs={};missing=False
                def command(line,prompt=b'B3> '):
                    start=len(memory.tx);memory.rx.extend(line.encode()+b'\r')
                    run(cpu,lambda:len(memory.tx)>start and memory.tx.endswith(prompt) and not memory.rx)
                    value=bytes(memory.tx[start:]);logs[line]=value.decode('ascii','replace');return value
                try:
                    if variant=='F-only':
                        run(cpu,lambda:memory.tx.endswith(b'REC> '))
                        assert b'FIXED F RECOVERY' in memory.tx
                        classification='fixed-F-recovery-menu-only-no-Jn'
                    else:
                        run(cpu,lambda:cpu.pc==mon['V2_LINE_BYTE'] and memory.tx.endswith(b'B3> '))
                        if is816:assert cpu.mode==1;cpu.allow_reset=False
                        for line in ('C','P','W','T 1','APPS'):command(line)
                        if variant in ('full','no-UCHESS'):
                            command('ASM',b'ASM> ')
                            for line in ('NEW','10 ORG $0200','20 LDA #$2A','30 BRK $01','40 END','ASM'):
                                command(line,b'ASM> ')
                            assert bytes(memory.ram[0x200:0x204])==bytes.fromhex('a9 2a 00 01')
                            command('QUIT')
                        elif variant=='no-ASM-E':
                            answer=command('ASM');assert b'invalid' in answer.lower() or b'not installed' in answer.lower(),answer
                        # Exercise a multi-byte decode, actual single-step and HOLD.
                        memory.ram[0x200:0x20b]=bytes.fromhex('00 01 a9 2a 8d 00 04 4c 67 7e ea')
                        command('G 0200',b'DBG> ')
                        command('U 0202',b'DBG> ')
                        command('S',b'DBG> ')
                        assert bytes(memory.ram[0x7000:0x7003])==bytes.fromhex('04 02 2a')
                        command('C');assert memory.ram[0x400]==0x2a
                        classification='monitor-and-DBG1-usable-with-ASM' if variant!='no-ASM-E' else 'monitor-and-DBG1-usable-ASM-unavailable'
                except MissingDependency as error:
                    assert variant in ('no-DBG1','opaque-lower-banks'),str(error)
                    missing=True;classification='coupled-DBG1-required-not-erase-only-removable'
                assert not memory.flash_writes and not memory.bus.writes
                if variant in ('no-DBG1','opaque-lower-banks'):assert missing
                if is816:assert cpu.mode==1
                results.append(dict(passed=True,CPU='65C816 E=1' if is816 else '65C02',slot=slot,variant=variant,
                    classification=classification,expected_missing_dependency_observed=missing,commands=logs,
                    model_flash_command_attempts=0,board_access=False))
                print('PASS',results[-1]['CPU'],slot,variant,classification,flush=True)
    assert all(SHA(ROOT/name)==digest for name,digest in pins.items())
    a.out.write_text(json.dumps(dict(passed=True,checks=len(results),results=results,source_sha256=pins,firmware_sha256=IMAGE,
        monitor_slots_exercised=['A'],hardware_component_removal_tested=False,model_only=True,board_access=False,native_debugging=False,
        RTC_drift_in_release_qualification=False,uninstaller_implemented=False),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
