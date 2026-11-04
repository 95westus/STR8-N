"""Linked RAM-probe CPU/pin-model checks. No serial or device access.

The digital pin model supplies an explicit released WR level and DATA=$FF.
It does not establish the installed VIA bus keeper, reset ordering or analog
thresholds. Every tested probe and public console instruction executes.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PIN_SOURCE = ROOT / 'output/qualification/physical-reset-ff-investigation/trace_reset.py'
spec = importlib.util.spec_from_file_location('ram_probe_pin_model', PIN_SOURCE)
pin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin)
core = pin.m.core
CAP = 0x6400
NONCE = bytes.fromhex('702c3e510d9b46a8ae091277cdd38b64')
REGISTERS = pin.REGISTERS


def valid_capsule(data, case, nonce=NONCE, require_fresh_nonce=True):
    if len(data) != 256 or data[:5] != b'RFP1\x01':
        return False
    if data[5] != case or data[15] != 0xa5 or data[240:] != nonce:
        return False
    if require_fresh_nonce and not any(nonce):
        return False
    if data[7] not in (1, 2, 128) or not 1 <= data[6] <= 6:
        return False
    if any(data[a] ^ data[b] != 255 for a, b in ((5, 10), (7, 11), (12, 13))):
        return False
    checksum = 0
    for index, byte in enumerate(data):
        if index != 15:
            checksum ^= byte
    return checksum == 0


class ProbeMemory(core.Memory):
    """Guard all stores and record physical WR transitions, not DDRA enables."""
    def __init__(self, original, *, released=1):
        super().__init__(original.banks, dual=True)
        self.ram[:] = original.ram
        self.bank = original.bank
        self.pins = pin.Pins(wr_input=released, released_data=255)
        self.pins.orb, self.pins.ddrb, self.pins.ddra, self.pins.ora = 8, 12, 0, 0x20
        self.cpu = None
        self.pc = None
        self.armed = False
        self.writes, self.reads = [], []
        self.capsule_prefixes = []
        self.block_after = None
        self.ifr = 0x10  # One injected CB1 flag, acknowledged by ORB reads.
        self.ier = 0x80
        self.rx.extend(b'pending input: do not consume\r\n')
        self.ram[0x7fec], self.ram[0x7feb] = 0xee, 0
        self.ram[0x7d02], self.ram[0x7c2b], self.ram[0xf8] = 1, 0, 0
        self.ram[0xf4] = 0

    def __getitem__(self, address):
        if self.armed and 0x7f00 <= address < 0x8000:
            self.reads.append((self.cpu.processorCycles, self.pc, address))
        if address == 0x7fe0:
            # RXF# remains low while pending input exists. Never consume it.
            inputs = (1 if self.ft_tx_blocked else 0) | (0 if self.rx else 2) | 8
            inputs |= self.pins.wr_input << 2
            result = (self.pins.orb & self.pins.ddrb) | (inputs & (~self.pins.ddrb & 255))
            self.ifr &= ~0x10
            return result
        if address == 0x7fe1:
            raise AssertionError('Probe read FT DATA/RX register instead of ORA no-handshake')
        if address == 0x7fef:
            return self.pins.data()
        if address == 0x7fe2:
            return self.pins.ddrb
        if address == 0x7fe3:
            return self.pins.ddra
        if address == 0x7fed:
            return self.ifr
        if address == 0x7fee:
            return self.ier
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        value &= 255
        assert self.armed and self.cpu is not None
        assert address < 0x8000, ('Flash write', self.pc, address, value)
        allowed = (0x100 <= address < 0x200 or CAP <= address < CAP + 240
                   or address == 0xf4 or 0xe0 <= address <= 0xff or address in REGISTERS)
        assert allowed, ('Unapproved store', hex(self.pc), hex(address), value)
        if 0xe0 <= address <= 0xff and address != 0xf4:
            assert 0x7900 <= self.pc < 0x7c00, ('Probe used zero page', hex(self.pc), hex(address))
        self.writes.append((self.cpu.processorCycles, self.pc, address, value))
        if address in REGISTERS:
            before = len(self.pins.captures)
            self.pins.write(REGISTERS[address], value, pc=self.pc,
                            cycle=self.cpu.processorCycles, address=address)
            assert self.pins.ddrb & 8 and self.pins.orb & 8, 'RD# became active or floating'
            for row in self.pins.captures[before:]:
                assert not self.ft_tx_blocked
                self.tx.append(row['byte'])
            self.ram[address] = value
            if self.block_after is not None and len(self.tx) >= self.block_after:
                self.ft_tx_blocked = True
            return
        self.ram[address] = value
        if CAP <= address < CAP + 240:
            self.capsule_prefixes.append((address, value, bytes(self.ram[CAP:CAP + 256])))


def setup(build, out, manifest, cpu, case, released=1, change=None, block_after=None):
    core.GENERATION = json.loads((build / 'prototype-report.json').read_text())['experimental_generation']
    h = core.Machine(build, cpu)
    memory = ProbeMemory(h.m, released=released)
    memory.cpu = h.c
    h.m = h.c.memory = memory
    row = next(row for row in manifest['cases'] if row['id'] == case)
    body = (out / row['bin']).read_bytes()
    assert core.sha(body) == row['sha256']
    memory.ram[0x2000:0x2000 + len(body)] = body
    memory.ram[CAP:CAP + 256] = bytes(240) + NONCE
    if change:
        change(memory, manifest)
    memory.block_after = block_after
    memory.armed = True
    h.c.pc, h.c.sp, h.c.p = 0x2000, 255, 0x24
    h.c.processorCycles = 0
    h.initial = bytes(memory.ram)
    h.flash = tuple(map(bytes, memory.banks))
    h.pending = bytes(memory.rx)
    return h


def execute(h, symbols, case):
    stops = (0xb160, symbols['RP_ARMED_HALT'], symbols['RP_REFUSED_HALT'])
    for steps in range(250_000):
        if h.c.pc in stops:
            break
        h.m.pc = h.c.pc
        opcode = h.m[h.c.pc]
        pin.m.timed_step(h.c, opcode)
    else:
        raise AssertionError(('probe timeout', h.name, hex(h.c.pc), bytes(h.m.tx)))
    memory = h.m
    data = bytes(memory.ram[CAP:CAP + 256])
    expected_nonce = h.initial[CAP + 240:CAP + 256]
    fresh = any(expected_nonce)
    assert valid_capsule(data, case, expected_nonce, fresh), (h.name, case, data[:16].hex())
    if not fresh:
        assert data[7:9] == bytes([128, 7])
        assert not valid_capsule(data, case, expected_nonce), 'Host freshness rule accepted zero nonce'
    assert memory.capsule_prefixes[-1][0:2] == (CAP + 15, 165)
    assert all(not valid_capsule(prefix, case, expected_nonce, fresh)
               for _, _, prefix in memory.capsule_prefixes[:-1])
    assert data[240:] == expected_nonce
    for index in range(256):
        corrupt = bytearray(data)
        corrupt[index] ^= 1
        assert not valid_capsule(corrupt, case, expected_nonce, fresh), index
    assert bytes(memory.rx) == h.pending
    assert not memory.acia_tx and not memory.events
    assert h.flash == tuple(map(bytes, memory.banks))
    assert memory.bank == 3 and memory.ram[0x7fec] == h.initial[0x7fec]
    assert memory.ram[0x7feb] == h.initial[0x7feb]
    assert memory.ram[:0xe0] == h.initial[:0xe0]
    assert memory.ram[0x200:0x2000] == h.initial[0x200:0x2000]
    assert memory.ram[0x2000:0x6400] == h.initial[0x2000:0x6400]
    assert memory.ram[0x6500:0x7900] == h.initial[0x6500:0x7900]
    assert memory.ier == (0x81 if data[8] == 1 else 0x80)
    assert not any(address in (0x7f80, 0x7f81, 0x7fe1) for _, _, address in memory.reads)
    # Each row reads IFR, IER, PCR, ACR, ORB, ORA(no handshake), IFR, IER.
    snapshot_reads = [address for _, pc, address in memory.reads
                      if symbols['RP_SNAPSHOT'] <= pc < symbols['RP_COMMIT']]
    assert snapshot_reads == [0x7fe3, 0x7fe2, 0x7fed, 0x7fee, 0x7fec, 0x7feb,
                              0x7fe0, 0x7fef, 0x7fed, 0x7fee] * data[6]
    assert data[19] == 0x10 and data[25] == 0, 'IFR-before/after row did not expose ORB acknowledgment'
    if h.c.pc != 0xb160:
        writes, reads, tx = len(memory.writes), len(memory.reads), bytes(memory.tx)
        for _ in range(100):
            memory.pc = h.c.pc
            pin.m.timed_step(h.c, memory[h.c.pc])
        assert (writes, reads, tx) == (len(memory.writes), len(memory.reads), bytes(memory.tx))
    return dict(status=data[7], reason=data[8], phase=data[12], snapshots=data[6],
                capsule_hex=data.hex(), capsule_write_prefixes_checked=len(memory.capsule_prefixes),
                single_byte_capsule_corruptions_rejected=256, pc=h.c.pc,
                corrected_cycles=h.c.processorCycles, instructions=steps,
                output_hex=bytes(memory.tx).hex(), final_pins=memory.pins.state(),
                VIA_events=memory.pins.events,
                no_flash_or_unapproved_RAM_writes=True, owner_ZP_00_DF_preserved=True,
                pending_input_preserved=True, IFR_read_before_and_after_ORB=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    args = parser.parse_args()
    out = args.probe.resolve()
    manifest = json.loads((out / 'manifest.json').read_text())
    symbols = json.loads((out / 'symbols.json').read_text())
    build = Path(manifest['source_build'])
    assert core.sha((HERE / 'probe.asm').read_bytes()) == manifest['probe_source_sha256']
    assert core.sha((HERE / 'build.py').read_bytes()) == manifest['builder_sha256']
    assert core.sha((build / 'symbols.json').read_bytes()) == manifest['runtime_symbols_sha256']
    for name, expected in manifest['component_hashes'].items():
        assert core.sha((build / 'payload' / name).read_bytes()) == expected
    for row in manifest['cases']:
        assert core.sha((out / row['bin']).read_bytes()) == row['sha256']
        assert core.sha((out / row['s19']).read_bytes()) == row['s19_sha256']
    rows = []
    begin = time.time()
    for cpu in ('65c02', '65c816-e'):
        for released in (0, 1):
            for case in (0, 1, 2, 3, 4, 5, 8, 9, 10, 11):
                h = setup(build, out, manifest, cpu, case, released)
                result = execute(h, symbols, case)
                assert result['status'] == (2 if case >= 8 else 1)
                expected = (bytes.fromhex(next(r for r in manifest['cases'] if r['id'] == case)['arm_marker_hex'])
                            if case >= 8 else {3: b'\xa5', 4: b'\0', 5: b'\xff'}.get(case, b''))
                assert bytes(h.m.tx) == expected, (cpu, case, released, bytes(h.m.tx), expected)
                if case < 8:
                    assert h.c.pc == 0xb160 and h.c.sp == 255
                    assert (h.m.pins.orb, h.m.pins.ddrb, h.m.pins.ddra) == (12, 12, 0)
                    assert h.m.ram[0xf4] == h.initial[0xf4]
                else:
                    assert h.c.pc == symbols['RP_ARMED_HALT'] and h.m.ram[0xf4] == 1
                    expected_final = {8: (8, 12, 0), 9: (12, 12, 0), 10: (8, 8, 0), 11: (12, 12, 255)}[case]
                    assert (h.m.pins.orb, h.m.pins.ddrb, h.m.pins.ddra) == expected_final
                    if case == 11:
                        assert h.m.pins.ora == 165
                rows.append(dict(cpu=cpu, category='positive', case=case, released_WR=released,
                                 released_DATA=255, passed=True, **result))
        negatives = [
            ('IER', 1, lambda m, _: setattr(m, 'ier', 0x81)),
            ('DDRA', 2, lambda m, _: setattr(m.pins, 'ddra', 255)),
            ('DDRB', 2, lambda m, _: setattr(m.pins, 'ddrb', 8)),
            ('PCR', 3, lambda m, _: m.ram.__setitem__(0x7fec, 0xcc)),
            ('ACR', 4, lambda m, _: m.ram.__setitem__(0x7feb, 1)),
            ('RD-low', 5, lambda m, _: setattr(m.pins, 'orb', 0)),
            ('console-mask', 6, lambda m, _: m.ram.__setitem__(0x7d02, 3)),
            ('binary-mode', 6, lambda m, _: m.ram.__setitem__(0x7c2b, 1)),
            ('zero-nonce', 7, lambda m, _: m.ram.__setitem__(slice(CAP + 240, CAP + 256), bytes(16))),
            ('invalid-case', 8, lambda m, mf: m.ram.__setitem__(mf['selector_address'], 255)),
            ('TXE-busy', 9, lambda m, _: setattr(m, 'ft_tx_blocked', True))]
        for name, reason, change in negatives:
            case = 255 if name == 'invalid-case' else 3
            h = setup(build, out, manifest, cpu, 3, change=change)
            result = execute(h, symbols, case)
            assert result['status'] == 128 and result['reason'] == reason
            assert not h.m.tx and not h.m.pins.events
            rows.append(dict(cpu=cpu, category='precondition-refusal', case=case,
                             negative=name, passed=True, **result))
        h = setup(build, out, manifest, cpu, 9, block_after=2)
        result = execute(h, symbols, 9)
        assert result['status'] == 128 and result['reason'] == 9
        assert bytes(h.m.tx) == b'\r\n' and h.c.pc == symbols['RP_REFUSED_HALT']
        rows.append(dict(cpu=cpu, category='mid-READY-blocked-refusal', case=9, passed=True, **result))
        print('PASS RAM probe', cpu, 32, 'groups', flush=True)
    assert len(rows) == 64
    report = dict(passed=True, checks=len(rows), hardware=False, serial_access=False,
                  device_or_network_attempts=core.ATTEMPTS, elapsed_seconds=time.time() - begin,
                  cpu_coverage=dict(Counter(row['cpu'] for row in rows)), cases=rows,
                  manifest_sha256=core.sha((out / 'manifest.json').read_bytes()),
                  probe_source_sha256=manifest['probe_source_sha256'], builder_sha256=manifest['builder_sha256'],
                  checker_sha256=core.sha(Path(__file__).read_bytes()),
                  case_binary_hashes={str(row['id']): row['sha256'] for row in manifest['cases']},
                  component_hashes=manifest['component_hashes'],
                  runtime_symbols_sha256=manifest['runtime_symbols_sha256'],
                  pin_model_dependency_sha256=core.sha(PIN_SOURCE.read_bytes()),
                  reused_model_hashes={str(path.relative_to(ROOT)): core.sha(path.read_bytes()) for path in
                      (ROOT / 'prototypes/boot-record-v2/test_boot_startup.py',
                       ROOT / 'prototypes/boot-record-v2/test_boot_countdown.py',
                       ROOT / 'prototypes/boot-record-v2/test.py',
                       ROOT / 'tools/installer/flash_model.py')},
                  assumptions=['Digital instruction-boundary pin model, not electrical timing proof',
                               'Released WR is tested at both static levels; released DATA is explicitly FF',
                               'FT245 configured and accepting writes while TXE# low; RD# remains high',
                               'Injected CB1 IFR flag is cleared by ORB read; snapshots expose before/after',
                               'No reset-assertion edge or actual VIA bus keeper behavior is inferred'],
                  limitations=['Physical captured undriven DATA is not required to be FF',
                               'Snapshot ORB/ORA reads can acknowledge interrupt flags; hidden latches are not recoverable',
                               'Return path stops at pinned MON B prompt before its normal output'])
    core.save(out / 'probe-cpu-tests.json', report)
    print('PASS', len(rows), 'groups; report', out / 'probe-cpu-tests.json', flush=True)


if __name__ == '__main__':
    main()
