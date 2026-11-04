"""2512-only FLASH page install/edit/Q/restore with fresh escrow and CPU proof."""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path
import board_ram_config_2512 as io
import installer_build as protocol

ROOT, HERE = io.ROOT, io.HERE
BUILD = ROOT/'BUILD/b15-bank-monitor-r3'
FIRMWARE = ROOT/'BUILD/pr04-b15-cancel-r3'
SOURCE = ROOT/'output/qualification/b15-2512-install-20261026'
FLASH = b'FLASH> '
OI = b'INSTALLER I Q> '
HEADER = b'SEND OIP1 HEADER\r\n'
PAYLOAD = b'SEND 4096\r\n'
READ = b'READ SECTOR+CRC\r\n'
CONFIRM = b'00; type YES> '
AUTH = ('Install the B0:8 FLASH example on 2512, test RAM and flash editing plus Q back to B3>, '
        'then restore the original images, boot settings, and owner RAM.')


def banks_before():
    return [(SOURCE/f'b15-device-final-flash-r2-b{n}.bin').read_bytes() for n in range(4)]


def guard(marker, run, pending=False):
    assert marker['board'] == '2512' and marker['firmware'] == '2.0proto b15'
    assert marker['monitor_generation'] == 0x8000000f
    assert marker['MON_A_present'] and marker['MON_B_present']
    assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped']
    assert not any(v for k, v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('physical_reset_pending', 'owner_application_running',
        'power_off_reported', 'poweroff_pending_owner_confirmation', 'current_soak_worker_pid',
        'one_shot_collection_active', 'firmware_verification_pending', 'mon_restore_pending',
        'boot_settings_restore_pending'))
    if pending:
        assert marker['bank_monitor_run'] == str(run) and marker['application_RAM_restore_pending']
        assert not marker.get('opaque_sector_restore_pending'), 'Use retained recovery escrow after an interrupted test'
    else:
        assert not any(marker.get(k) for k in ('block_snapshot', 'application_RAM_restore_pending',
                                             'opaque_sector_restore_pending'))
        assert marker['current_physical_bank_sha256'] == dict(zip(('B0','B1','B2','B3'), map(io.sha, banks_before())))


def admission():
    host = io.read(HERE/'bank-monitor-host-tests.json')
    assert host['passed'] and not host['hardware'] and not host['serial_access']
    assert host['helper_sha256'] == io.sha(Path(__file__).read_bytes())
    assert host['checker_sha256'] == io.sha((HERE/'test_board_bank_monitor_2512.py').read_bytes())
    q = io.read(BUILD/'bank-monitor-qualification.json')
    r = io.read(BUILD/'bank-monitor-build.json')
    t = io.read(BUILD/'bank-monitor-tests.json')
    assert q['passed'] and not q['hardware'] and q['model_groups'] == 69
    assert q['build_report_sha256'] == io.sha((BUILD/'bank-monitor-build.json').read_bytes())
    assert q['model_report_sha256'] == io.sha((BUILD/'bank-monitor-tests.json').read_bytes())
    assert t['test_source_sha256'] == io.sha((HERE/'test_bank_monitor.py').read_bytes())
    for name, digest in r['source_hashes'].items():
        assert io.sha((HERE/name).read_bytes()) == digest
    for name, digest in q['reproduced_payloads'].items():
        assert io.sha((BUILD/'payload'/name).read_bytes()) == digest
    assert io.sha((io.SERVICE/'payload/mon-service-load.bin').read_bytes()) == '6833aae9c7eca2d343ac86cec7e6de8ced8464a3e27c6f5880fe621c43c57975'
    assert io.sha(banks_before()[3][-4096:]) == r['f_sha256']


def checkpoint(run, state, phase, active=True):
    state.update(phase=phase, updated_utc=io.now())
    io.save(run/'state.json', state)
    marker = io.read(io.MARKER)
    marker.update(state='bank-monitor-'+phase, bank_monitor_run=str(run), recovery_worker_active=active,
        block_snapshot=not state.get('passed', False),
        application_RAM_restore_pending=state.get('RAM_pending', False),
        application_ram_restored=not state.get('RAM_pending', False),
        opaque_sector_restore_pending=state.get('images_pending', False))
    io.save(io.MARKER, marker)


