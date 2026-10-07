"""Rehearse board-specific multi-bank installer plans against exact backups.

Flash/transport/commit instructions execute in the emulator. Long FNV range
loops are accelerated after an actual-opcode hash equivalence check.
"""
import argparse
import hashlib
import json
from pathlib import Path

import beta4_migration as migration
import test_v2_rtc_kernel as kernel
from test_v2_rtc import MPU as BaseMPU

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = kernel.fw.OUT/'migrator'
MANIFEST = json.loads((TEMPLATE / 'manifest.json').read_text())
S = MANIFEST['symbols']


class Memory(kernel.model.Memory):
    def __init__(self, banks, allowed, maintenance):
        super().__init__(banks)
        self.allowed = allowed
        self.maintenance = maintenance
        self.id_mode = False
        self.committed = False
        self.records=maintenance if isinstance(maintenance,dict) else ({2:maintenance} if len(maintenance)==4096 else {1:maintenance})
        self.record_commits=[]
        self.require_maintenance_commit = any(bank==1 for bank,sector in allowed)

    def __getitem__(self, a):
        if self.id_mode and a in (0x8000, 0x8001):
            return 0xBF if a == 0x8000 else 0xB5
        return super().__getitem__(a)

    def __setitem__(self, a, value):
        if a == 0xD555 and value == 0x90 and self.unlock == 2:
            self.id_mode = True
            self.unlock = 0
            return
        if self.id_mode and a == 0x8000 and value == 0xF0:
            self.id_mode = False
            return
        super().__setitem__(a, value)

    def mutated(self, kind, address, value):
        assert (self.bank, address >> 12) in self.allowed
        if self.bank in self.records and address == 0x8003 and value == 0x3F:
            target=self.records[self.bank]
            assert bytes(self.banks[self.bank][:len(target)]) == target, 'Record committed before complete verification'
            self.committed = True
            self.record_commits.append(self.bank)
        if self.require_maintenance_commit and self.bank == 3 and address >> 12 in (8, 9):
            assert self.committed, 'Original MAINT removed before relocated copy committed'
        self.events.append((kind, self.bank, address, value))


class CPU(BaseMPU):
    accelerate_hash = True
    def step(self):
        if self.pc == 0x2001 and self.memory[self.pc] == 0xFB:
            self.pc += 1
            return self
        if self.accelerate_hash and self.pc == S['MIG_HASH_RANGE']:
            start = self.memory.ram[0xE0] | self.memory.ram[0xE1] << 8
            stop = self.memory.ram[0x620C]
            end = (stop << 8) if stop else 0x10000
            value = migration.fnv(bytes(self.memory[a] for a in range(start, end)))
            self.memory.ram[0x6204:0x6208] = value.to_bytes(4, 'little')
            self.memory.ram[0xE0:0xE2] = bytes([0, stop])
            self.a, self.x = stop, 0
            self.p |= self.CARRY | self.ZERO
            self.pc = (self.stPopWord() + 1) & 0xFFFF
            return self
        return super().step()


