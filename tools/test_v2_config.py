"""Linked configuration persistence, validity, startup timing and hold checks."""
import hashlib
import json

from test_v2_boot import IMAGE, OUT, SYM, Memory, MPU, command, hold, run, waiting
from test_v2_flash import boot_flash, send

CASES = []


def config(enable=1, bank=1, address=0x9000, delay=10, **changes):
    data = bytearray([1, enable, bank, address & 255, address >> 8, delay] + [0]*10)
    for key, value in changes.items():
        data[int(key)] = value
    a = b = 0
    for value in data[:14]:
        a = (a + value) & 255
        b = (b + a) & 255
    data[14:] = bytes([a, b])
    return data


def startup(data, bank=0, keys=b''):
    mem = Memory(bank)
    mem.banks[bank][0x6FF0:0x7000] = data
    mem.rx.extend(keys)
    cpu = MPU(memory=mem, pc=0xF000)
    return cpu, mem


def check_config_command():
    for resident in range(4):
        cpu, mem = boot_flash(resident)
        assert b'No config' in command(cpu, b'C\r')
        selected = (resident+1) % 4
        command(cpu, f'B{selected}\r'.encode())
        before = [bytes(b) for b in mem.banks]
        output = send(cpu, b'C 1 2 9000 0A\rY\r')
        assert b'C 01 02 9000 0A' in output and b'Done' in output, output
        assert f'B{resident}\r\n'.encode() in output
        assert mem.banks[resident][0x6FF0:0x7000] == config(bank=2)
        assert mem.banks[resident][:0x6FF0] == before[resident][:0x6FF0]
        assert mem.banks[resident][0x7000:] == before[resident][0x7000:]
        assert all(mem.banks[b] == before[b] for b in range(4) if b != resident)
        assert mem.bank == resident and mem.ram[SYM['V2_SELECTED']] == selected
        assert b'C 01 02 9000 0A' in command(cpu, b'C\r')
        # Replace a programmed config, requiring erase; preserve all neighbors.
        output = send(cpu, b'C 0 3 F000 FF\rY\r')
        assert b'Erase/rewrite' in output
        assert mem.banks[resident][0x6FF0:0x7000] == config(0, 3, 0xF000, 255)
        assert mem.banks[resident][:0x6FF0] == before[resident][:0x6FF0]
        assert mem.banks[resident][0x7000:] == before[resident][0x7000:]
        events = len(mem.events)
        send(cpu, b'C 0 3 F000 FF\rY\r')
        assert len(mem.events) == events
    CASES.append('C show/set in all resident banks, exact integrity bytes, neighbor preservation, selected bank restored, no-op writes skipped')


def check_rejection_and_failure():
    cpu, mem = boot_flash()
    command(cpu, b'B2\r')
    for line, expected in [(b'C 1\r', b'Bad hex'), (b'C 1 0 9000 0A x\r', b'Bad hex'),
                           (b'C 2 0 9000 0A\r', b'Bad range'),
                           (b'C 1 4 9000 0A\r', b'Bad range'),
                           (b'C 1 0 9000 09\r', b'Bad range'),
                           (b'C 1 0 7F00 0A\r', b'Bad range'),
                           (b'C 1 0 0100 0A\r', b'Bad range'),
                           (b'C 1 0 9000 0A\rN\r', b'Cancelled'),
                           (b'C 1 0 9000 0A\r\x03', b'Cancelled')]:
        output = send(cpu, line)
        assert expected in output, (line, output)
        assert not mem.events and mem.ram[SYM['V2_SELECTED']] == 2 and mem.bank == 0
    mem.fault = 'timeout'
    assert b'Flash timeout' in send(cpu, b'C 1 0 9000 0A\rY\r')
    assert mem.bank == 0 and mem.ram[SYM['V2_SELECTED']] == 2
    cpu, mem = boot_flash()
    command(cpu, b'B2\r')
    mem.rx.extend(b'C 1 1 9000 0A\rY\r')
    from test_v2_flash import W
    run(cpu, lambda: cpu.pc == W['V2W_PROGRAM'], limit=300000)
    mem.rx.extend(b'\x03')
    run(cpu, lambda: waiting(cpu), limit=1000000)
    assert b'Cancelled' in mem.tx and mem.banks[0][0x6FF0:0x7000] == config()
    assert mem.ram[SYM['V2_SELECTED']] == 2
    CASES.append('C syntax/range/confirmation rejection, flash failure, atomic cancellation, bank restoration on every exit')


def check_validity():
    # Every single-bit corruption of the 16-byte record must hold at boot.
    good = config()
    for index in range(16):
        for bit in range(8):
            data = bytearray(good); data[index] ^= 1 << bit
            cpu, mem = startup(data)
            hold(cpu)
            assert mem.bank == 0 and b'S/Ctrl-C hold' not in mem.tx
    for data in [b'\xff'*16, b'\0'*16, config(enable=0),
                 config(enable=2), config(bank=4), config(delay=0), config(delay=9),
                 config(**{'0': 2}), config(**{'6': 1}),
                 *(config(address=a) for a in (0xE0, 0x100, 0x1FF, 0x6900, 0x7E00, 0x7FFF))]:
        cpu, mem = startup(data)
        hold(cpu)
        assert mem.bank == 0 and b'S/Ctrl-C hold' not in mem.tx
    CASES.append('erased/disabled/unknown/malformed configs hold; all 128 single-bit corruptions rejected; unsafe targets rejected')


