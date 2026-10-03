"""Check that a24 firmware keeps ACIA untouched on FT245 and absent-USB paths."""
import sys
import build_v2_a24 as a24
sys.modules['build_v2'] = a24
import test_v2_boot as boot


def step(self):
    if self.pc == boot.REPORT['worker']['V2W_BOOT_DELAY']:
        self.boot_waits += 1
        if self.boot_waits == getattr(self.memory, 'host_ready_after_wait', None):
            self.memory.ft245_present = True
        self.processorCycles += 329_000
        self.pc = boot.REPORT['worker']['V2W_BOOT_DELAY_DONE']
        return
    return boot.BaseMPU.step(self)


boot.MPU.step = step
ACIA = {0x7F80, 0x7F81, 0x7F82, 0x7F83}


def main():
    cpu, mem = boot.boot(3)
    assert not ACIA.intersection(mem.io_reads + mem.writes)
    assert boot.command(cpu, b'?\r').find(b'J0-3 boot') >= 0
    assert not ACIA.intersection(mem.io_reads + mem.writes)
    boot.call_public(cpu, boot.VSYM['STR8V2_RAM_BOARD_QUERY'])
    assert cpu.y == 0x11
    mem.ft245_present = False
    boot.call_public(cpu, boot.VSYM['STR8V2_RAM_CON_INIT'])
    assert mem.ram[boot.SYM['V2_CONSOLE']] == 0
    assert not ACIA.intersection(mem.io_reads + mem.writes)

    absent = boot.Memory(3, ft245_present=False)
    cpu = boot.MPU(memory=absent, pc=boot.SYM['START'])
    absent.cpu = cpu
    boot.run(cpu, lambda: cpu.pc == boot.REPORT['worker']['V2W_TX_WAIT'], limit=800_000)
    assert absent.ram[boot.SYM['V2_CONSOLE']] == 0
    assert not ACIA.intersection(absent.io_reads + absent.writes)
    assert not absent.acia_tx
    # A host that appears during the cold-start wait must reach the prompt.
    late = boot.Memory(3, ft245_present=False)
    late.host_ready_after_wait = 80
    cpu = boot.MPU(memory=late, pc=boot.SYM['START'])
    late.cpu = cpu
    boot.hold(cpu)
    assert cpu.boot_waits == 160
    assert late.tx.startswith(b'.' * 81)
    assert f'STR8-N {a24.VERSION} B3 65C02'.encode() in late.tx
    assert not ACIA.intersection(late.io_reads + late.writes)
    print('a24 FT245-only console: PASS')


if __name__ == '__main__':
    main()
