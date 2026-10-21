"""One command for an exact-source, preserving RC1 upgrade to v1g.

Example: python upgrade.py --port COM5 --usb-serial A10MQGVHA --board 2604
                         --out PRIVATE-NEW-DIRECTORY
No manual source/profile/intermediate-release selection. A completed flashing
transaction requires the board's physical RESET button; USB control lines are
never used as reset. Already-current verification requires no reset or writes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE/'engine')]
import uniform_upgrade as plans
import board_link as board
import install_transport as engine
import legacy_transport as wire
import runtime as r
import serial_test_coordination as coordination

NOW=lambda:datetime.now(timezone.utc).isoformat()


def settle(link,quiet_seconds=.5,timeout_seconds=10):
    """Archive queued startup/command output; never let an old prompt satisfy a
    new identity request. Link.read has already written these bytes to the log.
    """
    deadline=time.monotonic()+timeout_seconds;quiet=time.monotonic()
    archived=bytearray(link.pending);link.pending.clear()
    while time.monotonic()<deadline:
        body=link.read(max(1,link.serial.in_waiting))
        if body:archived.extend(body);quiet=time.monotonic()
        elif time.monotonic()-quiet>=quiet_seconds:return bytes(archived)
    raise TimeoutError('Serial output did not settle; no source admission')


def establish_monitor(link):
    settle(link)
    reply=link.command('',b'> ')
    r.require(reply.endswith(b'\r\nB3> '),'Idle B3 monitor required; do not auto-exit an application/debugger')
    settle(link)
    return reply


def save(path,value):
    temporary=path.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def flash(link):
    result=[]
    try:
        for bankno in range(4):
            prompt=f'\r\nB{bankno}> '.encode();link.command(f'B{bankno}',prompt)
            result.append(board.read_range(link,0x8000,0xffff,prompt))
    finally:link.command('B3')
    return result


def capture(link,path,number,usb,*,beta4=False):
    path.mkdir();(path/'.gitignore').write_text('*\n')
    first=flash(link);second=flash(link)
    r.require(first==second,'Independent full four-bank captures differ')
    end=0x64ff if beta4 else int.from_bytes(link.dump(0x7d0a,0x7d0b),'little')
    r.require(end in (0x64ff,0x66ff),'Unknown application RAM limit')
    ram=board.read_range(link,0x200,end)
    r.require(ram==board.read_range(link,0x200,end),'Independent original application RAM captures differ')
    files={}
    for n,body in enumerate(first):
        for suffix in ('','-repeat'):
            name=f'b{n}{suffix}.bin';(path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
    for name,body in [('application-ram.bin',ram),('application-ram-repeat.bin',ram),('restore-application-ram.s19',wire.s19(dict(enumerate(ram,0x200)),0x200))]:
        (path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
    save(path/'capture.json',dict(schema=1,board=number,usb_serial=usb,repeat_verified=True,files=files))
    plans.read_capture(path)
    return first,ram


def identity(link,number,generation=None,*,beta4=False,require_bound_identity=False):
    text=link.command('VERSION')
    r.require((b'2.0b4' in text) if beta4 else b'2.0rc1' in text,'Wrong firmware')
    if require_bound_identity:r.require(('Board: '+number).encode() in text,'Wrong stored board identity')
    r.require(b'65C02' in text or b'65C816' in text,'Unsupported CPU')
    if generation is not None:
        for slot in ('A','B'):
            r.require(f'MONITOR {slot} gen {generation:08X} VALID'.encode() in text,'Wrong monitor generation/CRC')
    if not beta4:r.require(link.dump(0x7bfc,0x7bff)==bytes(4),'Active debugger lifecycle/registry: stop cleanly first')
    return text


def run(args,*,target='v1g',on_state=None,allow_flash=True,qualification=False):
    """The public CLI always uses v1g; qualification may supply a source fixture."""
    manifest=plans.package(HERE)
    r.require(qualification or manifest['hardware_qualified'] is True,'Development kit: physical qualification is pending; public installation disabled')
    r.require(args.board and args.usb_serial and args.port,'Explicit board/USB/port required')
    r.require(target in manifest['profiles'],'Unknown qualification target')
    out=args.out.resolve();r.require(not out.exists(),'Use a fresh private output directory')
    from serial.tools.list_ports import comports
    r.require(sum(p.device==args.port and p.serial_number==args.usb_serial for p in comports())==1,'Port/USB identity mismatch')
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    state=dict(passed=False,board=args.board,usb_serial=args.usb_serial,port=args.port,started_utc=NOW(),pid=os.getpid(),
               phase='entry',target_profile=target,native_debugging=False,RTC_drift_in_release_qualification=False,
               application_RAM_restore_pending=False,physical_reset_pending=False,flash_written=False,
               uniform_manifest_sha256=r.sha((HERE/'uniform-manifest.json').read_bytes()))
    def checkpoint(phase=None):
        if phase:state['phase']=phase
        save(out/'report.json',state)
        if on_state:on_state(dict(state))
    checkpoint()
    coordination.ROOT=args.coordination_root.resolve()
    with coordination.serial_lease('rc1-uniform-upgrade-'+args.board,timeout=60):
        with (out/'serial.jsonl').open('x') as log:
            link=wire.Link(args.port,log);borrowed=False;monitor_available=False
            try:
                # Never auto-exit a debugger/application or issue reset/pref commands.
                settle(link)
                link.send(b'\r')
                try:reply=link.until(b'> ',2)
                except TimeoutError:reply=b''
                stock=not reply
                beta4=False
                if stock:
                    link.pending.clear();link.serial.rts=True
                    print('WDC debugger identity probe armed; press physical RESET if the source is running a program.',flush=True)
                    source_identity=link.stock_info_after_reset(seconds=args.reset_timeout)
                    r.require(source_identity[:4] in (b'SXB2',b'SXB6'),'Unsupported WDC source identity')
                    state['stock_identity_hex']=source_identity.hex();refs={}
                else:
                    r.require(reply.endswith(b'\r\nB3> '),'Require idle B3 monitor; no board mutation performed')
                    settle(link)
                    version=link.command('VERSION');beta4=b'2.0b4' in version
                    state['version_before']=identity(link,args.board,beta4=beta4).decode('ascii')
                    cpu=link.dump(0x7d01,0x7d01)[0]
                    if not beta4:r.require(cpu in (2,0x16),'Only 65C02 / 65C816 E runtime supported')
                    state['CPU_descriptor']=cpu
                    state['active_page_before']=link.dump(0x7d30,0x7d30)[0]
                    refs={cmd:link.command(cmd) for cmd in ('C','P','W')}
                checkpoint('capturing')
                if stock:
                    import bootstrap_routes
                    banks,original_ram=bootstrap_routes.capture_stock(link,out/'before',args.board,args.usb_serial,save)
                else:banks,original_ram=capture(link,out/'before',args.board,args.usb_serial,beta4=beta4)
                info=plans.prepare(HERE,out/'before',out/'plan',target=target,accept_unknown_wear_history=getattr(args,'accept_unknown_wear_history',False),history=getattr(args,'history',None),metadata_escrow=getattr(args,'metadata_escrow',None))
                if stock:r.require(info['source_profile']==('wdcmonv2-65C816' if source_identity[:4]==b'SXB6' else 'wdcmonv2-65C02'),'WDC source identity/image CPU mismatch')
                state.update(action=info['action'],source_profile=info['source_profile'],plan_sha256=r.sha((out/'plan/plan.json').read_bytes()),
                             before_flash_sha256=r.hashes(banks),original_RAM_sha256=r.sha(original_ram),RAM_bytes=len(original_ram))
                if info['transaction'] is None:
                    r.require(flash(link)==banks,'Flash changed during no-write verification')
                    r.require(board.read_range(link,0x200,0x200+len(original_ram)-1)==original_ram,'RAM changed during no-write verification')
                    r.require({cmd:link.command(cmd) for cmd in refs}==refs,'C/P/W changed during no-write verification')
                    state.update(passed=True,already_current=True,all_four_banks_verified=True,application_RAM_unchanged=True,
                                 settings_unchanged=True,final_flash_sha256=r.hashes(banks),finished_utc=NOW())
                    checkpoint('completed-no-write');return state
                r.require(allow_flash,'Read-only qualification expected already-current firmware; no RAM/flash write performed')
                plans.verify(HERE,out/'plan')
                if stock:
                    r.require(link.stock_read(0x8000,32768)==banks[3],'Fresh WDC source differs')
                    r.require(link.stock_read(0x200,len(original_ram))==original_ram,'Fresh WDC RAM differs')
                else:
                    r.require(flash(link)==banks,'Fresh pre-execution source differs')
                    r.require(board.read_range(link,0x200,0x200+len(original_ram)-1)==original_ram,'Fresh pre-execution RAM differs')
                borrowed=True;monitor_available=False;state['application_RAM_restore_pending']=True
                checkpoint('installing')
                def progress(n,op):state['transfers_sent']=n;checkpoint()
                state.update(engine.execute(link,out/'plan',stock=stock,host_readback=True,progress=progress))
                state.update(flash_written=True,physical_reset_pending=True)
                checkpoint('awaiting-physical-reset')
                print('RESET REQUIRED:',args.board,'transaction verified. Press physical RESET; no rollback or intermediate release is needed.',flush=True)
                # Receive-only waiting: reset is never synthesized from USB lines.
                if stock:link.serial.rts=False
                boot=link.until(b'\r\nB3> ',args.reset_timeout)
                (out/'boot.txt').write_bytes(boot)
                r.require(b'STR8-N 2.0rc1' in boot,'Incomplete physical boot capture')
                state['physical_reset_pending']=False;monitor_available=True
                checkpoint('verifying-target')
                state['version_after']=identity(link,args.board,manifest['profiles'][target]['generation']).decode('ascii')
                expected=[(out/'plan'/f'expected-b{n}.bin').read_bytes() for n in range(4)]
                actual=flash(link);r.require(actual==expected,'Four-bank target readback differs')
                r.require(plans.identify(HERE,manifest,actual)==target,'Wrong exact target image')
                if not stock:
                    _,_,before_cfg,_=r.clean_journal(banks);_,_,after_cfg,_=r.clean_journal(actual)
                    r.require(before_cfg[8:15]==after_cfg[8:15] and before_cfg[21]==after_cfg[21],'Owner startup settings changed')
                    if not beta4:
                        r.require(before_cfg[15:17]==after_cfg[15:17],'Monitor preference changed')
                        r.require(link.dump(0x7d30,0x7d30)[0]==state['active_page_before'],'Active monitor changed')
                state.update(all_four_banks_verified=True,settings_unchanged=not stock and not beta4,settings_migrated_as_documented=True,final_flash_sha256=r.hashes(actual),
                             erase_order=info['transaction']['planned_erase_order'],transfers=state['transfers_completed'])
                state['checks_passed']=True
            except BaseException:
                state['failure']=traceback.format_exc();raise
            finally:
                if borrowed and monitor_available:
                    try:
                        board.load(link,out/'before/restore-application-ram.s19')
                        for _ in range(2):
                            r.require(board.read_range(link,0x200,0x200+len(original_ram)-1)==original_ram,'Full original RAM reread differs')
                        state.update(application_RAM_restore_pending=False,RAM_restored=True,full_RAM_rereads=2)
                    except BaseException:state['restoration_failure']=traceback.format_exc()
                state['passed']=bool(state.get('passed') or state.get('checks_passed')) and not any(k in state for k in ('failure','restoration_failure')) and not state['application_RAM_restore_pending'] and not state['physical_reset_pending']
                state['finished_utc']=NOW();checkpoint('completed' if state['passed'] else 'inspection-required');link.serial.close()
    r.require(state['passed'],'Upgrade failed; preserve private receipt/escrow and inspect pending restoration')
    return state


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('port','usb-serial','board'):ap.add_argument('--'+key,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--coordination-root',type=Path,default=HERE/'private-serial-coordination')
    ap.add_argument('--reset-timeout',type=int,default=900)
    ap.add_argument('--accept-unknown-wear-history',action='store_true',help='WDC source only: acknowledge a new tracked baseline, not lifetime wear')
    ap.add_argument('--history',type=Path,help='Optional owner-local board-bound conservative wear escrow for WDC migration')
    ap.add_argument('--metadata-escrow',type=Path,help='Optional private STR8-N metadata escrow from a verified prior capture')
    args=ap.parse_args();run(args)


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError) as error:raise SystemExit('REFUSED/FAILED: '+str(error))
