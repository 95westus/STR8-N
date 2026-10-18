"""Fresh, serial-disabled rehearsal of a frozen beta34 -> beta35 board plan.

Only owner-local historical images enter the emulator. Results never imply a
new board readback or a general WDC/b1/b4 migration route. FNV range loops are
accelerated only after checking the linked hash instructions against Python.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FLEET = ROOT/'output/qualification/beta35-fleet-2026-10-16'
OLD = ROOT/'output/qualification/beta34-fleet-2026-10-16'
FREEZE = ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json'


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board',required=True,choices=['2205','2512','2604','2609'])
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    freeze=read(FREEZE);workspace=Path(freeze['frozen_source_directory'])
    os.environ['STR8_RTC_BUILD']='BUILD/v2-beta35-candidate'
    os.environ['STR8_TEST_DEPS']=str(workspace/'BUILD/test-deps')
    sys.path.insert(0,str(workspace/'tools'))
    import serial
    def no_serial(*a,**k):raise RuntimeError('Hardware serial access forbidden in offline prerelease rehearsal')
    serial.Serial=no_serial
    import test_v2_rtc_upgrade as test
    import beta4_migration as migration
    migration.Link=no_serial
    build=workspace/'BUILD/v2-beta35-candidate'
    assert sha((build/'build.json').read_bytes())==freeze['build_sha256']
    manifest=read(build/'migrator/manifest.json');test.MANIFEST=manifest;test.S=manifest['symbols']
    folder=FLEET/args.board;plan=read(folder/'plan.json');historical=read(folder/'model.json')
    assert plan['build_sha256']==historical['build_sha256']==freeze['build_sha256']
    assert historical['passed'] and plan['expected_hashes']==historical['expected_hashes']
    installer=(folder/'installer.s19').read_bytes()
    assert sha(installer)==plan['installer_sha256']==historical['installer_sha256']
    priorfolder=OLD/'fresh/2512' if args.board=='2512' else OLD/args.board/'hardware'
    prefix='flash-1-b' if args.board=='2512' else 'final-b'
    banks=[(priorfolder/f'{prefix}{i}.bin').read_bytes() for i in range(4)]
    expected=[(folder/f'expected-b{i}.bin').read_bytes() for i in range(4)]
    assert [sha(b) for b in banks]==plan['prior_hashes']
    assert [sha(b) for b in expected]==plan['expected_hashes']
    assert read(OLD/'report.json')['boards'][args.board]['final_flash_sha256']==plan['prior_hashes']
    cells,entry=migration.read_s19(folder/'installer.s19')
    payloads=[(folder/f'transfer-{i:02d}.bin').read_bytes() for i in range(len(plan['steps']))]
    for i,(b,s) in enumerate(plan['steps']):
        desired=bytearray(expected[b][(s-8)*4096:(s-7)*4096])
        if (b,s)==(1,11):desired[3]=255
        if (b,s)==(3,11):desired[31]=255
        assert payloads[i]==desired
    allowed=set(map(tuple,plan['steps']))
    clock=expected[1][0x3000:0x3000+24+read(build/'clock/build.json')['bytes']]
    class Memory(test.Memory):
        def __init__(self,initial):
            super().__init__(initial,allowed,{},commit_records={(1,0xB000):clock})
            self.new_monitor_committed=False
        def mutated(self,kind,address,value):
            assert not(self.bank==3 and 0xA000<=address<0xB000),'Fallback A changed'
            if self.bank==3 and address==0xB01F and value==0:
                assert bytes(self.banks[1])==expected[1] and bytes(self.banks[2])==expected[2]
                assert bytes(self.banks[3][0x3000:0x4000])==expected[3][0x3000:0x4000]
                self.new_monitor_committed=True
            super().mutated(kind,address,value)

    def fresh(initial):
        memory=Memory(initial)
        for a,v in cells.items():memory.ram[a]=v
        cpu=test.CPU(memory=memory,pc=entry);memory.cpu=cpu
        return memory,cpu

    # Independently run the actual linked FNV routine before enabling its shortcut.
    memory,cpu=fresh(banks);sample=bytes(range(256));memory.ram[0x6000:0x6100]=sample
    memory.ram[0xE0:0xE2]=b'\0\x60';memory.ram[0x620C]=0x61
    cpu.pc=test.S['MIG_HASH_RANGE'];cpu.accelerate_hash=False;cpu.stPushWord(0x1FF)
    test.run(cpu,lambda:cpu.pc==0x0200)
    assert int.from_bytes(memory.ram[0x6204:0x6208],'little')==migration.fnv(sample)
    checks=[]

    def execute(label,*,stale_bank=None,corrupt_row=None,partial_row=None):
        initial=[bytearray(b) for b in banks]
        if stale_bank is not None:initial[stale_bank][0x123]^=1
        memory,cpu=fresh(initial);memory.rx.extend(b'Y\r')
        for i,(b,s) in enumerate(plan['steps']):
            token=f'SEND 4096 BYTES FOR B{b}:{s:X}\r\n'.encode()
            test.run(cpu,lambda:token in bytes(memory.tx) or cpu.pc==test.S['MIG_HALT'])
            if cpu.pc==test.S['MIG_HALT']:
                assert stale_bank is not None and not any(e[1]==stale_bank for e in memory.events)
                assert bytes(memory.banks[stale_bank])==bytes(initial[stale_bank])
                break
            memory.tx.clear();events_before=len(memory.events);payload=bytearray(payloads[i])
            if corrupt_row==i:payload[127]^=1
            if partial_row==i:payload=payload[:2048]
            memory.rx.extend(payload)
            if corrupt_row==i:
                test.run(cpu,lambda:cpu.pc==test.S['MIG_HALT'])
                assert len(memory.events)==events_before and not memory.new_monitor_committed
                break
            if partial_row==i:
                test.run(cpu,lambda:not memory.rx and cpu.pc==test.S['V2W_RAW_POLL'])
                assert len(memory.events)==events_before and not memory.new_monitor_committed
                break
        else:
            test.run(cpu,lambda:cpu.pc==0xF004)
            assert [bytes(b) for b in memory.banks]==expected and memory.bank==3
            assert memory.new_monitor_committed and memory.events[-1]==('program',3,0xB01F,0)
            assert [(e[1],e[2]>>12) for e in memory.events if e[0]=='erase']==list(map(tuple,plan['steps']))
        assert bytes(memory.banks[0])==banks[0]
        assert bytes(memory.banks[3][0x2000:0x3000])==banks[3][0x2000:0x3000]
        checks.append({'name':label,'passed':True,'mutation_events':len(memory.events),
                       'new_monitor_committed':memory.new_monitor_committed})
        print('PASS',args.board,label,flush=True)

    execute('exact seven-sector update and verified final monitor commit')
    for bank in (1,2,3):execute(f'stale B{bank} refuses before its first mutation',stale_bank=bank)
    for row in range(len(payloads)):execute(f'corrupt payload row {row} refuses before row mutation',corrupt_row=row)
    for row in range(len(payloads)):execute(f'partial payload row {row} waits without row mutation/monitor commit',partial_row=row)
    model_sources={}
    for module in list(sys.modules.values()):
        path=Path(getattr(module,'__file__','') or '.')
        if path.is_file() and path.suffix=='.py' and path.resolve().is_relative_to(workspace.resolve()):
            model_sources[path.resolve().relative_to(workspace).as_posix()]=sha(path.read_bytes())
    for name,digest in model_sources.items():
        if name in freeze['source_files']:assert digest==freeze['source_files'][name],name
    report={'passed':True,'board':args.board,'version':'2.0b35','generation':47,
            'finished_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,
            'installer_sha256':plan['installer_sha256'],'prior_hashes':plan['prior_hashes'],
            'expected_hashes':plan['expected_hashes'],'build_sha256':freeze['build_sha256'],
            'source_route':'Exact historical beta34 generation 46 board preimage; B28 A retained, B34 B replaced',
            'board_access':False,'serial_disabled':True,'new_hardware_readback':False,
            'physical_power_cut_test':False,'hash_opcode_equivalence_checked':True,
            'hash_range_loops_accelerated':True,'model_sources':model_sources,
            'harness_sha256':sha(Path(__file__).read_bytes())}
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
