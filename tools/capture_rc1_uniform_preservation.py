"""Fresh repeated private flash/RAM/EEPROM/SRAM escrow for uniform qualification.

Only pinned preserving readers/mode observers execute in borrowed RAM. No flash,
EEPROM, RTC setter, SRAM initialization/format or native-mode test. Every
borrowed byte of application RAM is restored and completely reread twice.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import traceback
from datetime import datetime,timezone

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
BOARDS={'2604':('COM5','A10MQGVHA'),'2609':('COM8','A10MPQXCA')}
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--kit',type=Path,required=True)
    ap.add_argument('--board',choices=BOARDS,required=True);ap.add_argument('--label',default='original')
    args=ap.parse_args();run=args.run.resolve();kit=args.kit.resolve();assert run.is_relative_to(Q)
    auth=READ(run/'owner-authorization.json');assert auth['owner_authorized'] and args.board in auth['boards'] and not auth['native_debugging'] and not auth['RTC_drift_in_release_qualification']
    sys.path[:0]=[str(kit),str(kit/'engine')]
    import upgrade as u
    from qualify_v2_spi_storage import memory_request
    from qualify_v2_spi_install import read_application_s19
    from serial.tools.list_ports import comports
    u.plans.package(kit)
    port,usb=BOARDS[args.board];assert sum(p.device==port and p.serial_number==usb for p in comports())==1
    assert set(READ(Q/'active-rtc-campaign.json')['powered_off_boards'])=={'2205','2512'}
    marker_path=Q/'device-operations'/f'{args.board}.json';marker=READ(marker_path)
    assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped'] and not marker.get('physical_reset_pending')
    assert not marker.get('application_RAM_restore_pending') and not marker.get('current_soak_worker_pid') and not marker.get('register_edit_worker_active') and not marker.get('block_snapshot')
    out=run/args.board/args.label;assert not out.exists();out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    previous=out/'device-operation-before.json';u.save(previous,marker)
    report=dict(passed=False,board=args.board,pid=os.getpid(),label=args.label,started_utc=datetime.now(timezone.utc).isoformat(),
                native_debugging=False,RTC_drift_in_release_qualification=False,flash_written=False,persistent_devices_written=False,
                application_RAM_restore_pending=False,uniform_manifest_sha256=SHA(kit/'uniform-manifest.json'))
    def checkpoint(state):
        report['state']=state;u.save(out/'report.json',report)
        marker.update(state=state,uniform_upgrade_run=str(run),uniform_upgrade_worker_pid=os.getpid(),
            application_RAM_restore_pending=report['application_RAM_restore_pending'],block_snapshot=state not in ('preserving-capture-passed',),
            uniform_upgrade_worker_active=state not in ('preserving-capture-passed','inspection-required'))
        u.save(marker_path,marker)
    def clock(link):
        text=link.command('R CLOCK',b'CLOCK> ')+link.command('STATUS',b'CLOCK> ');link.command('Q')
        raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode())
        assert len(raw)==9 and raw[0]&128 and raw[3]&8
        return dict(control=raw[7],trim=raw[8],oscillator_running=True,backup_enabled=True)
    u.coordination.ROOT=Q/'serial-coordination';checkpoint('preserving-capture-entry')
    with u.coordination.serial_lease('rc1-uniform-preserving-capture-'+args.board,timeout=60):
        with (out/'serial.jsonl').open('x') as log:
            link=u.wire.Link(port,log);original=None
            try:
                u.establish_monitor(link)
                report['version']=u.identity(link,args.board,50,require_bound_identity=True).decode('ascii')
                report['active_page']=link.dump(0x7d30,0x7d30)[0]
                refs={cmd:link.command(cmd) for cmd in ('C','P','W')};report['status_sha256']={cmd:hashlib.sha256(body).hexdigest() for cmd,body in refs.items()}
                banks,original=u.capture(link,out/'capture',args.board,usb)
                report.update(flash_repeat_verified=True,all_four_bank_sha256=u.r.hashes(banks),original_RAM_sha256=hashlib.sha256(original).hexdigest(),application_RAM_restore_pending=True)
                checkpoint('preserving-reader-probes')
                report['clock_controls_before']=clock(link)
                for name,path,digest in [('eeprom',ROOT/'BUILD/v2-eeprom-inventory/probe.s19','afded41e146341f4ab28fb82cf03934d91a3e7dc7fcc466bff03a70506a98621'),
                                         ('SRAM',ROOT/'BUILD/v2-spi-resident/hardware-client/client.s19','e892f3175bb315b2be8db4a94317e41569f50a22de3f067eb74170595593c4fc')]:
                    cells,_=read_application_s19(path);assert hashlib.sha256(bytes(cells[i] for i in range(min(cells),max(cells)+1))).hexdigest()==digest
                    report[name+'_reader_sha256']=SHA(path)
                    u.board.load(link,path)
                    images=[]
                    for repeat in range(2):
                        if name=='eeprom':
                            link.command('G 2000');raw=link.dump(0x2400,0x2494)
                            assert raw[0x90]==0 and raw[0x91]==raw[0x92] and (raw[0x93]^raw[0x94])&raw[0x91]==0
                            image=raw[:137]
                        else:
                            blocks=[]
                            for block in range(16):
                                link.write_ram(0x3e20,b'\x01\x03\0');link.write_ram(0x3e00,memory_request(1,block*8192));link.command('G 2003')
                                reply=link.dump(0x3e10,0x3e38);assert reply[8:10]==b'\0\x40' and reply[0x23]==reply[0x24]
                                blocks.append(link.dump(0x4000,0x5fff));print('READ',args.board,name,repeat,block,flush=True)
                            image=b''.join(blocks)
                        (out/(name+('-repeat' if repeat else '')+'.bin')).write_bytes(image);images.append(image)
                    assert images[0]==images[1]
                    report[name+'_repeat_verified']=True;report[name+'_sha256']=hashlib.sha256(images[0]).hexdigest();checkpoint('preserving-reader-probes')
                if args.board=='2609':
                    observer=Q/'rc1-debugger-2609-boardtest-2026-10-19-030225Z/mode-observer';proof=READ(observer/'report.json')
                    assert proof['passed'] and not proof['enters_native_mode'] and SHA(observer/'mode.s19')==proof['s19_sha256']
                    u.board.load(link,observer/'mode.s19');link.command('G 2000');mode=link.dump(0x2440,0x244d)
                    assert mode[:6]==bytes.fromhex('160100000000') and mode[6]&12==4 and mode[7:12]==bytes.fromhex('0117040116') and mode[12]&1 and not mode[12]&8 and mode[13]==0xa5
                    report.update(E1_verified=True,mode_hex=mode.hex(),mode_observer_sha256=SHA(observer/'mode.s19'))
                report['clock_controls_after']=clock(link);assert report['clock_controls_after']==report['clock_controls_before']
                assert {cmd:link.command(cmd) for cmd in refs}==refs
                assert u.flash(link)==banks;report['flash_unchanged']=True
                report['checks_passed']=True
            except BaseException:report['failure']=traceback.format_exc();raise
            finally:
                try:
                    if original is not None:
                        u.board.load(link,out/'capture/restore-application-ram.s19')
                        for _ in range(2):assert u.board.read_range(link,0x200,0x200+len(original)-1)==original
                        report.update(application_RAM_restore_pending=False,full_RAM_rereads=2,RAM_restored=True)
                except BaseException:report['restoration_failure']=traceback.format_exc()
                report['passed']=bool(report.get('checks_passed')) and not report['application_RAM_restore_pending'] and not any(k in report for k in ('failure','restoration_failure'))
                report['finished_utc']=datetime.now(timezone.utc).isoformat();checkpoint('preserving-capture-passed' if report['passed'] else 'inspection-required');link.serial.close()
    assert report['passed'];print('PASS',args.board,'fresh repeated preserving escrow and full RAM restoration',flush=True)


if __name__=='__main__':main()
