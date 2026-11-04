"""2512-only CONFIG test with fresh escrow, modeled postimages and restoration."""
import argparse
import binascii
import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tmp/migration-python')]
from installer.engine.legacy_transport import Link, s19
from serial_test_coordination import serial_lease

BUILD = ROOT/'BUILD/pr04-b14-ram-config-r1'
SERVICE = ROOT/'BUILD/pr04-b14-mon-absent-r5'
SOURCE = ROOT/'BUILD/pr04-b14-mon-restore-live'
MARKER = ROOT/'output/qualification/device-operations/2512.json'
USB = 'A10MQFLCA'
MON = b'\r\nB3> '
REC = b'REC> '
CFG = b'RAM CONFIG ? B C I W Q> '
FIX = b'FIXED CONFIG D R Q> '
SVC = b'RAM SERVICE> '
CHOICES = b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'
AUTH_TEXT = ('Load the new RAM CONFIG on 2512 and test enabling a bank, setting its entry, '
             'and saving the default boot. Restore the original settings afterward. '
             'consider a menu based ram config as well')


def sha(data): return hashlib.sha256(data).hexdigest()
def crc(data): return binascii.crc_hqx(data, 65535)
def read(path): return json.loads(path.read_text())
def now(): return datetime.now(timezone.utc).isoformat()


def durable(path, data):
    path = Path(path); tmp = path.with_suffix(path.suffix+'.pending')
    with tmp.open('wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)
    assert path.read_bytes() == data


def save(path, obj): durable(path, (json.dumps(obj, indent=2)+'\n').encode())
def expected_source(): return [(SOURCE/f'expected-b{n}.bin').read_bytes() for n in range(4)]


def latest(banks):
    records = []
    for offset in range(0x4000, 0x6000, 256):
        r = bytes(banks[3][offset:offset+256])
        if r[:6] == b'SNBT\x01\x20' and r[255] == 0 and crc(r[:252]) == int.from_bytes(r[252:254], 'little'):
            assert crc(r[:30]) == int.from_bytes(r[30:32], 'little')
            records.append(r)
    return max(records, key=lambda r:int.from_bytes(r[8:12], 'little'))


def settings(r): return r[7:8]+r[12:30]


def host_proof():
    proof = read(HERE/'ram-config-host-tests.json')
    assert proof['passed'] and proof['checks'] >= 12 and not proof['hardware'] and not proof['serial_access']
    assert proof['helper_sha256'] == sha(Path(__file__).read_bytes())
    assert proof['checker_sha256'] == sha((HERE/'test_board_ram_config_2512.py').read_bytes())


def guard(marker, run, pending=False):
    assert marker['board'] == '2512' and marker['firmware'] == '2.0proto b14'
    assert marker['monitor_generation'] == 0x8000000e
    assert marker['MON_A_present'] and marker['MON_B_present']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('physical_reset_pending', 'owner_application_running',
        'power_off_reported', 'poweroff_pending_owner_confirmation', 'opaque_sector_restore_pending',
        'mon_restore_pending', 'current_soak_worker_pid', 'one_shot_collection_active'))
    assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped']
    if pending:
        assert marker['ram_config_run'] == str(run) and marker['application_RAM_restore_pending']
    else:
        assert not marker.get('block_snapshot') and not marker.get('application_RAM_restore_pending')
        assert marker['current_physical_bank_sha256'] == dict(zip(('B0','B1','B2','B3'), map(sha, expected_source())))


def checkpoint(run, state, phase, active=True):
    state.update(phase=phase, updated_utc=now()); save(run/'state.json', state)
    marker = read(MARKER)
    marker.update(state='ram-config-'+phase, ram_config_run=str(run), recovery_worker_active=active,
        block_snapshot=not state.get('passed', False),
        application_RAM_restore_pending=state.get('RAM_pending', False),
        application_ram_restored=not state.get('RAM_pending', False),
        boot_settings_restore_pending=state.get('settings_pending', False))
    save(MARKER, marker)


def open_link(run, phase):
    from serial.tools.list_ports import comports
    ports = [p for p in comports() if p.serial_number == USB]
    assert len(ports) == 1, 'Unique 2512 USB identity required'
    log = (run/f'serial-{phase}-{datetime.now(timezone.utc).strftime("%H%M%S.%f")}.jsonl').open('x')
    try: return Link(ports[0].device, log), log
    except BaseException: log.close(); raise