def sync(link):
    raw = bytearray(); start = last = time.monotonic()
    while time.monotonic()-last < .5:
        assert time.monotonic()-start < 15
        part = link.read(4096)
        if part:
            raw.extend(part); last = time.monotonic()
    assert not link.pending
    assert all(c in (8,9,10,13,127) or 32 <= c <= 126 for c in raw)
    link.send(b'\r')
    reply = bytearray(); deadline = time.monotonic()+5
    while not (reply.endswith(io.MON) or reply.endswith(io.REC)):
        assert time.monotonic() < deadline
        reply.extend(link.read(4096))
    if reply.endswith(io.REC):
        assert bytes(reply) in (b'\r\nREFUSED: command\r\nREC> ', b'\r\nREC> ')
        selected = link.command('B', io.MON)
        assert b'STR8-N 2.0proto b15 B3 65C02' in selected
        reply.extend(selected)
    else:
        assert bytes(reply) in (io.MON, b'\r\n'+io.MON)
    return bytes(raw)+reply


def capture(run):
    admission(); assert not run.exists()
    assert run.is_relative_to((ROOT/'output/qualification').resolve())
    run.mkdir(parents=True); (run/'.gitignore').write_text('*\n')
    io.save(run/'authorization.json', dict(owner_authorized=True, user_text=AUTH, board='2512',
        usb_serial=io.USB, install_sector='B0:8', temporary_flash_edit_sector='B0:9',
        restore_original_images=True, preserve_boot_policy=True, restore_owner_RAM=True,
        journal_wear_reservations=True, F_MON_writes=False, RTC_writes=False, other_boards=False,
        recorded_utc=io.now()))
    state = dict(passed=False, board='2512', RAM_pending=False, images_pending=False,
                 physical_reset_used=False, RTC_writes=False)
    with io.serial_lease('FLASH-example-2512-capture', timeout=30):
        marker = io.read(io.MARKER); guard(marker, run)
        io.durable(run/'marker-before.json', io.MARKER.read_bytes())
        link, log = io.open_link(run, 'FLASH-capture')
        try:
            io.durable(run/'initial-monitor.txt', sync(link))
            assert link.dump(0x7d01,0x7d02) == b'\x02\x03'
            assert link.dump(0x7d30,0x7d30) == b'\xb0'
            banks = banks_before()
            sy = io.read(FIRMWARE/'symbols.json'); info = io.read(FIRMWARE/'prototype-report.json')
            for address in (0xb000,0xf000):
                assert io.dump(link,address,address+4095) == banks[3][address-0x8000:address-0x7000]
            for label,a,n in (('BOOT_WORKER_IMAGE',0x7800,info['f']['worker_bytes']),
                              ('BOOT_VECTOR_IMAGE',0x7e20,info['f']['vectors_bytes'])):
                offset = sy['core/str8n-v2-boot'][label]-0xf000
                assert io.dump(link,a,a+n-1) == banks[3][-4096:][offset:offset+n]
            assert sy['core/monitor-b0']['V2_PROMPT'] == 0xb160
            shim = bytes.fromhex('78D8A9018D027D20797E4C60B1')
            old = [link.dump(0x2000,0x200c) for _ in range(2)]; assert old[0] == old[1]
            io.durable(run/'shim-original.bin', old[0])
            state['RAM_pending'] = True; checkpoint(run,state,'escrow-before-console-shim')
            io.upload(link,0x2000,shim); assert link.command('G 2000').endswith(io.MON)
            assert link.dump(0x7d02,0x7d02) == b'\x01'
            ram = [io.dump(link,0x200,0x64ff) for _ in range(2)]; assert ram[0] == ram[1]
            owner = bytearray(ram[0]); owner[0x1e00:0x1e0d] = old[0]
            zp = [link.dump(0,0xdf) for _ in range(2)]; assert zp[0] == zp[1]
            io.durable(run/'owner-ram.bin', owner); io.durable(run/'owner-zp.bin', zp[0])
            io.durable(run/'restore-owner-ram.s19', io.s19(dict(enumerate(owner,0x200)),0x200))
            print('PASS fresh repeated owner RAM/ZP escrow', flush=True)
            for repeat in (1,2):
                observed = io.mon_flash(link); assert observed == banks, 'Fresh source flash differs'
                for n,data in enumerate(observed): io.durable(run/f'source-r{repeat}-b{n}.bin',data)
                print('PASS fresh full flash read',repeat,flush=True)
            io.upload(link,0x2000,old[0]); assert io.dump(link,0x200,0x64ff) == owner
            record = io.latest(banks); assert record[7] == ord('B') and record[13] == 15 and record[14:18] == bytes([8]*4)
            io.durable(run/'original-record.bin',record)
            for sector in (0x80,0x90):
                offset = (sector-0x80)<<8
                io.durable(run/f'original-B0-{sector:02X}.bin',banks[0][offset:offset+4096])
            state.update(capture_passed=True, original_bank_sha256=list(map(io.sha,banks)),
                owner_ram_sha256=io.sha(owner), owner_zp_sha256=io.sha(zp[0]),
                original_policy_hex=policy(record).hex())
            checkpoint(run,state,'captured-awaiting-model',active=False)
            print('PASS fresh preserving capture; FT-only MON B; no flash changes',flush=True)
        except BaseException:
            state['error'] = traceback.format_exc(); checkpoint(run,state,'capture-stopped-preserve-escrow',active=False)
            if not state['RAM_pending']: io.save(io.MARKER,marker)
            raise
        finally:
            link.serial.close(); log.close()


