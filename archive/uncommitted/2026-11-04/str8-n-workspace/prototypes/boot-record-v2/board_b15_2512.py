"""Explicit 2512 b14 -> b15 capture/install/test; preserve owner data and policy."""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path
import board_ram_config_2512 as io

ROOT,HERE=io.ROOT,io.HERE
BUILD=ROOT/'BUILD/pr04-b15-cancel-r3'
OLD=ROOT/'BUILD/pr04-b14-raw-r4'
SOURCE=ROOT/'output/qualification/ram-config-2512-20261026-r3'
MARKER=io.MARKER
DONE=b'MIGRATION VERIFIED; RESET VIA F'
OLD_DONE=b'MIGRATION VERIFIED; PRESS PHYSICAL RESET'
AUTH_TEXT=('Install b15 on 2512 and test Ctrl-C cancellation at SEND BIN, then verify a normal BIN load. '
           'Preserve the boot settings, opaque images, and owner RAM.')


def source_banks():return [(SOURCE/f'restored-settings-r2-b{n}.bin').read_bytes() for n in range(4)]


def guard(marker,run,pending=False):
    assert marker['board']=='2512' and marker['firmware']=='2.0proto b14' and marker['monitor_generation']==0x8000000e
    assert marker['current_physical_bank_sha256']==dict(zip(('B0','B1','B2','B3'),map(io.sha,source_banks())))
    assert marker['MON_A_present'] and marker['MON_B_present']
    assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('physical_reset_pending','owner_application_running','power_off_reported',
        'poweroff_pending_owner_confirmation','opaque_sector_restore_pending','mon_restore_pending',
        'boot_settings_restore_pending','one_shot_collection_active','current_soak_worker_pid'))
    if pending:assert marker['b15_run']==str(run) and marker['application_RAM_restore_pending']
    else:assert not marker['block_snapshot'] and not marker['application_RAM_restore_pending']


def checkpoint(run,state,phase,active=True):
    state.update(phase=phase,updated_utc=io.now());io.save(run/'state.json',state)
    marker=io.read(MARKER)
    marker.update(state='b15-'+phase,b15_run=str(run),installer_worker_active=active,
        block_snapshot=not state.get('passed',False),
        application_RAM_restore_pending=state.get('RAM_pending',False),
        application_ram_restored=not state.get('RAM_pending',False),
        firmware_verification_pending=state.get('firmware_pending',False),physical_reset_pending=False)
    io.save(MARKER,marker)


def host_proof():
    r=io.read(HERE/'b15-host-tests.json')
    assert r['passed'] and not r['hardware'] and not r['serial_access'] and r['checks']>=5
    assert r['helper_sha256']==io.sha(Path(__file__).read_bytes())
    assert r['checker_sha256']==io.sha((HERE/'test_board_b15_2512.py').read_bytes())


