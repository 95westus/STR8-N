"""Leave the qualified FLASH example installed at B0:8; restore fresh owner RAM."""
import argparse
import time
import traceback
from pathlib import Path
import board_bank_monitor_2512 as prior

io = prior.io
ROOT, HERE, BUILD, FIRMWARE = prior.ROOT, prior.HERE, prior.BUILD, prior.FIRMWARE
SOURCE = ROOT/'output/qualification/FLASH-2512-install-edit-restore-20261027-r2'
AUTH = ('Reinstall the FLASH example on 2512 at B0:8 and leave it installed so I can try it. '
        'Preserve the boot settings and owner RAM, and keep a backup of the original B0 image.')


def banks_before():
    return [(SOURCE/f'restored-full-flash-r2-b{n}.bin').read_bytes() for n in range(4)]


def guard(marker, run, pending=False):
    assert marker['board'] == '2512' and marker['firmware'] == '2.0proto b15'
    assert marker['monitor_generation'] == 0x8000000f
    assert marker['MON_A_present'] and marker['MON_B_present']
    assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('physical_reset_pending','owner_application_running',
        'power_off_reported','poweroff_pending_owner_confirmation','current_soak_worker_pid',
        'one_shot_collection_active','firmware_verification_pending','mon_restore_pending',
        'boot_settings_restore_pending','opaque_sector_restore_pending'))
    assert marker['current_physical_bank_sha256'] == dict(zip(('B0','B1','B2','B3'),map(io.sha,banks_before())))
    if pending:
        assert marker['flash_keep_run'] == str(run) and marker['application_RAM_restore_pending']
    else:
        assert not marker.get('block_snapshot') and not marker.get('application_RAM_restore_pending')


def admission():
    prior.admission()
    host = io.read(HERE/'flash-keep-host-tests.json')
    assert host['passed'] and not host['hardware'] and not host['serial_access']
    assert host['helper_sha256'] == io.sha(Path(__file__).read_bytes())
    assert host['checker_sha256'] == io.sha((HERE/'test_board_flash_keep_2512.py').read_bytes())
    old = io.read(SOURCE/'audited-results.json')
    assert old['passed'] and old['original_images_restored'] and old['owner_RAM_restored']


def checkpoint(run,state,phase,active=True):
    state.update(phase=phase,updated_utc=io.now()); io.save(run/'state.json',state)
    marker = io.read(io.MARKER)
    marker.update(state='flash-keep-'+phase,flash_keep_run=str(run),recovery_worker_active=active,
        block_snapshot=not state.get('passed',False),application_RAM_restore_pending=state['RAM_pending'],
        application_ram_restored=not state['RAM_pending'],
        firmware_verification_pending=state.get('verification_pending',False))
    io.save(io.MARKER,marker)


