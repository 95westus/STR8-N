"""Execute exact b2 revision updater artifacts before physical installation."""
import argparse
import json
from pathlib import Path
import build_v2_b2_revision_update as revision
import test_v2_b2 as host
import test_v2_b2_board_update as harness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    before = [(args.evidence / f'before-b{b}.bin').read_bytes() for b in range(4)]
    source = before[3][0x6000:]
    artifacts = {}
    for phase in ('e', 'f'):
        folder = args.evidence / 'updaters-monitor-scratch' / f'{phase}-update'
        meta = json.loads((folder / 'manifest.json').read_text())
        path = folder / f'str8n-v2-b2-{phase}-update-2000.s19'
        assert revision.update.sha(path.read_bytes()) == meta['s19_sha256']
        artifacts[phase] = (path, (folder / 'staged-sector.bin').read_bytes(), meta['symbols'])
    expected_worker = (args.evidence / 'before-worker.bin').read_bytes()[:741]
    new_image = host.boot.IMAGE
    new_worker_start = host.boot.REPORT['resident']['V2_WORKER_IMAGE']-0xE000
    assert expected_worker == new_image[new_worker_start:new_worker_start+741]
    groups = []
    try:
        for phase in ('e', 'f'):
            phase_source = source if phase == 'e' else artifacts['e'][1]+source[4096:]
            planned = revision.plan(phase_source, phase, source[4096:])
            assert planned[1] == artifacts[phase][1]
            for case in ('success', 'cancel', 'guard', 'rollback'):
                host.boot.IMAGE = phase_source
                mem = host.flash.FlashMemory(3)
                for bank in range(4):
                    mem.banks[bank][:] = before[bank]
                mem.banks[3][0x6000:] = phase_source
                mem.rx.append(ord('S'))  # Hold configured autostart; settings remain exact.
                cpu = harness.B2CPU(memory=mem, pc=0xF004)
                mem.cpu = cpu
                host.boot.run(cpu, lambda: host.boot.waiting(cpu), limit=2_000_000)
                assert mem.ram[0x7900:0x7900+741] == expected_worker
                memory, entry = revision.firmware.read_s19(artifacts[phase][0])
                for address, byte in memory.items():
                    mem.ram[address] = byte
                old_banks = [bytes(b) for b in mem.banks]
                sym = artifacts[phase][2]
                cpu.pc = entry
                harness.prompt(cpu, sym)
                if case == 'guard':
                    offset = 0x7000 if phase == 'e' else 0x6000
                    mem.banks[3][offset] ^= 1
                elif case == 'rollback':
                    mem.fault = 'timeout'
                mem.rx.append(ord('N' if case == 'cancel' else 'Y'))
                if case == 'rollback':
                    host.boot.run(cpu, lambda: cpu.pc == sym['E_ROLLBACK'], limit=15_000_000)
                    mem.fault = None
                harness.finish(cpu)
                expected = bytearray(old_banks[3])
                if case == 'success':
                    offset = 0x6000 if phase == 'e' else 0x7000
                    expected[offset:offset+4096] = artifacts[phase][1]
                    assert b'b2 VERIFIED' in mem.tx
                elif case == 'guard':
                    expected[0x7000 if phase == 'e' else 0x6000] ^= 1
                    assert b'IMAGE MISMATCH' in mem.tx
                elif case == 'rollback':
                    assert b'OLD RESTORED' in mem.tx
                else:
                    assert b'ABORTED' in mem.tx
                assert [bytes(b) for b in mem.banks[:3]] == old_banks[:3]
                assert bytes(mem.banks[3]) == bytes(expected)
                groups.append(f'{phase}:{case}')
                print('PASS', groups[-1], flush=True)
    finally:
        host.boot.IMAGE = new_image
    (args.evidence / 'revision-updater-host-tests.json').write_text(json.dumps(dict(
        passed=groups, source_ef_sha256=revision.update.sha(source),
        candidate_ef_sha256=revision.update.sha(new_image),
        preserved_b2_recovery_backup=True, staging=0x6100,
        identical_ram_worker=True), indent=2)+'\n')


if __name__ == '__main__':
    main()
