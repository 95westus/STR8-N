"""STR8-N UTIL MEMORY — PC memory backup, restore, import and export.

Run --help. Serial support requires the matching memory-agent RAM image and a
BASE1 monitor. The directory device is an offline test device, never hardware.
"""
import argparse
import binascii
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'str8n-memory-backup/1'
REGIONS = {'flash': (1, 131072, 4096), 'spi-sram': (2, 131072, 256),
           'eeprom': (3, 128, 8), 'cpu-ram': (4, 25856, 4096),
           'zero-page': (5, 224, 224), 'spi-mode': (6, 1, 1)}
ORDER = ('flash', 'spi-sram', 'spi-mode', 'eeprom', 'zero-page', 'cpu-ram')
PROMPT = b'MEMORY1> '


def sha(data):
    return hashlib.sha256(data).hexdigest()


def crc(data):
    return binascii.crc_hqx(data, 0xffff).to_bytes(2, 'little')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def admit_monitor_banner(face, cpu):
    require(re.search(rb'BASE1\s*/\s*PR05\b', face) is not None,
            'BASE1 / PR05 monitor required')
    markers = ((b'CPU $02', b'CPU: 65C02') if cpu == '65c02' else
               (b'CPU $16', b'CPU: 65C816'))
    require(any(marker in face for marker in markers), 'Monitor CPU does not match profile')


def parse_monitor_dump(reply, first, last):
    cells = {}
    for line in reply.decode('ascii').splitlines():
        match = re.fullmatch(r'([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})(?:\s+\|.*\|)?', line.strip())
        if match:
            address = int(match[1], 16)
            for offset, byte in enumerate(bytes.fromhex(match[2]), address):
                require(offset not in cells, 'Duplicate monitor dump address')
                cells[offset] = byte
    require(set(cells) == set(range(first, last+1)), 'Incomplete memory readback')
    return bytes(cells[a] for a in range(first, last+1))