def sync_mon(link):
    raw = bytearray(); start = last = time.monotonic()
    while time.monotonic()-last < .5:
        assert time.monotonic()-start < 15
        part = link.read(4096)
        if part: raw.extend(part); last = time.monotonic()
    assert all(c in (8,9,10,13,127) or 32 <= c <= 126 for c in raw)
    link.send(b'\r'); reply=bytearray(); deadline=time.monotonic()+5
    while not (reply.endswith(MON) or reply.endswith(REC)):
        assert time.monotonic()<deadline, 'No known idle monitor/recovery prompt'
        reply.extend(link.read(4096))
    assert all(c in (8,9,10,13,127) or 32 <= c <= 126 for c in reply)
    if reply.endswith(REC):
        assert bytes(reply) in (b'\r\nREFUSED: command\r\nREC> ', b'\r\nREC> ')
        selected=link.command('B',MON)
        assert b'STR8-N 2.0proto b14 B3 65C02' in selected
        reply.extend(selected)
    else:
        assert bytes(reply) in (MON,b'\r\n'+MON)
    return bytes(raw)+bytes(reply)


def dump(link, first, last):
    return b''.join(link.dump(a,min(a+511,last)) for a in range(first,last+1,512))


def upload(link, address, data):
    assert 0x200 <= address < address+len(data) <= 0x6500
    packet = s19(dict(enumerate(data,address)),address)
    link.command('L', b'S19')
    for row in packet.splitlines(): link.send(row+b'\r\n'); time.sleep(.04)
    reply = link.until(MON)
    assert f'Entry {address:04X}'.encode() in reply
    assert not any(t in reply for t in (b'Bad', b'Error', b'REFUSED', b'Protected'))
    assert dump(link,address,address+len(data)-1) == data


def ft_only(link, run, state, banks):
    sy = read(BUILD/'symbols.json'); info = read(BUILD/'prototype-report.json')
    assert link.dump(0x7d30,0x7d30) == b'\xb0'
    for a in (0xb000,0xf000): assert dump(link,a,a+4095) == banks[3][a-0x8000:a-0x7000]
    for label, a, length in (('BOOT_WORKER_IMAGE',0x7800,info['f']['worker_bytes']),
                            ('BOOT_VECTOR_IMAGE',0x7e20,info['f']['vectors_bytes'])):
        offset = sy['core/str8n-v2-boot'][label]-0xf000
        assert dump(link,a,a+length-1) == banks[3][-4096:][offset:offset+length]
    prompt = sy['core/monitor-b0']['V2_PROMPT']
    assert prompt == 0xb160 and banks[3][prompt-0x8000:prompt-0x8000+5] == bytes.fromhex('ADF97DC954')
    shim = bytes.fromhex('78D8A9018D027D20797E4C')+prompt.to_bytes(2,'little')
    borrowed = [link.dump(0x2000,0x2000+len(shim)-1) for _ in range(2)]
    assert borrowed[0] == borrowed[1]
    durable(run/'shim-original.bin',borrowed[0])
    state['RAM_pending'] = True; checkpoint(run,state,'escrowed-before-FT-shim')
    upload(link,0x2000,shim)
    assert link.command('G 2000').endswith(MON)
    assert link.dump(0x7d02,0x7d02) == b'\x01'
    return borrowed[0]


def mon_flash(link):
    result = []
    try:
        for n in range(4):
            prompt = f'\r\nB{n}> '.encode(); link.command(f'B{n}',prompt)
            result.append(b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096)))
    finally: link.command('B3')
    return result


def capture(run):
    host_proof()
    assert not run.exists(); run.mkdir(parents=True); (run/'.gitignore').write_text('*\n')
    save(run/'authorization.json',dict(owner_authorized=True,user_text=AUTH_TEXT,board='2512',usb_serial=USB,
        action='RAM CONFIG enable-entry-default test and restore',other_boards=False,RTC_writes=False,
        F_MON_image_writes=False,opaque_image_writes=False,journal_settings_and_wear=True,recorded_utc=now()))
    state = dict(passed=False,board='2512',RAM_pending=False,settings_pending=False,physical_reset_used=False)
    with serial_lease('ram-config-2512-capture',timeout=30):
        marker = read(MARKER); guard(marker,run)
        durable(run/'marker-before.json',MARKER.read_bytes())
        link,log = open_link(run,'capture')
        try:
            durable(run/'initial-monitor.txt',sync_mon(link))
            assert link.dump(0x7d01,0x7d02) == b'\x02\x03'
            banks = expected_source()
            borrowed = ft_only(link,run,state,banks)
            ram = [dump(link,0x200,0x64ff) for _ in range(2)]
            assert ram[0] == ram[1]
            original = bytearray(ram[0]); original[0x1e00:0x1e00+len(borrowed)] = borrowed
            zp = [link.dump(0,0xdf) for _ in range(2)]; assert zp[0] == zp[1]
            durable(run/'owner-ram.bin',bytes(original)); durable(run/'owner-zp.bin',zp[0])
            durable(run/'restore-owner-ram.s19',s19(dict(enumerate(original,0x200)),0x200))
            for repeat in (1,2):
                observed = mon_flash(link); assert observed == banks, 'Fresh full flash differs from admitted source'
                for n,data in enumerate(observed): durable(run/f'before-r{repeat}-b{n}.bin',data)
            upload(link,0x2000,borrowed)
            assert dump(link,0x200,0x64ff) == bytes(original)
            r = latest(banks)
            assert r[7] == ord('B') and r[13] == 15 and r[14:18] == bytes([8]*4)
            durable(run/'original-record.bin',r)
            state.update(capture_passed=True,bank_sha256=list(map(sha,banks)),owner_ram_sha256=sha(original),
                owner_zp_sha256=sha(zp[0]),original_settings_hex=settings(r).hex())
            checkpoint(run,state,'captured-awaiting-model',active=False)
            print('PASS fresh 2512 escrow; original default B, mask F, entries 8000; FT-only MON B',flush=True)
        except BaseException:
            state['error'] = traceback.format_exc()
            checkpoint(run,state,'capture-stopped-preserve-escrow',active=False)
            if not state['RAM_pending'] and not state['settings_pending']:
                save(MARKER,marker)
            raise
        finally: link.serial.close(); log.close()


