"""Build/test a non-writing user demo for exact b15 F; offline only."""
import argparse,json,shutil
from pathlib import Path
import prepare_ram_config_2609 as p
from str8build.assemble import Assembly
from test_b14_core import load_core
from test_b14_raw import start,feed

BIN='b15-F-DEMO-RAM.bin'
WAIT=b'Press one key to test input> '
REC=b'REC> '
HELP=b'L=0200 ^C=cancel idle3s\r\nA/B 0-3 C1USB/2ACIA/3both\r\n'


def verify(out):
    out=Path(out).resolve();q=p.read(out/'qualification.json')
    assert q['passed'] and q['checks']==8
    for name,value in q['inputs'].items():assert p.digest(name)==value['sha256'],'Changed input '+name
    assert p.digest(out/'payload'/BIN)==q['sha256'] and not q['hardware']
    return q


def prepare(out):
    out=Path(out).resolve();assert out.is_relative_to(p.ROOT/'output/qualification') and not out.exists()
    source,base,_=p.baseline();original_marker=p.digest(p.ROOT/'output/qualification/device-operations/2609.json')
    paths=[Path(__file__),p.HERE/'f-user-demo-b15.asm',p.TARGET/'s/include/str8n-v2-public.inc',
           p.TARGET/'symbols.json',p.TARGET/'prototype-report.json',p.TARGET/'payload/f-offline-component.bin',
           p.HERE/'test_b14_core.py',p.HERE/'test_b14_raw.py']
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n');shutil.copytree(p.TARGET/'s',out/'s');(out/'payload').mkdir()
    shutil.copy2(p.HERE/'f-user-demo-b15.asm',out/'s/core/f-user-demo.asm')
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln')
    assert a.assembler and a.linker
    a.compiled=[];a.symbols=p.read(p.TARGET/'symbols.json')
    body,sy=a.link('core','f-user-demo',0x200,'DEMO_END');a.emit(BIN,body)
    assert sy['DEMO_START']==0x200 and sy['DEMO_END']<=0x6500
    shutil.copy2(p.TARGET/'payload/f-offline-component.bin',out/'payload/f-offline-component.bin')
    shutil.copy2(p.TARGET/'prototype-report.json',out/'prototype-report.json');p.save(out/'symbols.json',a.symbols)
    for n,b in enumerate(source):(out/f'source-b{n}.bin').write_bytes(b)
    only=list(source);empty=bytearray(only[3]);empty[0x2000:0x7000]=b'\xff'*0x5000;only[3]=bytes(empty)
    cases=[];core,_=load_core();core.GENERATION=p.GENERATION
    for cpu in ('65c816-e','65c02'):
        for label,banks in (('F-only-no-MON-CD-E',only),('current-2609',source)):
            h=core.Machine(out,cpu,opaque=True);h.m.banks[:]=list(map(bytearray,banks));h.recovery()
            h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE']);before=list(map(bytes,h.m.banks))
            text=bytearray(h.port_command(1,b'?\r'));assert HELP in text
            text.extend(h.port_command(1,b'C1\r'))
            denied=h.port_command(1,b'0\r')
            assert denied==b'0\r\n\r\nRecovery L A/B 0-3 C1/2/3 ?\r\nREC> ' and h.m.bank==3 and not h.m.events
            text.extend(denied)
            start(h,1);cancel=h.port_command(1,b'\x03',REC);text.extend(cancel)
            assert not h.m.events and list(map(bytes,h.m.banks))==before
            cases.append(dict(passed=True,cpu=cpu,case=label+'-help-USB-disabled-bank-load-cancel'))
            start(h,1);feed(h,1,body);h.run(lambda:bytes(h.m.tx).endswith(WAIT))
            begin=bytes(h.m.tx).rfind(b'STR8-N b15 F USER DEMO');text.extend(bytes(h.m.tx[begin:]))
            assert f'CPU code (02=65C02, 16=65C816): {"16" if cpu=="65c816-e" else "02"}\r\n'.encode() in text
            assert b'RAM calculation, hex 1234 + 0001 = 1235\r\n' in text
            result=h.port_command(1,b'!',REC);text.extend(result);assert b'Received key byte, hex: 21\r\n' in result
            assert b'Boot : 6 5 4 3 2 1 0' in result and list(map(bytes,h.m.banks))==before and not h.m.events
            expected=bytearray(body)
            for name,value in (('DEMO_CPU',0x16 if cpu=='65c816-e' else 2),('DEMO_CAPS',0x17),('DEMO_SUM',0x35),('DEMO_KEY',0x21)):
                expected[sy[name]-0x200]=value
            expected[sy['DEMO_SUM']-0x200+1]=0x12
            assert bytes(h.m.ram[0x200:0x200+len(body)])==expected
            (out/f'executed-RAM-{cpu}.bin').write_bytes(expected)
            (out/f'simulated-{label}-{cpu}.txt').write_bytes(text)
            cases.append(dict(passed=True,cpu=cpu,case=label+'-raw-L-compute-input-public-queries-return-REC',flash_writes=0))
            print('PASS',cpu,label,'F-only user services and no flash mutation',flush=True)
    assert not p.ATTEMPTS and p.digest(p.ROOT/'output/qualification/device-operations/2609.json')==original_marker
    q=dict(passed=True,checks=len(cases),cases=cases,hardware=False,board_access=False,serial_access=False,BIN=BIN,
        bytes=len(body),sha256=p.sha(body),F_sha256=p.F_SHA,load_address='0200',end_exclusive=f'{sy["DEMO_END"]:04X}',
        requires=['Exact b15 F'],MON_or_journal_required=False,flash_writes=0,saved_setting_writes=0,
        inputs={str(path):p.binding(path) for path in paths},baseline=base)
    p.save(out/'qualification.json',q)
    print('PASS F demo:',len(body),'bytes;',len(cases),'model groups; no board access',flush=True)
    return q


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','verify']);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();prepare(args.out) if args.command=='prepare' else verify(args.out)