def run(cpu, stop, limit=60000000):
    for steps in range(limit):
        if stop():
            return steps
        assert cpu.pc < 0x8000, 'Installer executed ROM code'
        cpu.step()
    raise AssertionError((hex(cpu.pc), bytes(cpu.memory.tx[-200:])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    info = json.loads((args.root / 'upgrade/plan.json').read_text())
    installer = args.root / 'upgrade/installer.s19'
    assert hashlib.sha256(installer.read_bytes()).hexdigest() == info['installer_sha256']
    banks = [(args.root / f'prior/b{i}.bin').read_bytes() for i in range(4)]
    cells, entry = migration.read_s19(installer)
    allowed = {(x['bank'], x['sector']) for x in info['steps']}
    maintenance = ({1:(args.root/'upgrade/expected-b1.bin').read_bytes()[:8192],2:(args.root/'upgrade/expected-b2.bin').read_bytes()[:8192]} if info.get('journal_update') else
                   (args.root/'upgrade/expected-b2.bin').read_bytes()[:4096] if info.get('clock_update')
                   else (kernel.fw.OUT/'str8n-maint-1.6-b1-8000-9fff.bin').read_bytes())
    memory = Memory(banks, allowed, maintenance)
    for a, value in cells.items():
        memory.ram[a] = value
    # Actual FNV opcodes on a 256-byte range before enabling loop acceleration.
    memory.ram[0x6000:0x6100] = bytes(range(256))
    memory.ram[0xE0:0xE2] = b'\0\x60'
    memory.ram[0x620C] = 0x61
    cpu = CPU(memory=memory, pc=S['MIG_HASH_RANGE'])
    memory.cpu = cpu
    cpu.accelerate_hash = False
    cpu.stPushWord(0x01FF)
    run(cpu, lambda: cpu.pc == 0x0200)
    assert int.from_bytes(memory.ram[0x6204:0x6208], 'little') == migration.fnv(bytes(range(256)))
    cpu = CPU(memory=memory, pc=entry)
    memory.cpu = cpu
    memory.rx.extend(b'Y\r')
    for i, step in enumerate(info['steps']):
        token = f'SEND 4096 BYTES FOR B{step["bank"]}:{step["sector"]:X}\r\n'.encode()
        run(cpu, lambda: token in bytes(memory.tx))
        assert b'MIGRATION REFUSED/FAILED' not in memory.tx
        memory.tx.clear()
        memory.rx.extend((args.root / f'upgrade/transfer-{i:02d}.bin').read_bytes())
    run(cpu, lambda: cpu.pc == S['MIG_HALT'])
    assert b'MIGRATION VERIFIED' in memory.tx, bytes(memory.tx[-200:])
    for b in range(4):
        expected = (args.root / f'upgrade/expected-b{b}.bin').read_bytes()
        assert bytes(memory.banks[b]) == expected, f'B{b} final mismatch'
    erases = [event for event in memory.events if event[0] == 'erase']
    assert [(b, a >> 12) for _, b, a, _ in erases] == [(x['bank'], x['sector']) for x in info['steps']]
    # Stale target-bank preimage must refuse before the first erase.
    stale = [bytearray(b) for b in banks]
    first_bank = info['steps'][0]['bank']
    stale[first_bank][0x234] ^= 1
    refused = Memory(stale, allowed, maintenance)
    for a, value in cells.items():
        refused.ram[a] = value
    bad_cpu = CPU(memory=refused, pc=entry)
    refused.cpu = bad_cpu
    refused.rx.extend(b'Y\r')
    run(bad_cpu, lambda: bad_cpu.pc == S['MIG_HALT'])
    assert b'REFUSED/FAILED' in refused.tx and not refused.events
    # First staged payload corruption must likewise cause no mutation.
    refused = Memory(banks, allowed, maintenance)
    for a, value in cells.items():
        refused.ram[a] = value
    bad_cpu = CPU(memory=refused, pc=entry)
    refused.cpu = bad_cpu
    refused.rx.extend(b'Y\r')
    token = f'SEND 4096 BYTES FOR B{info["steps"][0]["bank"]}:{info["steps"][0]["sector"]:X}\r\n'.encode()
    run(bad_cpu, lambda: token in bytes(refused.tx))
    bad_data = bytearray((args.root / 'upgrade/transfer-00.bin').read_bytes())
    bad_data[99] ^= 1
    refused.rx.extend(bad_data)
    run(bad_cpu, lambda: bad_cpu.pc == S['MIG_HALT'])
    assert b'REFUSED/FAILED' in refused.tx and not refused.events
    report = dict(passed=True, board=info['board'], installer_sha256=info['installer_sha256'],
        expected_hashes=info['expected_hashes'], erases=erases,
        maintenance_committed=memory.committed and memory.require_maintenance_commit,
        record_committed=memory.committed, committed_record_bank=info.get('record_commit_bank',1) if memory.committed else None,
        maintenance_commit_required=memory.require_maintenance_commit,
        actual_hash_opcode_check=True, hash_range_loops_accelerated=True, physical_hardware_tested=False)
    report.update(stale_preimage_refused=True, corrupt_payload_refused=True)
    report['record_commits']=memory.record_commits
    (args.root / 'upgrade/model-check.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS', info['board'], 'exact bank results, sector order, MAINT commit, pinned guards and RAM execution')


if __name__ == '__main__':
    main()
