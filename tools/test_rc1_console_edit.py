"""Exercise linked ASM/DBG line editing through their actual console readers."""
import hashlib
import json
import os

os.environ.setdefault('STR8_SOURCE_BUILD','BUILD/current')
from test_rc1_source_store import Harness,ROOT,OUT,packed

BS='\x08';DEL='\x7f';CSI='\x1b[3~';ERASE='\x08 \x08'


def main():
    cases=[]
    for cpu in ('65c02','65c816-e'):
        for slot in ('A','B'):
            h=Harness(cpu,slot,edu=(slot=='B'));h.command_limit=20000000;h.open()
            for key in (BS,DEL,CSI):
                h.command('NEW')
                text=h.command('10 LDA #$12'+key+'3')
                assert ERASE in text and h.source()==packed([(10,'LDA #$13')]),(repr(key),text,h.source())
                text=h.command(key*4);assert ERASE not in text
                text=h.command('abc'+key*5);assert text.count(ERASE)==3
                cases.append(dict(cpu=cpu,slot=slot,context='ASM',key=repr(key),passed=True))
            h.command('NEW')
            h.command('10 LDA #$1\x1b[D\x1b[1;5D2')
            assert h.source()==packed([(10,'LDA #$12')])
            h.command('20 NOP\x1b[3');assert h.source()==packed([(10,'LDA #$12'),(20,'NOP')])
            text=h.command('LIST'+' '*116+'Z'+BS+' ');assert 'Error' not in text
            h.command('NEW')
            text=h.command('PASTE\rLDA #$12'+DEL+'3\r.');assert ERASE not in text
            assert h.source()==packed([(10,'LDA #$13')])
            h.command('NEW');h.command('10 NOP\r\n20 BRK $01\r\n30 JMP $7E67')
            h.command('ASM',contains='OK 6 bytes');h.command('QUIT','monitor')
            h.command('G 0201','debug')
            for key,reg,start,last,expected in ((BS,'A','13','2','12'),(DEL,'X','34','5','35'),(CSI,'Y','67','8','68')):
                text=h.command(f'R {reg}={start}'+key+last,'debug',contains=f'{reg}={expected}')
                assert ERASE in text and '\x7f' not in text,(repr(key),text)
                empty=h.command(key*5,'debug');assert ERASE not in empty
                cases.append(dict(cpu=cpu,slot=slot,context='DBG',key=repr(key),passed=True))
            text=h.command('R'+' '*39+'Z'+DEL+' ','debug');assert '?' not in text
            text=h.command('R\x1b[D\x1b[1;5D','debug');assert 'A=12' in text
            text=h.command('R\x1b[3','debug');assert 'A=12' in text
            text=h.command('R A=00\x03','debug');assert '?' not in text
            h.command('R','debug',contains='A=12')
            h.command('C','monitor');assert h.m.ram[0x7BFC:0x7C00]==bytes(4)
            print('PASS',cpu,slot,'ASM/DBG BS, DEL, CSI Delete; erase echo, empty/full lines, paste, escape and cancel',flush=True)
    report=dict(passed=True,board_access=False,firmware_sha256=hashlib.sha256((OUT/'firmware.bin').read_bytes()).hexdigest(),
                CPUs=['65c02','65c816-e'],monitor_slots=['A','B'],bare_SXB_and_EDU=True,cases=cases)
    (OUT/'console-edit-tests.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