def capture(run):
    admission(); assert not run.exists()
    assert run.is_relative_to((ROOT/'output/qualification').resolve())
    run.mkdir(parents=True); (run/'.gitignore').write_text('*\n')
    io.save(run/'authorization.json',dict(owner_authorized=True,user_text=AUTH,board='2512',
        usb_serial=io.USB,target='B0:8',leave_installed=True,original_B0_backup_required=True,
        preserve_boot_settings=True,restore_owner_RAM=True,other_boards=False,RTC_writes=False,
        F_MON_writes=False,B0_9_writes=False,recorded_utc=io.now()))
    state = dict(passed=False,board='2512',RAM_pending=False,verification_pending=False,
                 leave_installed=True,physical_reset_used=False,RTC_writes=False)
    with io.serial_lease('FLASH-keep-2512-capture',timeout=30):
        marker = io.read(io.MARKER); guard(marker,run)
        io.durable(run/'marker-before.json',io.MARKER.read_bytes())
        link,log = io.open_link(run,'FLASH-keep-capture')
        try:
            io.durable(run/'initial-monitor.txt',prior.sync(link))
            assert link.dump(0x7d01,0x7d02) == b'\x02\x03'
            active = link.dump(0x7d30,0x7d30)[0]
            assert active in (0xa0,0xb0)
            state['initial_monitor'] = 'A' if active == 0xa0 else 'B'
            banks = banks_before(); sy = io.read(FIRMWARE/'symbols.json')
            info = io.read(FIRMWARE/'prototype-report.json')
            for address in (active<<8,0xf000):
                assert io.dump(link,address,address+4095) == banks[3][address-0x8000:address-0x7000]
            for label,a,n in (('BOOT_WORKER_IMAGE',0x7800,info['f']['worker_bytes']),
                              ('BOOT_VECTOR_IMAGE',0x7e20,info['f']['vectors_bytes'])):
                offset = sy['core/str8n-v2-boot'][label]-0xf000
                assert io.dump(link,a,a+n-1) == banks[3][-4096:][offset:offset+n]
            prompt = sy['core/monitor-a0' if active == 0xa0 else 'core/monitor-b0']['V2_PROMPT']
            assert prompt == (active<<8)+0x160
            shim = bytes.fromhex('78D8A9018D027D20797E4C')+prompt.to_bytes(2,'little')
            old = [link.dump(0x2000,0x200c) for _ in range(2)]; assert old[0] == old[1]
            io.durable(run/'shim-original.bin',old[0])
            state['RAM_pending'] = True; checkpoint(run,state,'escrow-before-console-shim')
            io.upload(link,0x2000,shim); assert link.command('G 2000').endswith(io.MON)
            assert link.dump(0x7d02,0x7d02) == b'\x01'
            ram = [io.dump(link,0x200,0x64ff) for _ in range(2)]; assert ram[0] == ram[1]
            owner = bytearray(ram[0]); owner[0x1e00:0x1e0d] = old[0]
            zp = [link.dump(0,0xdf) for _ in range(2)]; assert zp[0] == zp[1]
            io.durable(run/'owner-ram.bin',owner); io.durable(run/'owner-zp.bin',zp[0])
            io.durable(run/'restore-owner-ram.s19',io.s19(dict(enumerate(owner,0x200)),0x200))
            print('PASS fresh owner RAM/ZP captured twice',flush=True)
            for repeat in (1,2):
                observed = io.mon_flash(link); assert observed == banks
                for n,data in enumerate(observed): io.durable(run/f'source-r{repeat}-b{n}.bin',data)
                print('PASS fresh full flash read',repeat,flush=True)
            io.durable(run/'original-B0.bin',banks[0])
            io.durable(run/'original-B0-80.bin',banks[0][:4096])
            record = io.latest(banks)
            assert record[7] == ord('B') and record[13] == 15 and record[14:18] == bytes([8]*4)
            io.durable(run/'original-record.bin',record)
            io.save(run/'backup-manifest.json',dict(board='2512',usb_serial=io.USB,recorded_utc=io.now(),
                repeated_hardware_capture=True,original_B0=dict(file='original-B0.bin',bytes=32768,sha256=io.sha(banks[0])),
                overwritten_sector=dict(file='original-B0-80.bin',bank=0,address='8000',bytes=4096,sha256=io.sha(banks[0][:4096])),
                owner_RAM=dict(file='owner-ram.bin',range='0200-64FF',sha256=io.sha(owner)),
                owner_ZP=dict(file='owner-zp.bin',range='00-DF',sha256=io.sha(zp[0])),
                boot_record=dict(file='original-record.bin',sha256=io.sha(record)),
                restoration='Restore only B0:8 through a new preimage-checked journaled OIP1 operation; retain actual wear history.'))
            io.upload(link,0x2000,old[0]); assert io.dump(link,0x200,0x64ff) == owner
            state.update(capture_passed=True,original_bank_sha256=list(map(io.sha,banks)),
                owner_ram_sha256=io.sha(owner),owner_zp_sha256=io.sha(zp[0]))
            checkpoint(run,state,'captured-awaiting-model',active=False)
            print('PASS full original B0 backup durable; owner RAM restored; no flash changed',flush=True)
        except BaseException:
            state['error'] = traceback.format_exc(); checkpoint(run,state,'capture-stopped-preserve-escrow',active=False)
            if not state['RAM_pending']: io.save(io.MARKER,marker)
            raise
        finally:
            link.serial.close(); log.close()


