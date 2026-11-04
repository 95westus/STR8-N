"""CPU/NOR tests of the ROM-to-RAM FLASH page. No serial/device access."""
import argparse
import json
from pathlib import Path
import test_b14_tools as tools

base = tools.base
base.GENERATION = 0x8000000f
PROMPT = b'FLASH> '
CONFIRM = b'00; type YES> '


class Machine(tools.InstallerMachine):
    def __init__(self, build, cpu, origin=0x8000, rows=None, monitors=True, banks=None,
                 accelerated=True):
        if rows is None:
            rows = [(0xc000, base.record(target='0', pages=(origin >> 12, 8, 8, 8)))]
        super().__init__(build, cpu, rows, banks)
        self.i = self.sy[f'core/bank-monitor-{origin:04x}']
        self.accelerate_local_crc = accelerated
        if banks is None:
            # Distinct full sectors make preservation checks meaningful.
            for bank, sector in tools.ALLOWED:
                offset = (sector - 0x80) << 8
                self.m.banks[bank][offset:offset+4096] = bytes(
                    (n + bank * 37 + sector) & 255 for n in range(4096))
            image = (build / f'payload/bank-monitor-{origin:04x}.bin').read_bytes()
            offset = origin - 0x8000
            self.m.banks[0][offset:offset+len(image)] = image
            if monitors:
                tools.install_protected_monitor_fixtures(self)
        self.origin = origin

    def boot(self, ending=PROMPT):
        # Exercise the saved B0 default through the complete countdown,
        # opaque handoff and ROM copying. No key forces the selection.
        self.c.pc = self.b['BOOT_START_CHOICES']
        # The established core runner folds the previously qualified empty
        # startup drain. Switch back to the OIP runner for local RAM CRCs.
        base.Machine.run(self, lambda: self.c.pc == self.origin and self.m.bank == 0)
        self.run(lambda: bytes(self.m.tx).endswith(ending))
        if ending == PROMPT:
            assert self.m.bank == 3 and self.m.ram[self.i['BM_HOME']] == 0
        self.m.rx.clear()
        self.m.acia_rx.clear()

    def cmd(self, command, port=1, ending=PROMPT):
        # Both consoles broadcast text. Finish the slower ACIA prompt before
        # changing input ports so an old trailing prompt cannot end the call.
        self.run(lambda: self.c.pc == self.w['V2W_GETC'] and not self.m.rx
                 and not self.m.acia_rx and not self.m.ram[0xf9])
        return self.port_command(port, command, ending)

    def write(self, command, port=1, yes=b'YES\r'):
        first = self.cmd(command, port, CONFIRM)
        return first + self.cmd(yes, port)


def settings(row):
    # Boot/default/enable/entries/MON pins/config stay exactly the same.
    return row[7:8] + row[12:30] + row[32:64] + row[160:252]