def capture(run):
    host_proof();assert not run.exists();run.mkdir(parents=True);(run/'.gitignore').write_text('*\n')
    state=dict(passed=False,board='2512',RAM_pending=False,firmware_pending=False,flash_written=False,physical_reset_used=False)
    io.save(run/'authorization.json',dict(owner_authorized=True,user_text=AUTH_TEXT,board='2512',usb_serial=io.USB,
        action='preserving b15 installation and raw cancellation/load test',F_MON_updates=True,
        preserve_boot_policy=True,preserve_opaque_images=True,preserve_owner_RAM=True,
        other_boards=False,RTC_writes=False,recorded_utc=io.now()))
    with io.serial_lease('b15-2512-fresh-capture',timeout=30):
        marker=io.read(MARKER);guard(marker,run)
        io.durable(run/'marker-before.json',MARKER.read_bytes())
        link,log=io.open_link(run,'b15-capture')
        try:
            io.durable(run/'initial-monitor.txt',io.sync_mon(link))
            assert link.dump(0x7d01,0x7d02)==b'\x02\x03' and link.dump(0x7d30,0x7d30)==b'\xb0'
            banks=source_banks();sy=io.read(OLD/'symbols.json');info=io.read(OLD/'prototype-report.json')
            for first in (0xb000,0xf000):assert io.dump(link,first,first+4095)==banks[3][first-0x8000:first-0x7000]
            for label,a,n in (('BOOT_WORKER_IMAGE',0x7800,info['f']['worker_bytes']),('BOOT_VECTOR_IMAGE',0x7e20,info['f']['vectors_bytes'])):
                off=sy['core/str8n-v2-boot'][label]-0xf000
                assert io.dump(link,a,a+n-1)==banks[3][-4096:][off:off+n]
            assert sy['core/monitor-b0']['V2_PROMPT']==0xb160
            shim=bytes.fromhex('78D8A9018D027D20797E4C60B1')
            original=[link.dump(0x2000,0x200c) for _ in range(2)];assert original[0]==original[1]
            io.durable(run/'shim-original.bin',original[0])
            state['RAM_pending']=True;checkpoint(run,state,'RAM-escrow-before-session-shim')
            io.upload(link,0x2000,shim);assert link.command('G 2000').endswith(io.MON)
            assert link.dump(0x7d02,0x7d02)==b'\x01'
            ram=[io.dump(link,0x200,0x64ff) for _ in range(2)];assert ram[0]==ram[1]
            owner=bytearray(ram[0]);owner[0x1e00:0x1e0d]=original[0]
            zp=[link.dump(0,0xdf) for _ in range(2)];assert zp[0]==zp[1]
            io.durable(run/'owner-ram.bin',owner);io.durable(run/'owner-zp.bin',zp[0])
            io.durable(run/'restore-owner-ram.s19',io.s19(dict(enumerate(owner,0x200)),0x200))
            for repeat in (1,2):
                observed=io.mon_flash(link);assert observed==banks
                for n,data in enumerate(observed):io.durable(run/f'source-r{repeat}-b{n}.bin',data)
            io.upload(link,0x2000,original[0]);assert io.dump(link,0x200,0x64ff)==owner
            record=io.latest(banks);io.durable(run/'original-record.bin',record)
            state.update(capture_passed=True,source_sha256=list(map(io.sha,banks)),
                owner_ram_sha256=io.sha(owner),owner_zp_sha256=io.sha(zp[0]),original_policy_hex=policy(record).hex())
            checkpoint(run,state,'captured-awaiting-qualified-plan',active=False)
            print('PASS fresh b14 source, repeated full flash and owner RAM/ZP escrow; FT-only MON B',flush=True)
        except BaseException:
            state['error']=traceback.format_exc();checkpoint(run,state,'capture-stopped-preserve-escrow',active=False)
            if not state['RAM_pending']:io.durable(MARKER,(run/'marker-before.json').read_bytes())
            raise
        finally:link.serial.close();log.close()


def policy(record):return record[7:8]+record[12:18]+record[22:30]


class RestartLink:
    """Reuse the existing transport, substituting only the completion token."""
    def __init__(self,link):self.link=link
    def __getattr__(self,name):return getattr(self.link,name)
    def until(self,token,seconds=45):return self.link.until(DONE if token==OLD_DONE else token,seconds)


def idle(link,seconds):
    assert not link.pending
    start=time.monotonic();seen=bytearray()
    while time.monotonic()-start<seconds:seen.extend(link.read(4096))
    assert not seen,'Unexpected output before the first BIN byte'
    return time.monotonic()-start


def cancel_ready(link,run,label,ending=b'\r',wait=0):
    link.send(b'L'+ending);assert link.until(b'SEND BIN\r\n')==b'L\r\nSEND BIN\r\n'
    waited=idle(link,wait) if wait else 0
    start=time.monotonic();link.send(b'\x03');out=link.until(io.REC,10)
    elapsed=time.monotonic()-start
    assert b'Recovery L A/B 0-3 C1/2/3 ?' in out and b'STR8-N' not in out
    assert elapsed<2
    io.durable(run/(label+'.txt'),out)
    io.save(run/(label+'.json'),dict(passed=True,hardware=True,first_byte_Ctrl_C=True,
        command_ending_hex=ending.hex(),initial_wait_seconds=waited,cancel_reply_seconds=elapsed))


