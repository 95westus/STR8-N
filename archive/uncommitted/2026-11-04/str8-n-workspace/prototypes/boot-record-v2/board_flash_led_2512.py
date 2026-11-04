"""Preserving 2512 FLASH LED update; retain the owner's newly erased B0:9."""
import argparse
import time
import traceback
from pathlib import Path
import board_bank_monitor_2512 as wire

io, ROOT, HERE = wire.io, wire.ROOT, wire.HERE
BUILD = ROOT/'BUILD/b15-bank-monitor-led-r1'
OLD_BUILD = ROOT/'BUILD/b15-bank-monitor-r3'
PREVIOUS = ROOT/'output/qualification/FLASH-2512-keep-20261027-r3'
OLD_SHA = '900db634ce838aaf0cd85c53029377fe254ac4a4033d431a63d276da3f5902ec'


def guard(marker,run,pending=False):
    assert marker['board'] == '2512' and marker['firmware'] == '2.0proto b15'
    assert marker['MON_A_present'] and marker['MON_B_present']
    assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('one_shot_collection_active','physical_reset_pending',
        'owner_application_running','power_off_reported','poweroff_pending_owner_confirmation',
        'current_soak_worker_pid','mon_restore_pending','opaque_sector_restore_pending',
        'boot_settings_restore_pending','firmware_verification_pending'))
    assert marker['FLASH_installed']['sha256'] == OLD_SHA
    if pending:
        assert marker['flash_led_run'] == str(run) and marker['application_RAM_restore_pending']
    else:
        assert not marker.get('block_snapshot') and not marker.get('application_RAM_restore_pending')


def host_proof():
    p = io.read(HERE/'flash-led-host-tests.json')
    assert p['passed'] and not p['hardware'] and not p['serial_access']
    assert p['helper_sha256'] == io.sha(Path(__file__).read_bytes())
    assert p['checker_sha256'] == io.sha((HERE/'test_board_flash_led_2512.py').read_bytes())


def qualify():
    host_proof()
    q = io.read(BUILD/'bank-monitor-qualification.json')
    led = io.read(BUILD/'bank-monitor-led-tests.json')
    report = io.read(BUILD/'bank-monitor-build.json')
    assert q['passed'] and q['model_groups'] == 69
    assert led['passed'] and led['groups'] == 34
    assert led['checker_sha256'] == io.sha((HERE/'test_bank_monitor_leds.py').read_bytes())
    assert led['build_report_sha256'] == io.sha((BUILD/'bank-monitor-build.json').read_bytes())
    for name,digest in report['source_hashes'].items(): assert io.sha((HERE/name).read_bytes()) == digest
    for name,digest in q['reproduced_payloads'].items(): assert io.sha((BUILD/'payload'/name).read_bytes()) == digest


def checkpoint(run,state,phase,active=True):
    state.update(phase=phase,updated_utc=io.now()); io.save(run/'state.json',state)
    m = io.read(io.MARKER)
    m.update(state='flash-led-'+phase,flash_led_run=str(run),recovery_worker_active=active,
        block_snapshot=not state.get('passed',False),application_RAM_restore_pending=state['RAM_pending'],
        application_ram_restored=not state['RAM_pending'],firmware_verification_pending=state.get('verification_pending',False))
    io.save(io.MARKER,m)


def sync(link):
    raw = bytearray(); start = last = time.monotonic()
    while time.monotonic()-last < .5:
        assert time.monotonic()-start < 15
        part = link.read(4096)
        if part: raw.extend(part); last = time.monotonic()
    assert not link.pending and all(c in (8,9,10,13,127) or 32<=c<=126 for c in raw)
    link.send(b'\r'); out = bytearray(); deadline = time.monotonic()+8
    while not any(out.endswith(token) for token in (io.MON,io.REC,wire.FLASH)):
        assert time.monotonic() < deadline
        out.extend(link.read(4096))
    if out.endswith(wire.FLASH):
        assert bytes(out) == b'\r\nREFUSED: syntax (use ?)\r\n'+wire.FLASH
        out.extend(link.command('Q',io.MON))
        assert b'STR8-N 2.0proto b15 B3 65C02' in out
    elif out.endswith(io.REC):
        out.extend(link.command('B',io.MON))
        assert b'STR8-N 2.0proto b15 B3 65C02' in out
    else:
        assert bytes(out) in (io.MON,b'\r\n'+io.MON)
    return bytes(raw)+out


