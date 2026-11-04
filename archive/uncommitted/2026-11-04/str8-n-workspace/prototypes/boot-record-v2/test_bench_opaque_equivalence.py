"""Qualify unchanged OIP1 runtime against the separately qualified bench MONs.

This receipt extends the complete opaque-installer CPU report only to a build
with identical F, RAM installer, CONFIG, worker/vector bytes and symbols. It
does not qualify executing the different MON code or its private providers.
"""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('opaque_equivalence_tests', HERE / 'test_opaque_installer.py')
oi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oi)

COMPONENTS = ('f-offline-component.bin', 'ram-config-offline.bin',
              'ram-installer-offline.bin', 'ram-installer-offline.rlp1')
MODULES = ('core/str8n-v2-boot', 'core/str8n-v2-worker',
           'core/str8n-v2-vectors', 'core/ram-config', 'core/ram-installer')
NEW_BODY = bytes(reversed(range(256))) * 16


def read_json(path):
    return json.loads(path.read_text())


def startup_load(bench, cpu):
    h = oi.InstallerMachine(bench, cpu)
    for bank, sector in oi.ALLOWED:
        start = (sector - 0x80) << 8
        h.m.banks[bank][start:start + 4096] = bytes((n + bank * 37 + sector) & 255 for n in range(4096))
    assert h.c.pc == h.b['BOOT_START_CHOICES']
    h.m.rx.append(ord('S'))
    h.run(lambda: bytes(h.m.tx).endswith(b'REC> '))
    assert b'OFFLINE PROTOTYPE S A B 0 1 2 3' in h.m.tx
    binary = (bench / 'payload/ram-installer-offline.bin').read_bytes()
    h.command(b'L\r', b'SEND HEADER+BIN\r\n')
    assert b'LOADED;' in h.command(oi.base.header(binary) + binary)
    h.command(b'R\r', oi.PROMPT)
    h.run(lambda: h.c.pc == h.w['V2W_GETC'])
    assert h.m.banks[3][0x2000:0x4000] == b'\xff' * 8192
    assert not h.m.events
    return h


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-build', type=Path, required=True)
    parser.add_argument('--bench-build', type=Path, required=True)
    args = parser.parse_args()
    source, bench = args.source_build.resolve(), args.bench_build.resolve()
    source_report_path = source / 'opaque-installer-cpu-tests.json'
    source_report = read_json(source_report_path)
    assert source_report['passed'] and source_report['checks'] == 120
    assert source_report['hardware'] is False and source_report['serial_access'] is False
    assert len(source_report['cases']) == 120 and all(row['passed'] for row in source_report['cases'])
    assert source_report['test_source_sha256'] == oi.sha((HERE / 'test_opaque_installer.py').read_bytes())
    source_symbols = read_json(source / 'symbols.json')
    bench_symbols = read_json(bench / 'symbols.json')
    assert source_report['symbols_sha256'] == oi.sha((source / 'symbols.json').read_bytes())
    assert source_report['prototype_report_sha256'] == oi.sha((source / 'prototype-report.json').read_bytes())
    source_manifest = read_json(source / 'prototype-report.json')
    bench_manifest = read_json(bench / 'prototype-report.json')
    assert bench_manifest['bench_core'] and bench_manifest['journal_duplicate_guard']
    assert source_manifest['experimental_generation'] == bench_manifest['experimental_generation']
    oi.base.GENERATION = bench_manifest['experimental_generation']
    runtime_hashes = {}
    for name in COMPONENTS:
        reference = (source / 'payload' / name).read_bytes()
        candidate = (bench / 'payload' / name).read_bytes()
        assert reference == candidate, ('Runtime component differs', name)
        runtime_hashes[name] = oi.sha(candidate)
        assert source_report['component_hashes'][name] == runtime_hashes[name]
    for module in MODULES:
        assert source_symbols[module] == bench_symbols[module], ('Runtime symbols differ', module)
    runtime_symbols = {module: bench_symbols[module] for module in MODULES}
    f = (bench / 'payload/f-offline-component.bin').read_bytes()
    boot = bench_symbols['core/str8n-v2-boot']
    worker_start = boot['BOOT_WORKER_IMAGE'] - 0xf000
    vector_start = boot['BOOT_VECTOR_IMAGE'] - 0xf000
    worker_size = bench_manifest['f']['worker_bytes']
    vector_size = bench_manifest['f']['vectors_bytes']
    worker_hash = oi.sha(f[worker_start:worker_start + worker_size])
    vector_hash = oi.sha(f[vector_start:vector_start + vector_size])
    assert worker_hash == next(row['sha256'] for row in reversed(bench_manifest['compiled'])
                               if row['name'] == 'str8n-v2-worker')
    assert vector_hash == next(row['sha256'] for row in reversed(bench_manifest['compiled'])
                               if row['name'] == 'str8n-v2-vectors')
    firmware = (bench / 'firmware.bin').read_bytes()
    target = read_json(bench / 'bench-target.json')
    assert len(firmware) == 98304 and oi.sha(firmware) == target['firmware_sha256']
    monitor_hashes = {}
    for sector in (0xa0, 0xb0):
        name = f'monitor-{sector:02x}-offline-component.bin'
        component = (bench / 'payload' / name).read_bytes()
        offset = 65536 + ((sector - 0x80) << 8)
        assert firmware[offset:offset + 4096] == component
        monitor_hashes[name] = oi.sha(component)
    assert firmware[0x17000:0x18000] == f
    cases = []
    for cpu in ('65c02', '65c816-e'):
        fallback = oi.InstallerMachine(bench, cpu, rows=[(0xc000, oi.base.record(target='B'))])
        # Both CPU models' actual 8MHz tick instructions are qualified by the
        # core report. Summarize only those delay ticks; execute the complete
        # configured-default and generation-check fallback control flow.
        fallback.hooks[fallback.b['BR_TENTH']] = lambda t: oi.return_from_call(t)
        fallback.run(lambda: bytes(fallback.m.tx).endswith(b'REC> '))
        assert not fallback.m.events and fallback.m.banks[3][0x2000:0x4000] == b'\xff' * 8192
        cases.append(dict(cpu=cpu, case='configured-default-B-missing-MON-timeout-fallback',
                          passed=True, F_startup_control_flow_executed=True,
                          MON_instructions_executed=0, qualified_delay_ticks_accelerated=True))
        print('PASS', cpu, 'configured-default-B-missing-MON-timeout-fallback', flush=True)
        h = startup_load(bench, cpu)
        assert not h.m.events
        # Loading through F above explicitly requires both MON slots absent.
        oi.install_protected_monitor_fixtures(h)
        visited = set()
        real_step = h.c.step

        def step():
            assert not (h.m.bank == 3 and 0xa000 <= h.c.pc < 0xc000), 'MON instruction executed'
            visited.add((h.m.bank, h.c.pc))
            return real_step()

        h.c.step = step
        application = (bytes(h.m.ram[0x200:0x2000]),
                       bytes(h.m.ram[h.i['INSTALLER_END']:0x6500]))
        for bank, sector in ((0, 0xf0), (3, 0xe0)):
            h.m.arm((bank, sector))
            original = h.sector(bank, sector)
            out = h.request(oi.frame(bank=bank, sector=sector, preimage=original), oi.BODY)
            assert b'OK: verified sector' in out and h.sector(bank, sector) == oi.BODY
            assert len(h.m.reservations) == 1
            events = len(h.m.events)
            h.m.assert_preserved()
            out = h.request(oi.frame(op=0, bank=bank, sector=sector))
            assert out == oi.READ_READY + oi.BODY + oi.crc(oi.BODY).to_bytes(2, 'little') + oi.READ_DONE + oi.PROMPT
            assert len(h.m.events) == events
            h.m.arm((bank, sector))
            image = tuple(map(bytes, h.m.banks))
            out = h.request(oi.frame(bank=bank, sector=sector, preimage=oi.BODY), oi.BODY)
            assert b'OK: identical' in out and not h.m.events
            assert tuple(map(bytes, h.m.banks)) == image

            def corrupt(t):
                del t.hooks[t.i['OI_PROGRAM_END']]
                t.m.banks[bank][((sector - 0x80) << 8) + 37] ^= 1

            h.m.arm((bank, sector))
            h.hooks[h.i['OI_PROGRAM_END']] = corrupt
            out = h.request(oi.frame(bank=bank, sector=sector, body=NEW_BODY,
                                     preimage=h.sector(bank, sector)), NEW_BODY)
            assert b'FAILED: flash/readback' in out and h.sector(bank, sector) != NEW_BODY
            assert len(h.m.reservations) == 1
            h.m.assert_preserved()
            h.m.arm((bank, sector))
            out = h.request(oi.frame(bank=bank, sector=sector, body=NEW_BODY,
                                     preimage=h.sector(bank, sector)), NEW_BODY)
            assert b'OK: verified sector' in out and h.sector(bank, sector) == NEW_BODY
            h.m.assert_preserved()
            out = h.request(oi.frame(op=0, bank=bank, sector=sector))
            assert out == oi.READ_READY + NEW_BODY + oi.crc(NEW_BODY).to_bytes(2, 'little') + oi.READ_DONE + oi.PROMPT
            assert application == (bytes(h.m.ram[0x200:0x2000]),
                                   bytes(h.m.ram[h.i['INSTALLER_END']:0x6500]))

            def timeout(t):
                del t.hooks[t.i['OI_PROGRAM']]
                # Start only after the durable journal reservation, target
                # erase, and erased-sector verification have succeeded.
                t.m.fault = 'timeout'

            h.m.arm((bank, sector))
            h.hooks[h.i['OI_PROGRAM']] = timeout
            out = h.request(oi.frame(bank=bank, sector=sector,
                                     preimage=h.sector(bank, sector)), oi.BODY)
            assert b'FAILED: flash/readback' in out and h.sector(bank, sector) != oi.BODY
            assert len(h.m.reservations) == 1
            h.m.assert_preserved()
            h.m.fault = None
            h.m.arm((bank, sector))
            out = h.request(oi.frame(bank=bank, sector=sector,
                                     preimage=h.sector(bank, sector)), oi.BODY)
            assert b'OK: verified sector' in out and h.sector(bank, sector) == oi.BODY
            h.m.assert_preserved()
            out = h.request(oi.frame(op=0, bank=bank, sector=sector))
            assert out == oi.READ_READY + oi.BODY + oi.crc(oi.BODY).to_bytes(2, 'little') + oi.READ_DONE + oi.PROMPT
            mid_read_block = bank == 3 and sector == 0xe0
            if mid_read_block:
                h.m.arm((bank, sector))
                image = tuple(map(bytes, h.m.banks))
                h.begin()
                start = len(h.m.tx)
                h.m.ft_block_after = start + len(oi.READ_READY) + 17
                h.m.rx.extend(oi.frame(op=0, bank=bank, sector=sector))
                h.run(lambda: bytes(h.m.acia_tx).endswith(oi.LOCKED))
                assert bytes(h.m.tx[start:]) == oi.READ_READY + oi.BODY[:17]
                assert b'REFUSED: TX blocked' in h.m.acia_tx
                assert not h.m.events and tuple(map(bytes, h.m.banks)) == image
                h.m.ft_block_after = None
                h.m.ft_tx_blocked = False
                oi.assert_quarantined(h)
                h.m.assert_preserved()
            assert application == (bytes(h.m.ram[0x200:0x2000]),
                                   bytes(h.m.ram[h.i['INSTALLER_END']:0x6500]))
            cases.append(dict(cpu=cpu, bank=bank, sector=sector, passed=True,
                              F_startup_S_selection=True, F_RLP1_load_with_MON_absent=True,
                              actual_bench_MON_AB_inserted=True,
                              write_readback_noop_fault_and_fresh_retry=True,
                              program_poll_timeout_and_fresh_retry=True,
                              mid_read_FT245_block_quarantines_without_mutation=mid_read_block,
                              raw_payload_bytes=4096, all_byte_values=True,
                              F_MON_AB_other_sectors_and_application_RAM_preserved=True,
                              MON_instructions_executed=0,
                              visited_instruction_locations=len(visited)))
            print('PASS', cpu, f'bench-equivalent-B{bank}:{sector >> 4:X}', flush=True)
    receipt = dict(schema=1, passed=True, hardware=False, serial_access=False,
                   device_or_network_attempts=oi.base.ATTEMPTS,
                   source_build=str(source), source_report_sha256=oi.sha(source_report_path.read_bytes()),
                   source_cases=source_report['checks'], source_mutation_prefixes=source_report['mutation_prefixes'],
                   source_safe_reservation_refusals=source_report['safe_reservation_refusals'],
                   bench_firmware_sha256=oi.sha(firmware),
                   bench_symbols_sha256=oi.sha((bench / 'symbols.json').read_bytes()),
                   runtime_component_hashes=runtime_hashes, bench_monitor_hashes=monitor_hashes,
                   runtime_symbols=runtime_symbols,
                   worker_sha256=worker_hash, vectors_sha256=vector_hash,
                   worker_bytes=worker_size, vectors_bytes=vector_size,
                   monitor_execution_qualified=False,
                   scope='Unchanged F-initialized OIP1 RAM runtime and protection of bench MON bytes. '
                         'The source report supplies full framing/protection/interruption evidence; '
                         'bench MON execution and private providers are outside this receipt.',
                   bench_core_report_sha256=oi.sha((bench / 'cpu-tests.json').read_bytes()),
                   bench_target_report_sha256=oi.sha((bench / 'bench-target-tests.json').read_bytes()),
                   checker_sha256=oi.sha(Path(__file__).read_bytes()), cases=cases)
    destination = bench / 'bench-runtime-equivalence.json'
    oi.base.save(destination, receipt)
    print('PASS total', len(cases), flush=True)
    print('RECEIPT', destination, flush=True)


if __name__ == '__main__':
    main()
