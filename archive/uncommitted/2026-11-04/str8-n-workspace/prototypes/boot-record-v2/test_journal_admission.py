"""Execute shared journal admission in all four guarded writer links offline."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('journal_admission_base', HERE/'test.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
ROOT = base.ROOT
MODULES = ('core/monitor-a0', 'core/monitor-b0',
           'core/ram-config', 'core/ram-installer')
COUNT_INDEX = 5


def fixture_cases():
    original = base.record(seq=7, counts=[10 + n for n in range(32)])
    counts = [10 + n for n in range(32)]
    counts[COUNT_INDEX] += 100
    different_counts = base.record(seq=7, counts=counts)
    different_config = bytearray(original)
    different_config[0x23] ^= 1
    different_config = base.seal(different_config)
    bad_crc = bytearray(original)
    bad_crc[0x40] ^= 1
    torn = bytearray(different_counts)
    torn[0xff] = 0xff
    older = base.record(seq=6, counts=[200]*32)
    saturated = [10 + n for n in range(32)]
    saturated[COUNT_INDEX] = 0xffffff
    return (
        ('identical-duplicate', [(0xc000, original), (0xd000, original)], True, True, original),
        ('same-sequence-divergent-counts',
         [(0xc000, original), (0xd000, different_counts)], False, False, original),
        ('same-sequence-divergent-config',
         [(0xc000, original), (0xd000, different_config)], False, False, original),
        ('same-sequence-committed-body-CRC-invalid',
         [(0xc000, original), (0xd000, bytes(bad_crc))], False, False, original),
        ('uncommitted-divergent-page-ignored',
         [(0xc000, original), (0xd000, bytes(torn))], True, True, original),
        ('older-divergent-record-ignored',
         [(0xc000, original), (0xd000, older)], True, True, original),
        ('saturated-counter',
         [(0xc000, base.record(seq=7, counts=saturated))], True, False, None),
    )


def machine(build, cpu, module, records):
    h = base.Machine(build, cpu, records,
                     ram_config=module == 'core/ram-config')
    if module == 'core/ram-installer':
        image = (build/'payload/ram-installer-offline.bin').read_bytes()
        h.m.ram[0x2000:0x2000 + len(image)] = image
    sy = h.sy[module]
    assert 'JE_CHECK_DUPLICATES' in sy, 'Writer was not linked with admission guard'
    assert sy['JE_ENTER'] <= sy['JE_CHECK_DUPLICATES'] < sy['JE_END']
    h.m.ram[0x7c60:0x7c62] = sy['JE_ENTER'].to_bytes(2, 'little')
    h.m.ram[0x7d3c] = COUNT_INDEX
    return h, sy


def latest(h):
    assert h.call(h.b['BOOT_READ_RECORD'])
    page = h.m.ram[0x7d35]
    offset = (page - 0x80) << 8
    return bytes(h.m.banks[3][offset:offset + 256])


def writer_tests(build, cpu, passed):
    for module in MODULES:
        for label, records, readable, mutable, original in fixture_cases():
            h, sy = machine(build, cpu, module, records)
            flash_before = tuple(map(bytes, h.m.banks))
            app_before = bytes(h.m.ram[0x200:0x6500])
            # Exercise the linked guard itself with no instruction hooks. CRC
            # acceleration is separately qualified by test.py; this additional
            # read executes the actual CRC too for each CPU and writer link.
            if label == 'identical-duplicate':
                h.accelerate_crc = False
            assert h.call(sy['JE_ENTER'], 0) == readable, (cpu, module, label, 'read')
            assert not h.m.events
            assert tuple(map(bytes, h.m.banks)) == flash_before
            assert bytes(h.m.ram[0x200:0x6500]) == app_before

            h, sy = machine(build, cpu, module, records)
            flash_before = tuple(map(bytes, h.m.banks))
            app_before = bytes(h.m.ram[0x200:0x6500])
            assert h.call(sy['JE_ENTER'], 2) == mutable, (cpu, module, label, 'reserve')
            assert bytes(h.m.ram[0x200:0x6500]) == app_before
            if not mutable:
                assert not h.m.events, (cpu, module, label, h.m.events)
                assert tuple(map(bytes, h.m.banks)) == flash_before
            else:
                assert h.m.events and all(e[1] == 3 and 0xc000 <= e[2] < 0xe000
                                          for e in h.m.events)
                expected = bytearray(original)
                expected[8:12] = (int.from_bytes(original[8:12], 'little') + 1).to_bytes(4, 'little')
                offset = 0x40 + COUNT_INDEX*3
                expected[offset:offset + 3] = (int.from_bytes(original[offset:offset + 3], 'little') + 1).to_bytes(3, 'little')
                assert latest(h) == base.seal(expected), (cpu, module, label, 'snapshot preservation')
                for bank in range(4):
                    if bank != 3:
                        assert bytes(h.m.banks[bank]) == flash_before[bank]
                assert bytes(h.m.banks[3][:0x4000]) == flash_before[3][:0x4000]
                assert bytes(h.m.banks[3][0x6000:]) == flash_before[3][0x6000:]
            passed(cpu, module, label, read_admitted=readable,
                   reservation_admitted=mutable, mutation_events=len(h.m.events),
                   application_ram_preserved=True,
                   configuration_and_other_counters_preserved=True,
                   full_flash_unchanged_on_refusal=(True if not mutable else None))


def installer_saturation(build, cpu, passed):
    # End-to-end no-MON tool entry must refuse a target erase when its durable
    # reservation cannot be made. The journal-only base NOR rejects any target
    # command outright, so an accidental target erase also fails this test.
    counts = [1]*32
    counts[0] = 0xffffff
    h = base.Machine(build, cpu, [(0xc000, base.record(counts=counts))], opaque=True)
    image = (build/'payload/ram-installer-offline.bin').read_bytes()
    h.recovery()
    h.command(b'L\r', b'SEND HEADER+BIN\r\n')
    assert b'LOADED;' in h.command(base.header(image) + image)
    prompt = b'INSTALLER I Q> '
    h.command(b'R\r', prompt)
    assert h.m.banks[3][0x2000:0x4000] == b'\xff'*8192
    before = tuple(map(bytes, h.m.banks))
    h.port_command(1, b'I\r', b'SEND OIP1 HEADER\r\n')
    body = bytes(range(256))*16
    raw = (b'OIP1\x01\x01\x00\x80\x00\x10'
           + base.crc(bytes([255])*4096).to_bytes(2, 'little')
           + base.crc(body).to_bytes(2, 'little') + bytes(4))
    header = raw + base.crc(raw).to_bytes(2, 'little')
    h.port_command(1, header, b'SEND 4096\r\n')
    out = h.port_command(1, body, prompt)
    assert b'REFUSED: durable wear reservation' in out
    assert not h.m.events and tuple(map(bytes, h.m.banks)) == before
    assert h.m.bank == 3 and h.m.ram[0xf4] == 0 and h.m.ram[0x7c2b] == 0
    passed(cpu, 'core/ram-installer', 'saturated-counter-full-protocol-no-target-erase',
           actual_f_load_run=True, both_MON_absent=True, mutation_events=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    report = json.loads((build/'prototype-report.json').read_text())
    base.GENERATION = report['experimental_generation']
    assert report.get('journal_duplicate_guard'), 'Use the guarded opaque-installer variant'
    cases = []

    def passed(cpu, module, case, **details):
        cases.append(dict(cpu=cpu, module=module, case=case, passed=True, **details))
        print('PASS', cpu, module, case, flush=True)

    for cpu in ('65c02', '65c816-e'):
        writer_tests(build, cpu, passed)
        installer_saturation(build, cpu, passed)
    assert all(base.sha((ROOT/name).read_bytes()) == digest
               for name, digest in report['selected_source_hashes'].items())
    output = dict(passed=True, checks=len(cases), failures=0, hardware=False,
                  serial_access=False, device_or_network_attempts=base.ATTEMPTS,
                  experimental_generation=base.GENERATION,
                  selected_source_unchanged=True, cases=cases,
                  component_hashes={p.name: base.sha(p.read_bytes())
                                    for p in (build/'payload').glob('*-offline*.bin')},
                  symbols_sha256=base.sha((build/'symbols.json').read_bytes()),
                  test_source_sha256=base.sha(Path(__file__).read_bytes()),
                  dependency_hashes={p.name: base.sha(p.read_bytes())
                                     for p in (HERE/'test.py', HERE/'journal-guard.inc',
                                               build/'s/core/prototype-engine.inc')})
    base.save(build/'journal-admission-cpu-tests.json', output)
    print('PASS total', len(cases), flush=True)


if __name__ == '__main__':
    main()