def check_handoffs_and_reentry():
    for resident in range(4):
        for target in range(4):
            cpu, mem = startup(config(bank=target), resident)
            run(cpu, lambda: cpu.pc == SYM['V2_AUTO_TICK'])
            # Timing measured separately: shorten only these handoff cases.
            mem.ram[SYM['V2_TICKS']] = 1
            cpu.pc = SYM['V2_AUTO_POLL']; cpu.x = cpu.y = 1
            run(cpu, lambda: cpu.pc == 0x9000)
            assert mem.bank == target and cpu.sp == 255
            assert cpu.p & cpu.INTERRUPT and not cpu.p & cpu.DECIMAL
    for address in (0, 0xDF, 0x200, 0x68FF, 0x8000, 0xFFFF):
        cpu, mem = startup(config(address=address))
        run(cpu, lambda: cpu.pc == SYM['V2_AUTO_TICK'])
        mem.ram[SYM['V2_TICKS']] = 1
        cpu.pc = SYM['V2_AUTO_POLL']; cpu.x = cpu.y = 1
        run(cpu, lambda: cpu.pc == address)
        assert mem.bank == 1
    cpu, mem = startup(config())
    cpu.pc = SYM['V2_PROMPT_ENTRY']
    pointers = bytes(mem.ram[0x7E00:0x7F00])
    hold(cpu)
    assert mem.bank == 0 and b'S/Ctrl-C hold' not in mem.tx
    assert mem.ram[0x7E00:0x7F00] == pointers
    CASES.append('16 generic autostart handoffs, allowed RAM/flash endpoints; F003 always holds and preserves user vectors')


def check_stop_keys():
    for key in (b'S', b's', b'\x03'):
        cpu, mem = startup(config(), keys=key)
        hold(cpu)
        assert b'Cancelled' in mem.tx and mem.bank == 0
        # Stop keys already queued while the banner is blocked must survive.
        cpu, mem = startup(config(), keys=key)
        mem.tx_blocked = True
        run(cpu, lambda: not mem.rx and (mem.ram[SYM['V2_RX_COUNT']] or mem.ram[SYM['V2_CANCEL_REQUEST']]))
        mem.tx_blocked = False
        hold(cpu)
        assert b'Cancelled' in mem.tx and mem.bank == 0
        # Arriving during the window, after unrelated input.
        cpu, mem = startup(config(), keys=b'xyz\r')
        run(cpu, lambda: cpu.pc == SYM['V2_AUTO_TICK'])
        cpu.step()
        mem.rx.extend(key)
        hold(cpu)
        assert b'Cancelled' in mem.tx and mem.bank == 0
    cpu, mem = startup(config(), keys=b'x'*100)
    mem.tx_blocked = True
    run(cpu, lambda: not mem.rx and cpu.pc == SYM['V2_TX_WAIT'])
    mem.tx_blocked = False
    hold(cpu)
    assert b'Cancelled' in mem.tx and mem.bank == 0
    CASES.append('S/s/Ctrl-C hold from queued or live input, blocked banner and overflow; unrelated input cannot bypass hold')


def check_timing():
    cpu, mem = startup(config())
    run(cpu, lambda: cpu.pc == SYM['V2_AUTO_TICK'])
    start = cpu.processorCycles
    run(cpu, lambda: cpu.pc == 0x9000, limit=4000000)
    cycles = cpu.processorCycles - start
    print(f'Window cycles: {cycles}; at 8 MHz: {cycles/8000000:.6f}s', flush=True)
    assert 8000000 <= cycles <= 8240000, cycles
    cpu, mem = startup(config(delay=255))
    run(cpu, lambda: cpu.pc == SYM['V2_AUTO_TICK'])
    assert mem.ram[SYM['V2_TICKS']] == 255
    cpu.step()
    run(cpu, lambda: cpu.pc == SYM['V2_AUTO_TICK'], limit=300000)
    assert mem.ram[SYM['V2_TICKS']] == 254
    mem.rx.extend(b'S')
    hold(cpu)
    assert mem.bank == 0
    CASES.append('minimum ten-tenth startup window measured at 8 MHz; no loop bypass in timing test')


def main():
    for test in (check_config_command, check_rejection_and_failure, check_validity,
                 check_handoffs_and_reentry, check_stop_keys, check_timing):
        test()
        print('PASS:', CASES[-1], flush=True)
    (OUT / 'config-test-results.json').write_text(json.dumps({
        'passed': CASES, 'image_sha256': hashlib.sha256(IMAGE).hexdigest(),
        'physical_hardware_tested': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
