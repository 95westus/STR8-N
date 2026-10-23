"""Probe unchanged resident ASM through linked CPU instructions, offline only."""
import argparse
import binascii
import hashlib
import importlib.abc
import json
import os
from pathlib import Path
import re
import socket
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
ATTEMPTS=[]
class NoSerial(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='serial' or fullname.startswith('serial.'):
            ATTEMPTS.append(fullname);raise AssertionError('Offline probe cannot import serial')
sys.meta_path.insert(0,NoSerial())
def no_network(*args,**kwargs):
    ATTEMPTS.append('network');raise AssertionError('Offline probe cannot connect to a network')
socket.create_connection=no_network
socket.socket.connect=no_network
socket.socket.connect_ex=no_network
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def cases():
    # Independent expected encodings; every case runs the existing machine code.
    rows=[]
    def yes(name,lines,body=b'',origin=0x200,**kw):rows.append(dict(name=name,lines=lines,body=body,origin=origin,error=0,**kw))
    def no(name,lines,error):rows.append(dict(name=name,lines=lines,error=error))
    yes('rom-origin', ['ORG $F000','entry: LDA #$42','JSR $7E6D','RTS','END'],bytes.fromhex('A9 42 20 6D 7E 60'),0xF000)
    yes('ram-logical-origin',['ORG $7000','BYTE 1,2,3','END'],bytes([1,2,3]),0x7000)
    yes('initial-origins-replace',['ORG $F000','ORG $1000','BYTE $AA'],b'\xAA',0x1000)
    yes('forward-org-fills',['ORG $E000','BYTE 1','ORG $E004,$AA','BYTE 2'],bytes.fromhex('01 AA AA AA 02'),0xE000)
    yes('default-org-fill',['BYTE 1','ORG $0203','BYTE 2'],bytes([1,0,0,2]))
    no('backward-org-after-emission',['BYTE 1','ORG $0200'],5)
    yes('last-address-byte',['ORG $FFFF','BYTE $AA'],b'\xAA',0xFFFF)
    no('address-overflow',['ORG $FFFF','BYTE 1,2'],5)
    no('org-after-last-byte',['ORG $FFFF','BYTE 1','ORG $0000'],5)
    yes('label-after-last-byte-wraps',['ORG $FFFF','BYTE 1','AFTER:','END'],b'\x01',0xFFFF,symbol=('AFTER',0))
    yes('branch-across-zero',['ORG $FFFE','BRA $0000'],bytes.fromhex('80 00'),0xFFFE)
    yes('branch-back-across-zero',['ORG $0000','BRA $FFFF'],bytes.fromhex('80 FD'),0)
    yes('default-origin-and-end',['BYTE 1','END','BOGUS'],b'\x01')
    no('end-has-no-entry-operand',['END $0200'],1)
    yes('empty-document',[],b'')
    text=bytes.fromhex('FF 80 0A 41 34 12 34 12 00 00 FF FF 41 0A 0D 09 00 22 5C')
    yes('expressions-and-strings',['BASE EQU $1234','ORG $E000',"BYTE $FF,-128,%1010,'A',<BASE,>BASE",
        'WORD BASE,$FFFF+1,0-1',r'TEXT "A\n\r\t\0\"\\"','WORD *','END'],text+(0xE000+len(text)).to_bytes(2,'little'),0xE000)
    yes('optional-dot-and-equ-case',['x .eQu 3','.org $0200','.byte X','.word $1234','.fill 2,$AA','.end'],bytes.fromhex('03 34 12 AA AA'))
    yes('immediate-signed-byte',['LDA #-128','LDA #255','BRK $FF','BRK'],bytes.fromhex('A9 80 A9 FF 00 FF 00 00'))
    for name,line in [('byte-low','BYTE -129'),('byte-high','BYTE 256'),('literal-overflow','WORD $10000'),('brk-negative','BRK -1')]:no(name,[line],5)
    for name,line in [('multiply','WORD 2*3'),('divide','WORD 8/2'),('bitwise-and','WORD 1&1'),('bitwise-or','WORD 1|2'),('shift','WORD 1<<2')]:no(name,[line],1)
    yes('depth-seven-groups',['BYTE '+'('*7+'1'+')'*7],b'\x01')
    no('depth-eight-groups',['BYTE '+'('*8+'1'+')'*8],12)
    yes('depth-seven-prefixes',['BYTE '+'+'*7+'1'],b'\x01')
    no('depth-eight-prefixes',['BYTE '+'+'*8+'1'],12)
    yes('forward-reference-retains-absolute',['ORG $10','LDA later','later: NOP'],bytes.fromhex('AD 13 00 EA'),0x10)
    yes('known-zero-page',['LOW EQU $10','LDA LOW'],bytes.fromhex('A5 10'))
    yes('forced-low-byte-forward',['ORG $10','LDA <later','later: NOP'],bytes.fromhex('A5 12 EA'),0x10)
    no('forward-constant-layout',['X EQU Y','Y EQU 1'],14)
    no('forward-org-layout',['ORG DEST','DEST EQU $0200'],14)
    no('forward-fill-layout',['FILL COUNT,0','COUNT EQU 1'],14)
    no('undefined-reference',['LDA MISSING'],3)
    no('duplicate-symbol',['X EQU 1','X EQU 2'],4)
    yes('locals-and-global-equ-scope',['G:','C EQU 1','.here: BYTE C','H:','.here: BYTE 2'],bytes([1,2]))
    no('orphan-local',['.here: NOP'],15)
    no('qualified-local-not-expression',['G:','.here: NOP','WORD G.HERE'],1)
    yes('symbol-name-fifteen',['ABCDEFGHIJKLMNO EQU 1','BYTE ABCDEFGHIJKLMNO'],b'\x01')
    no('symbol-name-sixteen',['ABCDEFGHIJKLMNOP EQU 1'],1)
    yes('local-name-fifteen',['G:','.ABCDEFGHIJKLMNO: BYTE 1','WORD .ABCDEFGHIJKLMNO'],bytes.fromhex('01 00 02'))
    for name,target,body in [('branch-plus127','$0281','80 7F'),('branch-minus128','$0182','80 80')]:yes(name,['BRA '+target],bytes.fromhex(body))
    no('branch-plus128',['BRA $0282'],6);no('branch-minus129',['BRA $0181'],6)
    yes('addressing-modes',['LDA #1','LDA $20','LDA $20,X','LDX $20,Y','LDA $1234','LDA $1234,X','LDA $1234,Y',
        'LDA ($20,X)','LDA ($20),Y','LDA ($20)','JMP ($1234)','JMP ($1234,X)','ASL A','STZ $20','PHX','PLX'],
        bytes.fromhex('A9 01 A5 20 B5 20 B6 20 AD 34 12 BD 34 12 B9 34 12 A1 20 B1 20 B2 20 6C 34 12 7C 34 12 0A 64 20 DA FA'))
    yes('65c02-bit-encodings-on-both-hosts',['BBR3 $20,$0203','RMB2 $20','SMB5 $21'],bytes.fromhex('3F 20 00 27 20 D7 21'))
    for token in ['INCLUDE "x.inc"','INCBIN "x.bin"','DB 1','DW 1','XDEF FOO','XREF FOO','MODULE NAME','CODE','IF 1','MACRO FOO','REP #$20','JSL $1234']:
        no('unsupported-'+token.split()[0].lower(),[token],2)
    yes('source-line-120',[';'+'X'*119])
    no('source-line-121',[';'+'X'*120],1)
    yes('source-packed-7168',[';'+'X'*119]*57+[';'+'X'*95])
    yes('output-12544',['FILL $3100,$A5'],b'\xA5'*0x3100)
    no('output-12545',['FILL $3101,$A5'],9)
    no('rom-range-before-output-limit',['ORG $D000','FILL $3100,$A5'],5)
    yes('symbols-256',[f'V{i} EQU {i}' for i in range(256)],symbol=('V255',255))
    no('symbols-257',[f'V{i} EQU {i}' for i in range(257)],8)
    no('undefined-names-also-use-symbols',[f'WORD V{i}' for i in range(257)],8)
    return rows


def parse_s19(reply):
    cells={};entries=[];sizes=[]
    for line in reply.splitlines():
        if not re.fullmatch(r'S[19][0-9A-F]{8,}',line):continue
        raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255,line
        address=int.from_bytes(raw[1:3],'big')
        if line.startswith('S1'):
            sizes.append(len(raw)-4)
            for i,value in enumerate(raw[3:-1]):assert address+i not in cells;cells[address+i]=value
        else:assert raw[0]==3;entries.append(address)
    assert len(entries)==1 and all(1<=size<=16 for size in sizes)
    return cells,entries[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--cpu',choices=('65c02','65c816-e'),action='append')
    parser.add_argument('--only',help='Optional regex for focused diagnosis; receipt marks partial coverage')
    args=parser.parse_args();build=args.build.resolve();out=args.out.resolve()
    assert not out.exists() and not out.is_relative_to(build) and not any(out.is_relative_to(ROOT/p) for p in ('src','tools','release','archive'))
    baseline=json.loads((ROOT/'tests/baselines/phase5.json').read_text());report=json.loads((build/'build-report.json').read_text())
    firmware=(build/'firmware.bin').read_bytes();assert report['passed'] and all(report['baseline_checks'].values())
    assert sha(firmware)==report['firmware_sha256']==baseline['firmware_sha256']
    asm=json.loads((build/'symbols.json').read_text())['assembler/asm-app']
    header=firmware[0x6000:0x6010]
    assert header[:4]==b'AP\1\1' and binascii.crc_hqx(header[:14],65535)==int.from_bytes(header[14:],'little')
    assert struct.unpack('<5H',header[4:14])==(7325,0xE010,0x200,0x64FF,0x3F00)
    opcodes=firmware[asm['OP_TABLE']-0x8000:asm['OP_END']-0x8000]
    mnemonics=sorted({opcodes[i:i+4].rstrip(b'\0').decode() for i in range(0,len(opcodes),6)})
    assert len(opcodes)==212*6 and len(mnemonics)==98
    static=dict(AP_header_hex=header.hex(),opcode_forms=212,mnemonics=mnemonics,opcode_table_sha256=sha(opcodes))
    os.environ['STR8_SOURCE_BUILD']=str(build)
    from test_rc1_source_store import Harness,packed
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n');rows=[]
    def record(name,profile,**values):
        row=dict(name=name,**profile,passed=True,**values);rows.append(row)
        save(out/'progress.json',dict(cases=rows,attempts=ATTEMPTS));print('PASS',profile['cpu'],profile['slot'],profile['coverage'],name,flush=True)
    selected=[row for row in cases() if not args.only or re.search(args.only,row['name'])]
    assert selected,'No matching cases'
    for cpu in args.cpu or ('65c02','65c816-e'):
        for slot in ('A','B'):
            for edu in (False,True):
                full=edu==(slot=='B');profile=dict(cpu=cpu,slot=slot,edu=edu,coverage='full' if full else 'smoke')
                h=Harness(cpu,slot,edu=edu);h.open();h.command_limit=30000000
                initial_flash=list(map(bytes,h.m.banks))
                registers=('pc','sp','p','a','x','y')+(('b','mode','pbr','dbr','dpr') if cpu=='65c816-e' else ())
                def compile(lines,inject=None,raw=None,end=None):
                    source=packed([(10*(i+1),line) for i,line in enumerate(lines)]) if raw is None else raw
                    assert len(source)<=7168
                    h.set_source(source);h.m.ram[0x200:0x3300]=b'\xCC'*0x3100
                    if end is not None:h.m.ram[0x6300:0x6302]=end.to_bytes(2,'little')
                    saved={n:getattr(h.cpu,n) for n in registers};bank=h.m.bank;step=h.cpu.step
                    # The callable engine owns all application ZP. Preserve the
                    # suspended editor caller for subsequent interactive probes.
                    caller_zp=bytes(h.m.ram[:0x40]);upper_ram=bytes(h.m.ram[0x6500:0x7B00])
                    h.cpu.stPushWord(0x1FF);h.cpu.pc=h.asm['ASM_ASSEMBLE']
                    if inject:
                        def wrapped():
                            if h.cpu.pc==h.asm['ASSEMBLE_PASS'] and h.m.ram[h.asm['PASS']]==2 and not wrapped.done:
                                inject(h);wrapped.done=True
                            return step()
                        wrapped.done=False;h.cpu.step=wrapped
                    start=h.steps
                    try:
                        h.run(lambda:h.cpu.pc==0x200,limit=30000000)
                        error=h.m.ram[h.asm['ERROR']];valid=h.m.ram[0x6306]
                        length=int.from_bytes(h.m.ram[0x6302:0x6304],'little');origin=int.from_bytes(h.m.ram[0x6304:0x6306],'little')
                        assert bool(h.cpu.p&1)==bool(error) and valid==int(error==0)
                        assert h.m.bank==bank and list(map(bytes,h.m.banks))==initial_flash and not h.m.flash_writes
                        assert bytes(h.m.ram[0x6500:0x7B00])==upper_ram
                        if raw is None and not inject:
                            after=bytearray(h.m.ram[0x3300:0x3300+len(source)]);pos=0
                            while pos<len(after):after[pos+3]=source[pos+3];pos+=4+source[pos+2]
                            assert after==source,'Compiler changed source beyond mode cache'
                        if cpu=='65c816-e':assert h.cpu.b==saved['b'] and h.cpu.mode==1 and (h.cpu.dpr,h.cpu.dbr,h.cpu.pbr)==(0,0,0)
                        top=int.from_bytes(h.m.ram[0x10:0x12],'little')
                        return dict(error=error,valid=valid,length=length,origin=origin,body=bytes(h.m.ram[0x200:0x200+length]),
                                    symbol_table=bytes(h.m.ram[0x4F00:top]),steps=h.steps-start)
                    finally:
                        h.cpu.step=step
                        h.m.ram[:0x40]=caller_zp
                        for name,value in saved.items():setattr(h.cpu,name,value)
                run_cases=selected if full else [r for r in selected if r['name'] in ('rom-origin','last-address-byte','addressing-modes')]
                for case in run_cases:
                    result=compile(case['lines']);assert result['error']==case['error'],(profile,case['name'],result)
                    if not case['error']:
                        assert result['body']==case['body'] and result['origin']==case['origin'],(profile,case['name'],result)
                        if 'symbol' in case:
                            name,value=case['symbol'];table=result['symbol_table']
                            assert any(table[i:i+16].rstrip(b'\0')==name.encode() and int.from_bytes(table[i+16:i+18],'little')==value for i in range(0,len(table),20))
                    record(case['name'],profile,error=result['error'],output_bytes=result['length'],output_sha256=sha(result['body']),origin=result['origin'],steps=result['steps'])
                if full and not args.only:
                    for end in (0x32FF,0x4F01):
                        result=compile([],end=end);assert result['error']==7
                        record('source-end-refusal-'+hex(end),profile,error=7)
                    result=compile([],raw=b'\x0A\0\x05\0NOP');assert result['error']==1
                    record('truncated-source-record',profile,error=1)
                    def mutate(target):target.m.ram[0x3300+4+2]=ord('2')
                    result=compile(['X=1'],inject=mutate);assert result['error']==10
                    record('pass2-source-change-refused',profile,error=10)
                    for origin,body in ((0xF000,bytes.fromhex('A9 42 60')),(0xFFFF,b'\xAA')):
                        lines=[f'ORG ${origin:04X}',*(['LDA #$42','RTS'] if origin==0xF000 else ['BYTE $AA'])]
                        h.set_source(packed([(10*(i+1),line) for i,line in enumerate(lines)]));answer=h.command('ASM',contains='OK ')
                        assert 'ORG differs' in answer and 'S 1 AUTO' not in answer
                        cells,entry=parse_s19(h.command('S19'));assert cells==dict(enumerate(body,origin)) and entry==origin
                        record('s19-logical-origin-'+hex(origin),profile,data_bytes=len(cells),entry=entry)
                    h.set_source(packed([(10,'BYTE 1'),(20,'LDA MISSING')]))
                    h.command('ASM',contains='Undefined symbol');assert h.m.ram[0x200]==1 and not h.m.ram[0x6306]
                    assert 'Assemble successfully first' in h.command('S19')
                    record('failure-invalidates-partial-output-and-export',profile)
                    h.command('NEW');h.command('10 ;'+'X'*116);original=h.source()
                    h.command('10 ;'+'X'*117,contains='Line too long');assert h.source()==original
                    h.command('NEW');h.command('PASTE\r'+';'+'X'*119+'\r.');assert len(h.source())==124
                    record('console120-includes-number-prefix-paste120-is-text',profile)
                    h.set_source(packed([(10*(i+1),line) for i,line in enumerate([';'+'X'*119]*57+[';'+'X'*95])]))
                    original=h.source();assert len(original)==7168
                    h.command('60000 NOP',contains='Source full');assert h.source()==original
                    record('editor-source-full-refuses-without-changing-document',profile)
                    lines=['ORG $0200','LDA later','later: NOP'];h.set_source(packed([(10*(i+1),line) for i,line in enumerate(lines)]))
                    h.command('ASM',contains='OK ')
                    before=h.source();positions=[];pos=0
                    while pos<len(before):positions.append(pos);pos+=4+before[pos+2]
                    assert any(before[pos+3] for pos in positions)
                    reply=h.command('SAVE SRAM CONTRACT')
                    assert not h.m.ram[0x6306]
                    if edu:
                        assert 'Source saved' in reply;_,data=h.latest('CONTRACT');assert data[:4]==b'AS\1\10'
                        canonical=bytearray(before);pos=0
                        while pos<len(canonical):canonical[pos+3]=0;pos+=4+canonical[pos+2]
                        assert data[8:]==canonical
                        h.command('NEW');h.command('LOAD SRAM CONTRACT\rYES',contains='Source loaded')
                        assert h.source()==canonical;h.command('ASM',contains='OK ')
                    else:assert 'Source storage:' in reply and not h.m.transfers
                    record('source-save-cache-canonicalization' if edu else 'bare-sram-refusal-invalidates-output',profile)
                assert list(map(bytes,h.m.banks))==initial_flash and not h.m.flash_writes
    assert not ATTEMPTS
    summary=dict(passed=True,board_access=False,serial_ports_opened=0,network_attempts=0,hardware_qualified=False,
        partial=bool(args.only),firmware_sha256=sha(firmware),firmware_unchanged=True,source_test_sha256=sha(Path(__file__).read_bytes()),
        harness_sha256=sha((ROOT/'tools/test_rc1_source_store.py').read_bytes()),cases=rows,case_count=len(rows),
        model_scope='Unchanged linked monitor/ASM instructions; FT245 and optional SRAM ABI modeled, discovery/delay shortcuts inherited; no emitted 65C02-only opcode executed on816',
        exact_resource_boundary_tests=not bool(args.only),static=static,all_modeled_flash_banks_unchanged=True,attempts=ATTEMPTS)
    save(out/'report.json',summary);print('PASS resident contract:',out/'report.json',flush=True)


if __name__=='__main__':main()