def raw_load(link, body, prompt):
    assert 0 < len(body) <= 0x6300
    assert link.command('L',b'SEND BIN\r\n') == b'L\r\nSEND BIN\r\n'
    for off in range(0,len(body),64): link.send(body[off:off+64]); time.sleep(.01)
    assert link.until(prompt,30) == prompt


def restart_S(link, command_bytes):
    link.send(command_bytes)
    prefix = link.until(CHOICES,30)
    link.send(b'S')
    reply = link.until(REC,15)
    assert b'Recovery L A/B 0-3 C1/2/3 ?' in reply
    return prefix+reply


def exact(link,n):
    data = bytes(link.pending[:n]); del link.pending[:len(data)]
    return data+link.exact(n-len(data))


def service_read(link, command, count):
    assert not link.pending
    link.send(command); result = exact(link,count+2)
    assert crc(result[:-2]) == int.from_bytes(result[-2:],'little')
    assert link.until(SVC,15) == SVC
    return result[:-2]


def flash_service(link,run,label,expected):
    for repeat in (1,2):
        banks = [service_read(link,b'F'+bytes([n]),32768) for n in range(4)]
        for n,data in enumerate(banks): durable(run/f'{label}-r{repeat}-b{n}.bin',data)
        assert banks == expected, 'Hardware full-flash postimage differs from both CPU models: '+label
    print('PASS',label,'two independent full-flash reads match both CPUs',flush=True)


def config_command(link,run,label,line):
    reply = link.command(line,CFG); durable(run/(label+'.txt'),reply)
    assert reply == line.encode()+b'\r\nOK\r\n'+CFG


