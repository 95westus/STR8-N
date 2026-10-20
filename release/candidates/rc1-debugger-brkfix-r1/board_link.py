"""Explicit-port experimental board tools. Preparation never invokes this file."""
import argparse
import contextlib
import json
from pathlib import Path
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'engine'))
import board_plan as plans
import install_transport as engine
import legacy_transport as wire
import runtime as r
from smoke_checks import check


def save(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)


def read_range(link,first,last,prompt=b'\r\nB3> '):
    return b''.join(link.dump(a,min(a+0xFFF,last),prompt) for a in range(first,last+1,0x1000))


def load(link,path):
    cells={};entry=None
    for row in path.read_text().splitlines():
        raw=bytes.fromhex(row[2:]);plans.require(sum(raw)&255==255 and len(raw)==raw[0]+1,'Bad S19')
        address=int.from_bytes(raw[1:3],'big')
        if row.startswith('S1'):
            for offset,v in enumerate(raw[3:-1]):
                plans.require(address+offset not in cells,'Overlapping S19');cells[address+offset]=v
        elif row.startswith('S9'):
            plans.require(entry is None and len(raw)==4,'Bad S9');entry=address
        else:plans.require(row.startswith('S0'),'Unsupported S19 record')
    ram_end=int.from_bytes(link.dump(0x7D0A,0x7D0B),'little')
    plans.require(ram_end in (0x64FF,0x66FF),'Unknown application RAM limit')
    plans.require(cells and min(cells)>=0x200 and max(cells)<=ram_end and entry in cells,'RAM image outside application range')
    plans.require(set(cells)==set(range(min(cells),max(cells)+1)),'Sparse S19')
    link.command('L',b'S19')
    for row in path.read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
    text=link.until(b'\r\nB3> ')
    plans.require(f'Entry {entry:04X}'.encode() in text and not any(t in text for t in (b'Bad',b'Protected',b'Wrap',b'Error')),'Loader refused image')
    plans.require(read_range(link,min(cells),max(cells))==bytes(cells[a] for a in sorted(cells)),'RAM image readback differs')
    return cells


def identity(link,board,generation):
    # Require an already-idle B3 monitor; do not auto-exit an application/debugger.
    link.command('')
    text=link.command('VERSION')
    plans.require(('Board: '+board).encode() in text and b'2.0rc1' in text,'Wrong board/firmware identity')
    plans.require(b'65C02' in text or b'65C816' in text,'Unsupported CPU')
    for slot in ('A','B'):
        plans.require(f'MONITOR {slot} gen {generation:08X} VALID'.encode() in text,'Wrong monitor generation/CRC')
    return text.decode('ascii')


@contextlib.contextmanager
def connection(args,out):
    plans.require(args.port and args.usb_serial and args.board,'Explicit port, USB serial and board required')
    from serial.tools.list_ports import comports
    plans.require(sum(p.device==args.port and p.serial_number==args.usb_serial for p in comports())==1,'Port/USB identity mismatch')
    plans.require(not out.exists(),'Use a fresh --out receipt directory');out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    import serial_test_coordination as coordination
    coordination.ROOT=args.coordination_root.resolve()
    with coordination.serial_lease('debugger-board-test-'+args.board,timeout=30):
        with (out/'serial.jsonl').open('x') as log:
            link=wire.Link(args.port,log)
            try:yield link
            finally:link.serial.close()


