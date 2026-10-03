"""Execute F-pocket failure/retry, no-extension startup and migration checks."""
import json
import sys
import tempfile
from pathlib import Path

import build_v2_config as candidate
import build_v2_config_update as updater

LEGACY = '--legacy' in sys.argv
if LEGACY:
    import build_v2_a24 as firmware
else:
    firmware = candidate
sys.modules['build_v2'] = firmware
sys.modules['build_v2_a24'] = firmware
import test_v2_a24_console  # install FT245 model timing
import test_v2_boot as boot
import test_v2_flash as flash
import test_v2_config as config


def save_failures():
    for fault in ('timeout', 'verify', 'erase_verify'):
        cpu, mem = flash.boot_flash(3)
        # Force a sector erase, then fail during the rewrite.
        mem.banks[3][0x7FD0:0x7FE0] = config.config(enable=0)
        before = bytes(mem.banks[3])
        mem.fault = fault
        mem.rx.extend(b'C 1 2 9000 0A\rY\r')
        boot.run(cpu, lambda: cpu.pc == flash.W['V2W_RESET_WAIT'], limit=8_000_000)
        assert b'Flash fail' in mem.tx and cpu.pc < 0x8000
        assert mem.ram[boot.SYM['V2_NMI_HOLD']] == 1
        desired = bytes(mem.ram[0x6900:0x7900])
        assert desired[:0xFD0] == before[0x7000:0x7FD0]
        assert desired[0xFE0:] == before[0x7FE0:]
        # Arbitrary input cannot cause a jump into damaged ROM.
        mem.rx.extend(b'N')
        for _ in range(1000):
            cpu.step()
            assert cpu.pc < 0x8000
        mem.fault = None
        mem.rx.extend(b'Y')
        boot.run(cpu, lambda: boot.waiting(cpu), limit=8_000_000)
        assert mem.banks[3][0x7000:] == desired
        assert mem.ram[boot.SYM['V2_NMI_HOLD']] == 0
        assert b'Done' in mem.tx and mem.banks[3][:0x7000] == before[:0x7000]
    print('PASS: C erase/program failures remain in RAM; retry verifies complete F before return')


def optional_extension():
    for descriptor in (None, 1):
        mem = flash.FlashMemory(3)
        if descriptor is None:
            mem.banks[3][0x6000:0x7000] = b'\xff' * 4096
        else:
            mem.banks[3][0x6802] = descriptor
        mem.banks[3][0x7FD0:0x7FE0] = config.config(bank=2)
        mem.rx.extend(b'S')
        cpu = boot.MPU(memory=mem, pc=boot.SYM['START']); mem.cpu = cpu
        boot.hold(cpu)
        assert mem.bank == 3
        assert b'C 01 02 9000 0A' in boot.command(cpu, b'C\r')
        assert b'SR unavailable' in boot.command(cpu, b'T 3\r')
        assert b'Done' in flash.send(cpu, b'C 0 2 9000 0A\rY\r')
        assert updater.valid_config(mem.banks[3][0x7FD0:0x7FE0])
        cpu.pc = boot.SYM['START']
        boot.hold(cpu)
        assert b'C 00 02 9000 0A' in boot.command(cpu, b'C\r')
    print('PASS: absent and old E extension rejected; F settings, hold and C remain usable')


def planner_checks():
    f = (candidate.OUT / f'{candidate.STEM}-f000-ffff.bin').read_bytes()
    settings = config.config(bank=2)
    configured = f[:0xFD0] + settings + f[0xFE0:]
    source = bytes(4096) + configured
    assert updater.plan(source)[1] == configured
    for malformed in (source[:-1], source + b'X', source[:4096] + b'X' + configured[1:],
                      source[:4096+0xFD0] + bytes([2]) + source[4096+0xFD1:]):
        try:
            updater.plan(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError('Malformed firmware/configuration was accepted')
    print('PASS: configured F recognition/preservation; malformed length, code and settings refused')


def exercise_update(extension=False):
    cpu, mem = flash.boot_flash(3)
    if LEGACY:
        mem.banks[3][0x6FF0:0x7000] = config.config(bank=2)
    else:
        mem.banks[3][0x6000:0x7000] = bytes(4096)
        mem.banks[3][0x7FD0:0x7FE0] = config.config(bank=2)
    source = bytes(mem.banks[3][0x6000:])
    with tempfile.TemporaryDirectory(dir=candidate.OUT) as folder:
        path, new, sym = updater.build(source, Path(folder), extension)
        program, entry = candidate.read_s19(path)
        for scenario in ('success', 'cancel', 'changed_target', 'changed_guard', 'failure'):
            cpu, mem = flash.boot_flash(3)
            mem.banks[3][0x6000:] = source
            for address, value in program.items():
                mem.ram[address] = value
            cpu.pc, cpu.sp = entry, 0xFF
            target_offset = 0x6000 if extension else 0x7000
            guard_offset = 0x7000 if extension else 0x6000
            if scenario == 'changed_target':
                mem.banks[3][target_offset + 3] ^= 1
            if scenario == 'changed_guard':
                mem.banks[3][guard_offset + 3] ^= 1
            before = [bytes(bank) for bank in mem.banks]
            if scenario.startswith('changed'):
                boot.run(cpu, lambda: cpu.pc == 0xF007, limit=2_000_000)
                assert b'OLD IMAGE MISMATCH' in mem.tx and not mem.events
                continue
            boot.run(cpu, lambda: b'TYPE Y to repair>' in mem.tx, limit=2_000_000)
            assert not mem.events
            mem.rx.extend(b'N' if scenario == 'cancel' else b'Y')
            if scenario == 'failure':
                mem.fault = 'timeout'
                boot.run(cpu, lambda: cpu.pc == sym['E_FAILED_WAIT'], limit=8_000_000)
                assert cpu.pc < 0x8000
                mem.fault = None
                mem.rx.extend(b'Y')
            boot.run(cpu, lambda: cpu.pc == (0xF007 if scenario == 'cancel' else 0xF004), limit=15_000_000)
            expected = new if scenario == 'success' else before[3][target_offset:target_offset+4096]
            assert bytes(mem.banks[3][target_offset:target_offset+4096]) == expected
            assert mem.banks[3][guard_offset:guard_offset+4096] == before[3][guard_offset:guard_offset+4096]
            assert all(bytes(mem.banks[i]) == before[i] for i in range(3))
            if scenario == 'cancel':
                assert not mem.events
            if scenario == 'success' and not extension:
                assert mem.banks[3][0x7FD0:0x7FE0] == config.config(bank=2)
    print('PASS: guarded', 'E extension' if extension else 'alpha24 F migration',
          'success/cancel/exact E+F rejection/failure restoration; other sectors preserved')


if __name__ == '__main__':
    receipt = candidate.OUT / ('legacy-migration-test.json' if LEGACY else 'config-safety-test.json')
    receipt.unlink(missing_ok=True)
    if LEGACY:
        exercise_update()
    else:
        planner_checks()
        save_failures()
        optional_extension()
        exercise_update(extension=True)
    receipt.write_text(json.dumps(dict(passed=True, hardware_tested=False,
        image_sha256=updater.sha((candidate.OUT / f'{candidate.STEM}-f000-ffff.bin').read_bytes()))) + '\n')