def run_test(run):
    host_proof()
    proof = read(run/'model-proof.json'); state = read(run/'state.json')
    if 'error' in state:
        state.setdefault('prior_host_errors',[]).append(dict(phase=state['phase'],error=state.pop('error')))
    assert proof['passed'] and proof['hardware'] is False and state['capture_passed']
    assert proof['helper_sha256'] == sha(Path(__file__).read_bytes())
    for name,digest in proof['artifact_sha256'].items(): assert sha(Path(name).read_bytes()) == digest
    with serial_lease('ram-config-2512-test-restore',timeout=30):
        marker = read(MARKER); guard(marker,run,pending=True)
        link,log = open_link(run,'test')
        try:
            sync_mon(link)
            original_ram = (run/'owner-ram.bin').read_bytes(); original_zp = (run/'owner-zp.bin').read_bytes()
            assert dump(link,0x200,0x64ff) == original_ram and link.dump(0,0xdf) == original_zp
            assert mon_flash(link) == expected_source()
            checkpoint(run,state,'before-CONFIG-test')
            durable(run/'J3-S.txt',restart_S(link,b'J3\r'))
            link.command('C1',REC)
            state['settings_pending'] = True; checkpoint(run,state,'before-fixed-disable-bank0')
            raw_load(link,(run/'fixed-config.bin').read_bytes(),FIX)
            reply = link.command('D',FIX); durable(run/'temporary-disabled.txt',reply)
            assert reply == b'D\r\nOK\r\n'+FIX
            link.command('Q',REC)
            raw_load(link,(BUILD/'payload/ram-config-offline.bin').read_bytes(),CFG)
            show = link.command('B',CFG); durable(run/'CONFIG-before.txt',show)
            assert b'DEFAULT=B\r\n' in show and b'B0 OFF ENTRY=8000\r\n' in show
            config_command(link,run,'enable-and-entry','B 0 A000')
            config_command(link,run,'save-default','C 0')
            show = link.command('B',CFG); durable(run/'CONFIG-saved.txt',show)
            assert b'DEFAULT=0\r\n' in show and b'B0 ON  ENTRY=A000\r\n' in show
            checkpoint(run,state,'saved-bank0-A000-default0')
            # Intercept Q at the boot choices. Never execute unknown opaque bytes.
            durable(run/'saved-default-Q-S.txt',restart_S(link,b'Q\r'))
            link.command('C1',REC)
            raw_load(link,(SERVICE/'payload/mon-service-load.bin').read_bytes(),SVC)
            saved = [(run/f'expected-saved-b{n}.bin').read_bytes() for n in range(4)]
            flash_service(link,run,'saved-settings',saved)
            link.send(b'Q'); link.until(REC,10)
            raw_load(link,(BUILD/'payload/ram-config-offline.bin').read_bytes(),CFG)
            config_command(link,run,'restore-entry','B 0 8000')
            config_command(link,run,'restore-default','C B')
            show = link.command('B',CFG); durable(run/'CONFIG-restored.txt',show)
            assert b'DEFAULT=B\r\n' in show and b'B0 ON  ENTRY=8000\r\n' in show
            durable(run/'restored-default-Q-S.txt',restart_S(link,b'Q\r'))
            link.command('C1',REC)
            raw_load(link,(SERVICE/'payload/mon-service-load.bin').read_bytes(),SVC)
            restored = [(run/f'expected-restored-b{n}.bin').read_bytes() for n in range(4)]
            flash_service(link,run,'restored-settings',restored)
            assert settings(latest(restored)) == (run/'original-settings.bin').read_bytes()
            state['settings_pending'] = False; checkpoint(run,state,'settings-restored-before-RAM')
            packet = original_ram+crc(original_ram).to_bytes(2,'little')
            link.send(b'W')
            for off in range(0,len(packet),64): link.send(packet[off:off+64]); time.sleep(.01)
            assert link.until(SVC,30) == SVC
            for _ in range(2): assert service_read(link,b'M',0x6300) == original_ram
            for _ in range(2): assert service_read(link,b'Z',0xe0) == original_zp
            link.send(b'J'); boot = link.until(MON,40); durable(run/'final-original-default-B-boot.txt',boot)
            assert b'Boot : 6 5 4 3 2 1 0' in boot and b'STR8-N 2.0proto b14 B3 65C02' in boot
            assert link.dump(0x7d01,0x7d02) == b'\x02\x03' and link.dump(0x7d30,0x7d30) == b'\xb0'
            assert dump(link,0x200,0x64ff) == original_ram
            assert link.dump(0,0xdf) == original_zp
            durable(run/'final-owner-ram.bin',original_ram); durable(run/'final-owner-zp.bin',original_zp)
            state.update(passed=True,RAM_pending=False,settings_pending=False,original_settings_restored=True,
                owner_RAM_restored=True,owner_ZP_preserved=True,final_console='BOTH',final_monitor='B',
                final_bank_sha256=list(map(sha,restored)),physical_reset_used=False,RTC_writes=False,
                F_MON_opaque_images_unchanged=True,software_saved_default_reset_verified=True)
            checkpoint(run,state,'completed',active=False)
            marker = read(MARKER)
            marker.update(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),map(sha,restored))),
                current_firmware_sha256=sha(b''.join(restored[1:])),last_preservation_report=str(run/'test-results.json'),
                last_RAM_preservation_receipt=str(run/'test-results.json'),application_RAM_restore_verified=True,
                reason='RAM CONFIG bank/entry/default hardware test passed; original boot settings and fresh RAM/ZP restored',
                completion_receipt=dict(path=str(run/'state.json'),sha256=sha((run/'state.json').read_bytes())))
            save(MARKER,marker)
            save(run/'test-results.json',dict(state,hardware=True,failures=0,serial_released=True,
                journal_erases=proof['journal_erases'],model_proof_sha256=sha((run/'model-proof.json').read_bytes()),
                limits=['No opaque image execution or image installation', 'No physical reset/power-cut test',
                        'Restored logical settings; new journal history and actual wear retained']))
            print('PASS 2512 enable OFF->ON, entry A000, default0 persisted; original settings/RAM/ZP restored; BOTH MON B',flush=True)
        except BaseException:
            state['error'] = traceback.format_exc(); checkpoint(run,state,'stopped-preserve-escrow',active=False); raise
        finally: link.serial.close(); log.close()


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=('capture','test'));p.add_argument('--run',type=Path,required=True)
    x=p.parse_args();run=x.run.resolve()
    (capture if x.stage == 'capture' else run_test)(run)