def durable(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    require(Path(path).read_bytes() == data, 'Local file verification failed')


def save(path, value):
    path = Path(path)
    pending = path.with_suffix('.pending')
    with pending.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(path)


def selected(text):
    names = list(ORDER) if text == 'all' else text.split(',')
    require(names and len(set(names)) == len(names) and all(n in REGIONS for n in names),
            'Unknown or repeated region; use all or comma-separated region names')
    return [n for n in ORDER if n in names]


def chunks(name):
    _, size, block = REGIONS[name]
    offsets = list(range(0, size, block))
    if name == 'cpu-ram':
        # The agent's 2000-2FFF receive buffer must be restored in one LAST write.
        offsets = list(range(0, 0x1e00, 0x100)) + list(range(0x2e00, size, 0x100)) + [0x1e00]
        return [(p, 4096 if p == 0x1e00 else min(256, size-p)) for p in offsets]
    return [(p, min(block, size-p)) for p in offsets]


def archive(path):
    path = Path(path)
    manifest = json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    require(manifest.get('schema') == SCHEMA and manifest.get('complete') is True,
            'Incomplete or unsupported backup')
    images = {}
    require(isinstance(manifest.get('regions'), dict) and manifest['regions'], 'Empty backup')
    for name, info in manifest['regions'].items():
        require(name in REGIONS and info.get('file') == name+'.bin', 'Invalid backup region/path')
        data = (path/(name+'.bin')).read_bytes()
        require(len(data) == REGIONS[name][1] == info.get('bytes') and sha(data) == info.get('sha256'),
                'Backup size/hash mismatch: '+name)
        images[name] = data
    require(isinstance(manifest.get('identity'), dict), 'Missing device identity')
    return manifest, images


class Wire:
    """CRC-framed requests; failed/ambiguous writes are never retried."""
    def __init__(self, stream, timeout=60, pause=0.002):
        self.stream, self.timeout, self.pause = stream, timeout, pause
        self.synchronized = True

    def exact(self, count):
        out = bytearray()
        deadline = time.monotonic()+self.timeout
        while len(out) < count:
            part = self.stream.read(count-len(out))
            out.extend(part)
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Memory reply incomplete ({len(out)}/{count}); no retry')
        return bytes(out)

    def send(self, data):
        for p in range(0, len(data), 16):
            part = data[p:p+16]
            require(self.stream.write(part) == len(part), 'Short serial write; no retry')
            if self.pause:
                time.sleep(self.pause)

    def request(self, operation, bank=0, address=0, count=0, data=None):
        require(self.synchronized, 'Transfer state is ambiguous; refusing another request')
        require(0 <= operation <= 255 and 0 <= bank < 4 and 0 <= address < 0x20000
                and 0 <= count <= 4096, 'Request outside protocol limits')
        require((data is not None) == bool(operation & 0x80), 'Write payload/operation mismatch')
        if data is not None:
            require(len(data) == count and count > 0, 'Write payload size mismatch')
        header = bytes((operation, bank))+address.to_bytes(3, 'little')+struct.pack('<H', count)
        self.synchronized = False
        self.send(header+crc(header))
        if data is not None:
            self.send(data+crc(data))
        prefix = self.exact(3)
        status, length = prefix[0], int.from_bytes(prefix[1:], 'little')
        expected = 0 if data is not None or operation == 0x7f else count
        require(length <= 4096, 'Invalid response size')
        body = self.exact(length)
        require(self.exact(2) == crc(prefix+body), 'Response CRC mismatch; no retry')
        # Status 2/3 is emitted only after a complete, CRC-valid request and
        # (for writes) its full payload. The failed operation is not retried,
        # but owner-RAM cleanup is safe at this known command boundary.
        if status in (2, 3) and length == 0:
            self.synchronized = True
        require(status == 0, f'Memory agent refused/failed: status {status}; no retry')
        require(length == expected, 'Unexpected response length')
        self.synchronized = True
        return body


class DirectoryDevice:
    """Explicit offline device: full-size region files and identity.json."""
    def __init__(self, path):
        self.path = Path(path)
        self.identity = json.loads((self.path/'identity.json').read_text())
        for name, (_, size, _) in REGIONS.items():
            require((self.path/(name+'.bin')).stat().st_size == size, 'Device size mismatch: '+name)

    def read(self, name, offset, count):
        with (self.path/(name+'.bin')).open('rb') as stream:
            stream.seek(offset)
            data = stream.read(count)
        require(len(data) == count, 'Short device read')
        return data

    def write(self, name, offset, data):
        require(0 <= offset < offset+len(data) <= REGIONS[name][1], 'Write outside region')
        require(name != 'flash' or offset+len(data) <= 0x1f000, 'Foundation is protected')
        with (self.path/(name+'.bin')).open('r+b') as stream:
            stream.seek(offset)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    def close(self):
        pass


class SerialDevice:
    def __init__(self, profile, agent, out):
        from installer.engine.legacy_transport import Link
        self.profile, self.agent, self.out = profile, agent, Path(out)
        self.identity = {k: profile[k] for k in ('board', 'cpu', 'usb_serial')}
        require(profile['cpu'] in ('65c02', '65c816-e'), 'Unsupported CPU mode')
        require(profile.get('layout') == 'wdc-sxb-edu-revd-base1', 'Unsupported hardware layout')
        self.saved = {}
        self.link = None
        self.running = False
        self.dirty_ram = False
        self.marker_path = ROOT/'output/qualification/device-operations'/(profile['board']+'.json')
        self.original_marker = None
        self.log = (self.out/'serial.jsonl').open('x')
        try:
            if self.marker_path.exists():
                self.original_marker = json.loads(self.marker_path.read_text())
                require(not self.original_marker.get('block_snapshot')
                        and not self.original_marker.get('application_RAM_restore_pending')
                        and not self.original_marker.get('physical_reset_pending')
                        and not any(v for k, v in self.original_marker.items() if k.endswith('_worker_active')),
                        'Board has a pending operation/restoration; no port opened')
            import serial.tools.list_ports
            require(any(p.device.casefold() == profile['port'].casefold()
                        and p.serial_number == profile['usb_serial'] for p in serial.tools.list_ports.comports()),
                    'Port/USB serial identity mismatch')
            manifest = json.loads((agent/'manifest.json').read_text())
            self.image = (agent/manifest.get('file', 'memory-agent.bin')).read_bytes()
            require(manifest['protocol'] == 1 and sha(self.image) == manifest['sha256'], 'Agent hash mismatch')
            self.link = Link(profile['port'], self.log)
            self.link.send(b'\r')
            deadline = time.monotonic()+20
            while b'B3> ' not in self.link.pending and b'REC> ' not in self.link.pending:
                require(time.monotonic() < deadline, 'No monitor/recovery prompt received')
                self.link.pending.extend(self.link.read(max(1, self.link.serial.in_waiting)))
            if b'REC> ' in self.link.pending and b'B3> ' not in self.link.pending:
                self.link.until(b'REC> ')
                face = self.link.command('B', b'B3> ')
            else:
                face = self.link.until(b'B3> ')
            face += self.link.command('V', b'B3> ')
            face += self.link.command('VERSION', b'B3> ')
            durable(self.out/'identity-response.txt', face)
            admit_monitor_banner(face, profile['cpu'])
            foundation = self.dump(0xf000, 0xffff)
            require(sha(foundation) == profile['foundation_sha256'] == manifest['foundation_sha256'],
                    'Foundation does not match profile/agent recovery binding')
            self.identity['foundation_sha256'] = sha(foundation)
            # Capture BEFORE uploading anything. These are the public owner ranges.
            for name, first, last in (('cpu-ram', 0x200, 0x66ff), ('zero-page', 0, 0xdf)):
                data = self.dump(first, last)
                require(data == self.dump(first, last), 'Unstable owner RAM: '+name)
                self.saved[name] = data
                durable(self.out/('entry-'+name+'.bin'), data)
            save(self.out/'ram-state.json', {'restore_pending': True, 'ranges': ['0000-00DF', '0200-66FF']})
            self.mark(memory_tool_worker_active=True, application_RAM_restore_pending=True,
                      application_ram_restored=False, block_snapshot=True)
            self.dirty_ram = True
            self.link.command('Q', b'REC> ')
            self.link.send(b'L\r')
            self.link.until(b'SEND BIN\r\n')
            self.wire = Wire(self.link.serial)
            self.wire.send(self.image)
            self.link.until(PROMPT)
            self.running = True
        except BaseException:
            # Do not attempt commands when the bootstrap phase is ambiguous.
            if self.link:
                self.link.serial.close()
            if self.dirty_ram:
                self.mark(memory_tool_worker_active=False)
            self.log.close()
            raise

    def dump(self, first, last):
        return b''.join(parse_monitor_dump(
            self.link.command(f'D {a:04X} {min(last, a+511):04X}', b'B3> '), a, min(last, a+511))
            for a in range(first, last+1, 512))

    def read(self, name, offset, count):
        # Saved pre-helper owner RAM is only used for the initial backup; later
        # verification must read the actual board through the agent.
        return self.transfer(name, offset, count)

    def transfer(self, name, offset, count, data=None):
        code = REGIONS[name][0] | (0x80 if data is not None else 0)
        address, bank = offset, 0
        if name == 'flash':
            bank, address = divmod(offset, 32768)
            address += 0x8000
        elif name == 'cpu-ram':
            address += 0x200
        return self.wire.request(code, bank, address, count, data)

    def write(self, name, offset, data):
        if name == 'flash':
            self.mark(firmware_verification_pending=True)
        self.transfer(name, offset, len(data), data)

    def mark(self, **values):
        if self.original_marker is not None:
            state = json.loads(self.marker_path.read_text())
            state.update(values)
            state['last_memory_tool_run'] = str(self.out)
            save(self.marker_path, state)

    def close(self):
        try:
            if self.running:
                if not self.wire.synchronized:
                    # Sending cleanup bytes into an incomplete binary request
                    # could complete the wrong mutation. Keep the fresh escrow.
                    save(self.out/'ram-state.json', {'restore_pending': True,
                         'reason': 'Ambiguous transfer; no blind cleanup commands sent',
                         'escrow': ['entry-cpu-ram.bin', 'entry-zero-page.bin']})
                    self.mark(memory_tool_worker_active=False)
                    return
                # User restore/load may deliberately change owner RAM. The
                # caller updates saved only after every requested write verifies.
                for name in ('zero-page', 'cpu-ram'):
                    for offset, count in chunks(name):
                        self.write(name, offset, self.saved[name][offset:offset+count])
                for name in ('zero-page', 'cpu-ram'):
                    require(read_region(self, name) == self.saved[name], 'Owner RAM restoration failed')
                self.wire.request(0x7f)
                self.link.until(b'REC> ')
                self.running = False
                save(self.out/'ram-state.json', {'restore_pending': False,
                     'ranges': ['0000-00DF', '0200-66FF'], 'verified': True,
                     'final_prompt': 'REC> ',
                     'service_resident': '6800-77FF; stack/system workspace excluded'})
                self.mark(memory_tool_worker_active=False, application_RAM_restore_pending=False,
                          application_ram_restored=True, block_snapshot=False, final_prompt='REC>')
        finally:
            if self.link:
                self.link.serial.close()
            self.log.close()


def read_region(device, name, initial=False):
    if initial and name in getattr(device, 'saved', {}):
        return device.saved[name]
    _, size, block = REGIONS[name]
    # RAM reads stream from the source; they do not overwrite the receive buffer.
    return b''.join(device.read(name, p, min(block, size-p)) for p in range(0, size, block))


def backup(device, path, names):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    durable(path/'.gitignore', b'*\n')
    manifest = {'schema': SCHEMA, 'complete': False, 'identity': device.identity,
                'cpu_ram_scope': ['0000-00DF', '0200-66FF'],
                'excluded': ['CPU registers', 'active stack 0100-01FF', 'system zero page E0-FF',
                             'monitor/service workspace 6700-7EFF', 'I/O 7F00-7FFF',
                             'EEPROM factory/protected area 80-FF'], 'regions': {}}
    save(path/'manifest.json', manifest)
    for name in names:
        print('Backing up '+name, flush=True)
        data = read_region(device, name, initial=True)
        require(data == read_region(device, name, initial=True), 'Independent capture differs: '+name)
        durable(path/(name+'.bin'), data)
        manifest['regions'][name] = {'file': name+'.bin', 'bytes': len(data), 'sha256': sha(data)}
        save(path/'manifest.json', manifest)
    manifest['complete'] = True
    save(path/'manifest.json', manifest)
    archive(path)
    return manifest


def plan(device, images):
    changes = []
    for name in ORDER:
        if name not in images:
            continue
        target = images[name]
        for offset, count in chunks(name):
            before = (device.saved[name][offset:offset+count] if name in getattr(device, 'saved', {})
                      else device.read(name, offset, count))
            after = target[offset:offset+count]
            if before == after:
                continue
            require(name != 'flash' or offset < 0x1f000,
                    'Backup Foundation differs: serial restoration cannot replace its recovery code')
            changes.append({'region': name, 'offset': offset, 'bytes': count,
                            'before_sha256': sha(before), 'after_sha256': sha(after)})
    return changes


def apply(device, images, changes, receipt):
    state = {'complete': False, 'pending': None, 'completed': [], 'changes': changes,
             'flash_history': 'Exact-image restore; native journal bytes may roll back. Host erase-attempt log retained.'}
    save(receipt, state)
    try:
        for change in changes:
            name, offset, count = change['region'], change['offset'], change['bytes']
            # RAM receive-buffer side effects mean CPU RAM cannot use stale
            # per-chunk preimages; all other storage is checked immediately.
            if name != 'cpu-ram':
                require(sha(device.read(name, offset, count)) == change['before_sha256'],
                        'Device changed since plan: '+name)
            state['pending'] = change
            save(receipt, state)  # persist uncertainty BEFORE sending any write
            data = images[name][offset:offset+count]
            device.write(name, offset, data)
            require(device.read(name, offset, count) == data, 'Write readback differs: '+name)
            state['completed'].append(change)
            state['pending'] = None
            save(receipt, state)
        for name, data in images.items():
            if name in ('zero-page', 'cpu-ram'):
                continue
            require(read_region(device, name) == data, 'Final verification differs: '+name)
        # Storage verification uses the staging buffer. Restore requested CPU
        # RAM only after those reads, including chunks that were initially equal.
        for name in ('zero-page', 'cpu-ram'):
            if name in images:
                for offset, count in chunks(name):
                    device.write(name, offset, images[name][offset:offset+count])
        for name in ('zero-page', 'cpu-ram'):
            if name in images:
                require(read_region(device, name) == images[name], 'Final RAM verification differs: '+name)
        # Carry the requested final RAM state through normal cleanup.
        if hasattr(device, 'saved'):
            device.saved.update({n: d for n, d in images.items() if n in device.saved})
        state['complete'] = True
        save(receipt, state)
        return state
    except BaseException as error:
        state['error'] = str(error)
        save(receipt, state)
        raise


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', action='version', version='STR8-N UTIL MEMORY 0.1.0\nCopyright (c) 2026 95west.us/wlp1963; MIT')
    sub = p.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect', help='Validate a saved backup without opening a port')
    inspect.add_argument('backup', type=Path)
    init = sub.add_parser('init-test-device', help='Create an OFFLINE directory device')
    init.add_argument('directory', type=Path)
    for command in ('backup', 'verify', 'plan', 'restore', 'load', 'offload'):
        q = sub.add_parser(command)
        target = q.add_mutually_exclusive_group(required=True)
        target.add_argument('--device-dir', type=Path, help='OFFLINE test device')
        target.add_argument('--profile', type=Path, help='Explicit serial hardware profile JSON')
        q.add_argument('--agent', type=Path, default=ROOT/'BUILD/memory-agent-v1')
        q.add_argument('--out', type=Path, required=True, help='New private run directory')
        if command in ('backup', 'verify', 'plan', 'restore'):
            q.add_argument('--regions', default='all')
        if command in ('verify', 'plan', 'restore'):
            q.add_argument('backup', type=Path)
        if command in ('load', 'offload'):
            q.add_argument('region', choices=REGIONS)
            q.add_argument('file', type=Path)
        if command == 'load':
            q.add_argument('--offset', type=lambda value: int(value, 0), default=0,
                           help='Byte offset within the region image (decimal or 0xHEX)')
        if command in ('restore', 'load'):
            q.add_argument('--write', action='store_true', help='Execute after saving a fresh preimage; otherwise plan only')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == 'inspect':
        manifest, _ = archive(args.backup)
        print(json.dumps(manifest, indent=2))
        return
    if args.command == 'init-test-device':
        args.directory.mkdir(parents=True, exist_ok=False)
        durable(args.directory/'.gitignore', b'*\n')
        save(args.directory/'identity.json', {'board': 'OFFLINE-TEST', 'cpu': '65c02', 'usb_serial': 'NONE'})
        for name, (_, size, _) in REGIONS.items():
            durable(args.directory/(name+'.bin'), bytes([0x40 if name == 'spi-mode' else 0xff])*size)
        print('Created OFFLINE test device: '+str(args.directory))
        return
    # Validate every local input before opening a port.
    names = selected(getattr(args, 'regions', 'all'))
    images = None
    load_data = None
    expected = None
    if args.command in ('verify', 'plan', 'restore'):
        expected, all_images = archive(args.backup)
        require(all(n in all_images for n in names), 'Requested region absent from backup')
        images = {n: all_images[n] for n in names}
    elif args.command == 'load':
        load_data = args.file.read_bytes()
        require(0 <= args.offset < args.offset+len(load_data) <= REGIONS[args.region][1],
                'LOAD image does not fit within the selected region')
        if args.region == 'spi-mode':
            require(load_data in (b'\0', b'\x40', b'\x80'), 'Invalid SPI mode')
    elif args.command == 'offload':
        require(not args.file.exists() and args.file.parent.is_dir(),
                'Offload destination must be a new file in an existing directory')
    if images and 'spi-mode' in images:
        require(images['spi-mode'] in (b'\0', b'\x40', b'\x80'), 'Invalid SPI mode')
    args.out.mkdir(parents=True, exist_ok=False)
    durable(args.out/'.gitignore', b'*\n')
    profile = json.loads(args.profile.read_text()) if args.profile else None
    lease = contextlib.nullcontext()
    if profile:
        require(re.fullmatch(r'[A-Za-z0-9_-]+', profile.get('board', '')) is not None,
                'Invalid board identifier')
        requested = list(images) if images else ([args.region] if hasattr(args, 'region') else names)
        require(all(n in profile.get('regions', []) for n in requested),
                'Requested memory is not declared fitted in the profile')
        from serial_test_coordination import serial_lease
        lease = serial_lease('memory-tool-'+profile['board'], timeout=30)
    with lease:
        device = DirectoryDevice(args.device_dir) if args.device_dir else SerialDevice(profile, args.agent, args.out)
        try:
            if expected:
                require(expected['identity'] == device.identity, 'Backup belongs to a different device identity')
            if args.command == 'backup':
                backup(device, args.out/'backup', names)
            elif args.command == 'offload':
                data = read_region(device, args.region, initial=True)
                require(data == read_region(device, args.region, initial=True), 'Capture differs')
                durable(args.file, data)
                save(args.out/'offload.json', {'region': args.region, 'bytes': len(data), 'sha256': sha(data)})
            elif args.command == 'verify':
                for name, data in images.items():
                    require(read_region(device, name, initial=True) == data, 'Verification differs: '+name)
                save(args.out/'verify.json', {'complete': True, 'regions': list(images)})
            else:
                # Save independent preimages before writes (also for single-region LOAD).
                backup(device, args.out/'before', list(images) if images else [args.region])
                if args.command == 'load':
                    _, originals = archive(args.out/'before')
                    target = bytearray(originals[args.region])
                    target[args.offset:args.offset+len(load_data)] = load_data
                    images = {args.region: bytes(target)}
                changes = plan(device, images)
                save(args.out/'plan.json', {'identity': device.identity, 'changes': changes,
                     'write_requested': getattr(args, 'write', False)})
                print(f'{len(changes)} changed blocks; plan: {args.out / "plan.json"}')
                if getattr(args, 'write', False):
                    apply(device, images, changes, args.out/'receipt.json')
        finally:
            device.close()
    print('Complete: '+str(args.out))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, TimeoutError) as error:
        print('STOPPED: '+str(error), file=sys.stderr)
        sys.exit(1)
