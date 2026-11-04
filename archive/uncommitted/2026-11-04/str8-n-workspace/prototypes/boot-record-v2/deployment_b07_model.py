"""Linked native reservation + unchanged RAM transaction qualification.

Each real NOR mutation prefix keeps a committed native snapshot and conservative
wear. FNV executes on each CPU before acceleration; no serial/network access.
"""
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'tools'), str(Path(__file__).resolve().parent)]
from installer.common import save
from installer.engine import runtime as r, legacy_transport as wire, install_transport as transport
from installer.flash_model import Memory as BaseMemory
import deployment_b07 as planning


def execute(pkg, plan, initial, *, is816, deps02, deps816, fault=None, verifier=None):
    pkg, plan = Path(pkg), Path(plan)
    info = (verifier or planning.verify)(pkg, plan)
    symbols = r.read(planning.TEMPLATE / 'symbols.json')
    tx = info['transaction']; reserve_address = tx['reservation_offset'] + 0x8000
    sys.path[:0] = [str(Path(deps02).resolve()), str(Path(deps816).resolve())]
    from py65.devices.mpu65c02 import MPU as CPU02
    from py65816.devices.mpu65c816 import MPU as CPU816
    assert r.sha(Path(sys.modules[CPU816.__module__].__file__).read_bytes()) == 'a94fc4c40f3a252b0c5197252ce0ea35310b6f5ada986c40eae16c649d5bfc02'

    class Memory(BaseMemory):
        def __init__(self):
            super().__init__(initial)
            self.ram[0x7fec] = 0xee; self.id_mode = False
            self.erases = [0] * 32; self.reservation_verified = False
            self.native_prefixes = 0; self.f_prefixes = 0
            self.reservation_program_addresses = []
        def __getitem__(self, address):
            assert 0 <= address <= 65535
            if self.id_mode and address in (0x8000, 0x8001):
                return 0xbf if address == 0x8000 else 0xb5
            return super().__getitem__(address)
        def __setitem__(self, address, value):
            assert 0 <= address <= 65535
            if address == 0xd555 and value == 0x90 and self.unlock == 2:
                self.id_mode = True; self.unlock = 0; return
            if self.id_mode and address == 0x8000 and value == 0xf0:
                self.id_mode = False; return
            if fault == 'reservation-commit' and self.bank == 3 and address == reserve_address + 255 and self.unlock == 3:
                self.unlock = 0
                return
            super().__setitem__(address, value)
        def mutated(self, kind, address, value):
            assert self.bank == 3
            if 0xc000 <= address < 0xe000:
                assert kind != 'erase' and reserve_address <= address < reserve_address + 256
                self.reservation_program_addresses.append(address)
            else:
                assert (self.bank, address & 0xf000) in ((3, 0xa000), (3, 0xf000), (3, 0xb000))
            if kind == 'erase':
                self.erases[self.bank * 8 + (address >> 12) - 8] += 1
            rows = planning.snbt_records(self.banks)
            assert rows, 'Native durability lost at a mutation prefix'
            latest = max(rows)[2]
            seq = int.from_bytes(latest[8:12], 'little')
            if seq == tx['sequence_after']:
                self.reservation_verified = True
                assert latest[32:48].hex() == tx['target_config']
                assert latest[160:164].hex() == tx['history_unknown_mask']
                assert latest[164:168].hex() == tx['provenance']
            if kind == 'erase':
                assert self.reservation_verified, 'Erase before native commit255'
            for index, count in enumerate(self.erases):
                observed = int.from_bytes(latest[64 + index * 3:67 + index * 3], 'little')
                assert observed >= tx['counts_before'][index] + count, 'Wear reservation insufficient'
            self.native_prefixes += 1
            if address & 0xf000 == 0xf000:
                self.f_prefixes += 1
            self.events.append((kind, self.bank, address, value))

    class CPU(CPU816 if is816 else CPU02):
        accelerate = True
        def step(self):
            if is816:
                assert self.mode == 1 and (self.dpr, self.dbr, self.pbr) == (0, 0, 0)
            if not is816 and self.pc == 0x2001 and self.memory[self.pc] == 0xfb:
                self.pc += 1; return self
            if self.accelerate and self.pc == symbols['MIG_HASH_RANGE']:
                first = int.from_bytes(self.memory.ram[0xe0:0xe2], 'little'); stop = self.memory.ram[0x620c]
                value = wire.fnv(bytes(self.memory[x] for x in range(first, (stop << 8) if stop else 65536)))
                self.memory.ram[0x6204:0x6208] = value.to_bytes(4, 'little')
                self.memory.ram[0xe0:0xe2] = bytes([0, stop])
                self.a, self.x = stop, 0; self.p |= self.CARRY | self.ZERO
                self.pc = (self.stPopWord() + 1) & 65535
                return self
            return super().step()

    def run(cpu, predicate, limit=40000000):
        for _ in range(limit):
            if predicate():
                return
            assert cpu.pc < 0x8000
            cpu.step()
        raise AssertionError(('timeout', hex(cpu.pc), bytes(cpu.memory.tx[-180:])))

    memory = Memory(); cells, entry = wire.read_s19(plan / 'installer-model-only.s19')
    for address, value in cells.items():
        memory.ram[address] = value
    cpu = CPU(memory=memory, pc=entry); cpu.pc = entry; memory.cpu = cpu
    if is816:
        cpu.b = 0xa5
    memory.ram[0x6000:0x6100] = bytes(range(256)); memory.ram[0xe0:0xe2] = b'\0\x60'; memory.ram[0x620c] = 0x61
    cpu.pc = symbols['MIG_HASH_RANGE']; cpu.accelerate = False; cpu.stPushWord(0x1ff)
    run(cpu, lambda: cpu.pc == 0x200)
    assert int.from_bytes(memory.ram[0x6204:0x6208], 'little') == wire.fnv(bytes(range(256)))
    cpu.pc = entry; cpu.accelerate = True
    if fault == 'stale':
        memory.banks[0][0] ^= 1
    if fault == 'reservation-corrupt':
        memory.ram[0x3600] ^= 1

    class Endpoint:
        def monitor_load(self, path):
            assert path == plan / 'installer-model-only.s19'
        def send(self, data):
            if fault == 'corrupt' and len(data) == 64 and not getattr(self, 'corrupted', False):
                data = bytes([data[0] ^ 1]) + data[1:]; self.corrupted = True
            memory.rx.extend(data)
        def until(self, token, seconds=45):
            run(cpu, lambda: token in memory.tx or cpu.pc == symbols['MIG_HALT'])
            if token not in memory.tx:
                raise ValueError('device refused: ' + bytes(memory.tx[-160:]).decode('ascii', 'replace'))
            end = memory.tx.index(token) + len(token)
            reply = bytes(memory.tx[:end]); del memory.tx[:end]
            return reply

    with patch.object(transport.time, 'sleep', return_value=None):
        if fault:
            try:
                transport.execute(Endpoint(), plan)
            except ValueError:
                assert b'REFUSED/FAILED' in memory.tx
                if fault in ('stale', 'reservation-corrupt'):
                    assert not memory.events
                assert not any(memory.erases), 'Refusal must precede all erases'
                return dict(passed=True, fault=fault, CPU='65C816 E=1' if is816 else '65C02',
                            mutation_events=len(memory.events), erase_attempts=0, linked_FNV_checked=True,
                            native_snapshot_retained=True, native_debugging=False)
            raise AssertionError('Fault was accepted')
        result = transport.execute(Endpoint(), plan)
    run(cpu, lambda: cpu.pc == symbols['MIG_HALT'])
    expected = [(plan / f'expected-b{n}.bin').read_bytes() for n in range(4)]
    assert list(map(bytes, memory.banks)) == expected
    assert [[e[1], e[2] >> 12] for e in memory.events if e[0] == 'erase'] == tx['planned_erase_order']
    assert memory.reservation_program_addresses[-1] == reserve_address + 255
    assert all(address != reserve_address + 255 for address in memory.reservation_program_addresses[:-1])
    assert expected[:3] == initial[:3]
    assert expected[3][:0x2000] == initial[3][:0x2000] and expected[3][0x6000:0x7000] == initial[3][0x6000:0x7000]
    for _, off, row in planning.snbt_records(initial):
        assert expected[3][off:off + 256] == row
    assert len(planning.snbt_records(expected)) == len(planning.snbt_records(initial)) + 1
    return dict(passed=True, CPU='65C816 E=1' if is816 else '65C02', transfers=result['transfers_completed'],
                erases=sum(memory.erases), C_D_erases=0, mutation_events=len(memory.events),
                native_prefixes_checked=memory.native_prefixes, F_transition_prefixes=memory.f_prefixes,
                native_commit255_last=True, linked_FNV_checked=True, exact_all_four_bank_target=True,
                original_native_records_preserved=True, history_unknown_and_provenance_preserved=True,
                RTC_provider_TZ_history_auxiliary_and_B0_B1_B2_preserved=True, native_debugging=False)


def qualify(target, folder, *, deps02, deps816):
    target, folder = Path(target), Path(folder)
    info = planning.verify(target, folder)
    _, banks = planning.capture.validate(folder / 'capture', allow_synthetic=info['synthetic_model_fixture'])
    models = []
    for is816 in (False, True):
        for fault in (None, 'stale', 'corrupt', 'reservation-corrupt', 'reservation-commit'):
            row = execute(target, folder, banks, is816=is816, deps02=deps02, deps816=deps816, fault=fault)
            models.append(row)
            print('PASS native model', row['CPU'], fault or 'success', flush=True)
    proof = dict(passed=True, hardware=False, board_access=False, serial_access=False, models=models,
                 plan_sha256=r.sha((folder / 'plan.json').read_bytes()), firmware_sha256=info['firmware_sha256'],
                 planner_sha256=r.sha(Path(planning.__file__).read_bytes()), model_source_sha256=r.sha(Path(__file__).read_bytes()),
                 native_reserve_source_sha256=r.sha((planning.HERE / 'native-reserve.asm').read_bytes()),
                 native_extension_receipt_sha256=r.sha((folder / 'native-reservation-extension.json').read_bytes()))
    save(folder / 'model-proof.json', proof)
    return proof
