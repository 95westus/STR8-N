"""2512-only Tera Term launcher; eat one recognized startup FF, log raw first.

The serial transport remains byte-exact. A loopback TCP connection presents
one text startup to Tera Term. Any client transmission disables filtering;
all bytes after startup (including binary FF) pass through unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
USB = 'A10MQFLCA'
MARKER = ROOT / 'output/qualification/device-operations/2512.json'
PREFIX = b'\xff\r\nWAIT...\r\n'


class BootPrefixFilter:
    """One-shot, bounded prefix recognition; never strip arbitrary FF bytes."""
    def __init__(self, *, enabled=True, seconds=10):
        self.armed = enabled
        self.pending = bytearray()
        self.started = None
        self.seconds = seconds
        self.suppressed = 0
        self.reason = 'armed' if enabled else 'raw'

    def finish(self, reason='end'):
        data = bytes(self.pending)
        self.pending.clear()
        self.armed = False
        if self.reason == 'armed':
            self.reason = reason
        return data

    def feed(self, data, now=None):
        if not self.armed or not data:
            return data
        now = time.monotonic() if now is None else now
        expired = self.tick(now)
        if not self.armed:
            return expired + data
        if self.started is None:
            self.started = now
        # Hold at most the short marker, regardless of input chunk size.
        take = min(len(PREFIX) - len(self.pending), len(data))
        self.pending.extend(data[:take])
        remainder = data[take:]
        if not PREFIX.startswith(self.pending):
            return self.finish('different-prefix') + remainder
        if len(self.pending) == len(PREFIX):
            self.suppressed = 1
            self.reason = 'recognized-startup-FF'
            return self.finish()[1:] + remainder
        return b''

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        if self.armed and self.started is not None and now - self.started >= self.seconds:
            return self.finish('incomplete-prefix-timeout')
        return b''


def bridge(peer, link, *, raw=False, seconds=10):
    """link.read/send own the raw log, before this presentation-only filter."""
    filt = BootPrefixFilter(enabled=not raw, seconds=seconds)
    peer.settimeout(5)
    rx = tx = 0
    # Drain TCP through EOF even if Tera Term has already exited: its final
    # file-transfer bytes can still be queued in the socket receive buffer.
    while True:
        ready, _, _ = select.select([peer], [], [], .01)
        if ready:
            data = peer.recv(4096)
            if not data:
                break
            held = filt.finish('client-transmission')
            if held:
                peer.sendall(held)
            link.send(data)
            tx += len(data)
        data = link.read(min(4096, max(1, link.serial.in_waiting)))
        rx += len(data)
        shown = filt.feed(data) + filt.tick()
        if shown:
            peer.sendall(shown)
    return dict(raw_RX_bytes=rx, client_TX_bytes=tx,
                suppressed_startup_FF=filt.suppressed, filter_end=filt.reason,
                incomplete_prefix_retained_in_raw_log=len(filt.pending))


def profile_bytes(source, port):
    """Copy settings; change only the private loopback profile, never defaults."""
    text = source.decode('utf-16') if source.startswith(b'\xff\xfe') else source.decode('utf-8-sig')
    values = dict(Port='tcpip', HostName='127.0.0.1', TCPPort=str(port),
                  Telnet='off', TelAutoDetect='off', TCPLocalEcho='off',
                  TCPCRSend='', TelEcho='off', AutoWinClose='on',
                  LogBinary='on', LogAutoStart='off', EnableLineMode='off',
                  StartupMacro='')
    pending = {k.lower(): (k, v) for k, v in values.items()}
    lines, active, found = [], False, False
    for line in text.splitlines():
        if line.startswith('['):
            if active:
                lines.extend(k + '=' + v for k, v in pending.values())
                pending.clear()
            active = line.strip().lower() == '[tera term]'
            if active and found:
                raise ValueError('Duplicate Tera Term settings section')
            found |= active
        key = line.split('=', 1)[0].strip().lower()
        if active and key in pending:
            k, v = pending.pop(key)
            line = k + '=' + v
        elif active and key in {k.lower() for k in values}:
            raise ValueError('Duplicate modified profile key: ' + key)
        lines.append(line)
    if active:
        lines.extend(k + '=' + v for k, v in pending.values())
    if not found:
        raise ValueError('Tera Term settings section missing')
    return ('\r\n'.join(lines) + '\r\n').encode('utf-16')


def check_marker(marker):
    if not marker.get('application_ram_restored'):
        raise ValueError('2512 owner RAM is not recorded as restored')
    for key in ('block_snapshot', 'application_RAM_restore_pending',
                'physical_reset_pending', 'installer_worker_active',
                'recovery_worker_active', 'RTC_collection_pending_monitor_recovery'):
        if marker.get(key):
            raise ValueError('2512 preservation/operation gate: ' + key)


def launch(args):
    # No serial/device imports or opens during module import and tests.
    from serial_test_coordination import serial_lease
    from serial.tools.list_ports import comports
    from installer.engine.legacy_transport import Link
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    run = ROOT / 'output/terminal/2512' / stamp
    run.mkdir(parents=True)
    receipt = dict(board='2512', usb_serial=USB, raw_mode=args.raw,
                   started_utc=stamp, startup_filter_sends_no_bytes=True,
                   other_boards_opened=[], raw_log='serial-raw.jsonl')
    process = None
    try:
        with serial_lease('teraterm-2512-startup-display', timeout=30):
            check_marker(json.loads(MARKER.read_bytes()))
            ports = [p for p in comports() if p.serial_number == USB]
            if len(ports) != 1:
                raise ValueError('Unique 2512 USB discovery required')
            with socket.socket() as server, (run / 'serial-raw.jsonl').open('x') as log:
                server.bind(('127.0.0.1', 0))
                server.listen(1)
                server.settimeout(.2)
                port = server.getsockname()[1]
                profile = run / '2512.ini'
                source = args.profile.read_bytes()
                profile.write_bytes(profile_bytes(source, port))
                receipt.update(source_profile_sha256=hashlib.sha256(source).hexdigest(),
                               private_profile=str(profile), loopback_port=port)
                link = Link(ports[0].device, log)
                try:
                    process = subprocess.Popen([str(args.teraterm), '127.0.0.1',
                        '/P=' + str(port), '/T=0', '/F=' + str(profile),
                        '/L=' + str(run / 'teraterm-received.bin'),
                        '/W=STR8-N 2512 - startup FF filtered' if not args.raw
                        else '/W=STR8-N 2512 - raw'])
                    deadline = time.monotonic() + 30
                    while True:
                        if process.poll() is not None or time.monotonic() > deadline:
                            raise TimeoutError('Private Tera Term did not connect')
                        try:
                            peer, _ = server.accept()
                            break
                        except socket.timeout:
                            pass
                    with peer:
                        receipt.update(state='connected-awaiting-startup', worker_pid=os.getpid(),
                                       teraterm_pid=process.pid, serial_released=False,
                                       shared_lease_released=False)
                        (run / 'session.json').write_text(json.dumps(receipt, indent=2) + '\n')
                        receipt.update(bridge(peer, link, raw=args.raw))
                    receipt['state'] = 'closed'
                    receipt['completed'] = True
                finally:
                    link.serial.close()
                    receipt['serial_released'] = not link.serial.is_open
        receipt['shared_lease_released'] = True
    except BaseException as error:
        receipt.update(state='failed', completed=False,
                       failure=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        (run / 'session.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print('2512 terminal session: ' + str(run), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch', action='store_true', required=True)
    parser.add_argument('--raw', action='store_true', help='Bypass startup suppression entirely')
    parser.add_argument('--teraterm', type=Path, default=Path('C:/Program Files/teraterm5/ttermpro.exe'))
    parser.add_argument('--profile', type=Path,
                        default=Path(os.environ['APPDATA']) / 'teraterm5/TERATERM.INI')
    args = parser.parse_args()
    if not args.teraterm.is_file() or not args.profile.is_file():
        parser.error('Installed Tera Term and existing settings are required')
    if importlib.util.find_spec('serial') is None:
        local = ROOT / 'tmp/migration-python'
        if not (local / 'serial/__init__.py').is_file():
            parser.error('pyserial is required by the selected Python runtime')
        # Existing local pyserial 3.5 used by the qualified board tools. No
        # installation, download, import hook or global environment change.
        sys.path.append(str(local))
    launch(args)


if __name__ == '__main__':
    main()
