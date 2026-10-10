"""Model the 2609 demo cleanup with actual MAINT and monitor SAVE code.

No serial ports: this verifies an explicitly selected 50-byte record removal,
preserves the neighboring WORK tail, then saves and executes the intended demo.
"""
import hashlib
import json
from pathlib import Path

from test_v2_spi_resident import boot, k, OUT


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = b''.join(bytes((0xA9, c, 0x20, 0x6D, 0x7E)) for c in b'DEMO') + bytes.fromhex('20 7F 7E 4C 67 7E')
HEADER = b'SR\x01\x3f' + (0x2600).to_bytes(2, 'little') + len(PROGRAM).to_bytes(2, 'little') + b'DEMO'.ljust(16, b'\0')


def main():
    cpu, mem = boot()
    prior = (ROOT / 'output/qualification/storage-demo-2609-2026-10-08/flash-b2-before.bin').read_bytes()
    assert len(prior) == 32768 and prior[0x4240:0x4272] == b'\xff' * 50
    mem.banks[2][:] = prior
    mem.banks[2][0x4240:0x4272] = HEADER + bytes([0x5A]) * 16 + PROGRAM[16:]
    before = [bytes(bank) for bank in mem.banks]
    count_before = k.model.counts(k.model.latest(mem.banks))
    transcript = bytearray()

    def command(line, limit=30000000):
        output = k.model.command(cpu, line, limit)
        transcript.extend(output)
        return output

    assert b'BANK MAINT 1.7' in command(b'R MAINT\r')
    assert b'BM> ' in command(b'R 2 C000-CFFF\r')
    assert mem.ram[0x5000:0x6000] == before[2][0x4000:0x5000]
    assert b'BM> ' in command(b'F 0240-0271 FF\r')
    assert mem.ram[0x5000:0x6000] == prior[0x4000:0x5000]

    # Protected destinations refuse before asking and do not mutate flash.
    output = command(b'W 3 C000\r')
    assert b'CANCELED' in output and b'WRITE? TYPE Y>' not in output
    assert [bytes(bank) for bank in mem.banks] == before and not mem.events
    output = command(b'W 2 C000\rNO\r')
    assert b'WRITE? TYPE Y>' in output and b'CANCELED' in output
    assert [bytes(bank) for bank in mem.banks] == before and not mem.events

    output = command(b'W 2 C000\rY\r', 60000000)
    assert b'VERIFIED' in output
    assert bytes(mem.banks[2]) == prior
    assert mem.banks[0] == before[0] and mem.banks[1] == before[1]
    assert bytes(mem.banks[3][:0x4000]) == before[3][:0x4000]
    assert bytes(mem.banks[3][0x6000:]) == before[3][0x6000:]
    count_after = k.model.counts(k.model.latest(mem.banks))
    index = 2 * 8 + 4
    expected_counts = count_before[:]
    expected_counts[index] += 1
    assert count_after == expected_counts
    assert [event for event in mem.events if event[0] == 'erase'] == [('erase', 2, 0xC000, 255)]
    assert b'B3> ' in command(b'Q\r')

    # Eight bytes per line stay below the monitor's smaller input limit.
    for offset in range(0, len(PROGRAM), 8):
        line = f'M {0x2600+offset:04X} '.encode() + b' '.join(f'{v:02X}'.encode() for v in PROGRAM[offset:offset+8]) + b'\r'
        assert b'Long line' not in command(line)
    assert mem.ram[0x2600:0x261A] == PROGRAM
    assert b'Done' in command(b'S 2 C240 2600 2619 DEMO\r')
    expected_bank = bytearray(prior)
    expected_bank[0x4240:0x4272] = HEADER + PROGRAM
    assert mem.banks[2] == expected_bank
    assert k.model.counts(k.model.latest(mem.banks)) == expected_counts
    mem.ram[0x2600:0x261A] = bytes(26)
    assert b'Done' in command(b'R 2 DEMO L\r') and mem.ram[0x2600:0x261A] == PROGRAM
    output = command(b'R 2 DEMO\r')
    assert b'DEMO\r\n' in output and b'B3> ' in output

    report = dict(passed=True, model_only=True, confirmation='Y plus Enter',
                  program_hex=PROGRAM.hex(' '), removal_range='B2:C240-C271',
                  erase_attempt_delta={'B2:C': 1}, protected_destinations_refused=True,
                  canceled_confirmation_no_mutation=True, work_tail_preserved=True,
                  intended_saved_bytes_verified=True,
                  final_bank2_sha256=hashlib.sha256(expected_bank).hexdigest())
    (OUT / 'demo-flash-repair-model.json').write_text(json.dumps(report, indent=2) + '\n')
    (OUT / 'demo-flash-repair-model.txt').write_bytes(transcript)
    print('PASS actual MAINT read/fill/write cleanup, exact Y confirmation, WORK-tail preservation, one accounted B2:C erase, monitor SAVE and executable DEMO')


if __name__ == '__main__':
    main()