def run(args):
    manifest=plans.package(HERE);info=None
    if args.operation in ('execute','verify-flash'):
        plans.require(args.plan,'--plan required');info=plans.verify(HERE,args.plan)
        plans.require((info['board'],info['usb_serial'])==(args.board,args.usb_serial),'Plan board/USB differs')
    if args.operation=='execute':plans.require(args.experimental,'Execution requires --experimental; no port opened')
    archive=None
    if args.operation=='restore-ram':
        plans.require(args.archive,'--archive required');archive,_=plans.capture(args.archive)
        plans.require((archive['board'],archive['usb_serial'])==(args.board,args.usb_serial),'Archive board/USB differs')
    state=dict(operation=args.operation,board=args.board,usb_serial=args.usb_serial,passed=False,
               experimental_board_test=True,native_debugging=False,flash_write_requested=args.operation=='execute',
               application_RAM_restore_pending=args.operation in ('execute','smoke'),physical_reset_pending=False,
               package_manifest_sha256=r.sha((HERE/'board-test-manifest.json').read_bytes()))
    with connection(args,args.out) as link:
        def checkpoint():save(args.out/'report.json',state)
        checkpoint()
        try:
            generation=(49 if info['direction']=='install' else 50) if args.operation=='execute' else args.expected_generation
            state['version']=identity(link,args.board,generation);checkpoint()
            if args.operation=='capture':
                files={}
                for repeat in range(2):
                    for bank in range(4):
                        prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                        body=read_range(link,0x8000,0xFFFF,prompt);name=f'b{bank}'+('-repeat' if repeat else '')+'.bin'
                        if repeat:plans.require(body==(args.out/f'b{bank}.bin').read_bytes(),'Repeated flash reads differ')
                        (args.out/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
                link.command('B3');ram_end=int.from_bytes(link.dump(0x7D0A,0x7D0B),'little')
                plans.require(ram_end in (0x64FF,0x66FF),'Unknown application RAM limit')
                body=read_range(link,0x200,ram_end)
                plans.require(body==read_range(link,0x200,ram_end),'Repeated RAM archive reads differ')
                (args.out/'application-ram.bin').write_bytes(body)
                (args.out/'restore-application-ram.s19').write_bytes(wire.s19(dict(enumerate(body,0x200)),0x200))
                for name in ('application-ram.bin','restore-application-ram.s19'):
                    body=(args.out/name).read_bytes();files[name]=dict(bytes=len(body),sha256=r.sha(body))
                save(args.out/'capture.json',dict(schema=1,board=args.board,usb_serial=args.usb_serial,repeat_verified=True,files=files))
                plans.capture(args.out)
            elif args.operation=='execute':
                state['plan_sha256']=r.sha((args.plan/'plan.json').read_bytes());checkpoint()
                def progress(n,op):state['transfers_sent']=n;checkpoint()
                result=engine.execute(link,args.plan,stock=False,host_readback=True,progress=progress)
                state.update(result)
            elif args.operation=='verify-flash':
                for bank in range(4):
                    prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                    body=read_range(link,0x8000,0xFFFF,prompt)
                    plans.require(r.sha(body)==info['expected_sha256'][bank],f'B{bank} differs from transaction target')
                link.command('B3');state['all_four_flash_banks_verified']=True
            elif args.operation=='smoke':
                suite=r.read(HERE/'smoke/scenarios.json');completed=[]
                for test in suite['tests']:
                    # Verify cleanup after each test before loading the next one.
                    cells=load(link,HERE/test['image'])
                    for step in test['steps']:
                        prompt=b'DBG> ' if step['prompt']=='DBG' else b'\r\nB3> '
                        text=link.command(step['command'],prompt);check(step,text)
                    plans.require(link.dump(0x7BFC,0x7BFD)==b'\0\0','Debugger lifecycle did not clear')
                    plans.require(read_range(link,min(cells),max(cells))==bytes(cells[a] for a in sorted(cells)),
                                  'Breakpoint patches remain after HOLD/X')
                    completed.append(test['name']);state['smoke_tests_completed']=completed;checkpoint()
                state['breakpoint_hits_verified']=suite['breakpoint_hits_expected']
                state['smoke_program_bytes_restored']=True
            elif args.operation=='restore-ram':
                load(link,args.archive/'restore-application-ram.s19')
                body=(args.archive/'application-ram.bin').read_bytes()
                plans.require(read_range(link,0x200,0x200+len(body)-1)==body,'Restored application RAM differs')
                state['application_RAM_restore_pending']=False;state['RAM_restoration_host_verified']=True
            state['passed']=True;checkpoint()
        except BaseException:
            state['failure']=traceback.format_exc();state['inspection_required']=True;checkpoint();raise
    print('PASS',args.operation,'receipt:',args.out/'report.json')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation',choices=('capture','execute','verify-flash','smoke','restore-ram'))
    ap.add_argument('--port',required=True);ap.add_argument('--usb-serial',required=True);ap.add_argument('--board',required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--plan',type=Path);ap.add_argument('--archive',type=Path)
    ap.add_argument('--expected-generation',type=int,choices=(49,50),default=50)
    ap.add_argument('--experimental',action='store_true')
    ap.add_argument('--coordination-root',type=Path,default=HERE.parents[1]/'output/qualification/serial-coordination')
    run(ap.parse_args())


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,AssertionError) as error:raise SystemExit('REFUSED/FAILED: '+str(error))
