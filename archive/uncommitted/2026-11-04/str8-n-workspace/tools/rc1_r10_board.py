"""Explicit 2512 RC1 r10 escrow/qualification adapter. Never auto-resets USB."""
import argparse,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
from installer import workflow
from installer.engine import legacy_transport as wire,runtime as r,install_transport as transport
from installer.common import save,inventory
from serial_test_coordination import serial_lease

ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT/'tmp/migration-python'))

def validate_capture(path):
    path=Path(path);m=r.read(path/'capture.json')
    assert m['repeat_verified'] and m['hardware_capture'] and not m['synthetic_model_fixture']
    assert (m['board'],m['usb_serial'])==('2512','A10MQFLCA')
    for name,info in m['files'].items():
        f=(path/name).resolve();assert f.is_relative_to(path.resolve())
        data=f.read_bytes();assert len(data)==info['bytes'] and r.sha(data)==info['sha256']
    banks=[]
    for n in range(4):
        data=(path/f'b{n}.bin').read_bytes();assert len(data)==32768 and data==(path/f'b{n}-repeat.bin').read_bytes();banks.append(data)
    ram=(path/'application-ram.bin').read_bytes()
    assert len(ram) in (0x6300,0x6500) and ram==(path/'application-ram-repeat.bin').read_bytes()
    assert (path/'restore-application-ram.s19').read_bytes()==wire.s19(dict(enumerate(ram,0x200)),0x200)
    r.clean_journal(banks)
    return banks,ram

def write_capture(path,banks,ram):
    assert not path.exists();path.mkdir();(path/'.gitignore').write_text('*\n')
    for n,data in enumerate(banks):
        for suffix in ('','-repeat'):(path/f'b{n}{suffix}.bin').write_bytes(data)
    for name in ('application-ram.bin','application-ram-repeat.bin'):(path/name).write_bytes(ram)
    (path/'restore-application-ram.s19').write_bytes(wire.s19(dict(enumerate(ram,0x200)),0x200))
    save(path/'capture.json',dict(schema=1,board='2512',usb_serial='A10MQFLCA',repeat_verified=True,
         synthetic_model_fixture=False,hardware_capture=True,files=inventory(path)))
    validate_capture(path)