def write_image(link,body,before):
    # The leave-installed authorization permits only one fixed B0:8 target.
    assert len(body) == len(before) == 4096
    assert body == (BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    return prior.opaque_write(link,0x80,body,before)


def install(run):
    admission()
    state = io.read(run/'state.json'); assert state['capture_passed'] and not state['verification_pending']
    proof = io.read(run/'live-model-proof.json')
    assert proof['passed'] and not proof['hardware'] and len(proof['cases']) == 2
    assert proof['helper_sha256'] == io.sha(Path(__file__).read_bytes())
    assert proof['checker_sha256'] == io.sha((HERE/'prepare_flash_keep_2512.py').read_bytes())
    for name,digest in proof['bindings'].items(): assert io.sha(Path(name).read_bytes()) == digest,name
    original = [(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    expected = [(run/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    owner,zp = (run/'owner-ram.bin').read_bytes(),(run/'owner-zp.bin').read_bytes()
    image = (BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    with io.serial_lease('FLASH-keep-2512-install',timeout=30):
        guard(io.read(io.MARKER),run,pending=True)
        link,log = io.open_link(run,'FLASH-keep-install')
        try:
            prior.sync(link)
            assert io.dump(link,0x200,0x64ff) == owner and link.dump(0,0xdf) == zp
            assert io.mon_flash(link) == original
            prior.to_recovery(link,run,'J3-S-install')
            prior.load_installer(link)
            io.durable(run/'OIP-original-8.bin',prior.opaque_read(link,0x80,original[0][:4096]))
            state['verification_pending'] = True; checkpoint(run,state,'before-B0-8-install')
            io.save(run/'install-B0-8.json',write_image(link,image,original[0][:4096]))
            io.durable(run/'OIP-installed-8.bin',prior.opaque_read(link,0x80,image))
            link.command('Q',io.REC)
            boot = link.command('0',prior.FLASH); io.durable(run/'FLASH-boot.txt',boot)
            assert b'FLASH / MAINT - b15 example\r\n' in boot
            help_text = link.command('?',prior.FLASH); io.durable(run/'FLASH-help.txt',help_text)
            assert b'F addr byte...' in help_text
            quit_text = link.command('Q',io.MON); io.durable(run/'FLASH-Q-to-B3.txt',quit_text)
            assert b'STR8-N 2.0proto b15 B3 65C02' in quit_text
            checkpoint(run,state,'FLASH-boot-help-Q-verified')
            print('PASS FLASH installed, read back, booted; help and Q to B3 verified',flush=True)
            prior.to_recovery(link,run,'J3-S-readback')
            io.raw_load(link,(io.SERVICE/'payload/mon-service-load.bin').read_bytes(),io.SVC)
            io.flash_service(link,run,'installed-full-flash',expected)
            assert prior.policy(io.latest(expected)) == prior.policy((run/'original-record.bin').read_bytes())
            state['verification_pending'] = False; checkpoint(run,state,'installed-flash-and-policy-verified')
            link.send(b'W'); packet = owner+io.crc(owner).to_bytes(2,'little')
            for off in range(0,len(packet),64):
                link.send(packet[off:off+64]); time.sleep(.01)
            assert link.until(io.SVC,30) == io.SVC
            for n in (1,2):
                ram = io.service_read(link,b'M',0x6300); observed_zp = io.service_read(link,b'Z',0xe0)
                io.durable(run/f'restored-owner-ram-r{n}.bin',ram)
                io.durable(run/f'restored-owner-zp-r{n}.bin',observed_zp)
                assert ram == owner and observed_zp == zp
            link.send(b'J'); boot = link.until(io.MON,40)
            io.durable(run/'final-default-B-boot.txt',boot)
            assert b'Boot : 6 5 4 3 2 1 0' in boot and b'STR8-N 2.0proto b15 B3 65C02' in boot
            assert link.dump(0x7d01,0x7d02) == b'\x02\x03' and link.dump(0x7d30,0x7d30) == b'\xb0'
            ram = io.dump(link,0x200,0x64ff); observed_zp = link.dump(0,0xdf)
            io.durable(run/'final-MON-owner-ram.bin',ram); io.durable(run/'final-MON-owner-zp.bin',observed_zp)
            assert ram == owner and observed_zp == zp
            state.update(passed=True,RAM_pending=False,FLASH_installed=True,FLASH_boot_help_Q_verified=True,
                owner_RAM_restored=True,owner_ZP_preserved=True,boot_settings_preserved=True,
                original_B0_backup_verified=True,final_console='BOTH',final_monitor='B',
                final_bank_sha256=list(map(io.sha,expected)))
            checkpoint(run,state,'completed',active=False)
            marker = io.read(io.MARKER)
            marker.update(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),map(io.sha,expected))),
                current_firmware_sha256=io.sha(b''.join(expected[1:])),application_RAM_restore_verified=True,
                FLASH_installed=dict(bank=0,entry='8000',bytes=4096,sha256=io.sha(image),run=str(run)),
                original_B0_backup=dict(path=str(run/'original-B0.bin'),sha256=io.sha(original[0])),
                last_preservation_report=str(run/'test-results.json'),last_RAM_preservation_receipt=str(run/'test-results.json'),
                last_recovery_report=str(run/'state.json'),last_recovery_scope='FLASH left installed at B0:8; boot settings/owner RAM preserved; original B0 backed up',
                reason='Owner requested FLASH left installed; verified boot/Q and restored fresh owner RAM/ZP; default MON B unchanged')
            io.save(io.MARKER,marker)
        except BaseException:
            state['error'] = traceback.format_exc(); checkpoint(run,state,'stopped-preserve-escrow',active=False)
            raise
        finally:
            link.serial.close(); log.close()
    state.update(serial_released=True,completed_utc=io.now()); io.save(run/'state.json',state)
    io.save(run/'test-results.json',dict(state,hardware=True,failures=0,
        helper_sha256=io.sha(Path(__file__).read_bytes()),model_proof_sha256=io.sha((run/'live-model-proof.json').read_bytes()),
        limits=['FLASH will borrow low RAM when the owner next launches it; fresh RAM escrow is retained',
                'No physical reset/power-cut or live ACIA electrical test','One new B0:8 wear reservation retained']))
    marker = io.read(io.MARKER)
    marker['completion_receipt'] = dict(path=str(run/'state.json'),sha256=io.sha((run/'state.json').read_bytes()))
    io.save(io.MARKER,marker)
    print('PASS FLASH remains installed at B0:8; settings/RAM preserved; original B0 backup kept; BOTH MON B; serial released',flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=('capture','install')); p.add_argument('--run',type=Path,required=True)
    x = p.parse_args(); (capture if x.stage == 'capture' else install)(x.run.resolve())
