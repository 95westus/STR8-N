"""Execute S19 loading and safe cancellation against the linked monitor."""
import hashlib
import json

from build_v2 import record
from test_v2_boot import OUT, IMAGE, SYM, boot, command, hold, run, waiting

CASES = []


def rec(kind, address, data=b''):
    return (record(kind, address, data) + '\r\n').encode()


def check_load():
    cpu, mem = boot(0)
    before = bytes(mem.ram[0x0200:0x6900])
    assert b'Entry 0200' in command(cpu, b'L\r' + rec('9', 0x0200))
    assert mem.ram[0x0200:0x6900] == before and mem.bank == 0
    for bank in range(4):
        cpu, mem = boot(bank)
        data = bytes(range(252))
        stream = rec('0', 0, b'test') + rec('1', 0x02FE, data)
        stream += rec('1', 0x68FC, bytes(range(252, 256))) + rec('9', 0x02FE)
        output = command(cpu, b'L\r\n' + stream.lower())
        assert b'Entry 02FE' in output, output
        assert mem.ram[0x02FE:0x03FA] == data
        assert mem.ram[0x68FC:0x6900] == bytes(range(252, 256))
        assert mem.bank == bank and not mem.bank_changes
    cpu, mem = boot(0)
    # The have-data flag must not wrap after 256 records.
    mem.rx.extend(b'L\r' + rec('1', 0x0200, b'X') * 256 + rec('9', 0xFFFF))
    run(cpu, lambda: waiting(cpu), limit=2000000)
    assert b'Entry FFFF' in mem.tx
    CASES.append('all banks, maximum-size/lowercase/page-crossing records, all byte values, 256 records, no execution')


def check_rejections():
    bad_checksum = rec('1', 0x0200, b'ABC')[:-4] + b'00\r\n'
    cases = [(bad_checksum, b'Bad checksum'),
             (b'S1030200FA\r', b'Bad S19'),  # empty S1
             (rec('9', 0x0200, b'X'), b'Bad S19'),
             (rec('9', 0x0200)[:-4] + b'00\r\n', b'Bad checksum'),
             (b'S2030200FA\r', b'Bad S19'),
             (b'S1020200\r', b'Bad S19'),
             (b'S1040200GG00\r', b'Bad S19'),
             (rec('1', 0x0200, b'X').rstrip() + b'X\r', b'Bad S19')]
    for address, data in [(0, b'X'), (0x1FF, b'XY'), (0x68FF, b'XY'),
                          (0x6900, b'X'), (0x7E00, b'X'), (0x8000, b'X'), (0xFFFF, b'XY')]:
        cases.append((rec('1', address, data), b'Protected'))
    for stream, expected in cases:
        cpu, mem = boot(0)
        before = bytes(mem.ram[0x0200:0x6900])
        output = command(cpu, b'L\r' + stream + b'M 0200 FF\rG 0200\r')
        assert expected in output, (stream, output)
        assert mem.ram[0x0200:0x6900] == before
        assert mem.bank == 0
    cpu, mem = boot(0)
    output = command(cpu, b'L\r' + rec('1', 0x0200, b'OK') + bad_checksum)
    assert b'Bad checksum' in output and mem.ram[0x0200:0x0203] == b'OKZ'
    assert b'Bad hex' in command(cpu, b'L 200\r')
    CASES.append('malformed/checksum/range rejection before writes; transfer tail drained; prior records retained')


def check_cancel_load():
    cpu, mem = boot(0)
    command(cpu, b'L\rS106020041')
    output = command(cpu, b'\x03' + rec('1', 0x0200, b'BAD'))
    assert b'Canceled' in output and mem.ram[0x0200:0x0203] == b'ZZZ'
    # Cancel in the middle of an accepted record's copy: finish that record.
    command(cpu, b'L\r')
    mem.rx.extend(rec('1', 0x0200, b'COMPLETE'))
    run(cpu, lambda: cpu.pc == SYM['V2_LOAD_COPY'] and cpu.y == 3)
    mem.rx.extend(b'\x03' + rec('1', 0x0300, b'NO'))
    hold(cpu)
    assert mem.ram[0x0200:0x0208] == b'COMPLETE'
    assert mem.ram[0x0300:0x0302] == b'ZZ'
    assert mem.ram[SYM['V2_NMI_HOLD']] == 0
    assert b'Canceled' in mem.tx
    CASES.append('partial record cancellation writes nothing; mid-copy cancellation completes only the accepted record')