def execute(build,plan,out,link,marker,marker_path):
    from prepare_rc1_r10_2512 import verify
    info=verify(build,plan);proof=r.read(plan/'model-proof.json')
    assert proof['passed'] and proof['plan_sha256']==r.sha((plan/'plan.json').read_bytes()) and proof['firmware_sha256']==info['firmware_sha256']
    for name in ('console-tests.json','debugger-test.json','debugger-test-65c816-e.json'):
        test=r.read(build/name);assert test['passed'] and test['firmware_sha256']==info['firmware_sha256']
    assert not out.exists();out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    save(out/'owner-authorization.json',dict(owner_authorized=True,board='2512',usb_serial='A10MQFLCA',
         scope='After drift ends install RC1 r10 with new firmware identity, verify boot and J3 -> S without physical reset; assess only 2604/2609',
         plan_sha256=r.sha((plan/'plan.json').read_bytes()),firmware_sha256=info['firmware_sha256']))
    state=dict(board='2512',passed=False,phase='fresh-source',flash_written=False,application_RAM_restore_pending=False,physical_reset_pending=False)
    available=True;borrowed=False
    def checkpoint(phase):
        state['phase']=phase;save(out/'flash-report.json',state)
        marker.update(state='rc1-r10-'+phase,installer_worker_active=not state.get('closed',False),
            installer_plan=str(plan.resolve()),installer_run=str(out.resolve()),
            block_snapshot=borrowed and not state.get('passed',False),application_RAM_restore_pending=state['application_RAM_restore_pending'],
            physical_reset_pending=state['physical_reset_pending'])
        if state.get('passed'):
            marker.update(firmware='2.0rc1',firmware_build='rc1-r10-recovery1',monitor_generation=51,
                          current_firmware_profile='RC1 r10',application_ram_restored=True)
        save(marker_path,marker)
    try:
        assert link.command('').endswith(b'\r\nB3> ')
        before=link.command('VERSION');assert b'Board: 2512' in before and b'2.0bf1' in before and b'65C02' in before
        banks,ram=validate_capture(plan/'capture')
        assert workflow.flash(link)==banks and workflow.read_range(link,0x200,0x200+len(ram)-1)==ram
        state['active_monitor_before']=link.dump(0x7d30,0x7d30).hex()
        (out/'version-before.txt').write_bytes(before)
        verify(build,plan)
        borrowed=True;available=False;state.update(application_RAM_restore_pending=True,physical_reset_pending=True)
        checkpoint('installing')
        def progress(n,op):
            state.update(transfers_completed=n,last_destination=f'B{op["bank"]}:{op["address"]:04X}');checkpoint('installing')
            print('TRANSFER',n,state['last_destination'],flush=True)
        state.update(transport.execute(link,plan,progress=progress));state['flash_written']=True;checkpoint('awaiting-physical-reset')
        print('RESET REQUIRED: 2512 transaction device-verified. Press main-board RESET once; do not power cycle.',flush=True)
        boot=link.until(b'\r\nB3> ',1800);(out/'boot-after-installer.txt').write_bytes(boot)
        assert b'STR8-N 2.0rc1' in boot
        available=True;state['physical_reset_pending']=False;checkpoint('verifying')
        version=link.command('VERSION');(out/'version-after.txt').write_bytes(version)
        assert b'Build: rc1-r10-recovery1' in version and b'Board: 2512' in version
        assert all(f'MONITOR {slot} gen 00000033 VALID'.encode() in version for slot in ('A','B'))
        expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        actual=workflow.flash(link);assert actual==expected
        assert actual[0]==banks[0] and actual[3][0x1000:0x2000]==banks[3][0x1000:0x2000]
        cfg=r.clean_journal(actual)[2][8:24];oldcfg=r.clean_journal(banks)[2][8:24]
        assert cfg[:9]==oldcfg[:9] and cfg[13]==oldcfg[13]
        assert link.dump(0x7d30,0x7d30).hex()==state['active_monitor_before']
        state.update(checks_passed=True,all_four_banks_verified=True,owner_settings_preserved=True,RTC_TZ_sector_preserved=True,
            B0_preserved=True,final_flash_sha256=r.hashes(actual))
    except BaseException:
        import traceback
        state['failure']=traceback.format_exc();raise
    finally:
        if borrowed and available:
            try:
                workflow.restore_ram(link,plan/'capture');state.update(application_RAM_restore_pending=False,RAM_restored=True,full_RAM_rereads=2)
            except BaseException:
                import traceback
                state['restoration_failure']=traceback.format_exc()
        state['passed']=bool(state.get('checks_passed')) and not any(k in state for k in ('failure','restoration_failure')) and not state['application_RAM_restore_pending'] and not state['physical_reset_pending']
        state['closed']=True;state['finished_utc']=datetime.now(timezone.utc).isoformat();checkpoint('installed' if state['passed'] else 'inspection-required')
    assert state['passed'];print('PASS 2512 RC1 r10 full flash, boot, settings and RAM verified',flush=True)

