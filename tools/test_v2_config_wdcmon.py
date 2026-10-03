"""Execute the a24c1 unified installer using the existing stock-board model."""
import json
import sys
import build_v2_config as firmware
import build_v2_config_wdcmon_ram as installer

sys.modules['build_v2_a24'] = firmware
import test_v2_a24_wdcmon_65c02 as regression

manifest = json.loads((installer.BUILD / 'manifest.json').read_text())
regression.INSTALLER = installer.BUILD / (installer.NAME + '.s19')
regression.MAP = regression.INSTALLER.with_suffix('.map')
regression.TOP = installer.BUILD / (firmware.STEM + '-f000-ffff.bin')
regression.INSTALLER_SHA256 = manifest['installer_s19_sha256']
regression.INSTALL_TOKEN = b'INSTALL STR8-N 2.0A24C1\r'

def fixture(full_entry=False):
    cpu, mem, stock, sym = regression.fixture()
    if not full_entry:
        # Most cases exercise policy branches directly; one success test runs
        # from SEC/$FB through identification and the original B3 hash.
        value = 2166136261
        for byte in stock:
            value = ((value ^ byte) * 16777619) & 0xffffffff
        for offset, byte in enumerate(value.to_bytes(4, 'little')):
            mem.ram[sym['W2I_SOURCE_HASH0']+offset] = byte
        cpu.pc = sym['W2I_CHOOSE_BACKUP']
    return cpu, mem, stock, sym


def receive_gate(cpu, sym):
    regression.run(cpu, lambda: cpu.pc == sym['W2I_RECEIVE_READY'])


def halted(cpu):
    regression.run(cpu, lambda: b'HALTED IN RAM' in cpu.memory.tx)


def selected_ranges():
    for bank, first, last in ((0, 8, 10), (1, 15, 15), (2, 9, 14), (1, 8, 15)):
        cpu, mem, stock, sym = fixture()
        begin, end = (first-8)*4096, (last-7)*4096
        mem.banks[bank][begin:end] = b'\xff' * (end-begin)
        before = [bytes(b) for b in mem.banks]
        sector_text = f'{first:X}' if first == last else f'{first:X}-{last:X}'
        mem.rx.extend(f'{bank}\r{sector_text}\rBACKUP B3\r'.encode())
        receive_gate(cpu, sym)
        expected = bytearray(before[bank]); expected[begin:end] = stock[begin:end]
        assert bytes(mem.banks[bank]) == expected
        assert all(bytes(mem.banks[b]) == before[b] for b in range(4) if b != bank)
        assert all(b == bank and 0x8000+begin <= address < 0x8000+end
                   for _, b, address, _ in mem.events)
        assert b'BACKUP RANGE == ORIGINAL B3 VERIFIED' in mem.tx
    print('PASS: backup banks 0/1/2, single/ranged sectors, exact copy and untouched neighbors')


def full_entry_success():
    cpu, mem, stock, sym = fixture(full_entry=True)
    mem.banks[1][0x7000:] = b'\xff' * 4096
    before = [bytes(b) for b in mem.banks]
    top = regression.TOP.read_bytes()
    mem.rx.extend(b'1\rF\rBACKUP B3\r' + top + regression.INSTALL_TOKEN)
    regression.run(cpu, lambda: cpu.pc == sym['W2I_V2_RESET_WAIT'])
    assert bytes(mem.banks[1]) == before[1][:0x7000] + stock[0x7000:]
    assert bytes(mem.banks[3]) == stock[:0x7000] + top
    assert bytes(mem.banks[0]) == before[0] and bytes(mem.banks[2]) == before[2]
    assert b'MIGRATION VERIFIED; PRESS PHYSICAL RESET' in mem.tx
    assert b'TYPE ONLY 0, 1, 2 OR NONE; PRESS ENTER' in mem.tx
    assert b'TYPE F OR 8-F (EXAMPLES); PRESS ENTER' in mem.tx
    assert b'TYPE BACKUP B3 AND PRESS ENTER' in mem.tx
    print('PASS: unified entry through selected B1:F backup and exact a24c1 install')


def refusals():
    for inputs in (b'BACKUP BANK 0\r', b'3\r', b'4\r', b'0\r7\r', b'0\rF-8\r',
                   b'0\r8-G\r', b'0\r8-FX\r', b'0\rF\rNO\r',
                   b'NONE\rN\r', b'NONE\rNO BACKUP\rN\r'):
        cpu, mem, _, _ = fixture()
        before = [bytes(b) for b in mem.banks]
        mem.rx.extend(inputs); halted(cpu)
        assert not mem.events and [bytes(b) for b in mem.banks] == before
    cpu, mem, _, _ = fixture()
    mem.banks[0][0x7123] = 0
    before = [bytes(b) for b in mem.banks]
    mem.rx.extend(b'0\rF\r'); halted(cpu)
    assert b'BACKUP RANGE USED AND DIFFERENT' in mem.tx
    assert not mem.events and [bytes(b) for b in mem.banks] == before
    cpu, mem, stock, sym = fixture()
    mem.banks[2][0x7000:] = stock[0x7000:]
    before = [bytes(b) for b in mem.banks]
    mem.rx.extend(b'2\rF\r'); receive_gate(cpu, sym)
    assert not mem.events and [bytes(b) for b in mem.banks] == before
    print('PASS: invalid bank/range and declined confirmations; occupied refusal; identical reuse')


