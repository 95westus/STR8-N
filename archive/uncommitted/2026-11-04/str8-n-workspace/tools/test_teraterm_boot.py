"""Data-integrity tests and installed Tera Term test with synthetic serial only."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import socket
import subprocess
import threading
import time

import teraterm_boot as boot


class FakeLink:
    def __init__(self):
        self.serial = self
        self.chunks = queue.Queue()
        self.raw = bytearray()
        self.tx = bytearray()
        self.ack = None

    @property
    def in_waiting(self):
        return 4096 if not self.chunks.empty() else 0

    def read(self, count):
        try:
            data = self.chunks.get(timeout=.01)
        except queue.Empty:
            return b''
        self.raw.extend(data)
        return data

    def send(self, data):
        self.tx.extend(data)
        if self.ack is not None and len(self.tx) == 4096:
            self.chunks.put(self.ack)


def recv_exact(peer, count):
    data = bytearray()
    peer.settimeout(5)
    while len(data) < count:
        part = peer.recv(count - len(data))
        assert part, 'Unexpected peer close'
        data.extend(part)
    return bytes(data)


def basic_tests(raw):
    assert raw.startswith(boot.PREFIX)
    wanted = raw[1:]
    checks = []
    for split in range(len(raw) + 1):
        f = boot.BootPrefixFilter()
        assert f.feed(raw[:split]) + f.feed(raw[split:]) + f.finish() == wanted
        assert f.suppressed == 1
    checks.append('saved FF boot: every two-chunk split')
    f = boot.BootPrefixFilter()
    assert b''.join(f.feed(bytes([b])) for b in raw) + f.finish() == wanted
    checks.append('saved FF boot: single-byte delivery')
    f = boot.BootPrefixFilter()
    assert f.feed(wanted) == wanted and f.suppressed == 0
    checks.append('clean boot unchanged')
    for first in range(256):
        f = boot.BootPrefixFilter()
        value = bytes([first]) + wanted
        assert f.feed(value) + f.finish() == (wanted if first == 255 else value)
    checks.append('all 256 possible leading bytes')
    for value in (b'\xff\xff' + wanted, b'\xffother', b'prefix' + raw,
                  b'\xff\r\nWAIt...\r\n', b'\xff' + b'.' * 160):
        f = boot.BootPrefixFilter()
        assert f.feed(value) + f.finish() == value and f.suppressed == 0
    checks.append('unrecognized/multiple/interior FF and old dots preserved')
    for length in range(1, len(boot.PREFIX)):
        f = boot.BootPrefixFilter()
        assert f.feed(boot.PREFIX[:length], now=0) == b''
        assert f.tick(now=11) == boot.PREFIX[:length] and f.suppressed == 0
    checks.append('every truncated prefix preserved on timeout')
    f = boot.BootPrefixFilter()
    assert f.feed(b'\xff', now=0) == b''
    assert f.feed(raw[1:], now=11) == raw and f.suppressed == 0
    checks.append('late completion cannot strip expired prefix')
    f = boot.BootPrefixFilter()
    assert f.feed(b'\xff') == b''
    assert f.finish('client-transmission') + f.feed(raw[1:]) == raw
    assert f.suppressed == 0
    checks.append('host TX during held FF preserves the entire prefix')
    binary = bytes(range(256)) * 16
    f = boot.BootPrefixFilter()
    assert f.feed(raw + binary) == wanted + binary
    assert f.feed(raw + binary) == raw + binary
    checks.append('one-shot only; subsequent FF and 4096-byte payload exact')
    f = boot.BootPrefixFilter(enabled=False)
    assert f.feed(raw + binary) == raw + binary and f.suppressed == 0
    checks.append('raw mode bypasses even an exact boot-looking binary prefix')
    return checks


def bridge_test(raw, *, transmit_first=False):
    link = FakeLink()
    client, peer = socket.socketpair()
    results, errors = [], []
    def run():
        try:
            with peer:
                results.append(boot.bridge(peer, link))
        except BaseException as error:
            errors.append(repr(error))
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    binary = bytes(range(256)) * 16
    with client:
        if transmit_first:
            client.sendall(binary)
            deadline = time.monotonic() + 5
            while len(link.tx) < len(binary) and time.monotonic() < deadline:
                time.sleep(.01)
            assert bytes(link.tx) == binary
        link.chunks.put(raw + binary)
        expected = (raw if transmit_first else raw[1:]) + binary
        assert recv_exact(client, len(expected)) == expected
        assert bytes(link.raw) == raw + binary
        if not transmit_first:
            client.sendall(binary)
            deadline = time.monotonic() + 5
            while len(link.tx) < len(binary) and time.monotonic() < deadline:
                time.sleep(.01)
            assert bytes(link.tx) == binary
    worker.join(5)
    assert not worker.is_alive() and not errors, errors
    assert results[0]['suppressed_startup_FF'] == (0 if transmit_first else 1)
    return results[0]


def native_test(raw, out):
    """Actual installed executable, loopback socket and fake serial; no COM open."""
    exe = Path('C:/Program Files/teraterm5/ttermpro.exe')
    profile = Path.home() / 'AppData/Roaming/teraterm5/TERATERM.INI'
    original_profile = profile.read_bytes()
    payload = bytes(range(256)) * 16
    (out / 'payload.bin').write_bytes(payload)
    macro = out / 'test.ttl'
    macro.write_text("for attempt 1 100\n testlink\n if result = 2 break\n mpause 50\nnext\n"
        "fileopen fh '" + str(out / 'macro-ready.txt') + "' 0\n"
        "filewriteln fh 'ready'\nfileclose fh\ntimeout=8\nwait 'B3> '\n"
        "bootresult=result\nfileopen fh '" + str(out / 'macro-trace.txt') + "' 0\n"
        "int2str value bootresult\nfilewriteln fh value\nfileclose fh\n"
        "if bootresult = 1 then\n sendfile '" + str(out / 'payload.bin') +
        "' 1\n wait 'FF_TEST_DONE'\n"
        " fileopen fh '" + str(out / 'macro-RX-ready.txt') + "' 0\n"
        " filewriteln fh 'ready'\n fileclose fh\n"
        " recvfile '" + str(out / 'native-received.bin') + "' 1 2\n"
        "endif\npause 1\nclosett\nend\n", encoding='ascii')
    link = FakeLink()
    link.ack = b'FF_TEST_DONE\r\n'
    results, errors = [], []
    process = None
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0)); server.listen(1); server.settimeout(10)
        port = server.getsockname()[1]
        target_profile = out / 'test.ini'
        target_profile.write_bytes(boot.profile_bytes(original_profile, port))
        log = out / 'teraterm-received.bin'
        try:
            process = subprocess.Popen([str(exe), '127.0.0.1', '/P=' + str(port),
                '/T=0', '/V', '/F=' + str(target_profile), '/M=' + str(macro),
                '/L=' + str(log), '/W=STR8-N offline FF test'])
            peer, _ = server.accept()
            def run():
                try:
                    with peer:
                        results.append(boot.bridge(peer, link))
                except BaseException as error:
                    errors.append(repr(error))
            worker = threading.Thread(target=run, daemon=True); worker.start()
            deadline = time.monotonic() + 10
            while not (out / 'macro-ready.txt').exists() and time.monotonic() < deadline:
                time.sleep(.02)
            assert (out / 'macro-ready.txt').exists(), 'Native macro did not arm'
            link.chunks.put(raw)
            deadline = time.monotonic() + 10
            while not (out / 'macro-RX-ready.txt').exists() and time.monotonic() < deadline:
                time.sleep(.02)
            assert (out / 'macro-RX-ready.txt').exists(), 'Native binary receiver did not arm'
            time.sleep(.5)
            link.chunks.put(payload)
            process.wait(timeout=15)
            worker.join(5)
            (out / 'synthetic-actual-TX.bin').write_bytes(link.tx)
            (out / 'native-diagnostics.json').write_text(json.dumps(dict(
                process_exit=process.returncode, bridge=results, errors=errors,
                raw_RX_bytes=len(link.raw), actual_TX_bytes=len(link.tx),
                actual_TX_sha256=hashlib.sha256(link.tx).hexdigest(),
                expected_TX_sha256=hashlib.sha256(payload).hexdigest(),
                synthetic_TX_prefix_hex=bytes(link.tx[:32]).hex(),
                teraterm_log_bytes=log.stat().st_size if log.exists() else None), indent=2)+'\n')
            assert not worker.is_alive() and not errors, errors
            assert bytes(link.raw) == raw + link.ack + payload
            assert bytes(link.tx) == payload, 'Tera Term binary send changed bytes'
            assert (out / 'native-received.bin').read_bytes() == payload, 'Native binary receive changed bytes'
            assert log.read_bytes().startswith(raw[1:] + link.ack), 'Tera Term startup log differs'
            assert profile.read_bytes() == original_profile
            return dict(passed=True, fake_serial=True, COM_ports_opened=0,
                        startup_and_ACK_bytes=len(raw)-1+len(link.ack), binary_TX_bytes=len(payload),
                        binary_RX_bytes=len(payload),
                        raw_FF_retained=True, default_profile_unchanged=True,
                        teraterm_received_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
        finally:
            if process is not None and process.poll() is None:
                process.terminate(); process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args(); out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    source = boot.ROOT / 'output/qualification/pr04-b07-2512-install-r2/prearmed-reset-boot.txt'
    raw = source.read_bytes()
    checks = basic_tests(raw)
    bridges = [bridge_test(raw), bridge_test(raw, transmit_first=True)]
    checks.extend(['duplex 4096-byte binary bridge and raw log', 'client TX cancels filter before binary data'])
    p = boot.profile_bytes(b'[Tera Term]\r\nPort=serial\r\n[Other]\r\nPort=serial\r\n', 12345).decode('utf-16')
    assert 'Port=tcpip' in p and '[Other]\r\nPort=serial' in p and 'TelAutoDetect=off' in p
    checks.append('private UTF16 profile with raw TCP and unrelated settings preserved')
    boot.check_marker(dict(application_ram_restored=True))
    for key in ('block_snapshot', 'application_RAM_restore_pending', 'physical_reset_pending',
                'installer_worker_active', 'recovery_worker_active', 'RTC_collection_pending_monitor_recovery'):
        try:
            boot.check_marker(dict(application_ram_restored=True, **{key: True}))
        except ValueError:
            pass
        else:
            raise AssertionError('Pending gate accepted: ' + key)
    checks.append('preservation and operation gates refuse before COM open')
    native = native_test(raw, out) if args.native else None
    if native:
        checks.append('installed Tera Term: filtered boot and exact 4096-byte binary files in both directions')
    report = dict(passed=True, checks=len(checks), cases=checks, bridges=bridges,
                  native=native, hardware=False, COM_ports_opened=0,
                  source_capture_sha256=hashlib.sha256(raw).hexdigest(),
                  source_sha256=hashlib.sha256(Path(boot.__file__).read_bytes()).hexdigest(),
                  checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, checks=len(checks), hardware=False, COM_ports_opened=0)))


if __name__ == '__main__':
    main()