def recovery_test(plan,out,link,*,board='2512',identity='rc1-r10-recovery1',generation=51,header=b'STR8-N 2.0rc1'):
    assert not out.exists();out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    if board=='2512':_,ram=validate_capture(plan/'capture')
    else:
        from installer.capture import validate
        validate(plan/'capture',board);ram=(plan/'capture/application-ram.bin').read_bytes()
    assert workflow.flash(link)==expected and workflow.read_range(link,0x200,0x200+len(ram)-1)==ram
    initial=link.command('VERSION');assert ('Build: '+identity).encode() in initial
    active=link.dump(0x7d30,0x7d30)[0];assert active in (0xa0,0xb0)
    active_letter='A' if active==0xa0 else 'B';other_letter='B' if active==0xa0 else 'A'
    cfg=r.clean_journal(expected)[2][8:24];assert cfg[7]==ord('P') and cfg[8]==active
    rows=[]
    def record(name,data):
        (out/(name+'.txt')).write_bytes(data);rows.append(dict(test=name,passed=True))
    link.send(b'J3\r');boot=link.until(b'A/B/S,Enter default [3s]: ')
    link.send(b'S');rec=link.until(b'REC> ')
    assert b'FIXED F RECOVERY' in rec;record('J3-S-software-entry',boot+rec)
    for ending,label in ((b'\r','CR'),(b'\n','LF'),(b'\r\n','CRLF')):
        cmd=('u '+active_letter.lower()).encode();link.send(cmd+ending);reply=link.until(b'REC> ')
        assert cmd+b'\r\nREFUSED: active slot' in reply;record('active-slot-echo-'+label,reply)
        cmd=('U '+other_letter).encode();link.send(cmd+ending);reply=link.until(b'Y then Enter> ')
        assert cmd+b'\r\n' in reply
        link.send(b'N'+ending);reply+=link.until(b'REC> ')
        assert b'N\r\nREFUSED: cancelled' in reply and b'SEND 4096' not in reply;record('confirmation-cancel-'+label,reply)
    link.send(b'U\r\n');reply=link.until(b'REC> ')
    assert b'REFUSED: use A/B/W/U A|B' in reply;record('syntax-reason',reply)
    link.send(b'W\r\n');reply=link.until(b'REC> ')
    counts=r.clean_journal(expected)[2][24:120]
    for n in range(32):
        text=f'B{n//8}:{8+n%8:X} {int.from_bytes(counts[3*n:3*n+3],"little"):06X}'.encode()
        assert text in reply,text
    record('wear-map-32-counts',reply)
    # Leave recovery through valid A, then use another software restart to
    # confirm the saved B preference. No physical reset occurs in these tests.
    link.send((other_letter+'\r').encode());reply=link.until(b'\r\nB3> ');version=link.command('VERSION')
    assert f'Running: MONITOR {other_letter}, gen {generation:08X}'.encode() in version;record('recovery-'+other_letter+'-launch',reply+version)
    link.send(b'J3\r');reply=link.until(b'A/B/S,Enter default [3s]: ')
    link.send(b'\r');reply+=link.until(b'\r\nB3> ');version=link.command('VERSION')
    assert header in reply and f'Running: MONITOR {active_letter}, gen {generation:08X}'.encode() in version;record('J3-default-'+active_letter+'-boot',reply+version)
    assert workflow.flash(link)==expected
    assert workflow.read_range(link,0x200,0x200+len(ram)-1)==ram
    assert workflow.read_range(link,0x200,0x200+len(ram)-1)==ram
    save(out/'recovery-report.json',dict(passed=True,board=board,build=identity,generation=generation,physical_reset_during_test=False,
        flash_unchanged=True,application_ram_unchanged=True,full_ram_rereads=2,checks=len(rows),cases=rows,
        successful_Y_binary_transition='CPU-model tested; live confirmation deliberately cancelled before any slot upload',
        completed_utc=datetime.now(timezone.utc).isoformat()))
    print('PASS',board,'J3 -> S recovery, both slot launches, CR/LF/CRLF echo/cancel/reasons, exact wear, no physical reset',flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('capture','validate-capture','execute','recovery'))
    p.add_argument('--out',type=Path,required=True);p.add_argument('--build',type=Path);p.add_argument('--plan',type=Path);args=p.parse_args()
    if args.action=='validate-capture':
        banks,ram=validate_capture(args.out/'capture')
        save(args.out/'capture-report.json',dict(passed=True,board='2512',usb_serial='A10MQFLCA',flash_written=False,ram_written=False,
             repeat_flash=True,repeat_ram=True,application_ram_bytes=len(ram),flash_sha256=r.hashes(banks),
             completed_utc=datetime.now(timezone.utc).isoformat(),scope='offline verification of already saved repeated hardware captures',
             prior_helper_failure='Generic installer board registry excludes 2512; original repeated captures retained.'))
        print('PASS verified 2512 repeated hardware capture',flush=True);return
    assert datetime.now(timezone.utc)>=datetime(2026,10,23,15,45,tzinfo=timezone.utc)
    final=r.read(ROOT/'output/qualification/rtc-campaign-snapshot-2026-10-23-154431Z/summary.json')
    assert final['passed'] and final['ports_released'] and all(b['application_ram_restored'] for b in final['boards'])
    marker=r.read(ROOT/'output/qualification/device-operations/2512.json')
    assert not any(marker.get(k) for k in ('block_snapshot','application_RAM_restore_pending','physical_reset_pending','owner_application_running','installer_worker_active'))
    from serial.tools.list_ports import comports
    matches=[x for x in comports() if x.serial_number=='A10MQFLCA'];assert len(matches)==1
    port=matches[0].device;out=args.out.resolve();assert not out.exists();out.mkdir(parents=True)
    (out/'.gitignore').write_text('*\n')
    with serial_lease('rc1-r10-2512-'+args.action,timeout=20), (out/'serial.jsonl').open('w') as log:
        link=wire.Link(port,log)
        try:
            if args.action=='execute':
                assert args.build and args.plan
                execute(args.build.resolve(),args.plan.resolve(),out/'install',link,marker,ROOT/'output/qualification/device-operations/2512.json')
                return
            if args.action=='recovery':
                assert args.plan
                marker_path=ROOT/'output/qualification/device-operations/2512.json'
                marker.update(state='rc1-r10-recovery-test',block_snapshot=True,recovery_worker_active=True);save(marker_path,marker)
                try:recovery_test(args.plan.resolve(),out/'recovery',link)
                except BaseException:
                    marker.update(state='rc1-r10-recovery-inspection-required',recovery_worker_active=False);save(marker_path,marker);raise
                marker.update(state='rc1-r10-recovery-verified',block_snapshot=False,recovery_worker_active=False,
                    firmware='2.0rc1',firmware_build='rc1-r10-recovery1',monitor_generation=51,current_firmware_profile='RC1 r10',
                    last_recovery_report=str(out/'recovery/recovery-report.json'));save(marker_path,marker)
                return
            # No ESC/RESET/application exit: only an already-idle monitor.
            assert link.command('').endswith(b'\r\nB3> ')
            version=link.command('VERSION')
            assert b'Board: 2512' in version and b'65C02' in version
            assert b'2.0bf1' in version or b'2.0rc1' in version
            (out/'version-before.txt').write_bytes(version)
            active=link.dump(0x7d30,0x7d30).hex()
            first=workflow.flash(link);second=workflow.flash(link);assert first==second
            end=int.from_bytes(link.dump(0x7d0a,0x7d0b),'little');assert end in (0x64ff,0x66ff)
            ram=workflow.read_range(link,0x200,end);assert workflow.read_range(link,0x200,end)==ram
            write_capture(out/'capture',first,ram)
            save(out/'capture-report.json',dict(passed=True,board='2512',port=port,usb_serial='A10MQFLCA',active_monitor=active,
                flash_written=False,ram_written=False,repeat_flash=True,repeat_ram=True,application_ram_bytes=len(ram),
                flash_sha256=r.hashes(first),completed_utc=datetime.now(timezone.utc).isoformat()))
            print('PASS 2512 repeated full flash/RAM escrow',flush=True)
        finally:link.serial.close()

if __name__=='__main__':main()