def policy(record):
    return record[7:8]+record[12:30]+record[32:64]+record[160:252]


def begin(link):
    assert not link.pending
    assert link.command('I', HEADER) == b'I\r\n'+HEADER


def opaque_read(link, sector, expected):
    assert sector in (0x80,0x90) and len(expected) == 4096
    begin(link); link.send(protocol.frame_header(0,sector))
    assert link.until(READ,10) == READ
    data = io.exact(link,4098)
    assert data[:4096] == expected and io.crc(data[:4096]) == int.from_bytes(data[4096:],'little')
    assert link.until(OI,10) == b'\r\nOK: read\r\n'+OI
    return data


def opaque_write(link, sector, body, before):
    assert sector in (0x80,0x90) and len(body) == len(before) == 4096
    begin(link); link.send(protocol.frame_header(0,sector,body,io.crc(before)))
    assert link.until(PAYLOAD,10) == PAYLOAD
    for off in range(0,4096,64):
        link.send(body[off:off+64]); time.sleep(.01)
    reply = link.until(OI,45)
    assert reply == b'OK: verified sector\r\n'+OI
    return dict(passed=True, bank=0,sector=sector,sha256=io.sha(body),preimage_crc=io.crc(before),reply=reply.decode())


def to_recovery(link, run, label):
    io.durable(run/(label+'.txt'),io.restart_S(link,b'J3\r'))
    link.command('C1',io.REC)


def load_installer(link):
    io.raw_load(link,(BUILD/'payload/ram-installer-offline.bin').read_bytes(),OI)


def command(link, run, label, line, token=FLASH):
    out = link.command(line,token); io.durable(run/(label+'.txt'),out)
    return out


