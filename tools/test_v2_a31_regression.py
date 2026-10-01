"""Shared monitor/flash regressions against alpha31, plus S/R and freed E pocket."""
import hashlib
import json
import sys
import build_v2_a31 as build
sys.modules['build_v2'] = build
import test_v2_boot as boot
import test_v2_monitor as monitor
import test_v2_load as load
import test_v2_flash as flash
import test_v2_interrupt_probe as interrupt


def step(self):
    if self.pc == boot.REPORT['worker']['V2W_BOOT_DELAY']:
        self.boot_waits += 1
        self.processorCycles += 329_000
        self.pc = boot.REPORT['worker']['V2W_BOOT_DELAY_DONE']
        return
    return boot.BaseMPU.step(self)


boot.MPU.step = step


def main():
    passed = []
    for check in (boot.check_boot_and_input, boot.check_handoffs, boot.check_vectors,
                  boot.check_image_and_instructions, boot.check_capability_abi,
                  boot.check_v135_roundtrip, boot.check_compact_messages):
        check()
        passed.append(check.__name__)
        print('PASS:', passed[-1], flush=True)
    boot.check_ram_abi_all_banks(acia_enabled=False)
    passed.append('RAM ABI across all banks')
    for suite in (monitor, load, flash, interrupt):
        suite.main()
        passed.append(suite.__name__)
        print('PASS:', passed[-1], flush=True)
    cpu, m = flash.boot_flash(3)
    original = bytes(range(32))
    m.ram[0x2000:0x2020] = original
    assert b'Done' in flash.send(cpu, b'S 3 8FF0 2000 201F TEST\r')
    m.ram[0x2000:0x2020] = b'\0'*32
    assert b'Done' in flash.send(cpu, b'R 3 8FF0\r')
    assert m.ram[0x2000:0x2020] == original
    assert b'TEST' in flash.send(cpu, b'T 3\r')
    assert b'EEPROM unavailable' in flash.send(cpu, b'C 0 0 V 0A\rY\r')
    passed.append('S/R/T and no-EDU configuration refusal')
    (build.OUT / 'a31-regression.json').write_text(json.dumps(dict(
        version=build.VERSION, passed=passed,
        image_sha256=hashlib.sha256(boot.IMAGE).hexdigest(),
        physical_hardware_tested=False, native_816_execution_tested=False), indent=2)+'\n')
    print('PASS: S/R/T and no-EDU configuration refusal')


if __name__ == '__main__':
    main()
