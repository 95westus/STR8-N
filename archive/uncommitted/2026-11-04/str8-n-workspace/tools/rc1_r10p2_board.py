"""Preserving RC1 r10 p2 board adapter; explicit identity and shared lease."""
import argparse,json,sys
from datetime import datetime,timezone
from pathlib import Path
from installer import capture,workflow
from installer.common import board_profile,save
from installer.engine import legacy_transport as wire,runtime as r,install_transport as transport
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT/'tmp/migration-python'))

def marker_for(board):
    path=ROOT/f'output/qualification/device-operations/{board}.json';m=r.read(path)
    assert m['board']==board and not any(m.get(k) for k in ('block_snapshot','application_RAM_restore_pending','physical_reset_pending','owner_application_running','power_off_reported','poweroff_pending_owner_confirmation'))
    assert not any(value for key,value in m.items() if key.endswith('_worker_active'))
    return path,m

def execute_board(board,build,plan,folder,link):
    from prepare_rc1_r10p2 import verify
    from rc1_r10_board import recovery_test
    info=verify(build,plan);proof=r.read(plan/'model-proof.json');assert proof['passed'] and proof['board']==board and proof['plan_sha256']==r.sha((plan/'plan.json').read_bytes())
    assert proof['firmware_sha256']==info['firmware_sha256']
    for name in ('console-tests.json','debugger-test.json','debugger-test-65c816-e.json','generation-header-tests.json','console-edit-tests.json'):
        report=r.read(build/name);assert report['passed'] and report['firmware_sha256']==info['firmware_sha256'],name
    assert r.read(build/'asm-dev-tests.json')['passed']
    markerpath,marker=marker_for(board);profile=board_profile(board);assert info['usb_serial']==profile['usb_serial']
    identity,banks=capture.validate(plan/'capture',board);ram=(plan/'capture/application-ram.bin').read_bytes()
    save(folder/'owner-authorization.json',dict(owner_authorized=True,board=board,usb_serial=profile['usb_serial'],
        scope=('Update 2512 to the exact g0034 firmware on 2604/2609 and verify boot and J3 -> S recovery' if board=='2512' else
               'Apply F recovery fixes to the current RC1 on 2604/2609, retain later features, boot header 2.0rc1 gxxxx in hexadecimal'),
        plan_sha256=r.sha((plan/'plan.json').read_bytes()),firmware_sha256=info['firmware_sha256']))
    state=dict(board=board,passed=False,phase='fresh-source',flash_written=False,application_RAM_restore_pending=False,physical_reset_pending=False,
               firmware_build='rc1-r10p2-current',firmware_sha256=info['firmware_sha256'])
    borrowed=False;available=True
    def checkpoint(phase):
        state['phase']=phase;save(folder/'flash-report.json',state)
        marker.update(state='g0034-'+phase,installer_worker_active=not state.get('closed',False),installer_plan=str(plan),installer_run=str(folder),
            block_snapshot=borrowed and not state['passed'],application_RAM_restore_pending=state['application_RAM_restore_pending'],physical_reset_pending=state['physical_reset_pending'])
        if state['passed']:marker.update(firmware='2.0rc1 g0034',firmware_build='rc1-r10p2-current',monitor_generation=52,current_firmware_profile='rc1-r10p2-current',current_firmware_sha256=info['firmware_sha256'],application_ram_restored=True)
        save(markerpath,marker)
    try:
        assert link.command('').endswith(b'\r\nB3> ')
        text=link.command('VERSION');assert f'Board: {board}'.encode() in text and profile['cpu'].encode() in text
        source_generation=int.from_bytes(bytes.fromhex(info['transaction']['source_config'])[9:13],'little')
        assert all(f'MONITOR {slot} gen {source_generation:08X} VALID'.encode() in text for slot in ('A','B'))
        assert link.dump(0x7bfc,0x7bff)==bytes(4)
        assert workflow.flash(link)==banks and workflow.read_range(link,0x200,0x200+len(ram)-1)==ram
        state['active_monitor_before']=link.dump(0x7d30,0x7d30).hex();(folder/'version-before.txt').write_bytes(text)
        verify(build,plan);borrowed=True;available=False
        state.update(application_RAM_restore_pending=True,physical_reset_pending=True);checkpoint('installing')
        def progress(n,op):
            state.update(transfers_completed=n,last_destination=f'B{op["bank"]}:{op["address"]:04X}');checkpoint('installing');print('TRANSFER',board,n,state['last_destination'],flush=True)
        state.update(transport.execute(link,plan,progress=progress));state['flash_written']=True;checkpoint('awaiting-physical-reset')
        print('RESET REQUIRED:',board,'device-verified. Press '+('S2/RESB' if board=='2609' else 'main-board RESET')+' once; keep power on.',flush=True)
        boot=link.until(b'\r\nB3> ',1800);(folder/'boot-after-installer.txt').write_bytes(boot)
        assert b'STR8-N 2.0rc1 g0034' in boot
        available=True;state['physical_reset_pending']=False;checkpoint('verifying')
        text=link.command('VERSION');(folder/'version-after.txt').write_bytes(text)
        assert b'STR8-N 2.0rc1 g0034' in text and b'Build: rc1-r10p2-current' in text
        assert all(f'MONITOR {slot} gen 00000034 VALID'.encode() in text for slot in ('A','B'))
        expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)];actual=workflow.flash(link);assert actual==expected
        assert actual[0]==banks[0] and actual[3][0x1000:0x2000]==banks[3][0x1000:0x2000]
        oldcfg=r.clean_journal(banks)[2][8:24];cfg=r.clean_journal(actual)[2][8:24]
        assert oldcfg[:9]==cfg[:9] and oldcfg[13]==cfg[13] and link.dump(0x7d30,0x7d30).hex()==state['active_monitor_before']
        state.update(checks_passed=True,all_four_banks_verified=True,owner_settings_preserved=True,RTC_TZ_sector_preserved=True,B0_preserved=True,final_flash_sha256=r.hashes(actual))
    except BaseException:
        import traceback
        state['failure']=traceback.format_exc();raise
    finally:
        if borrowed and available:
            try:workflow.restore_ram(link,plan/'capture');state.update(application_RAM_restore_pending=False,RAM_restored=True,full_RAM_rereads=2)
            except BaseException:
                import traceback
                state['restoration_failure']=traceback.format_exc()
        state['passed']=bool(state.get('checks_passed')) and not any(k in state for k in ('failure','restoration_failure')) and not state['application_RAM_restore_pending'] and not state['physical_reset_pending']
        state['closed']=True;state['finished_utc']=datetime.now(timezone.utc).isoformat();checkpoint('installed' if state['passed'] else 'inspection-required')
    assert state['passed'];print('PASS installed/boot/RAM',board,flush=True)
    marker.update(state='g0034-recovery-test',block_snapshot=True,recovery_worker_active=True);save(markerpath,marker)
    try:recovery_test(plan,folder/'recovery',link,board=board,identity='rc1-r10p2-current',generation=52,header=b'STR8-N 2.0rc1 g0034')
    except BaseException:
        marker.update(state='g0034-recovery-inspection-required',recovery_worker_active=False);save(markerpath,marker);raise
    marker.update(state='g0034-recovery-verified',block_snapshot=False,recovery_worker_active=False,last_recovery_report=str(folder/'recovery/recovery-report.json'));save(markerpath,marker)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('capture','execute'));p.add_argument('--board',choices=('2512','2604','2609'),action='append',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--build',type=Path);p.add_argument('--plan',type=Path);a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    if a.action=='execute':assert len(a.board)==1 and a.build and a.plan
    final=r.read(ROOT/'output/qualification/rtc-campaign-snapshot-2026-10-23-154431Z/summary.json');assert final['passed'] and final['ports_released']
    from serial.tools.list_ports import comports
    with serial_lease('rc1-r10p2-'+a.action,timeout=30):
        for board in a.board:
            marker_for(board);profile=board_profile(board);ports=[x for x in comports() if x.serial_number==profile['usb_serial']];assert len(ports)==1
            folder=out/board;folder.mkdir()
            with (folder/'serial.jsonl').open('w') as log:
                link=wire.Link(ports[0].device,log)
                try:
                    if a.action=='execute':execute_board(board,a.build.resolve(),a.plan.resolve(),folder,link);continue
                    assert link.command('').endswith(b'\r\nB3> ')
                    version=link.command('VERSION');assert f'Board: {board}'.encode() in version and profile['cpu'].encode() in version and b'2.0rc1' in version
                    assert link.dump(0x7bfc,0x7bff)==bytes(4),'Debugger active'
                    (folder/'version-before.txt').write_bytes(version)
                    banks=workflow.flash(link);assert workflow.flash(link)==banks
                    end=int.from_bytes(link.dump(0x7d0a,0x7d0b),'little');assert end in (0x64ff,0x66ff)
                    ram=workflow.read_range(link,0x200,end);assert workflow.read_range(link,0x200,end)==ram
                    capture.write(folder/'capture',profile,banks,ram)
                    save(folder/'capture-report.json',dict(passed=True,board=board,usb_serial=profile['usb_serial'],flash_written=False,ram_written=False,
                        repeat_flash=True,repeat_ram=True,application_ram_bytes=len(ram),flash_sha256=r.hashes(banks),completed_utc=datetime.now(timezone.utc).isoformat()))
                    print('PASS repeated preserving capture',board,flush=True)
                finally:link.serial.close()

if __name__=='__main__':main()
