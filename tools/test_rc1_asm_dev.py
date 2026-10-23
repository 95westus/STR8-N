"""Execute the linked development assembler through both monitor/CPU paths."""
import os
os.environ.setdefault('STR8_SOURCE_BUILD','BUILD/current')
import json
from test_rc1_source_store import Harness,ROOT,OUT,packed
from test_rc1_source_flash import FlashMemory

def main():
    cases=[]
    for cpu in ('65c02','65c816-e'):
        for slot in ('A','B'):
            h=Harness(cpu,slot,edu=slot=='B',memory_factory=FlashMemory);h.open();h.command_limit=20000000
            for cmd in ('LST','SYMS','SYMS FOO'):
                h.command(cmd,contains='Assemble successfully first')
            lines=['BASE EQU $0200','PORT .eQu $7FA0','ORG BASE','start: LDA #$42',
                   '.loop: STA PORT','BNE .loop','BYTE 1,2,3,4,5,6','END']
            source=packed([(10*(i+1),s) for i,s in enumerate(lines)])
            h.set_source(source);h.command('ASM',contains='OK 13 bytes')
            code=bytes(h.m.ram[0x200:0x20d]);assert code==bytes.fromhex('a9 42 8d a0 7f d0 fb 01 02 03 04 05 06')
            symbols=bytes(h.m.ram[0x4f00:0x6300]);answer=h.command('SYMS')
            assert '0200 BASE' in answer and '7FA0 PORT' in answer and '0202 START.LOOP' in answer,answer
            h.command('SYMS port',contains='7FA0 PORT')
            h.command('SYMS .loop',contains='0202 START.LOOP')
            h.command('SYMS MISSING',contains='No matching symbols')
            assert bytes(h.m.ram[0x4f00:0x6300])==symbols
            answer=h.command('LST');assert '40 0200 A9 42' in answer and 'start: LDA #$42' in answer,answer
            assert '0207 01 02 03 04' in answer and '020B 05 06' in answer,answer
            assert bytes(h.m.ram[0x200:0x20d])==code and h.source()[0:3]==source[0:3]
            h.command('DUMP',contains='0200: A9 42');h.command('S19',contains='S1')
            for line,expected in [('LDA MISSING','Symbol: MISSING'),('BRA $0400','-128..127'),
                                  ('LDA #$100','Value out of range'),('BOGUS','Unknown instruction')]:
                h.set_source(packed([(10,'ORG $0200'),(20,line),(30,'END')]))
                answer=h.command('ASM');assert 'Error line 20:' in answer and line in answer and expected in answer,answer
                h.command('LST',contains='Assemble successfully first')
            h.set_source(packed([(10,'X EQU 1'),(20,'X EQU 2')]))
            h.command('ASM',contains='Symbol: X')
            h.set_source(packed([(10,'ORG $0200'),(20,'FILL 20,$AA'),(30,'END')]))
            h.command('ASM',contains='OK 20 bytes');h.command('LST',contains='0210 AA AA AA AA')
            h.command('SAVE FLASH DEVTEST',contains='Source saved');h.command('NEW')
            h.command('LOAD FLASH DEVTEST\rYES',contains='Source loaded');h.command('ASM',contains='OK 20 bytes')
            h.command('10 ORG $0300');h.command('SYMS',contains='Assemble successfully first')
            h.command('ASM');h.command('LST',contains='0300 AA AA AA AA')
            h.command('NEW');h.command('ASM',contains='OK 0 bytes');h.command('LST');h.command('SYMS',contains='No matching symbols')
            # Installed end-of-line editing remains available.
            h.command('10 LDA #$12\x083');assert b'LDA #$13' in h.source()
            h.set_source(packed([(10+i,f'V{i} EQU {i}') for i in range(256)]))
            h.command('ASM',contains='OK 0 bytes')
            answer=h.command('SYMS');assert '00FF V255' in answer and 'No matching symbols' not in answer
            cases.append(dict(cpu=cpu,slot=slot,passed=True))
            print('PASS',cpu,slot,'EQU, listing bytes, scoped lookup, diagnostics, storage, editing',flush=True)
    report=dict(passed=True,cases=cases,board_access=False)
    (OUT/'asm-dev-tests.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
