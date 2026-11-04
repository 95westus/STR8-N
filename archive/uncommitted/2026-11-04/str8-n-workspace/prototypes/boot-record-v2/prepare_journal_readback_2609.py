"""Bind the established RAM flash-readback service to b15; CPU test before I/O.

Only F(bank), M (RAM read), and J (restart F) are used. There is no flash writer
in the service. The original fixed-range RAM restore commands are retained in
the established service source but are not admitted by this hardware workflow.
"""
import argparse,json,shutil
from pathlib import Path
import prepare_journal_init_2609 as p
from build import long_branches
from str8build.assemble import Assembly
from installer.common import save


def build(out,plan):
    out=Path(out).resolve();plan=Path(plan).resolve();info=p.verify(plan)
    assert not out.exists();(out/'s/core').mkdir(parents=True);(out/'payload').mkdir()
    core=out/'s/core'
    for name in ('str8n-v2-eq.inc','str8n-v2-public.inc','service-eq.inc'):
        shutil.copy2(p.TARGET/'s/include'/name,core/name)
    for name in ('vectors-symbols.inc','boot-symbols.inc'):
        shutil.copy2(p.TARGET/'s/core'/name,core/name)
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols={};a.compiled=[]
    prefix='        MODULE JOURNAL_READBACK\n        INCLUDE "str8n-v2-eq.inc"\n        INCLUDE "str8n-v2-public.inc"\n        INCLUDE "vectors-symbols.inc"\n        INCLUDE "boot-symbols.inc"\n        CODE\n'
    source=p.HERE/'mon-absent-service.inc'
    (core/'readback-service.asm').write_text(long_branches(prefix+source.read_text()+'\n        ENDMOD\n        END\n'))
    body,sy=a.link('core','readback-service',0x6800,'MS_END')
    loader='MS_BOOTSTRAP:\n        SEI\n        CLD\n'
    for n in range(len(body)):loader+=f'        LDA MS_BLOB+{n}\n        STA ${0x6800+n:04X}\n'
    loader+='        JMP $6800\n'+p.db('MS_BLOB',body)+'MS_LOAD_END:\n'
    (core/'readback-loader.asm').write_text(prefix+loader+'\n        ENDMOD\n        END\n')
    image,ls=a.link('core','readback-loader',0x200,'MS_LOAD_END')
    assert sy['MS_END']<0x7800 and ls['MS_LOAD_END']<0x6500
    a.emit('readback-RAM.bin',image);save(out/'symbols.json',dict(service=sy,loader=ls))
    return dict(passed=True,hardware=False,F_sha256=p.F_SHA,loader_bytes=len(image),loader_sha256=p.r.sha(image),
                service_bytes=len(body),service_source_sha256=p.digest(source),builder_sha256=p.digest(__file__),
                allowed_hardware_commands=['F00','F01','F02','F03','M','J'],plan_sha256=p.digest(plan/'plan.json'))


def test(out,plan):
    # Import the offline harness only in this process, never in a live worker.
    from test_b14_core import load_core
    from test_b14_raw import start,feed
    core,_=load_core();core.GENERATION=p.GENERATION
    cases=[];image=(out/'payload/readback-RAM.bin').read_bytes();prompt=b'RAM SERVICE> '
    for cpu in ('65c816-e','65c02'):
        for phase in ('source','expected'):
            banks=[(plan/f'{phase}-b{n}.bin').read_bytes() for n in range(4)]
            h=core.Machine(p.TARGET,cpu,opaque=True);h.m.banks[:]=list(map(bytearray,banks));h.m.bank=3
            h.m.tx.clear();h.m.rx.clear();h.c.pc=0xf004;h.c.p=0x34;h.c.sp=255
            if cpu=='65c816-e':h.c.mode=1;h.c.dpr=h.c.dbr=h.c.pbr=0
            h.run(lambda:bytes(h.m.tx).endswith(b'REC> '))
            h.port_command(1,b'C1\r');start(h,1);feed(h,1,image);h.run(lambda:bytes(h.m.tx).endswith(prompt))
            for bank in range(4):
                n=len(h.m.tx);h.m.rx.extend(b'F'+bytes([bank]))
                h.run(lambda:len(h.m.tx)>=n+32770+len(prompt) and bytes(h.m.tx).endswith(prompt))
                raw=bytes(h.m.tx[n:]);assert len(raw)==32770+len(prompt) and raw[:32768]==banks[bank]
                assert p.wire.crc(raw[:32768])==int.from_bytes(raw[32768:32770],'little')
            n=len(h.m.tx);h.m.rx.extend(b'M');h.run(lambda:len(h.m.tx)>=n+0x6302+len(prompt) and bytes(h.m.tx).endswith(prompt))
            raw=bytes(h.m.tx[n:]);assert raw[:len(image)]==image and p.wire.crc(raw[:0x6300])==int.from_bytes(raw[0x6300:0x6302],'little')
            h.port_command(1,b'J',b'REC> ')
            assert not h.m.events and list(map(bytes,h.m.banks))==banks
            cases.append(dict(passed=True,cpu=cpu,phase=phase,all_four_banks_exact=True,RAM_loader_readback_exact=True,no_flash_mutation=True,final_REC=True))
            print('PASS readback',cpu,phase,flush=True)
    return cases


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();plan=args.plan.resolve();report=build(out,plan);report['cases']=test(out,plan)
    save(out/'qualification.json',report);print('PASS read-only service b15 binding and four CPU/state cases; no board access',flush=True)
