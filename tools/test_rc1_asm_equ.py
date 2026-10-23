"""Run the linked EQU parser, old syntax, source storage and named launch."""
import hashlib
import json
import os
from pathlib import Path
import re

os.environ.setdefault('STR8_SOURCE_BUILD','BUILD/current')
from test_rc1_source_store import Harness,ROOT,OUT,packed
from test_rc1_source_flash import FlashMemory


def main():
    cases=[]
    valid=[
        ['PORT EQU $7FA0','BASE .eQu $0200','LO equ <PORT','HI EQU >PORT','N EQU 1+2',
         'ORG BASE','LDA #LO','LDX #HI','STA PORT','BYTE N','END'],
        ['ORG $0200','first:','.n EQU $55','LDA #.n','second:','.n .EQU $66','LDA #.n','END'],
        ['ONE EQU 1','TWO EQU ONE+1','ORG $0200','BYTE ONE,TWO','END'],
        ['EQU EQU 7','ORG $0200','BYTE EQU','END'],
        ['VALUE EQU 4 ; comment','ORG $0200','BYTE VALUE','END']]
    invalid=[
        ['X EQU 1','X EQU 2','END'],['X EQU','END'],['X EQU ; missing','END'],
        ['X EQU LATER','LATER EQU 1','END'],['X EQU X','END'],
        ['X EQU 1 trailing','END'],['X EQU (1','END'],['X EQU $10000','END'],
        ['.local EQU 1','END'],['ORG $0200','X:','X EQU 1','END']]
    def compile(h,lines):
        h.set_source(packed([(10*(i+1),s) for i,s in enumerate(lines)]))
        answer=h.command('ASM');n=int.from_bytes(h.m.ram[0x6302:0x6304],'little')
        ok=bool(h.m.ram[0x6306]);return answer,bytes(h.m.ram[0x200:0x200+n]) if ok else b'',ok
    def equal_form(lines):return [re.sub(r'(?i)\s+\.?EQU(?=\s|;|$)',' =',s,count=1) for s in lines]
    for cpu in ('65c02','65c816-e'):
        for slot in ('A','B'):
            h=Harness(cpu,slot,edu=(slot=='B'),memory_factory=FlashMemory);h.command_limit=20000000;h.open()
            for i,lines in enumerate(valid+invalid):
                a,code,ok=compile(h,lines);b,other,equal_ok=compile(h,equal_form(lines))
                assert ok==equal_ok and code==other,(lines,a,b)
                assert ok==(i<len(valid)),(lines,a)
                if not ok and lines[0] not in ('X EQU','X EQU ; missing'):
                    assert a==b,(lines,a,b)
                cases.append(dict(cpu=cpu,slot=slot,name='constant-case-'+str(i),passed=True))
            for text in ('X EQUATE 1','X EQU1','X .EQUATE 1','EQU 1'):
                answer,_,ok=compile(h,[text,'END']);assert not ok,(text,answer)
            # Ordinary mnemonic parsing after the same-size jump still works.
            _,code,ok=compile(h,['ORG $0200','LDA #1','STA $20','JMP $7E67','END'])
            assert ok and code==bytes.fromhex('A9 01 85 20 4C 67 7E')
            for stem in ('sxb-cs-patterns','edu-led31'):
                _,code,ok=compile(h,(ROOT/'examples/source-cycle'/(stem+'.asm')).read_text().splitlines())
                assert ok and code==(ROOT/'BUILD/rc1-dev-samples/listings'/(stem+'.bin')).read_bytes()
            master=(ROOT/'examples/source-cycle/edu-led31-loop.asm').read_text().splitlines()
            _,code,ok=compile(h,master)
            assert ok and code==(ROOT/'BUILD/rc1-edu-loop/program.bin').read_bytes()
            # Persist the actual EQU source as data, then reload and assemble.
            source=packed([(10*(i+1),s) for i,s in enumerate(master)])
            h.command('SAVE FLASH EQLOOP',contains='Source saved')
            h.command('NEW');h.command('LOAD FLASH EQLOOP\rYES',contains='Source loaded')
            assert h.source()==source
            _,again,ok=compile(h,master);assert ok and again==code
            h.command('QUIT','monitor');h.command('G 0200','debug',contains='PC=0252')
            h.command('S','debug',contains='PC=0253');h.command('X','monitor')
            cases.append(dict(cpu=cpu,slot=slot,name='original-samples-and-direct-EQU-master-save-load-assemble-debug',passed=True))
            print('PASS',cpu,slot,'EQU/= semantics, refusals, unchanged originals and direct EDU master cycle',flush=True)
    report=dict(passed=True,board_access=False,installation_permitted=False,
        firmware_sha256=hashlib.sha256((OUT/'firmware.bin').read_bytes()).hexdigest(),
        cases=cases,case_count=len(cases),CPUs=['65c02','65c816-e'],monitor_slots=['A','B'],
        bare_SXB_and_EDU=True,master_binary_bytes=430,master_matches_expanded_binary=True)
    (OUT/'equ-tests.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
