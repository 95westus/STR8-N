"""Check the staged a22 E sector through alpha21 I in the flash model."""
import build_v2
import build_v2_a22
from test_v2_flash import boot_flash, send


def main():
    cpu, mem = boot_flash(3)
    old_e = bytearray(mem.banks[3][0x6000:0x7000])
    old_e[0x010] = 0x42
    old_e[0xF20] = 0x77
    old_e[0xFF0:0x1000] = bytes(range(16))
    mem.banks[3][0x6000:0x7000] = old_e
    candidate_e = (build_v2_a22.OUT /
                   f'{build_v2_a22.STEM}-e000-efff.bin').read_bytes()
    staged = bytearray(old_e)
    staged[0x800:0xF00] = candidate_e[0x800:0xF00]
    lines = [build_v2.record('0', 0, b'STR8-N 2.0a22 E')]
    lines.extend(build_v2.record('1', address,
                                 staged[address-0xE000:address-0xE000+32])
                 for address in range(0xE000, 0xF000, 32))
    lines.append(build_v2.record('9', 0xF004))
    stream = ('\r\n'.join(lines) + '\r\n').encode()
    output = send(cpu, b'I E000 EFFF\rY\r' + stream, limit=35_000_000)
    assert b'Done' in output, output[-250:]
    assert bytes(mem.banks[3][0x6000:0x7000]) == staged
    assert bytes(mem.banks[3][0x7000:]) == build_v2.ROOT.joinpath(
        'BUILD/v2-alpha21/str8n-v2-alpha21-e000-ffff.bin').read_bytes()[-4096:]
    print('PASS: alpha21 I stages a22 E while preserving neighboring E and configuration bytes')


if __name__ == '__main__':
    main()
