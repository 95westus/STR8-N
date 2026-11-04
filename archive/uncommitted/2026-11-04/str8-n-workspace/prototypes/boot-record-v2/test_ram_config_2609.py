"""CPU/NOR qualification of b15 CONFIG, including the captured 2609 state."""
import argparse,json
from pathlib import Path
import prepare_ram_config_2609 as p
import test_ram_config_b14 as legacy
from test_b14_raw import start,feed

legacy.core.GENERATION=p.GENERATION
PROMPT=legacy.PROMPT


def current_machine(build,cpu,port=1,banks=None):
    h=legacy.core.Machine(build,cpu,opaque=True)
    banks=banks or [(build/f'source-b{n}.bin').read_bytes() for n in range(4)]
    h.m.banks[:]=list(map(bytearray,banks))
    h.recovery();h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
    h.original_ram=bytes(h.m.ram);h.initial_banks=tuple(map(bytes,h.m.banks))
    body=(build/'payload'/p.BIN).read_bytes();h.loaded_end=0x200+len(body)
    start(h,port);feed(h,port,body)
    h.run(lambda:bytes(h.m.tx).endswith(PROMPT) and bytes(h.m.acia_tx).endswith(PROMPT))
    assert not h.m.events and tuple(map(bytes,h.m.banks))==h.initial_banks
    legacy.preserved(h)
    return h


def readonly_checkpoint(build,cpu,port,passed):
    h=current_machine(build,cpu,port);before=tuple(map(bytes,h.m.banks));row=legacy.latest(before)
    assert row[7]==ord('S') and row[13]==0 and int.from_bytes(row[8:12],'little')==1020
    transcript=bytearray(bytes(h.m.tx if port==1 else h.m.acia_tx))
    for key in (b'?',b'B',b'C',b'W'):
        reply=legacy.command(h,port,key);transcript.extend(reply)
        assert not h.m.events and tuple(map(bytes,h.m.banks))==before
        if key in (b'B',b'C'):
            assert b'DEFAULT=S\r\n' in reply
            for bank in range(4):assert f'B{bank} OFF ENTRY=8000\r\n'.encode() in reply
        elif key==b'W':
            for n,value in enumerate(p.read(build/'baseline.json')['counts']):
                assert f'B{n//8}:{n%8+8:X} {value:06X}\r\n'.encode() in reply
            assert b'UNKNOWN HISTORY\r\n' in reply
    for key in (b'I',b'C 0',b'C 1',b'C 2',b'C 3',b'B 3 C000',b'B 3 D000',b'B 1 8000 X',b'C S X'):
        reply=legacy.command(h,port,key);assert b'REFUSED' in reply
        assert not h.m.events and tuple(map(bytes,h.m.banks))==before
    reply=h.port_command(port,b'Q\r',b'REC> ');transcript.extend(reply)
    assert b'Boot : 6 5 4 3 2 1 0' in reply and not h.m.events and tuple(map(bytes,h.m.banks))==before
    legacy.preserved(h)
    (build/f'simulated-inspection-{cpu}-port{port}.txt').write_bytes(transcript)
    passed(cpu,port,'captured-2609-inspection-Q-no-flash-default-S-mask-zero-counts-unchanged',commands=14)


def checkpoint_writes(build,cpu,passed):
    # These settings changes occur only in disposable models, never on 2609.
    source=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)]
    original=legacy.latest(source)
    for target in ('S','A','B'):
        h=current_machine(build,cpu)
        assert b'OK\r\n' in legacy.command(h,1,('C '+target).encode())
        row=legacy.latest(h.m.banks)
        assert row[7]==ord(target) and row[13]==0 and row[64:252]==original[64:252]
        assert row[32:64]==original[32:64] and int.from_bytes(row[8:12],'little')==1021
        if target in ('A','B'):assert int.from_bytes(row[18:22],'little')==p.GENERATION
        assert h.m.events and all(event[0]!='erase' for event in h.m.events)
        legacy.preserved(h);legacy.reboot_reader(build,cpu,h.m.banks)
    passed(cpu,1,'captured-2609-model-only-default-S-A-B-append-MON-generation-pin',targets=3)
    h=current_machine(build,cpu)
    assert b'OK\r\n' in legacy.command(h,1,b'B 1 8000')
    row=legacy.latest(h.m.banks)
    assert row[7]==ord('S') and row[13]==2 and row[64:252]==original[64:252]
    before=tuple(map(bytes,h.m.banks));events=list(h.m.events)
    assert b'OK\r\n' in legacy.command(h,1,b'B 1 8000')
    assert h.m.events==events and tuple(map(bytes,h.m.banks))==before
    assert b'OK\r\n' in legacy.command(h,1,b'C 1')
    row=legacy.latest(h.m.banks)
    assert row[7]==ord('1') and row[13]==2 and row[64:252]==original[64:252]
    assert int.from_bytes(row[8:12],'little')==1022
    assert all(event[0]!='erase' for event in h.m.events)
    legacy.preserved(h);legacy.reboot_reader(build,cpu,h.m.banks)
    passed(cpu,1,'captured-2609-model-only-enable-entry-noop-default-preserve-B0-and-counts')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--cpu',choices=legacy.CPUS,required=True);args=parser.parse_args();build=args.build.resolve();cpu=args.cpu
    info=p.verify(build);cases=[]
    def passed(cpu,port,case,**details):
        cases.append(dict(passed=True,cpu=cpu,port=port,case=case,**details))
        print('PASS',cpu,port,case,details,flush=True)
        p.save(build/f'config-progress-{cpu}.json',dict(completed=len(cases),cases=cases))
    for port in (1,2):
        legacy.interface_tests(build,cpu,port,passed)
        legacy.refusal_tests(build,cpu,port,passed)
        readonly_checkpoint(build,cpu,port,passed)
    legacy.bank_entries(build,cpu,passed)
    legacy.journal_refusals(build,cpu,passed)
    legacy.interruption_tests(build,cpu,passed)
    checkpoint_writes(build,cpu,passed)
    assert not p.ATTEMPTS
    receipt=dict(passed=True,checks=len(cases),failures=0,hardware=False,board_access=False,serial_access=False,
        CPU=cpu,app_sha256=info['app_sha256'],build_sha256=p.digest(build/'ram-config-build.json'),
        checker_sha256=p.digest(__file__),legacy_checker_sha256=p.digest(p.HERE/'test_ram_config_b14.py'),
        mutation_prefixes=sum(row.get('prefixes',0) for row in cases),cases=cases)
    p.save(build/f'ram-config-tests-{cpu}.json',receipt)
    print('PASS',cpu,'total',len(cases),'prefixes',receipt['mutation_prefixes'],flush=True)


if __name__=='__main__':main()