def install(run):
    host_proof()
    plan=run/'plan';state=io.read(run/'state.json');proof=io.read(run/'live-model-proof.json')
    assert state['capture_passed'] and not state['flash_written']
    assert proof['passed'] and not proof['hardware'] and proof['helper_sha256']==io.sha(Path(__file__).read_bytes())
    assert proof['checker_sha256']==io.sha((HERE/'prepare_b15_2512.py').read_bytes())
    for name,digest in proof['bindings'].items():assert io.sha(Path(name).read_bytes())==digest,name
    original_ram=(run/'owner-ram.bin').read_bytes();original_zp=(run/'owner-zp.bin').read_bytes()
    expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    from installer.engine import install_transport
    with io.serial_lease('b15-2512-preserving-install-test',timeout=30):
        marker=io.read(MARKER);guard(marker,run,pending=True)
        link,log=io.open_link(run,'b15-install')
        try:
            io.sync_mon(link)
            assert io.dump(link,0x200,0x64ff)==original_ram and link.dump(0,0xdf)==original_zp
            assert io.mon_flash(link)==source_banks()
            state['firmware_pending']=True;checkpoint(run,state,'source-rechecked-before-programming')
            def progress(n,op):
                state.update(transfers_completed=n,last_target=f'B{op["bank"]}:{op["address"]:04X}')
                checkpoint(run,state,'programming-device-verified-transfers')
            result=install_transport.execute(RestartLink(link),plan,host_readback=True,progress=progress)
            state.update(flash_written=True,transaction_device_verified=result['transaction_device_verified'])
            boot=link.until(io.MON,40);io.durable(run/'first-b15-software-boot.txt',boot)
            assert b'Boot : 6 5 4 3 2 1 0' in boot and b'STR8-N 2.0proto b15 B3 65C02' in boot
            assert link.dump(0x7d30,0x7d30)==b'\xb0'
            checkpoint(run,state,'b15-default-B-software-boot-verified')
            before_cancel=io.dump(link,0x200,0x64ff);io.durable(run/'before-cancel-ram.bin',before_cancel)
            io.durable(run/'J3-S-for-cancel.txt',io.restart_S(link,b'J3\r'))
            link.command('C1',io.REC);cancel_ready(link,run,'Ctrl-C-USB-after-wait',wait=3.5)
            link.command('C3',io.REC);cancel_ready(link,run,'Ctrl-C-BOTH-CRLF',ending=b'\r\n')
            assert b'^C=cancel' in link.command('?',io.REC)
            selected=link.command('B',io.MON);assert b'2.0proto b15' in selected
            assert io.dump(link,0x200,0x64ff)==before_cancel,'Cancellation changed application RAM'
            assert link.dump(0,0xdf)==original_zp
            checkpoint(run,state,'Ctrl-C-cancelled-without-RAM-writes')
            io.durable(run/'J3-S-for-normal-BIN.txt',io.restart_S(link,b'J3\r'))
            link.command('C1',io.REC)
            app=ROOT/'BUILD/pr04-b14-ram-config-r1/payload/ram-config-offline.bin';body=app.read_bytes()
            io.raw_load(link,body,io.CFG)
            shown=link.command('B',io.CFG);io.durable(run/'normal-BIN-CONFIG-settings.txt',shown)
            assert b'DEFAULT=B\r\n' in shown and all(f'B{n} ON  ENTRY=8000\r\n'.encode() in shown for n in range(4))
            link.send(b'Q\r');boot=link.until(io.MON,40);io.durable(run/'normal-BIN-quit-b15-default-B.txt',boot)
            assert b'2.0proto b15' in boot
            sy=io.read(ROOT/'BUILD/pr04-b14-ram-config-r1/symbols.json')['core/ram-config']
            executed=bytearray(body);executed[sy['CONFIG_ROW']-0x200]=4
            observed=io.dump(link,0x200,0x1ff+len(body));io.durable(run/'normal-BIN-independent-RAM-readback.bin',observed)
            assert observed==executed,'Normal BIN executed image differs beyond known display byte'
            checkpoint(run,state,'normal-BIN-loaded-executed-and-independently-read-back')
            io.durable(run/'J3-S-for-preservation.txt',io.restart_S(link,b'J3\r'))
            link.command('C1',io.REC)
            io.raw_load(link,(io.SERVICE/'payload/mon-service-load.bin').read_bytes(),io.SVC)
            io.flash_service(link,run,'b15-device-final-flash',expected)
            assert policy(io.latest(expected))==policy((run/'original-record.bin').read_bytes())
            state['firmware_pending']=False;checkpoint(run,state,'full-flash-and-boot-policy-verified')
            packet=original_ram+io.crc(original_ram).to_bytes(2,'little');link.send(b'W')
            for off in range(0,len(packet),64):link.send(packet[off:off+64]);time.sleep(.01)
            assert link.until(io.SVC,30)==io.SVC
            for n in (1,2):
                ram=io.service_read(link,b'M',0x6300);zp=io.service_read(link,b'Z',0xe0)
                io.durable(run/f'restored-owner-ram-r{n}.bin',ram);io.durable(run/f'restored-owner-zp-r{n}.bin',zp)
                assert ram==original_ram and zp==original_zp
            link.send(b'J');boot=link.until(io.MON,40);io.durable(run/'final-b15-default-B-boot.txt',boot)
            assert b'Boot : 6 5 4 3 2 1 0' in boot and b'STR8-N 2.0proto b15 B3 65C02' in boot
            assert link.dump(0x7d01,0x7d02)==b'\x02\x03' and link.dump(0x7d30,0x7d30)==b'\xb0'
            ram=io.dump(link,0x200,0x64ff);zp=link.dump(0,0xdf)
            io.durable(run/'final-MON-owner-ram.bin',ram);io.durable(run/'final-MON-owner-zp.bin',zp)
            assert ram==original_ram and zp==original_zp
            state.update(passed=True,RAM_pending=False,firmware_pending=False,boot_policy_preserved=True,
                opaque_images_preserved=True,owner_RAM_restored=True,owner_ZP_preserved=True,
                final_console='BOTH',final_monitor='B',final_bank_sha256=list(map(io.sha,expected)),
                Ctrl_C_cancellation_verified=True,normal_BIN_verified=True,RTC_writes=False)
            checkpoint(run,state,'completed',active=False)
            marker=io.read(MARKER)
            marker.update(firmware='2.0proto b15',monitor_generation=0x8000000f,firmware_build=str(BUILD),
                current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),map(io.sha,expected))),
                current_firmware_sha256=io.sha(b''.join(expected[1:])),installer_run=str(run),installer_plan=str(plan),
                installer_plan_sha256=io.sha((plan/'plan.json').read_bytes()),
                last_preservation_report=str(run/'test-results.json'),last_RAM_preservation_receipt=str(run/'test-results.json'),
                last_recovery_report=str(run/'state.json'),application_RAM_restore_verified=True,
                physical_boot_status='Software restart after verified migration; no physical reset used',
                reason='b15 installed; Ctrl-C and normal BIN verified; original boot policy/opaque images/RAM preserved',
                completion_receipt=dict(path=str(run/'state.json'),sha256=io.sha((run/'state.json').read_bytes())))
            io.save(MARKER,marker)
            io.save(run/'test-results.json',dict(state,hardware=True,failures=0,serial_released=True,
                live_model_proof_sha256=io.sha((run/'live-model-proof.json').read_bytes()),
                planned_targets=['B3:A','B3:F','B3:B'],planned_erases=3,C_D_erases=0,
                limits=['Software restart only; no physical reset or power-cut test',
                    'Logical boot policy preserved; generation pins and conservative erase history advanced',
                    'FT245 hardware tests; no live ACIA electrical qualification']))
            print('PASS b15 installed on 2512; Ctrl-C and normal BIN passed; boot policy/opaque images/RAM/ZP preserved; BOTH MON B',flush=True)
        except BaseException:
            state['error']=traceback.format_exc();checkpoint(run,state,'stopped-preserve-escrow',active=False);raise
        finally:link.serial.close();log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('capture','install'));p.add_argument('--run',type=Path,required=True)
    x=p.parse_args();(capture if x.stage=='capture' else install)(x.run.resolve())
