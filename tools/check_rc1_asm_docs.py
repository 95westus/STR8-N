"""Validate the shared documented program and source cycle without board access."""
import os
os.environ.setdefault('STR8_SOURCE_BUILD','BUILD/current')
import hashlib
import json
import re
from test_rc1_source_store import Harness,ROOT,OUT,packed
from test_rc1_source_flash import FlashMemory

def main():
    docs=ROOT/'docs/rc1'
    def numbered(name):
        text=(docs/name).read_text()
        if '<!-- asm-doc-example: hello -->' in text:
            text=text.split('<!-- asm-doc-example: hello -->',1)[1]
        else:text=text.split('## A small example program',1)[1]
        source=re.search(r'```asm\n(.*?)\n```',text,re.S)[1]
        return [(int(n),s) for n,s in (line.split(' ',1) for line in source.splitlines())]
    lines=numbered('ASM_SAVE_STORE.md')
    assert lines==numbered('QUICK_START.md')==numbered('ASM_GUIDE.md')
    expected=bytes.fromhex('78 d8 a9 41 20 6d 7e 4c 67 7e')
    cases=[]
    for cpu,slot in (('65c02','B'),('65c816-e','A')):
        h=Harness(cpu,slot,edu=True,memory_factory=FlashMemory);h.open();h.command_limit=20000000
        h.set_source(packed(lines));h.command('ASM',contains='OK 10 bytes, origin $0200, buffer $0200')
        assert bytes(h.m.ram[0x200:0x20a])==expected
        lst=h.command('LST');syms=h.command('SYMS')
        for row in ('60 0200 78','70 0201 D8','80 0202 A9 41','90 0204 20 6D 7E','100 0207 4C 67 7E'):assert row in lst
        for row in ('0200 BASE','7E6D PUTC','7E67 HOLD','0041 CHAR','0200 START','0202 START.READY'):assert row in syms
        h.command('SYMS start',contains='0200 START');h.command('SYMS .ready',contains='0202 START.READY')
        h.command('SYMS absent',contains='No matching symbols')
        h.command('80 LDA MISSING');h.command('ASM',contains='Error line 80: Undefined symbol\r\nLDA MISSING\r\nSymbol: MISSING')
        h.command('80 .ready: LDA #CHAR');h.command('ASM',contains='OK 10 bytes')
        h.command('SAVE SRAM HELLOSRC',contains='Source saved');h.command('LST',contains='Assemble successfully first')
        h.command('ASM');h.command('LST');h.command('SYMS .ready',contains='0202 START.READY')
        h.command('NEW');answer=h.command('LOAD SRAM HELLOSRC\rYES',contains='Source loaded')
        assert 'YES' in answer
        h.command('ASM',contains='OK 10 bytes');h.command('LST');h.command('SYMS .ready',contains='0202 START.READY')
        h.command('QUIT','monitor');h.command('G 0200','monitor',contains='A')
        h.command('ASM');h.command('NEW')
        for source,outputs in [([(10,'ORG $0200'),(20,'LDA MISSING')],['Error line 20: Undefined symbol','LDA MISSING','Symbol: MISSING']),
                               ([(10,'X EQU 1'),(20,'X EQU 2')],['Duplicate symbol','X EQU 2','Symbol: X']),
                               ([(10,'ORG $0200'),(20,'LDA #$100')],['Value out of range','LDA #$100']),
                               ([(10,'ORG $0200'),(20,'BRA $0400')],['Branch out of range','BRA $0400','Branch displacement must be -128..127 bytes'])]:
            h.set_source(packed(source));answer=h.command('ASM')
            assert all(s in answer for s in outputs),(source,answer)
        cases.append(dict(cpu=cpu,monitor=slot,passed=True,transcripts=h.transcripts))
        print('PASS documented EQU/LST/SYMS, errors, SRAM source cycle and print-A execution:',cpu,slot,flush=True)
    report=dict(passed=True,board_access=False,hardware_storage_written=False,cases=cases,
        files={n:hashlib.sha256((docs/n).read_bytes()).hexdigest() for n in
               ('QUICK_START.md','ASM_GUIDE.md','ASM_SAVE_STORE.md')})
    (OUT/'documentation-checks.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