def owner_snapshot(current,previous):
    assert len(current) == len(previous) == 0x6300
    sy = io.read(OLD_BUILD/'symbols.json')['core/bank-monitor-8000']
    old = (OLD_BUILD/'payload/bank-monitor-8000-ram.bin').read_bytes()
    code_bytes = sy['BM_CODE_END']-0x200
    if current[:code_bytes] == old[:code_bytes]:
        # FLASH overwrote exactly this whole-page prefix on entry. Preserve
        # freshly captured bytes after it, including any user M commands.
        return previous[:0xd00]+current[0xd00:], 'prior-owner-prefix-0200-0EFF-plus-fresh-tail'
    assert current[:0xd00] == previous[:0xd00], 'Unknown RAM prefix; retain capture without overwriting'
    return current,'fresh-owner-RAM-already-restored'


def capture(run):
    host_proof(); assert not run.exists()
    assert run.is_relative_to((ROOT/'output/qualification').resolve())
    run.mkdir(parents=True); (run/'.gitignore').write_text('*\n')
    io.save(run/'authorization.json',dict(owner_authorized=True,user_text='the leds, f0 stayed on. fix that',
        board='2512',usb_serial=io.USB,update='FLASH B0:8 LED idle cleanup',leave_installed=True,
        preserve_current_B0_9=True,preserve_settings=True,preserve_owner_RAM=True,
        live_LED_paths=['F 9000 00','I 9000; restore current erased sector'],F_MON_writes=False,RTC_writes=False))
    state = dict(passed=False,board='2512',RAM_pending=False,verification_pending=False)
    with io.serial_lease('FLASH-LED-2512-capture',timeout=30):
        marker = io.read(io.MARKER); guard(marker,run)
        io.durable(run/'marker-before.json',io.MARKER.read_bytes())
        link,log = io.open_link(run,'FLASH-LED-capture')
        try:
            io.durable(run/'initial-FLASH-Q.txt',sync(link))
            assert link.dump(0x7d01,0x7d02) == b'\x02\x03'
            active = link.dump(0x7d30,0x7d30)[0]; assert active in (0xa0,0xb0)
            system = [(PREVIOUS/f'installed-full-flash-r2-b{n}.bin').read_bytes() for n in range(4)]
            for address in (active<<8,0xf000):
                assert io.dump(link,address,address+4095) == system[3][address-0x8000:address-0x7000]
            original = [link.dump(0x2000,0x200c) for _ in range(2)]; assert original[0] == original[1]
            io.durable(run/'shim-original.bin',original[0])
            state['RAM_pending'] = True; checkpoint(run,state,'escrow-before-console-shim')
            shim = bytes.fromhex('78D8A9018D027D20797E4C')+((active<<8)+0x160).to_bytes(2,'little')
            io.upload(link,0x2000,shim); assert link.command('G 2000').endswith(io.MON)
            reads = [io.dump(link,0x200,0x64ff) for _ in range(2)]; assert reads[0] == reads[1]
            current = bytearray(reads[0]); current[0x1e00:0x1e0d] = original[0]
            io.durable(run/'current-RAM-before-tools.bin',current)
            previous = (PREVIOUS/'owner-ram.bin').read_bytes()
            assert io.sha(previous) == io.read(PREVIOUS/'backup-manifest.json')['owner_RAM']['sha256']
            owner,scope = owner_snapshot(bytes(current),previous)
            io.durable(run/'owner-ram.bin',owner)
            zp = [link.dump(0,0xdf) for _ in range(2)]; assert zp[0] == zp[1]
            io.durable(run/'owner-zp.bin',zp[0])
            print('PASS current RAM/ZP captured; known FLASH prefix escrow composed',flush=True)
            for repeat in (1,2):
                banks = io.mon_flash(link)
                for n,data in enumerate(banks): io.durable(run/f'source-r{repeat}-b{n}.bin',data)
                if repeat == 1: first = banks
                else: assert banks == first
                print('PASS fresh full flash read',repeat,flush=True)
            assert io.sha(banks[0][:4096]) == OLD_SHA
            assert banks[0][4096:8192] == b'\xff'*4096, 'Retain capture and replan live test for non-erased B0:9'
            for offset in (0x2000,0x3000,0x7000):
                assert banks[3][offset:offset+4096] == system[3][offset:offset+4096]
            row = io.latest(banks); io.durable(run/'original-record.bin',row)
            assert row[7] == ord('B') and row[13]&1 and row[14] == 8
            io.durable(run/'before-update-B0.bin',banks[0])
            io.durable(run/'before-update-B0-80.bin',banks[0][:4096])
            io.durable(run/'current-erased-B0-90.bin',banks[0][4096:8192])
            io.upload(link,0x2000,original[0]); assert io.dump(link,0x200,0x64ff) == current
            state.update(capture_passed=True,RAM_prefix_policy=scope,owner_ram_sha256=io.sha(owner),
                owner_zp_sha256=io.sha(zp[0]),current_flash_sha256=list(map(io.sha,banks)),user_B0_9_erase_verified=True)
            checkpoint(run,state,'captured-awaiting-model',active=False)
            print('PASS current erased B0:9 and settings backed up; no flash changed',flush=True)
        except BaseException:
            state['error'] = traceback.format_exc(); checkpoint(run,state,'capture-stopped-preserve-escrow',active=False)
            if not state['RAM_pending']: io.save(io.MARKER,marker)
            raise
        finally: link.serial.close(); log.close()


