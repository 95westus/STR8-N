"""Execute the exact B/F-guarded E updater before its board installation."""
import argparse
import json
from pathlib import Path
import build_v2_b2_service_update as revision
import test_v2_b2 as host
import test_v2_b2_board_update as harness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    before = [(args.evidence/f'before-b{i}.bin').read_bytes() for i in range(4)]
    source = before[3][0x6000:]
    folder = args.evidence/'e-updater'
    metadata = json.loads((folder/'manifest.json').read_text())
    artifact = folder/'str8n-v2-b2-e-update-2000.s19'
    memory, entry = revision.firmware.read_s19(artifact)
    new_e = (folder/'staged-sector.bin').read_bytes()
    backing = (revision.firmware.OUT/f'{revision.firmware.STEM}-b000-bfff.bin').read_bytes()
    assert revision.update.sha(artifact.read_bytes()) == metadata['s19_sha256']
    assert revision.plan(source, 'e', source[4096:])[1] == new_e
    expected_worker = (args.evidence/'before-worker.bin').read_bytes()[:741]
    image = host.boot.IMAGE
    passed = []
    try:
        for case in ('success', 'cancel', 'old-e', 'f-after-confirm',
                     'b-prefix-after-confirm', 'b-tail-after-confirm', 'rollback'):
            host.boot.IMAGE = source
            mem = host.flash.FlashMemory(3)
            for bank in range(4):
                mem.banks[bank][:] = before[bank]
            mem.banks[3][0x3000:0x4000] = backing
            mem.rx.append(ord('S'))
            cpu = harness.B2CPU(memory=mem, pc=0xF004)
            mem.cpu = cpu
            host.boot.run(cpu, lambda: host.boot.waiting(cpu), limit=2_000_000)
            assert mem.ram[0x7900:0x7900+741] == expected_worker
            for address, value in memory.items():
                mem.ram[address] = value
            cpu.pc = entry
            if case == 'old-e':
                mem.banks[3][0x6000] ^= 1
            original = [bytes(bank) for bank in mem.banks]
            expected = bytearray(original[3])
            if case != 'old-e':
                harness.prompt(cpu, metadata['symbols'])
                if case == 'f-after-confirm':
                    mem.banks[3][0x7000] ^= 1
                    expected[0x7000] ^= 1
                elif case == 'b-prefix-after-confirm':
                    mem.banks[3][0x3008] ^= 1
                    expected[0x3008] ^= 1
                elif case == 'b-tail-after-confirm':
                    mem.banks[3][0x3FFF] ^= 1
                    expected[0x3FFF] ^= 1
                elif case == 'rollback':
                    mem.fault = 'timeout'
                mem.rx.append(ord('N' if case == 'cancel' else 'Y'))
                if case == 'rollback':
                    host.boot.run(cpu, lambda: cpu.pc == metadata['symbols']['E_ROLLBACK'], limit=15_000_000)
                    mem.fault = None
            harness.finish(cpu)
            if case == 'success':
                expected[0x6000:0x7000] = new_e
                assert b'b2 VERIFIED' in mem.tx
                mem.rx.append(ord('S'))
                host.boot.run(cpu, lambda: host.boot.waiting(cpu), limit=2_000_000)
                assert host.call(cpu, host.REPORT['manager_rom']['MG_ROM_INIT_ENTRY'])[0]
                assert host.lookup(cpu, 'SERVICE.REGISTER')[0]
            elif case == 'cancel':
                assert b'ABORTED' in mem.tx
            elif case == 'rollback':
                assert b'OLD RESTORED' in mem.tx
            else:
                assert b'IMAGE MISMATCH' in mem.tx
            assert [bytes(b) for b in mem.banks[:3]] == original[:3]
            assert bytes(mem.banks[3]) == bytes(expected)
            passed.append(case)
            print('PASS', case, flush=True)
    finally:
        host.boot.IMAGE = image
    (args.evidence/'service-updater-host-tests.json').write_text(json.dumps(dict(
        passed=passed, source_ef_sha256=revision.update.sha(source),
        candidate_ef_sha256=revision.update.sha(image),
        updater_sha256=revision.update.sha(artifact.read_bytes()),
        backing_sha256=revision.update.sha(backing), staging=0x6100,
        end=metadata['end'], identical_ram_worker=True), indent=2)+'\n')


if __name__ == '__main__':
    main()