def run_test(run):
    admission()
    state = io.read(run/'state.json'); assert state['capture_passed'] and not state['images_pending']
    proof = io.read(run/'live-model-proof.json')
    assert proof['passed'] and not proof['hardware'] and {c['cpu'] for c in proof['cases']} == {'65c02','65c816-e'}
    assert proof['helper_sha256'] == io.sha(Path(__file__).read_bytes())
    assert proof['checker_sha256'] == io.sha((HERE/'prepare_bank_monitor_2512.py').read_bytes())
    for name,digest in proof['bindings'].items(): assert io.sha(Path(name).read_bytes()) == digest,name
    original_ram = (run/'owner-ram.bin').read_bytes(); original_zp = (run/'owner-zp.bin').read_bytes()
    original = [(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    installed = [(run/f'expected-edited-b{n}.bin').read_bytes() for n in range(4)]
    restored = [(run/f'expected-restored-b{n}.bin').read_bytes() for n in range(4)]
    image = (BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    edited = (run/'edited-B0-90.bin').read_bytes()
    with io.serial_lease('FLASH-example-2512-install-test-restore',timeout=30):
        guard(io.read(io.MARKER),run,pending=True)
        link,log = io.open_link(run,'FLASH-test')
        try:
            sync(link)
            assert io.dump(link,0x200,0x64ff) == original_ram and link.dump(0,0xdf) == original_zp
            assert io.mon_flash(link) == original
            to_recovery(link,run,'J3-S-before-install'); load_installer(link)
            io.durable(run/'OIP-original-8.bin',opaque_read(link,0x80,original[0][:4096]))
            io.durable(run/'OIP-original-9.bin',opaque_read(link,0x90,original[0][4096:8192]))
            state['images_pending'] = True; checkpoint(run,state,'before-B0-8-install')
            io.save(run/'install-B0-8.json',opaque_write(link,0x80,image,original[0][:4096]))
            io.durable(run/'OIP-installed-8.bin',opaque_read(link,0x80,image))
            link.command('Q',io.REC)
            boot = link.command('0',FLASH); io.durable(run/'FLASH-bank0-boot.txt',boot)
            assert b'FLASH / MAINT - b15 example\r\n' in boot and b'Q returns to MON\r\n' in boot
            state['FLASH_boot_verified'] = True; checkpoint(run,state,'FLASH-running')
            assert b'F addr byte...' in command(link,run,'FLASH-help','?')
            assert b'OK: RAM\r\n' in command(link,run,'RAM-edit','M 2000 41 42 03 00 FF')
            assert b'41 42 03 00 FF ' in command(link,run,'RAM-readback','D 2000')
            assert b'REFUSED:' in command(link,run,'RAM-protection','M 1FFF 55')
            assert b'REFUSED:' in command(link,run,'own-image-protection','F 8000 55')
            assert b'Data bank B0\r\n' in command(link,run,'select-B0','B0')
            assert command(link,run,'flash-edit-stage',proof['flash_edit_command'],CONFIRM).endswith(b'B0:9000; type YES> ')
            reply = command(link,run,'flash-edit-YES','YES')
            assert reply == b'YES\r\nOK: verified sector\r\n'+FLASH
            wanted = b' '.join(f'{v:02X}'.encode() for v in edited[:16])+b' '
            assert wanted in command(link,run,'flash-edit-readback','D 9000')
            assert command(link,run,'identical-stage',proof['flash_edit_command'],CONFIRM).endswith(CONFIRM)
            assert b'OK: identical; no erase\r\n' in command(link,run,'identical-YES','YES')
            state['flash_edit_verified'] = True
            reply = command(link,run,'FLASH-Q-to-B3','Q',io.MON)
            assert b'STR8-N 2.0proto b15 B3 65C02' in reply
            assert link.dump(0x7d30,0x7d30) == b'\xb0'
            assert link.dump(0x2000,0x2004) == b'AB\x03\x00\xff'
            state.update(RAM_edit_verified=True,Q_to_B3_verified=True)
            checkpoint(run,state,'edits-and-Q-verified')
            print('PASS live FLASH boot, RAM edit/readback, flash edit/no-op and Q to B3',flush=True)
            to_recovery(link,run,'J3-S-for-edited-readback')
            io.raw_load(link,(io.SERVICE/'payload/mon-service-load.bin').read_bytes(),io.SVC)
            io.flash_service(link,run,'edited-full-flash',installed)
            assert policy(io.latest(installed)) == policy((run/'original-record.bin').read_bytes())
            link.send(b'Q'); link.until(io.REC,10)
            load_installer(link); checkpoint(run,state,'before-original-images-restore')
            io.save(run/'restore-B0-9.json',opaque_write(link,0x90,original[0][4096:8192],edited))
            io.durable(run/'OIP-restored-9.bin',opaque_read(link,0x90,original[0][4096:8192]))
            io.save(run/'restore-B0-8.json',opaque_write(link,0x80,original[0][:4096],image))
            io.durable(run/'OIP-restored-8.bin',opaque_read(link,0x80,original[0][:4096]))
            state['images_pending'] = False; checkpoint(run,state,'original-images-restored')
            link.command('Q',io.REC)
            io.raw_load(link,(io.SERVICE/'payload/mon-service-load.bin').read_bytes(),io.SVC)
            io.flash_service(link,run,'restored-full-flash',restored)
            assert restored[:3] == original[:3]
            assert policy(io.latest(restored)) == policy((run/'original-record.bin').read_bytes())
            packet = original_ram+io.crc(original_ram).to_bytes(2,'little')
            link.send(b'W')
            for off in range(0,len(packet),64):
                link.send(packet[off:off+64]); time.sleep(.01)
            assert link.until(io.SVC,30) == io.SVC
            for n in (1,2):
                ram = io.service_read(link,b'M',0x6300); zp = io.service_read(link,b'Z',0xe0)
                io.durable(run/f'restored-owner-ram-r{n}.bin',ram)
                io.durable(run/f'restored-owner-zp-r{n}.bin',zp)
                assert ram == original_ram and zp == original_zp
            link.send(b'J'); boot = link.until(io.MON,40)
            io.durable(run/'final-default-B-boot.txt',boot)
            assert b'Boot : 6 5 4 3 2 1 0' in boot and b'STR8-N 2.0proto b15 B3 65C02' in boot
            assert link.dump(0x7d01,0x7d02) == b'\x02\x03' and link.dump(0x7d30,0x7d30) == b'\xb0'
            ram = io.dump(link,0x200,0x64ff); zp = link.dump(0,0xdf)
            io.durable(run/'final-MON-owner-ram.bin',ram); io.durable(run/'final-MON-owner-zp.bin',zp)
            assert ram == original_ram and zp == original_zp
            state.update(passed=True,RAM_pending=False,images_pending=False,owner_RAM_restored=True,
                owner_ZP_preserved=True,original_images_restored=True,boot_policy_preserved=True,
                final_console='BOTH',final_monitor='B',final_bank_sha256=list(map(io.sha,restored)))
            checkpoint(run,state,'completed',active=False)
            marker = io.read(io.MARKER)
            marker.update(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),map(io.sha,restored))),
                current_firmware_sha256=io.sha(b''.join(restored[1:])),application_RAM_restore_verified=True,
                last_preservation_report=str(run/'test-results.json'),last_RAM_preservation_receipt=str(run/'test-results.json'),
                last_recovery_report=str(run/'state.json'),
                reason='FLASH page installed/tested; B0:8/9 originals and fresh owner RAM/ZP restored; boot policy preserved',
                completion_receipt=dict(path=str(run/'state.json'),sha256=io.sha((run/'state.json').read_bytes())))
            io.save(io.MARKER,marker)
        except BaseException:
            state['error'] = traceback.format_exc(); checkpoint(run,state,'stopped-preserve-escrow',active=False)
            raise
        finally:
            link.serial.close(); log.close()
    state.update(serial_released=True,completed_utc=io.now()); io.save(run/'state.json',state)
    marker = io.read(io.MARKER)
    marker['completion_receipt'] = dict(path=str(run/'state.json'),sha256=io.sha((run/'state.json').read_bytes()))
    io.save(io.MARKER,marker)
    io.save(run/'test-results.json',dict(state,hardware=True,failures=0,
        model_proof_sha256=io.sha((run/'live-model-proof.json').read_bytes()),
        helper_sha256=io.sha(Path(__file__).read_bytes()),
        erase_targets=['B0:8 install','B0:9 edit','B0:9 restore','B0:8 restore'],
        limits=['FT245 hardware only; no live ACIA test','No physical reset or power-cut test',
                'Original boot settings restored; actual erase history retained in journal']))
    print('PASS original images/settings/owner RAM/ZP restored; BOTH MON B; serial released',flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=('capture','test')); p.add_argument('--run',type=Path,required=True)
    x = p.parse_args()
    (capture if x.stage == 'capture' else run_test)(x.run.resolve())