def no_backup():
    cpu, mem, stock, sym = fixture()
    before = [bytes(b) for b in mem.banks]
    mem.rx.extend(b'NONE\r')
    regression.run(cpu, lambda: bytes(mem.tx).endswith(b'TYPE NO BACKUP> '))
    assert not mem.events
    mem.rx.extend(b'NO BACKUP\r')
    regression.run(cpu, lambda: bytes(mem.tx).endswith(b'TYPE INSTALL WITHOUT BACKUP> '))
    assert not mem.events
    mem.rx.extend(b'INSTALL WITHOUT BACKUP\r'); receive_gate(cpu, sym)
    assert not mem.events and [bytes(b) for b in mem.banks] == before
    top = regression.TOP.read_bytes()
    mem.rx.extend(top + regression.INSTALL_TOKEN)
    regression.run(cpu, lambda: cpu.pc == sym['W2I_V2_RESET_WAIT'])
    assert [bytes(b) for b in mem.banks[:3]] == before[:3]
    assert bytes(mem.banks[3]) == stock[:0x7000] + top
    assert all(b == 3 and address >= 0xF000 for _, b, address, _ in mem.events)
    print('PASS: no backup requires two exact confirmations before B3:F-only installation')


def image_and_failure_gates():
    cpu, mem, stock, sym = fixture()
    bad = bytearray(regression.TOP.read_bytes()); bad[123] ^= 1
    mem.rx.extend(b'NONE\rNO BACKUP\rINSTALL WITHOUT BACKUP\r' + bad)
    halted(cpu)
    assert not mem.events and bytes(mem.banks[3]) == stock
    assert b'TOP CHECK FAILED' in mem.tx
    cpu, mem, stock, sym = fixture()
    mem.banks[1][0x7000:] = b'\xff' * 4096
    mem.fault = 'verify'
    mem.rx.extend(b'1\rF\rBACKUP B3\r'); halted(cpu)
    assert b'BACKUP FAILED' in mem.tx and bytes(mem.banks[3]) == stock
    assert all(b == 1 for _, b, _, _ in mem.events)
    # Source changes after backup policy may not pass the final install gate.
    cpu, mem, _, sym = fixture()
    mem.rx.extend(b'NONE\rNO BACKUP\rINSTALL WITHOUT BACKUP\r'); receive_gate(cpu, sym)
    mem.banks[3][0x123] ^= 1
    mem.rx.extend(regression.TOP.read_bytes() + regression.INSTALL_TOKEN); halted(cpu)
    assert not mem.events
    print('PASS: altered image, backup verify failure, and changed B3 refuse install')


def recovery_without_f():
    for choice in (b'NONE\rNO BACKUP\rINSTALL WITHOUT BACKUP\r', b'0\r8-E\rBACKUP B3\r'):
        cpu, mem, _, sym = fixture()
        mem.rx.extend(choice); receive_gate(cpu, sym)
        mem.fault = 'timeout'
        mem.rx.extend(regression.TOP.read_bytes() + regression.INSTALL_TOKEN)
        regression.run(cpu, lambda: cpu.pc == sym['W2I_RECOVERY'])
        events = list(mem.events)
        mem.rx.extend(b'O\r')
        cpu.step()
        regression.run(cpu, lambda: cpu.pc == sym['W2I_RECOVERY'])
        assert mem.events == events and not mem.rx
    print('PASS: recovery refuses old-F restore when NONE or backup excludes F')


def recovery_selected_f():
    cpu, mem, stock, sym = fixture()
    mem.banks[2][0x7000:] = stock[0x7000:]
    before = [bytes(b) for b in mem.banks]
    mem.rx.extend(b'2\rF\r'); receive_gate(cpu, sym)
    top = regression.TOP.read_bytes()
    mem.ram[0x4000:0x5000] = top
    cpu.pc = sym['W2I_RETRY_CANDIDATE']
    mem.fault = 'timeout'
    regression.run(cpu, lambda: cpu.pc == sym['W2I_RECOVERY'])
    mem.fault = None
    mem.rx.extend(b'O\r')
    regression.run(cpu, lambda: cpu.pc == 0xF818)
    assert bytes(mem.banks[3]) == stock
    assert [bytes(b) for b in mem.banks[:3]] == before[:3]
    assert b'OLD B3:F RESTORED FROM SELECTED BACKUP' in mem.tx
    assert mem.bank == 3 and all(b == 3 for _, b, _, _ in mem.events)
    print('PASS: failed install restores old F from selected B2:F, without touching other banks')


def main():
    selected_ranges()
    refusals()
    full_entry_success()
    no_backup()
    image_and_failure_gates()
    recovery_without_f()
    recovery_selected_f()
    (installer.BUILD / 'wdcmon-65c02-test.json').write_text(json.dumps(dict(
        version=firmware.VERSION, installer_s19_sha256=regression.INSTALLER_SHA256,
        physical_hardware_tested=False, passed=True,
        cases=['selected_ranges', 'refusals', 'full_entry_success', 'no_backup',
               'image_and_failure_gates', 'recovery_without_f', 'recovery_selected_f']), indent=2)+'\n')


if __name__ == '__main__':
    main()