def check_cancel_commands():
    for line in (b'M 0200 FF\r', b'G 0200\r', b'J1\r', b'B1\r'):
        cpu, mem = boot(0)
        output = command(cpu, line + b'\x03')
        assert b'Canceled' in output, output
        assert mem.ram[0x0200] == 0x5A and mem.bank == 0
        assert mem.ram[SYM['V2_SELECTED']] == 0
    cpu, mem = boot(0)
    assert b'Canceled' in command(cpu, b'M 0200 FF\x03')
    mem.rx.extend(b'M 7E00 00 02\r')
    run(cpu, lambda: cpu.pc == SYM['V2_M_WRITE'] and cpu.y == 1)
    mem.rx.extend(b'\x03')
    hold(cpu)
    assert mem.ram[0x7E00:0x7E02] == b'\x00\x02'
    assert not mem.ram[SYM['V2_NMI_HOLD']]
    command(cpu, b'B1\r')
    start = len(mem.tx)
    mem.rx.extend(b'D 8000 FFFF\r')
    run(cpu, lambda: cpu.pc == SYM['V2_D_ROW'] and len(mem.tx) > start + 130)
    mem.rx.extend(b'\x03')
    hold(cpu)
    assert b'Canceled' in mem.tx[start:] and len(mem.tx) - start < 400
    assert mem.bank == 0 and mem.ram[SYM['V2_SELECTED']] == 1
    CASES.append('line/display cancellation, pre-write/pre-jump cancellation, atomic M pointer completion')


def check_backpressure_and_queue():
    cpu, mem = boot(0)
    output = command(cpu, b'D 0200 0200\rM 0300 AA\rD 0300 0300\r')
    assert b'0300: AA' in output and mem.ram[0x0300] == 0xAA
    # Wrap the ring repeatedly without losing ordinary typeahead.
    for _ in range(10):
        assert b'0200: 5A' in command(cpu, b'D 0200 0200\r' * 3)
    mem.rx.extend(b'D 8000 FFFF\r')
    run(cpu, lambda: cpu.pc == SYM['V2_D_PRINT'])
    mem.tx_blocked = True
    run(cpu, lambda: cpu.pc == SYM['V2_TX_WAIT'])
    mem.rx.extend(b'\x03')
    run(cpu, lambda: cpu.pc == SYM['V2_CANCELLED'])
    assert mem.bank == 0
    mem.tx_blocked = False
    hold(cpu)
    assert b'Canceled' in mem.tx
    # Overflow while echo is blocked: even a valid prefix must not execute.
    mem.rx.extend(b'M 0400 FF' + b' ' * 80 + b'\r')
    mem.tx_blocked = True
    run(cpu, lambda: not mem.rx and cpu.pc == SYM['V2_TX_WAIT'])
    mem.tx_blocked = False
    hold(cpu)
    assert b'Bad input' in mem.tx and mem.ram[0x0400] == 0x5A
    assert b'0400: 5A' in command(cpu, b'D 0400 0400\r')
    CASES.append('typeahead preserved, ring wrap, blocked-output cancellation, overflow cannot execute truncated edits')


def main():
    for test in (check_load, check_rejections, check_cancel_load,
                 check_cancel_commands, check_backpressure_and_queue):
        test()
        print('PASS:', CASES[-1])
    (OUT / 'load-test-results.json').write_text(json.dumps({
        'passed': CASES, 'image_sha256': hashlib.sha256(IMAGE).hexdigest(),
        'physical_hardware_tested': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
