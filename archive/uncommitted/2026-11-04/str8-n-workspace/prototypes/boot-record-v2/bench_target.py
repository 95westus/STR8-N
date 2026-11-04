"""Compose and CPU-check a PR03 core bench target, with old auxiliary flash retained.

No board access or execution admission is provided. Only B3:F and MON A/B
change in the generic image. Board C/D migration is a separate capture-bound
deployment_plan operation; the generic image retains the base's journal seed.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'tools'), str(HERE)]
from installer.engine import legacy_transport as wire
from str8build.formats import save, sha
from deployment_plan import BASE_SHA, snapshot
from prepare_monitor_size import offline, ATTEMPTS

offline()

ENABLED = [
    'PR03 read-only F boot record scan; recovery S/A/B and opaque bank 0/1/2/3 handoff',
    'FT245 and ACIA initialized together; dual text console and initiating-port binary transfers',
    'RAM POLL/CHKC extension and existing fixed bank-independent console entries',
    'F RLP1 RAM load/run, download escrow and verified-range readback',
    'MON A/B bank selection, RAM dump/edit, S19 load/run and restricted non-B3 flash commands',
    'MON C saved default, P monitor promotion and W wear report through independent SNBT writers',
    'Standalone RAM CONFIG and OIP1 opaque-sector installer, loaded separately with range escrow',
]
INACTIVE = [
    'E named application and S/R/T dispatch, including ASM/APPS and named saved-program launch',
    'E automatic RTC service initialization/banner and TIME/VERSION provider hooks',
    'B2 MAINT, SRAM, WORK, EDU and BATCH provider dispatch through MON',
    'Named CLOCK launch through the legacy provider path',
    'DBG1 BRK services and interactive RAM debugger; MON uses the default BRK handler',
]


def compose(build, base):
    build, base = Path(build), Path(base)
    report = json.loads((build / 'prototype-report.json').read_text())
    expected_contract = 'PR04' if report.get('boot_countdown') else 'PR03'
    assert report['bench_core'] and report['dual_console'] and report['bootstrap_contract'] == expected_contract
    original = (base / 'firmware.bin').read_bytes()
    assert sha(original) == BASE_SHA and len(original) == 98304
    image = bytearray(original)
    overlays = []
    for address, name in ((0xa000, 'monitor-a0-offline-component.bin'),
                          (0xb000, 'monitor-b0-offline-component.bin'),
                          (0xf000, 'f-offline-component.bin')):
        body = (build / 'payload' / name).read_bytes()
        assert len(body) == 4096
        start = 65536 + address - 0x8000
        image[start:start + 4096] = body
        overlays.append(dict(bank=3, address=address, component=name, sha256=sha(body)))
    changed = []
    for bank in range(1, 4):
        for address in range(0x8000, 0x10000, 4096):
            start = (bank - 1) * 32768 + address - 0x8000
            if original[start:start + 4096] != image[start:start + 4096]:
                changed.append([bank, address])
    assert changed == [[3, 0xa000], [3, 0xb000], [3, 0xf000]]
    return bytes(image), dict(
        schema=1, prototype=True, bench_core=True, hardware=False,
        board_access=False, installation_permitted=False, deployable=False,
        base_firmware_sha256=sha(original), firmware_sha256=sha(image),
        image_bytes=len(image), bank_order=[1, 2, 3], overlays=overlays,
        changed_sectors=changed, retained_byte_identical=[
            'All B1 including DBG1/assembler/CLOCK/source storage', 'All B2 utilities/assets',
            'B3:8000 RTC provider', 'B3:9000 RTC code and TZ/history seed',
            'B3:E000 named application/service dispatcher',
            'Generic B3:C/D journal seed; board migration must replace it through deployment_plan'],
        banner=report['banner'], generation=report['experimental_generation'], bootstrap_contract=expected_contract,
        enabled_features=[item.replace('PR03', expected_contract) for item in ENABLED], retained_but_inactive_features=INACTIVE,
        source_selected_unchanged=report['selected_source_unchanged'])


def check(build, base, image):
    build, base = Path(build), Path(base)
    spec = importlib.util.spec_from_file_location('bench_component_tests', HERE / 'test.py')
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)
    report = json.loads((build / 'prototype-report.json').read_text())
    symbols = json.loads((build / 'symbols.json').read_text())
    original = (base / 'firmware.bin').read_bytes()
    assert image[:65536] == original[:65536]
    old_e = image[0x16000:0x17000]
    old_b2 = image[32768:65536]
    assert old_e[:4] == b'NA\x01?' and wire.crc(old_e) == 0
    assert old_b2[:4] == b'UX\x03*' and wire.crc(old_b2[:0x5800]) == 0
    assert image[0x2000:0x2004] == b'DG\x01\x01'
    results = []
    negative_commands = [b'VERSION\r', b'TIME\r', b'ASM\r', b'APPS\r', b'CLOCK\r',
                         b'MAINT\r', b'SRAM\r', b'WORK\r', b'EDU\r', b'BATCH W\r',
                         b'R MAINT\r', b'R ASM\r', b'S\r', b'R\r', b'T\r']
    for cpu in ('65c02', '65c816-e'):
        for target, page in (('A', 0xa0), ('B', 0xb0)):
            generation = report['experimental_generation']
            cfg = bytearray([1, 0, 3, 7, 0xf0, 10, 0, ord('P'), page, 0, 0, 0, 0, 0, 0, 0])
            cfg[9:13] = generation.to_bytes(4, 'little')
            cfg[14:] = wire.config_sum(cfg)
            row = snapshot(bytes(cfg), list(range(32)), 1, target, generation)
            h = tests.Machine(build, cpu, [(0xc000, row)])
            # Machine normally omits old E/B2. Restore the complete real target
            # before any MON entry, preserving the verified synthetic journal.
            for bank in range(1, 4):
                h.m.banks[bank][:] = image[(bank - 1) * 32768:bank * 32768]
            h.m.banks[3][0x4000:0x6000] = b'\xff' * 8192
            h.m.banks[3][0x4000:0x4100] = row
            ms = symbols[f'core/monitor-{page:02x}']
            visited = set()
            real_step = h.c.step

            def traced_step():
                bank, pc = h.m.bank, h.c.pc
                visited.add((bank, pc))
                assert bank not in (1, 2), ('Legacy bank executed', cpu, target, bank, hex(pc))
                assert not (bank == 3 and 0xe000 <= pc < 0xf000), ('Legacy E executed', cpu, target, hex(pc))
                assert pc not in (ms['AP_LEGACY_DISABLED'], ms['B29_LEGACY_DISABLED']), ('Disabled gate tail executed', cpu, target, hex(pc))
                return real_step()

            h.c.step = traced_step
            assert bytes(h.m[ms['AP_CHECK'] + n] for n in range(2)) == b'\x18\x60'
            assert not h.call(ms['AP_CHECK'])
            h.m.ram[0x7ef4] = h.m.ram[0x7ee4] = 0xa5
            h.call(ms['B29_CHECK_PROVIDER'])
            assert h.m.ram[0x7ef4] == h.m.ram[0x7ee4] == 0
            h.c.pc = h.b['BOOT_START_CHOICES']; h.c.sp = 255; h.c.p = 0x24
            h.run(lambda:bytes(h.m.tx).endswith(b'B3> '))
            assert report['banner'].encode() in h.m.tx
            assert bytes(h.m.ram[0x7e02:0x7e04]) == symbols['core/str8n-v2-vectors']['V2V_DEFAULT'].to_bytes(2, 'little')
            assert h.m.ram[0x7ef4] == h.m.ram[0x7ee4] == h.m.ram[0x7d19] == 0
            assert bytes(h.m.ram[0x7bfc:0x7c00]) == bytes(4)
            original_ram = bytes(h.m.ram[0x200:0x6500])
            for command in negative_commands:
                reply = h.command(command, b'B3> ')
                assert not h.m.events and bytes(h.m.ram[0x200:0x6500]) == original_ram
                assert b' Y?' not in reply
            # A real journal append uses tagged BRK flash primitives and must
            # return through DEFAULT without ever fetching the retained DBG1.
            h.command(b'C ' + target.encode() + b'\r', b' Y?')
            h.command(b'Y\r', b'B3> ')
            assert h.m.events and bytes(h.m.ram[0x200:0x6500]) == original_ram
            assert h.m.ram[0x7ef4] == h.m.ram[0x7ee4] == 0
            results.append(dict(CPU=cpu, slot=target, passed=True,
                                real_legacy_E_B2_headers_and_CRCs_present=True,
                                AP_CHECK_explicit_refusal=True, B29_explicitly_inactive=True,
                                default_BRK_pointer=True, tagged_BRK_journal_append_passed=True,
                                negative_legacy_commands=len(negative_commands),
                                legacy_auxiliary_instruction_fetches=0,
                                visited_instruction_locations=len(visited), owner_RAM_preserved=True))
    return dict(passed=True, hardware=False, board_access=False,
                firmware_sha256=sha(image), cases=results, device_or_network_attempts=ATTEMPTS,
                checker_sha256=sha(Path(__file__).read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=ROOT / 'BUILD/rc1-r10p2-g0034')
    args = parser.parse_args()
    build = args.build.resolve()
    assert not (build / 'firmware.bin').exists() and not (build / 'bench-target.json').exists()
    image, manifest = compose(build, args.base)
    proof = check(build, args.base, image)
    (build / 'firmware.bin').write_bytes(image)
    save(build / 'bench-target.json', manifest)
    save(build / 'bench-target-tests.json', proof)
    print('PASS bench target; actual legacy E/B2/DBG1 retained and uninvoked, both CPUs and MON slots', flush=True)
    print('SHA256', sha(image), flush=True)


if __name__ == '__main__':
    main()
