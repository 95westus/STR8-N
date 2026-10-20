"""Run the full-soak units against exact v1g CPU instructions, without hardware.

Only model metadata is seeded before boot. Firmware/utility instructions, FT245,
bit-level RTC/EEPROM I2C and SPI SRAM execute without replacing utility results.
The 816 may run rc1's bounded existing reset detector; all applications remain E=1.
"""
import argparse
import ast
import binascii
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FIRMWARE = '6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe_pairs(writes, original):
    """Accept only the exact v1g reserved-byte discovery toggle/restore pair."""
    expected = [(0x1ffff, original ^ 255), (0x1ffff, original)]
    assert len(writes) % 2 == 0, ('incomplete volatile SRAM probe', writes)
    for offset in range(0, len(writes), 2):
        assert writes[offset:offset+2] == expected, ('unexpected volatile SRAM write', writes)
    return len(writes)//2


def selected_classes(path, names, namespace):
    """Read only class definitions; never execute old builders/module main code."""
    tree = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    for name in names:
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def peripheral_classes():
    bus = selected_classes(ROOT/'tools/test_v2_rtc.py', ['BusMemory'],
                           dict(OUT=ROOT/'BUILD/v2-rtc-phase1'))
    bus['Memory'] = bus['BusMemory']
    selected_classes(ROOT/'tools/test_v2_i2c.py', ['Devices'], bus)
    selected_classes(ROOT/'tools/test_v2_journal.py', ['EEPROM'], bus)
    spi = selected_classes(ROOT/'tools/test_v2_spi_prototype.py', ['SRAM', 'Memory'],
                           dict(ROOT=ROOT, BODY=b''))
    return bus['EEPROM'], spi['Memory']


def s19(path):
    cells = {}
    entry = None
    for line in Path(path).read_text().splitlines():
        raw = bytes.fromhex(line[2:])
        assert sum(raw)&255 == 255 and len(raw) == raw[0]+1
        address = int.from_bytes(raw[1:3], 'big')
        if line.startswith('S1'):
            for i, value in enumerate(raw[3:-1]):
                assert address+i not in cells
                cells[address+i] = value
        elif line.startswith('S9'):
            entry = address
    return cells, entry