def install(run):
    qualify(); state = io.read(run/'state.json'); assert state['capture_passed'] and not state['verification_pending']
    proof = io.read(run/'live-model-proof.json')
    assert proof['passed'] and proof['helper_sha256'] == io.sha(Path(__file__).read_bytes())
    assert proof['checker_sha256'] == io.sha((HERE/'prepare_flash_led_2512.py').read_bytes())
    for name,digest in proof['bindings'].items(): assert io.sha(Path(name).read_bytes()) == digest,name
    source = [(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    final = [(run/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    owner,zp = (run/'owner-ram.bin').read_bytes(),(run/'owner-zp.bin').read_bytes()
    current = (run/'current-RAM-before-tools.bin').read_bytes()
    image = (BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    with io.serial_lease('FLASH-LED-2512-update-test',timeout=30):
        guard(io.read(io.MARKER),run,pending=True)
        link,log = io.open_link(run,'FLASH-LED-install')
        try:
            wire.sync(link)
            assert io.dump(link,0x200,0x64ff) == current and link.dump(0,0xdf) == zp
            assert io.mon_flash(link) == source
            wire.to_recovery(link,run,'J3-S-update'); wire.load_installer(link)
            state['verification_pending'] = True; checkpoint(run,state,'before-update')
            io.save(run/'install-B0-8.json',wire.opaque_write(link,0x80,image,source[0][:4096]))
            io.durable(run/'OIP-new-image.bin',wire.opaque_read(link,0x80,image))
            link.command('Q',io.REC)
            boot = link.command('0',wire.FLASH); io.durable(run/'new-FLASH-boot.txt',boot)
            for label,line in (('program','F 9000 00'),('erase','I 9000')):
                staged = link.command(line,wire.CONFIRM)
                assert staged.endswith(b'B0:9000; type YES> ')
                done = link.command('YES',wire.FLASH)
                assert done == b'YES\r\nOK: verified sector\r\n'+wire.FLASH
                io.durable(run/(label+'-returned-prompt.txt'),staged+done)
                readback = link.command('D 9000',wire.FLASH)
                assert (b'00 FF FF FF ' if label=='program' else b'FF FF FF FF ') in readback
                io.durable(run/(label+'-readback.txt'),readback)
            q = link.command('Q',io.MON); io.durable(run/'Q-to-B3.txt',q)
            assert b'STR8-N 2.0proto b15' in q
            print('PASS updated FLASH; real program/erase returned through fixed idle LED path; Q to B3',flush=True)
            wire.to_recovery(link,run,'J3-S-verify')
            io.raw_load(link,(io.SERVICE/'payload/mon-service-load.bin').read_bytes(),io.SVC)
            io.flash_service(link,run,'final-full-flash',final)
            assert final[0][4096:] == source[0][4096:] and final[1:3] == source[1:3]
            assert wire.policy(io.latest(final)) == wire.policy((run/'original-record.bin').read_bytes())
            state['verification_pending'] = False; checkpoint(run,state,'flash-settings-and-user-erase-verified')
            packet = owner+io.crc(owner).to_bytes(2,'little'); link.send(b'W')
            for off in range(0,len(packet),64): link.send(packet[off:off+64]); time.sleep(.01)
            assert link.until(io.SVC,30) == io.SVC
            for n in (1,2):
                ram = io.service_read(link,b'M',0x6300); observed_zp = io.service_read(link,b'Z',0xe0)
                io.durable(run/f'restored-RAM-r{n}.bin',ram); io.durable(run/f'restored-ZP-r{n}.bin',observed_zp)
                assert ram == owner and observed_zp == zp
            link.send(b'J'); boot = link.until(io.MON,40); io.durable(run/'final-default-B-boot.txt',boot)
            assert b'Boot : 6 5 4 3 2 1 0' in boot and b'2.0proto b15' in boot
            assert link.dump(0x7d01,0x7d02) == b'\x02\x03'
            ram = io.dump(link,0x200,0x64ff); observed_zp = link.dump(0,0xdf)
            io.durable(run/'final-MON-RAM.bin',ram); io.durable(run/'final-MON-ZP.bin',observed_zp)
            assert ram == owner and observed_zp == zp
            state.update(passed=True,RAM_pending=False,LED_fix_installed=True,FLASH_left_installed=True,
                owner_RAM_restored=True,owner_ZP_preserved=True,user_B0_9_erase_preserved=True,
                settings_preserved=True,final_console='BOTH',final_monitor='B',final_bank_sha256=list(map(io.sha,final)))
            checkpoint(run,state,'completed',active=False)
            m = io.read(io.MARKER)
            m.update(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),map(io.sha,final))),
                current_firmware_sha256=io.sha(b''.join(final[1:])),application_RAM_restore_verified=True,
                FLASH_installed=dict(bank=0,entry='8000',bytes=4096,sha256=io.sha(image),LED_fix=True,run=str(run)),
                last_preservation_report=str(run/'test-results.json'),last_RAM_preservation_receipt=str(run/'test-results.json'),
                last_recovery_report=str(run/'state.json'),last_recovery_scope='FLASH LED fix; user erased B0:9/settings/RAM preserved',
                reason='FLASH returns LEDs to 01 after raw flash operations; updated B0:8 left installed; B0:9 remains erased')
            io.save(io.MARKER,m)
        except BaseException:
            state['error'] = traceback.format_exc(); checkpoint(run,state,'stopped-preserve-escrow',active=False); raise
        finally: link.serial.close(); log.close()
    state.update(serial_released=True,completed_utc=io.now()); io.save(run/'state.json',state)
    io.save(run/'test-results.json',dict(state,hardware=True,failures=0,
        helper_sha256=io.sha(Path(__file__).read_bytes()),model_proof_sha256=io.sha((run/'live-model-proof.json').read_bytes()),
        limits=['Live serial prompt proves the fixed idle write path executed; no independent optical LED measurement',
                'Three actual erase reservations retained: one B0:8 update and two B0:9 test operations',
                'No RTC writes, physical reset/power-cut or live ACIA electrical test']))
    m = io.read(io.MARKER); m['completion_receipt'] = dict(path=str(run/'state.json'),sha256=io.sha((run/'state.json').read_bytes()))
    io.save(io.MARKER,m)
    print('PASS LED fix installed; user erased B0:9/settings/RAM preserved; BOTH MON B; serial released',flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('stage',choices=('capture','install'))
    p.add_argument('--run',type=Path,required=True); x = p.parse_args()
    (capture if x.stage=='capture' else install)(x.run.resolve())