def run(build):
    passed = []
    def ok(cpu, name, **extra):
        passed.append(dict(cpu=cpu, name=name, **extra))
        print(cpu, name, flush=True)

    for cpu in ('65c02', '65c816-e'):
        for origin in (0x8000, 0x9000):
            h = Machine(build, cpu, origin)
            before = tuple(map(bytes, h.m.banks))
            h.boot()
            ram = (build / f'payload/bank-monitor-{origin:04x}-ram.bin').read_bytes()
            # Mutable state has changed; immutable code and expected CRC match.
            end = h.i['BM_CODE_CRC'] + 2
            assert h.m.ram[0x200:end] == ram[:end-0x200]
            assert tuple(map(bytes, h.m.banks)) == before and not h.m.events
            ok(cpu, f'ROM-{origin:04X}-opaque-copy-boot')
            for port in (1, 2):
                out = h.cmd(b'?\r\n', port)
                assert b'F addr byte...' in out
                assert b'Data bank B2' in h.cmd(b'B2\r', port)
                expected = h.sector(2, 0x80)[:16]
                out = h.cmd(b'D 8000\r', port)
                assert (' '.join(f'{b:02X}' for b in expected)).encode() in out
                assert b'OK: RAM' in h.cmd(b'M 2000 01 02 03 04\r', port)
                assert h.m.ram[0x2000:0x2004] == b'\x01\x02\x03\x04'
                assert b'OK: RAM' in h.cmd(b'M 64FF 42\r', port)
                assert h.m.ram[0x64ff] == 0x42
                prefix = bytes(h.m.ram[0x2000:0x6500])
                for line in (b'M 1FFF 01\r', b'M 64FF 00 01\r', b'M FFFF 01\r',
                             b'M 2000 01 GG\r', b'M 2000\r',
                             b'M 2000 1 2 3 4 5 6 7 8 9\r', b'B4\r', b'B9\r',
                             b'D 7F80\r', b'D FFF1\r', b'D 64F1\r', b'D 1FFF\r',
                             b'D 8000 ZZ\r', b'Q X\r', b'I 9001\r'):
                    assert b'REFUSED:' in h.cmd(line, port), line
                    assert bytes(h.m.ram[0x2000:0x6500]) == prefix
                ok(cpu, f'{origin:04X}-port{port}-dump-RAM-parse-range')
            h.cmd(b'B0\r')
            protected = (0x80,) if origin == 0x8000 else (0x90, 0xa0)
            for sector in protected:
                for op in ('F', 'I'):
                    cmd = f'{op} {sector:02X}00' + (' 55' if op == 'F' else '') + '\r'
                    assert b'REFUSED:' in h.cmd(cmd.encode())
            h.cmd(b'B3\r')
            for sector in (0xa0, 0xb0, 0xc0, 0xd0, 0xf0):
                for op in ('F', 'I'):
                    cmd = f'{op} {sector:02X}00' + (' 55' if op == 'F' else '') + '\r'
                    assert b'REFUSED:' in h.cmd(cmd.encode())
            assert tuple(map(bytes, h.m.banks)) == before
            ok(cpu, f'{origin:04X}-self-and-B3-protection')
            out = h.cmd(b'Q\r', ending=b'B3> ')
            assert b'2.0proto b15' in out and h.m.ram[h.b['BOOT_ACTIVE']] == 0xb0
            assert tuple(map(bytes, h.m.banks)) == before
            ok(cpu, f'{origin:04X}-Q-returns-B3-default-stays-B0')

        # Successful flash edits in arbitrary target banks, including B3 user E.
        for bank, sector, port in ((0, 0x90, 1), (1, 0xf0, 2), (3, 0xe0, 1)):
            h = Machine(build, cpu)
            h.boot()
            h.cmd(f'B{bank}\r'.encode(), port)
            h.m.arm((bank, sector))
            original = h.sector(bank, sector)
            record = tools.latest_record(h.m.banks)
            command = f'F {sector:02X}FE FF 00 55 AA\r'.encode()
            # This crosses a CPU page, but stays within the same 4K sector.
            out = h.write(command, port)
            assert b'OK: verified sector' in out, out
            wanted = original[:254] + b'\xff\x00\x55\xaa' + original[258:]
            assert h.sector(bank, sector) == wanted
            newest = tools.latest_record(h.m.banks)
            assert settings(newest) == settings(record)
            for b in range(4):
                for s in range(0x80, 0x100, 0x10):
                    assert tools.counter(newest, b, s) == tools.counter(record, b, s) + int((b, s) == (bank, sector))
            assert len(h.m.reservations) == 1
            h.m.assert_preserved()
            ok(cpu, f'B{bank}-{sector:02X}-port{port}-edit-preserve-4092-wear-first')
            h.m.arm((bank, sector))
            assert b'identical; no erase' in h.write(command, port)
            assert not h.m.events
            ok(cpu, f'B{bank}-{sector:02X}-identical-no-wear')
            h.m.arm((bank, sector))
            baseline = tuple(map(bytes, h.m.banks))
            assert b'Cancelled' in h.write(f'I {sector:02X}00\r'.encode(), port, b'NO\r')
            assert b'Cancelled' in h.write(f'I {sector:02X}00\r'.encode(), port, b'\x03')
            assert tuple(map(bytes, h.m.banks)) == baseline and not h.m.events
            assert b'REFUSED:' in h.cmd(f'F {sector+15:02X}FF 01 02\r'.encode(), port)
            assert not h.m.events
            ok(cpu, f'B{bank}-{sector:02X}-cancel-and-sector-boundary')
            assert b'OK: verified sector' in h.write(f'I {sector:02X}00\r'.encode(), port)
            assert h.sector(bank, sector) == b'\xff' * 4096
            assert h.m.target_erases == 1
            h.m.assert_preserved()
            ok(cpu, f'B{bank}-{sector:02X}-erase-verify')

        # All eligible targets are admitted without mutation when already erased.
        for bank, sector in tools.ALLOWED:
            if (bank, sector) == (0, 0x80):
                continue
            h = Machine(build, cpu)
            offset = (sector - 0x80) << 8
            h.m.banks[bank][offset:offset+4096] = b'\xff' * 4096
            h.boot()
            h.cmd(f'B{bank}\r'.encode())
            h.m.arm((bank, sector))
            assert b'identical; no erase' in h.write(f'I {sector:02X}00\r'.encode())
            assert not h.m.events
        ok(cpu, 'all-26-eligible-targets-noop-admitted')

        # Confirmation pauses are untrusted: recheck stage and target before JE.
        for kind in ('stage', 'preimage'):
            h = Machine(build, cpu)
            h.boot()
            h.m.arm((0, 0x90))
            h.cmd(b'F 9000 42\r', ending=CONFIRM)
            if kind == 'stage':
                h.m.ram[0x6800] ^= 1
            else:
                h.m.banks[0][0x1001] ^= 1
            baseline = tuple(map(bytes, h.m.banks))
            out = h.cmd(b'YES\r')
            assert (b'staging CRC' if kind == 'stage' else b'preimage CRC') in out
            assert tuple(map(bytes, h.m.banks)) == baseline and not h.m.events
            ok(cpu, kind + '-changed-before-confirm-refused')

        # Invalid and conflicting journal history must prevent target mutation.
        for kind in ('bad-crc', 'conflicting-duplicate', 'saturated-wear'):
            row = base.record(target='0')
            if kind == 'bad-crc':
                bad = bytearray(row); bad[50] ^= 1
                rows = [(0xc000, bytes(bad))]
            elif kind == 'conflicting-duplicate':
                rows = [(0xc000, row), (0xc100, base.record(target='B'))]
            else:
                counts = [1] * 32; counts[1] = 0xffffff
                rows = [(0xc000, base.record(target='0', counts=counts))]
            h = Machine(build, cpu)
            h.boot()
            # Inject after normal boot to isolate writer admission. Conflicting
            # boot-record headers would otherwise block default selection.
            h.m.banks[3][0x4000:0x6000] = b'\xff' * 8192
            for address, row in rows:
                h.m.banks[3][address-0x8000:address-0x8000+256] = row
            h.m.arm((0, 0x90))
            before = tuple(map(bytes, h.m.banks))
            assert b'durable wear reservation' in h.write(b'F 9000 42\r')
            assert tuple(map(bytes, h.m.banks)) == before and not h.m.events
            ok(cpu, kind + '-journal-refusal')

        for kind in ('fallback-A', 'no-MON'):
            h = Machine(build, cpu)
            if kind == 'fallback-A':
                h.m.banks[3][0x3085] ^= 1
            else:
                h.m.banks[3][0x2000:0x4000] = b'\xff' * 8192
            h.boot()
            before = tuple(map(bytes, h.m.banks))
            h.cmd(b'Q\r', ending=b'REC> ' if kind == 'no-MON' else b'B3> ')
            if kind == 'fallback-A':
                assert h.m.ram[h.b['BOOT_ACTIVE']] == 0xa0
            assert tuple(map(bytes, h.m.banks)) == before
            ok(cpu, 'Q-' + kind)

        for kind in ('code', 'F'):
            h = Machine(build, cpu)
            h.boot()
            if kind == 'code':
                h.m.ram[h.i['BM_HELP']] ^= 1
            else:
                h.m.banks[3][0x7ff0] ^= 1
            before = tuple(map(bytes, h.m.banks))
            h.m.rx.extend(b'F 9000 42\r')
            h.run(lambda: h.c.pc == h.i['BM_HALT'])
            assert b'CRC mismatch' in h.m.tx
            assert tuple(map(bytes, h.m.banks)) == before and not h.m.events
            ok(cpu, kind + '-CRC-fail-closed')

        # Interrupt a representative erase and program; source and MON survive.
        for cut in ('erase', 'program'):
            h = Machine(build, cpu)
            h.boot()
            h.m.arm((0, 0x90))
            before = tuple(map(bytes, h.m.banks))
            def observe(memory):
                event = memory.events[-1]
                if event[1] == 0 and event[0] == cut:
                    raise tools.PowerLoss()
            h.m.observer = observe
            try:
                h.write(b'F 9000 42\r')
                raise AssertionError('Expected interruption')
            except tools.PowerLoss:
                pass
            h.m.assert_preserved()
            assert settings(tools.latest_record(h.m.banks)) == settings(tools.latest_record(before))
            reboot = Machine(build, cpu, banks=h.m.banks)
            reboot.boot()
            reboot.cmd(b'Q\r', ending=b'B3> ')
            ok(cpu, cut + '-interruption-source-MON-survive-reboot')

    # Differential check: run the real local CRC instructions on one whole boot.
    h = Machine(build, '65c02', accelerated=False)
    h.boot()
    h.cmd(b'Q\r', ending=b'B3> ')
    ok('65c02', 'local-CRC-real-opcodes-boot-and-Q')
    result = dict(passed=True, hardware=False, serial_access=False,
                  groups=len(passed), tests=passed,
                  test_source_sha256=base.sha(Path(__file__).read_bytes()),
                  build_sha256=base.sha((build / 'bank-monitor-build.json').read_bytes()))
    base.save(build / 'bank-monitor-tests.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    x = p.parse_args()
    result = run(x.build.resolve())
    print('PASS', result['groups'], 'groups', flush=True)