def metadata(slot):
    config = bytearray([1, 0, 3, 7, 0xf0, 10, 0]+[0]*9)
    config[7:13] = b'P'+bytes([0xa0 if slot == 'A' else 0xb0])+(50).to_bytes(4, 'little')
    a = b = 0
    for value in config[:14]:
        a = (a+value)&255
        b = (b+a)&255
    config[14:] = bytes([a, b])
    record = bytearray(b'\xff'*128)
    record[:8] = b'WC\x01\x00'+(1).to_bytes(4, 'little')
    record[8:24] = config
    record[24:120] = bytes(96)
    record[120:122] = binascii.crc_hqx(record[:120], 0xffff).to_bytes(2, 'little')
    record[127] = 0
    return bytes(record)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--build', type=Path, default=ROOT/'BUILD/rc1-debugger-v1g')
    ap.add_argument('--cpu', choices=('65c02', '65c816-e'), required=True)
    ap.add_argument('--module', type=Path, default=ROOT/'tools/rc1_dbg_full_soak_units.py')
    ap.add_argument('--cycle', type=int, default=0)
    ap.add_argument('--builtins-only', action='store_true')
    args = ap.parse_args()
    assert args.run.resolve().is_relative_to((ROOT/'output/qualification').resolve())
    harness_hash = sha(__file__)
    units_hash = sha(args.module)
    sys.path[:0] = [str(ROOT/'BUILD/v1.30/local/test-deps'), str(ROOT/'BUILD/test-deps-816'),
                    str(args.run), str(ROOT/'tools')]
    import serial
    def forbidden(*a, **kw):
        raise AssertionError('No hardware or network access in CPU qualification')
    serial.Serial = forbidden
    import socket
    socket.create_connection = forbidden
    socket.socket = forbidden
    is816 = args.cpu == '65c816-e'
    if is816:
        from py65816.devices.mpu65c816 import MPU as BaseMPU
        MODEL_SHA256 = 'a94fc4c40f3a252b0c5197252ce0ea35310b6f5ada986c40eae16c649d5bfc02'
        model_hash = sha(sys.modules[BaseMPU.__module__].__file__)
        assert model_hash == MODEL_SHA256
    else:
        from py65.devices.mpu65c02 import MPU as BaseMPU
        model_hash = sha(sys.modules[BaseMPU.__module__].__file__)
    image = (args.build/'firmware.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest() == EXPECTED_FIRMWARE
    symbols = json.loads((args.build/'symbols.json').read_text())
    boot = symbols['core/str8n-v2-boot']
    xce, restore = boot['BOOT_XCE'], boot['BOOT_XCE_RESTORE']
    detector = (xce+1, xce+2, xce+4, restore-1, restore)
    EEPROM, SPI = peripheral_classes()

    class Memory:
        def __init__(self, slot):
            self.ram = bytearray(b'\x5a'*65536)
            self.bank = 3
            self.banks = [bytearray(b'\xff'*32768)]+[bytearray(image[n:n+32768]) for n in range(0, len(image), 32768)]
            self.banks[0][-32:] = self.banks[3][-32:]
            self.banks[3][0x4000:0x6000] = metadata(slot)+b'\xff'*(8192-128)
            self.ram[0x7fec] = 0xee
            self.ram[0x7fe0] = 0x0c
            self.ram[0x7fe3] = 0
            self.ram[0x7fcb] = 0
            self.ram[0x7fce] = 0x80
            self.rx, self.tx = deque(), bytearray()
            self.flash_writes = []
            self.bus = EEPROM()
            self.bus.ram = self.ram
            self.bus.rtc_regs[:9] = bytes.fromhex('95 30 09 2a 20 10 26 00 0c')
            self.bus.ee[0xf2:0xf8] = bytes.fromhex('5410ecb664af')
            self.spi = SPI()
            self.spi.ram = self.ram
            self.spi.banks = self.banks
            layout = bytearray(64)
            layout[:7] = b'SS\x02\x08\x08\x00\x01'
            layout[8:12] = (1).to_bytes(4, 'little')
            layout[60:62] = binascii.crc_hqx(layout[:60], 0xffff).to_bytes(2, 'big')
            layout[63] = 0xa5
            self.spi.devices[0].data[:64] = layout
            self.steps = 0

        def __getitem__(self, address):
            if isinstance(address, slice):
                return [self[i] for i in range(*address.indices(65536))]
            assert 0 <= address <= 65535, ('nonzero CPU bank', hex(address))
            if address >= 0x8000:
                return self.banks[self.bank][address-0x8000]
            if address in (0x7fc3, 0x7fcf):
                return self.bus[address]
            if address in (0x7fc0, 0x7fc2, 0x7fcc, 0x7fcd):
                return self.spi[address]
            if address == 0x7fe0:
                return self.ram[address]&~0x23 | (0 if self.rx else 2)
            if address == 0x7fe1 and not self.ram[0x7fe3]:
                return self.rx[0] if self.rx else 0
            return self.ram[address]

        def __setitem__(self, address, value):
            assert 0 <= address <= 65535, ('nonzero CPU bank write', hex(address))
            value &= 255
            if address >= 0x8000:
                self.flash_writes.append((self.bank, address, value))
                raise AssertionError(('unexpected flash command', self.flash_writes[-1]))
            if address in (0x7fc3, 0x7fcf):
                self.bus[address] = value
                return
            if address in (0x7fc0, 0x7fc2):
                self.spi[address] = value
                return
            old = self.ram[address]
            self.ram[address] = value
            if address == 0x7fec:
                assert value&0xee in (0xcc, 0xce, 0xec, 0xee)
                self.bank = (1 if value&2 else 0)|(2 if value&0x20 else 0)
            elif address == 0x7fe0 and not old&8 and value&8 and self.rx:
                self.rx.popleft()
            elif address == 0x7fe3 and value == 255 and self.ram[0x7fe0]&4:
                self.tx.append(self.ram[0x7fe1])

    class MPU(BaseMPU):
        def __init__(self, memory):
            super().__init__(memory=memory, pc=0xf004)
            self.pc = 0xf004
            self.allow_reset = True
            self.native_steps = 0

        def step(self):
            self.memory.steps += 1
            op = self.memory[self.pc]
            if not is816 and op&15 == 15:
                zp = self.memory[(self.pc+1)&65535]
                offset = self.memory[(self.pc+2)&65535]
                bit = bool(self.memory[zp]&(1<<((op>>4)&7)))
                taken = bit if op&128 else not bit
                self.pc = (self.pc+3+(offset if offset < 128 else offset-256))&65535 if taken else (self.pc+3)&65535
                return self
            return super().step()

    def run(cpu, predicate, limit=40000000):
        trace = deque(maxlen=20)
        for _ in range(limit):
            if predicate():
                return
            if cpu.pc == 0x7af8:
                cpu.pc = (cpu.stPopWord()+1)&65535
                continue
            if is816:
                assert (cpu.pbr, cpu.dbr, cpu.dpr) == (0, 0, 0), list(trace)
                if not cpu.mode:
                    assert cpu.allow_reset and cpu.memory.bank == 3 and cpu.native_steps < len(detector), list(trace)
                    assert cpu.pc == detector[cpu.native_steps], list(trace)
                    cpu.native_steps += 1
            trace.append((cpu.memory.bank, cpu.pc, cpu.memory[cpu.pc], cpu.sp))
            cpu.step()
        raise AssertionError(('CPU timeout', list(trace), bytes(cpu.memory.tx[-500:])))

    def snapshot(m):
        return dict(flash=[hashlib.sha256(bytes(x)).hexdigest() for x in m.banks],
                    EEPROM=hashlib.sha256(m.bus.ee).hexdigest(), RTC=bytes(m.bus.rtc_regs).hex(),
                    SRAM=hashlib.sha256(m.spi.devices[0].data).hexdigest(), SRAM_mode=m.spi.devices[0].mode)

    spec = importlib.util.spec_from_file_location('full_units_cpu_under_test', args.module)
    units = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(units)
    assert sha(args.module) == units_hash, 'Unit source changed during import'
    cases = json.loads((args.run/'asm-cases.json').read_text())
    output = args.run/('full-soak-CPU-816.json' if is816 else 'full-soak-CPU-02.json')
    assert not output.exists(), 'Use a new result; never overwrite qualification'
    results = []
    transcripts = []
    started = time.monotonic()
    for slot in ('A', 'B'):
        m = Memory(slot)
        cpu = MPU(m)
        m.cpu = m.spi.cpu = cpu
        cpu.p = 0x24
        mon = symbols['core/monitor-'+slot.lower()+'0']
        print('CPU boot', args.cpu, slot, flush=True)
        run(cpu, lambda: cpu.pc == mon['V2_LINE_BYTE'] and m.tx.endswith(b'B3> '))
        assert m.ram[0x7d30] == (0xa0 if slot == 'A' else 0xb0)
        assert m.ram[0x7d0a:0x7d0c] == b'\xff\x64'
        if is816:
            assert cpu.mode == 1 and cpu.native_steps == len(detector)
            cpu.allow_reset = False
            cpu.b = 0xa5
        before = snapshot(m)
        write_counts = (len(m.bus.writes), len(m.spi.devices[0].writes), len(m.flash_writes))
        probe_original = m.spi.devices[0].data[0x1ffff]
        mode_write_count = len(m.spi.devices[0].mode_writes)

        class ModelLink:
            def __init__(self):
                self.cursor = len(m.tx)

            def send(self, value):
                m.rx.extend(value)

            def until(self, token, timeout=30):
                run(cpu, lambda: token in m.tx[self.cursor:])
                end = m.tx.index(token, self.cursor)+len(token)
                value = bytes(m.tx[self.cursor:end])
                self.cursor = end
                return value

            def command(self, text, prompt=b'\r\nB3> '):
                print('CPU command', args.cpu, slot, text, flush=True)
                self.cursor = len(m.tx)
                self.send(text.encode()+b'\r')
                value = self.until(prompt)
                transcripts.append(dict(slot=slot, command=text, prompt=prompt.decode(), output=value.decode('ascii', 'replace')))
                if is816:
                    assert cpu.mode == 1 and cpu.b == 0xa5, (text, cpu.mode, cpu.b)
                return value

            def dump(self, first, last, prompt=b'\r\nB3> '):
                text = self.command(f'D {first:04X} {last:04X}', prompt)
                import re
                rows = re.findall(rb'(?m)^([0-9A-F]{4}): ((?:[0-9A-F]{2}(?: |\r?$))+)', text)
                cells = {}
                for address, body in rows:
                    start = int(address, 16)
                    for n, v in enumerate(bytes.fromhex(body.decode())):
                        cells[start+n] = v
                return bytes(cells[a] for a in range(first, last+1))

        link = ModelLink()

        def load(link, path):
            cells, entry = s19(path)
            assert 0x200 <= min(cells) <= max(cells) <= 0x64ff and entry in cells
            link.command('L', b'S19')
            for row in Path(path).read_bytes().splitlines():
                link.send(row+b'\r\n')
            text = link.until(b'\r\nB3> ')
            assert f'Entry {entry:04X}'.encode() in text, text
            actual = bytes(m.ram[a] for a in sorted(cells))
            assert actual == bytes(cells[a] for a in sorted(cells))
            return cells

        transport = SimpleNamespace(load=load, read_range=lambda l, f, e, prompt=b'\r\nB3> ': l.dump(f, e, prompt))
        if args.builtins_only:
            base = dict(skipped=True, reason='explicit probe-only invocation')
        else:
            print('CPU base/utilities', args.cpu, slot, flush=True)
            base, _ = units.base_and_utilities(link, transport, args.cycle)
            assert base['passed']
            assert snapshot(m) == before, ('utility persistent mutation', slot, snapshot(m), before)
            probe_pairs(m.spi.devices[0].writes[write_counts[1]:], probe_original)
            assert len(m.bus.writes) == write_counts[0], ('RTC or EEPROM write during utilities', m.bus.writes)
        print('CPU builtins', args.cpu, slot, flush=True)
        probes, _ = units.builtins_unit(link, transport, cases, args.run/'builtin-images', args.cycle)
        assert probes['passed']
        assert snapshot(m) == before, ('probe persistent mutation', slot)
        assert not m.flash_writes
        assert len(m.bus.writes) == write_counts[0], ('RTC or EEPROM write', m.bus.writes)
        volatile_probe_writes = m.spi.devices[0].writes[write_counts[1]:]
        paired_probes = probe_pairs(volatile_probe_writes, probe_original)
        assert len(m.spi.devices[0].mode_writes) == mode_write_count, 'Unexpected SRAM mode write'
        row = dict(passed=True, slot=slot, CPU=args.cpu, base_utilities=base, builtins=probes,
                   persistent_snapshot_before=before, persistent_snapshot_after=snapshot(m),
                   persistent_writes_during_workload=0, CPU_steps=m.steps,
                   volatile_SRAM_discovery_probes=dict(address=0x1ffff, original=probe_original,
                       toggle_value=probe_original ^ 255, paired_probes=paired_probes,
                       writes=volatile_probe_writes, exact_toggle_restore_pairs_verified=True,
                       full_array_and_mode_unchanged=True),
                   reset_detector_native_steps=cpu.native_steps if is816 else 0,
                   native_applications=False, native_debugging=False)
        results.append(row)
        print('PASS', args.cpu, 'MON', slot, 'full base/utilities and fixed BRK probes' if not args.builtins_only else 'fixed BRK probes', flush=True)
    assert sha(__file__) == harness_hash, 'CPU harness source changed during qualification'
    assert sha(args.module) == units_hash, 'Unit source changed during qualification'
    proof = dict(passed=True, CPU=args.cpu, results=results, firmware_sha256=EXPECTED_FIRMWARE,
                 harness_sha256=harness_hash, units_sha256=units_hash, model_sha256=model_hash,
                 peripheral_model_sources={n: sha(ROOT/'tools'/n) for n in ('test_v2_rtc.py', 'test_v2_i2c.py', 'test_v2_journal.py', 'test_v2_spi_prototype.py')},
                 qualification_seconds=time.monotonic()-started, board_access=False, network_access=False,
                 native_applications=False, native_debugging=False,
                 reset_detector_only_native_instructions=is816,
                 fixture_metadata='in-memory saved MON preference, EDU ON, empty wear journal; post-boot peripheral baseline',
                 electrical_timing_qualified=False)
    output.write_text(json.dumps(proof, indent=2)+'\n')
    output.with_name(output.stem+'-transcripts.json').write_text(json.dumps(transcripts, indent=2)+'\n')
    print('PASS proof', output, flush=True)


if __name__ == '__main__':
    main()
